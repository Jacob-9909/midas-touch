"""
train.py
--------
생성된 (Query, Positive, Negative) 삼중쌍 데이터셋으로
KURE-v1 임베딩 모델 파인튜닝 실행.

지원 손실 함수:
1. MultipleNegativesRankingLoss (배치 내 암묵적 네거티브 RAG 대조 학습)
2. MarginMSELoss (교사의 고정밀 Margin 점수를 MSE 로 학습하는 지식 증류)
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

import numpy as np
import torch
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
    losses,
)
from sentence_transformers.evaluation import InformationRetrievalEvaluator

from .config import PipelineConfig, DEFAULT_CONFIG
from .dataset_builder import DatasetIO, Triplet
from .pipeline import setup_logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 재현성 시드 고정
# ---------------------------------------------------------------------------
def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------------------
# 데이터셋 로더
# ---------------------------------------------------------------------------
def load_train_eval_datasets(
    config: PipelineConfig,
) -> tuple[Dataset, list[Triplet]]:
    """저장된 JSONL에서 학습/평가 데이터셋 로드."""
    train_path = config.paths.train_dataset_jsonl
    eval_path = config.paths.eval_dataset_jsonl

    if not train_path.exists():
        raise FileNotFoundError(
            f"학습 데이터셋을 찾을 수 없습니다: {train_path}\n"
            "pipeline.py를 먼저 실행하세요."
        )

    train_triplets = DatasetIO.load_jsonl(train_path)
    eval_triplets = DatasetIO.load_jsonl(eval_path)

    # 설정된 손실 함수 타입에 따라 적절한 딕셔너리로 학습 데이터 매핑
    loss_type = config.training.loss_type
    if loss_type == "margin_mse":
        logger.info("MarginMSELoss 용 데이터 매핑 적용 (label = margin)")
        rows = [t.to_margin_mse_dict() for t in train_triplets]
    else:
        logger.info("MultipleNegativesRankingLoss 용 데이터 매핑 적용")
        rows = [t.to_sentence_transformer_dict() for t in train_triplets]

    train_dataset = Dataset.from_list(rows)

    logger.info(
        "데이터셋 로드 완료: train=%d, eval=%d",
        len(train_triplets), len(eval_triplets),
    )
    return train_dataset, eval_triplets


# ---------------------------------------------------------------------------
# 평가기 구성 (InformationRetrievalEvaluator)
# ---------------------------------------------------------------------------
def build_ir_evaluator(
    eval_triplets: list[Triplet],
    name: str = "finance-ir-eval",
) -> InformationRetrievalEvaluator:
    """평가 삼중쌍으로 IR 평가기 구성."""
    queries: dict[str, str] = {}
    corpus: dict[str, str] = {}
    relevant_docs: dict[str, set[str]] = {}

    for t in eval_triplets:
        queries[t.query_id] = t.query_text
        corpus[t.positive_passage_id] = t.positive_text
        corpus[t.negative_passage_id] = t.negative_text
        relevant_docs.setdefault(t.query_id, set()).add(t.positive_passage_id)

    evaluator = InformationRetrievalEvaluator(
        queries=queries,
        corpus=corpus,
        relevant_docs=relevant_docs,
        name=name,
        mrr_at_k=[10],
        ndcg_at_k=[10],
        accuracy_at_k=[1, 3, 5, 10],
        precision_recall_at_k=[1, 5, 10],
        show_progress_bar=True,
    )

    logger.info(
        "IR 평가기 구성 완료: 쿼리=%d, 코퍼스=%d", len(queries), len(corpus)
    )
    return evaluator


# ---------------------------------------------------------------------------
# 학습 실행
# ---------------------------------------------------------------------------
def train(config: PipelineConfig) -> SentenceTransformer:
    """파인튜닝 학습 실행."""
    set_seed(config.seed)
    train_cfg = config.training

    logger.info("모델 로드 중: %s", train_cfg.student_model_name)
    model = SentenceTransformer(train_cfg.student_model_name)

    # 데이터셋 로드
    train_dataset, eval_triplets = load_train_eval_datasets(config)

    # 지정된 Loss 타입으로 동적 분기
    loss_type = train_cfg.loss_type
    if loss_type == "margin_mse":
        logger.info("손실 함수 활성화: MarginMSELoss (지식 증류 모드)")
        loss = losses.MarginMSELoss(model=model)
    else:
        logger.info("손실 함수 활성화: MultipleNegativesRankingLoss (대조 학습 모드)")
        loss = losses.MultipleNegativesRankingLoss(
            model=model,
            scale=train_cfg.mnrl_scale,
        )

    # 평가기 구성
    evaluator = build_ir_evaluator(eval_triplets)

    # 학습 인자
    output_dir = str(train_cfg.output_dir)
    training_args = SentenceTransformerTrainingArguments(
        output_dir=output_dir,
        num_train_epochs=train_cfg.num_epochs,
        per_device_train_batch_size=train_cfg.train_batch_size,
        per_device_eval_batch_size=train_cfg.eval_batch_size,
        learning_rate=train_cfg.learning_rate,
        warmup_ratio=train_cfg.warmup_ratio,
        fp16=train_cfg.fp16,
        bf16=train_cfg.bf16,
        eval_strategy="steps",
        eval_steps=train_cfg.eval_steps,
        save_strategy="steps",
        save_steps=train_cfg.save_steps,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_finance-ir-eval_cosine_ndcg@10",
        greater_is_better=True,
        logging_steps=50,
        report_to="none",       # wandb 연동 시 "wandb"로 변경
        seed=config.seed,
        dataloader_drop_last=True,
    )

    logger.info(
        "학습 시작 (%s): epochs=%d, batch=%d, lr=%.2e",
        loss_type.upper(),
        train_cfg.num_epochs,
        train_cfg.train_batch_size,
        train_cfg.learning_rate,
    )

    trainer = SentenceTransformerTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        loss=loss,
        evaluator=evaluator,
    )

    trainer.train()

    # 최종 모델 저장
    final_model_path = Path(output_dir) / "final"
    model.save(str(final_model_path))
    logger.info("최종 모델 저장 완료: %s", final_model_path)

    # 최종 평가 점수 출력
    final_scores = evaluator(model)
    logger.info("최종 평가 결과:")
    for metric, score in final_scores.items():
        logger.info("  %s: %.4f", metric, score)

    return model


# ---------------------------------------------------------------------------
# 모델 추론 테스트 유틸
# ---------------------------------------------------------------------------
def quick_inference_test(
    model: SentenceTransformer,
    test_queries: list[str],
    test_passages: list[str],
) -> None:
    """파인튜닝 결과 빠른 시각 확인용."""
    print("\n[추론 테스트] 쿼리 ↔ 단락 유사도 행렬")
    print("-" * 60)

    q_embs = model.encode(test_queries, normalize_embeddings=True, convert_to_numpy=True)
    p_embs = model.encode(test_passages, normalize_embeddings=True, convert_to_numpy=True)
    sim_matrix = np.dot(q_embs, p_embs.T)

    header = " " * 30 + "".join(f"P{i:<6}" for i in range(len(test_passages)))
    print(header)
    for i, query in enumerate(test_queries):
        row = f"{query[:28]:<30}" + "".join(f"{sim_matrix[i, j]:.3f} " for j in range(len(test_passages)))
        print(row)
    print("-" * 60)


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KURE-v1 금융 임베딩 파인튜닝")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="학습 없이 데이터셋 로드 및 평가기 구성만 테스트",
    )
    args = parser.parse_args()

    setup_logging(args.log_level)
    config = DEFAULT_CONFIG

    try:
        config.validate()
    except ValueError as exc:
        logger.error("설정 검증 실패: %s", exc)
        raise SystemExit(1) from exc

    if args.test_only:
        logger.info("테스트 모드: 데이터셋 로드만 수행합니다.")
        train_dataset, eval_triplets = load_train_eval_datasets(config)
        evaluator = build_ir_evaluator(eval_triplets)
        logger.info("테스트 완료. train=%d, eval=%d", len(train_dataset), len(eval_triplets))
        return

    trained_model = train(config)

    # 간단한 추론 테스트
    sample_queries = [
        "ISA 계좌 세금 혜택이 얼마나 되나요?",
        "해외 주식 투자 환위험 어떻게 줄이나요",
        "연금저축 vs IRP 비교",
    ]
    sample_passages = [
        "개인종합자산관리계좌(ISA)는 비과세 한도 200만원 초과분에 대해 9.9% 분리과세를 적용합니다.",
        "해외 주식 투자 시 환헤지 ETF 또는 통화선도 계약을 활용하면 환위험을 일부 축소할 수 있습니다.",
        "연금저축은 세액공제 한도 400만원, IRP는 연금저축 포함 700만원 한도로 세액공제를 받을 수 있습니다.",
    ]
    quick_inference_test(trained_model, sample_queries, sample_passages)


if __name__ == "__main__":
    main()
