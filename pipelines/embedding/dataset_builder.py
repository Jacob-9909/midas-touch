"""
dataset_builder.py
------------------
(Query, Positive, Negative) 삼중쌍 조립 및 데이터셋 저장 모듈.

- MiningResult + SyntheticQuery → InputExample 형식 삼중쌍
- 학습/평가셋 분리 (stratified split)
- JSONL 저장 및 HuggingFace datasets 포맷 변환
- [고도화] MarginMSELoss 와 MultipleNegativesRankingLoss 포맷팅 동시 지원.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterator

from pipelines.embedding.config import PipelineConfig
from pipelines.embedding.hard_negative_miner import MiningResult
from pipelines.embedding.query_synthesizer import SyntheticQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------
@dataclass
class Triplet:
    """
    대조 학습용 (Query, Positive, Negative) 삼중쌍.
    """

    triplet_id: str
    query_id: str
    query_text: str
    positive_passage_id: str
    positive_text: str
    negative_passage_id: str
    negative_text: str
    query_type: str
    negative_similarity_score: float   # 교사 모델 기준
    positive_similarity_score: float   # 교사 모델 기준
    margin: float                       # positive - negative

    def to_sentence_transformer_dict(self) -> dict:
        """sentence-transformers MultipleNegativesRankingLoss 학습 형식으로 변환."""
        return {
            "anchor": self.query_text,
            "positive": self.positive_text,
            "negative": self.negative_text,
        }

    def to_margin_mse_dict(self) -> dict:
        """sentence-transformers MarginMSELoss 지식 증류 학습 형식으로 변환."""
        return {
            "anchor": self.query_text,
            "positive": self.positive_text,
            "negative": self.negative_text,
            "label": self.margin, # 교사 스코어의 마진(차이)을 float label 로 전달
        }

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 삼중쌍 조립기
# ---------------------------------------------------------------------------
class TripletAssembler:
    """
    SyntheticQuery + MiningResult를 결합하여 Triplet 리스트 생성.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config
        self._hn_cfg = config.hard_negative
        random.seed(config.seed)

    def assemble(
        self,
        queries: list[SyntheticQuery],
        mining_results: list[MiningResult],
        use_in_batch_fallback: bool = True,  # 디바이스 가동률 및 충분성 향상을 위해 True 기본값 권장
    ) -> list[Triplet]:
        """삼중쌍 조립."""
        # query_id → SyntheticQuery 매핑
        query_map: dict[str, SyntheticQuery] = {q.query_id: q for q in queries}

        # query_id → MiningResult 매핑
        mining_map: dict[str, MiningResult] = {r.query_id: r for r in mining_results}

        # 전체 단락 텍스트 풀 (배치 내 폴백용)
        all_positive_texts: list[tuple[str, str]] = [
            (q.passage_id, q.source_passage) for q in queries
        ]

        triplets: list[Triplet] = []
        skipped_no_hn = 0
        skipped_no_query = 0
        fallback_used = 0

        for query_id, result in mining_map.items():
            query = query_map.get(query_id)
            if query is None:
                skipped_no_query += 1
                continue

            if result.hard_negatives:
                # 하드 네거티브 존재 → 삼중쌍 직접 구성
                for hn in result.hard_negatives:
                    triplet = Triplet(
                        triplet_id=f"{query_id}_hn_{hn.passage_id}",
                        query_id=query_id,
                        query_text=query.query_text,
                        positive_passage_id=query.passage_id,
                        positive_text=query.source_passage,
                        negative_passage_id=hn.passage_id,
                        negative_text=hn.passage_text,
                        query_type=query.query_type,
                        negative_similarity_score=hn.similarity_score,
                        positive_similarity_score=hn.positive_score,
                        margin=hn.margin,
                    )
                    triplets.append(triplet)

            elif use_in_batch_fallback:
                # 하드 네거티브 없음 → 데이터 충분성 및 안정성을 위해 랜덤 단락 폴백 적용
                fallback_neg = self._sample_random_negative(
                    exclude_id=query.passage_id,
                    all_passages=all_positive_texts,
                )
                if fallback_neg:
                    neg_pid, neg_text = fallback_neg
                    triplet = Triplet(
                        triplet_id=f"{query_id}_rand_{neg_pid}",
                        query_id=query_id,
                        query_text=query.query_text,
                        positive_passage_id=query.passage_id,
                        positive_text=query.source_passage,
                        negative_passage_id=neg_pid,
                        negative_text=neg_text,
                        query_type=query.query_type,
                        negative_similarity_score=0.20,   # 평균 무관 스코어 추정값 fallback
                        positive_similarity_score=0.85,   # 평균 긍정 스코어 추정값 fallback
                        margin=0.65,
                    )
                    triplets.append(triplet)
                    fallback_used += 1
            else:
                skipped_no_hn += 1

        logger.info(
            "삼중쌍 조립 완료: %d개 생성 | "
            "HN 없어 건너뜀: %d | 폴백 사용: %d | 쿼리 미매핑: %d",
            len(triplets), skipped_no_hn, fallback_used, skipped_no_query,
        )
        return triplets

    @staticmethod
    def _sample_random_negative(
        exclude_id: str,
        all_passages: list[tuple[str, str]],
    ) -> tuple[str, str] | None:
        """긍정 단락을 제외하고 랜덤 단락 샘플링."""
        candidates = [(pid, text) for pid, text in all_passages if pid != exclude_id]
        if not candidates:
            return None
        return random.choice(candidates)


# ---------------------------------------------------------------------------
# 학습/평가셋 분리
# ---------------------------------------------------------------------------
class DatasetSplitter:
    """삼중쌍을 학습/평가셋으로 분리 (쿼리 단위 stratified split)."""

    def __init__(self, config: PipelineConfig) -> None:
        self._eval_ratio = config.eval_split_ratio
        self._seed = config.seed
        random.seed(config.seed)

    def split(
        self,
        triplets: list[Triplet],
    ) -> tuple[list[Triplet], list[Triplet]]:
        """쿼리 타입 분포를 유지하며 학습/평가셋 분리."""
        # 쿼리 타입별 그룹화
        type_groups: dict[str, list[Triplet]] = {}
        for t in triplets:
            type_groups.setdefault(t.query_type, []).append(t)

        train: list[Triplet] = []
        eval_: list[Triplet] = []

        for qtype, group in type_groups.items():
            random.shuffle(group)
            n_eval = max(1, int(len(group) * self._eval_ratio))
            eval_.extend(group[:n_eval])
            train.extend(group[n_eval:])
            logger.debug(
                "분리 [%s]: train=%d, eval=%d", qtype, len(group) - n_eval, n_eval
            )

        random.shuffle(train)
        random.shuffle(eval_)

        logger.info(
            "데이터셋 분리 완료: train=%d, eval=%d (eval ratio=%.2f)",
            len(train), len(eval_), self._eval_ratio,
        )
        return train, eval_


# ---------------------------------------------------------------------------
# JSONL I/O
# ---------------------------------------------------------------------------
class DatasetIO:
    """Triplet 리스트 ↔ JSONL 파일 입출력."""

    @staticmethod
    def save_jsonl(triplets: list[Triplet], path: Path) -> None:
        """Triplet 리스트를 JSONL 파일로 저장."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for t in triplets:
                f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
        logger.info("JSONL 저장 완료: %s (%d 행)", path, len(triplets))

    @staticmethod
    def load_jsonl(path: Path) -> list[Triplet]:
        """JSONL 파일에서 Triplet 리스트 로드."""
        triplets: list[Triplet] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                triplets.append(Triplet(**data))
        logger.info("JSONL 로드 완료: %s (%d 행)", path, len(triplets))
        return triplets

    @staticmethod
    def iter_sentence_transformer_format(
        path: Path,
        loss_type: str = "margin_mse"
    ) -> Iterator[dict]:
        """저장된 JSONL을 sentence-transformers 학습 형식으로 스트리밍."""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                t = Triplet(**data)
                if loss_type == "margin_mse":
                    yield t.to_margin_mse_dict()
                else:
                    yield t.to_sentence_transformer_dict()


# ---------------------------------------------------------------------------
# 데이터셋 통계 출력
# ---------------------------------------------------------------------------
def compute_dataset_stats(triplets: list[Triplet]) -> dict:
    """데이터셋 기본 통계 계산."""
    if not triplets:
        return {}

    query_type_counts: dict[str, int] = {}
    margins: list[float] = []
    neg_scores: list[float] = []
    pos_scores: list[float] = []

    for t in triplets:
        query_type_counts[t.query_type] = query_type_counts.get(t.query_type, 0) + 1
        if t.margin >= -1.0: # fallback 포함 통계 유연화
            margins.append(t.margin)
            neg_scores.append(t.negative_similarity_score)
            pos_scores.append(t.positive_similarity_score)

    import statistics

    return {
        "total_triplets": len(triplets),
        "unique_queries": len({t.query_id for t in triplets}),
        "unique_positives": len({t.positive_passage_id for t in triplets}),
        "unique_negatives": len({t.negative_passage_id for t in triplets}),
        "query_type_distribution": query_type_counts,
        "margin_mean": statistics.mean(margins) if margins else 0.0,
        "margin_stdev": statistics.stdev(margins) if len(margins) > 1 else 0.0,
        "pos_score_mean": statistics.mean(pos_scores) if pos_scores else 0.0,
        "neg_score_mean": statistics.mean(neg_scores) if neg_scores else 0.0,
        "avg_query_len_chars": statistics.mean(len(t.query_text) for t in triplets),
        "avg_positive_len_chars": statistics.mean(len(t.positive_text) for t in triplets),
    }
