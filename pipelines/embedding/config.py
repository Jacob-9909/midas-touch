"""
config.py
---------
금융 특화 임베딩 파인튜닝 파이프라인의 모든 설정값·프롬프트·스키마를 코드와 분리 관리.
환경변수(.env) 우선 → 기본값 fallback 방식으로 동작.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 환경변수 로드 (.env 파일 또는 시스템 환경변수)
# ---------------------------------------------------------------------------
load_dotenv()


def _require_env(name: str) -> str:
    """필수 환경변수를 읽고, 없으면 명확한 오류로 실패한다(하드코딩 기본값 금지)."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} 환경변수가 설정되어 있지 않습니다.")
    return value


# ---------------------------------------------------------------------------
# NVIDIA NIM API 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NIMConfig:
    """NVIDIA NIM API 접속 설정."""

    # NVIDIA_API_KEY 와 NVIDIA_NIM_API_KEY 둘 다 호환되도록 fallback 처리
    api_key: str = field(
        default_factory=lambda: os.environ.get(
            "NVIDIA_API_KEY", os.environ.get("NVIDIA_NIM_API_KEY", "")
        )
    )
    base_url: str = "https://integrate.api.nvidia.com/v1"

    # 쿼리 합성에 사용할 생성 모델. 하드코딩 기본값을 두면 .env 교체 후에도 옛 모델로
    # 조용히 돌아가므로(실제로 meta/llama-3.1-70b가 남아 있었다), 미설정이면 그냥 실패시킨다.
    generation_model: str = field(
        default_factory=lambda: _require_env("NIM_GENERATION_MODEL")
    )

    # 요청 타임아웃(초) / 동시 요청 수 상한 (40 RPM 안전 무풍지대를 위해 1로 고정 추천)
    request_timeout: int = 100
    max_concurrent_requests: int = 1

    # 생성 파라미터
    temperature: float = 0.85
    top_p: float = 0.95
    max_tokens: int = 4096


# ---------------------------------------------------------------------------
# 교사 임베딩 모델 설정 (하드 네거티브 마이닝)
# ---------------------------------------------------------------------------
TeacherModelName = Literal[
    "nlpai-lab/KURE-v1",
    "BAAI/bge-m3",
]


@dataclass(frozen=True)
class TeacherModelConfig:
    """하드 네거티브 마이닝에 사용할 교사 임베딩 모델 설정."""

    # 교사 임베딩 모델 (TEACHER_EMBEDDING_MODEL 환경변수로 override 가능)
    model_name: TeacherModelName = field(
        default_factory=lambda: os.environ.get(
            "TEACHER_EMBEDDING_MODEL", "nlpai-lab/KURE-v1"
        )
    )
    device: str = field(
        default_factory=lambda: os.environ.get("EMBEDDING_DEVICE", "cpu")
    )
    batch_size: int = 64
    normalize_embeddings: bool = True
    # 임베딩 계산 시 최대 시퀀스 길이
    max_seq_length: int = 512


# ---------------------------------------------------------------------------
# 하드 네거티브 마이닝 기준 (NV-Retriever 마진 공식)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HardNegativeConfig:
    """
    NV-Retriever 스타일 하드 네거티브 선별 기준.

    선별 조건:
        S_neg <= S_pos * margin_ratio          (상한: 긍정과 너무 유사한 것 제외)
        S_neg >= similarity_floor              (하한: 너무 동떨어진 것 제외)
    """

    # 긍정 유사도 대비 최대 허용 비율 (논문 권장: 0.95)
    margin_ratio: float = 0.9

    # 유사도 하한선 (랜덤 노이즈 수준 제외)
    similarity_floor: float = 0.30

    # 쿼리당 후보 검색 수 (BM25 대신 임베딩 교사 사용)
    top_k_candidates: int = 50

    # 쿼리당 최종 선택할 하드 네거티브 수
    num_hard_negatives_per_query: int = 3

    # 유사도 대량 마이닝 시의 연산 배치 크기 (OOM 방지)
    mining_batch_size: int = 1000


# ---------------------------------------------------------------------------
# 쿼리 합성 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QuerySynthesisConfig:
    """LLM 기반 쿼리 합성 파라미터."""

    # 단락당 생성할 쿼리 수 (다양성 확보를 위해 20개 권장)
    queries_per_passage: int = 10

    # 합성 쿼리 유형 분포 (비율 합계 = 1.0)
    query_type_distribution: dict[str, float] = field(
        default_factory=lambda: {
            "keyword": 0.20,       # 단순 키워드 검색형
            "question": 0.35,      # 자연어 질문형
            "vague_intent": 0.25,  # 비정형 의도 표현 (실제 사용자 패턴)
            "comparison": 0.10,    # 비교 질문형
            "regulatory": 0.10,    # 규제·법률 관련 질문형
        }
    )

    # 최소 쿼리 길이 (토큰) — 너무 짧은 것 필터링
    min_query_length: int = 5
    # 최대 쿼리 길이 (토큰)
    max_query_length: int = 80

    # 2차 LLM 쿼리 검증 활성화 여부 (Rate Limit 방지를 위해 기본값 False 추천)
    enable_validation: bool = False


# ---------------------------------------------------------------------------
# LoRA 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoraConfig:
    """PEFT LoRA 파인튜닝 설정."""

    # LoRA rank (높을수록 표현력↑, 파라미터↑)
    r: int = field(default_factory=lambda: int(os.environ.get("LORA_R", "16")))
    # LoRA scaling factor (통상 r * 2)
    lora_alpha: int = field(default_factory=lambda: int(os.environ.get("LORA_ALPHA", "32")))
    lora_dropout: float = field(
        default_factory=lambda: float(os.environ.get("LORA_DROPOUT", "0.1"))
    )
    # BERT/RoBERTa 계열 attention 레이어 타겟 (KURE-v1 기준)
    target_modules: list[str] = field(
        default_factory=lambda: os.environ.get(
            "LORA_TARGET_MODULES", "query,value"
        ).split(",")
    )
    bias: str = "none"
    # 학습 완료 후 adapter를 base model에 머지해서 저장할지 여부
    merge_on_save: bool = field(
        default_factory=lambda: os.environ.get("LORA_MERGE_ON_SAVE", "true").lower() == "true"
    )


# ---------------------------------------------------------------------------
# 파인튜닝 학습 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TrainingConfig:
    """KURE-v1 파인튜닝 하이퍼파라미터."""

    # 학생(파인튜닝 대상) 모델 (STUDENT_EMBEDDING_MODEL 환경변수로 override 가능)
    student_model_name: str = field(
        default_factory=lambda: os.environ.get(
            "STUDENT_EMBEDDING_MODEL", "nlpai-lab/KURE-v1"
        )
    )

    # 손실 함수 타입 ("mnrl" = MultipleNegativesRankingLoss, "margin_mse" = MarginMSELoss)
    loss_type: Literal["mnrl", "margin_mse"] = field(
        default_factory=lambda: os.environ.get("TRAIN_LOSS_TYPE", "margin_mse")
    )

    # 학습률 / 에폭 / 배치
    learning_rate: float = field(
        default_factory=lambda: float(os.environ.get("TRAIN_LEARNING_RATE", "2e-5"))
    )
    num_epochs: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_NUM_EPOCHS", "3"))
    )
    train_batch_size: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_BATCH_SIZE", "32"))
    )
    eval_batch_size: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_EVAL_BATCH_SIZE", "64"))
    )

    # 워밍업 비율
    warmup_ratio: float = field(
        default_factory=lambda: float(os.environ.get("TRAIN_WARMUP_RATIO", "0.1"))
    )

    # MultipleNegativesRankingLoss 온도 파라미터
    mnrl_scale: float = field(
        default_factory=lambda: float(os.environ.get("TRAIN_MNRL_SCALE", "20.0"))
    )

    # 평가 / 저장 주기 (스텝)
    eval_steps: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_EVAL_STEPS", "200"))
    )
    save_steps: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_SAVE_STEPS", "500"))
    )

    # 혼합 정밀도 (bf16 권장 — A100/H100, fp16은 RTX 계열)
    fp16: bool = field(
        default_factory=lambda: os.environ.get("TRAIN_FP16", "false").lower() == "true"
    )
    bf16: bool = field(
        default_factory=lambda: os.environ.get("TRAIN_BF16", "true").lower() == "true"
    )

    # 출력 디렉토리
    output_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("TRAINING_OUTPUT_DIR", "./output/kure-finance-v1")
        )
    )


# ---------------------------------------------------------------------------
# 파일 경로 설정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PathConfig:
    """파이프라인 전반의 파일 입출력 경로."""

    # 원천 금융 문서 디렉토리
    raw_documents_dir: Path = Path("./data/raw_documents")
    
    # 개별 파일별 격리 폴더 명
    sub_dir: str | None = None

    @property
    def base_dir(self) -> Path:
        return Path("./data") / self.sub_dir if self.sub_dir else Path("./data")

    @property
    def passages_jsonl(self) -> Path:
        return self.base_dir / "processed" / "passages.jsonl"

    @property
    def synthetic_queries_jsonl(self) -> Path:
        return self.base_dir / "processed" / "synthetic_queries.jsonl"

    @property
    def train_dataset_jsonl(self) -> Path:
        return self.base_dir / "dataset" / "train_triplets.jsonl"

    @property
    def eval_dataset_jsonl(self) -> Path:
        return self.base_dir / "dataset" / "eval_triplets.jsonl"

    @property
    def checkpoint_dir(self) -> Path:
        return self.base_dir / "checkpoints"

    def ensure_dirs(self) -> None:
        """필요한 디렉토리를 모두 생성."""
        for path in [
            self.raw_documents_dir,
            self.passages_jsonl.parent,
            self.synthetic_queries_jsonl.parent,
            self.train_dataset_jsonl.parent,
            self.checkpoint_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 프롬프트 템플릿 (코드와 완전 분리)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PromptTemplates:
    """
    LLM에 주입할 프롬프트 템플릿.
    {passage}, {num_queries}, {query_type} 등의 변수를 .format()으로 주입.
    """

    # 금융 쿼리 합성용 시스템 프롬프트
    query_synthesis_system: str = (
        "당신은 금융 분야 정보 검색 전문가입니다. "
        "주어진 금융 문서 단락에 대해 실제 자산관리 고객이나 금융 전문가가 "
        "해당 단락을 검색하기 위해 사용할 법한 다양한 형태의 질문과 검색어를 생성합니다. "
        "생성되는 쿼리는 반드시 한국어로 작성하며, 단순 키워드 나열부터 "
        "자연어 질문, 비정형 의도 표현까지 다양한 형태를 포함해야 합니다."
    )

    # 금융 쿼리 합성용 사용자 프롬프트 템플릿 (Few-shot 적용으로 퀄리티 상향)
    query_synthesis_user: str = (
        "다음 금융 문서 단락을 읽고, 이 단락을 검색하기 위한 한국어 검색 쿼리 {num_queries}개를 생성하세요.\n\n"
        "## 단락\n{passage}\n\n"
        "## 쿼리 유형 분포 및 생성 지침 (Few-shot 참고)\n"
        "1. 키워드형 ({keyword_ratio}%): 핵심 금융 용어 위주 검색어\n"
        "   - 예시: 'ISA 계좌 한도', 'IRP 비과세 혜택'\n"
        "2. 질문형 ({question_ratio}%): 정확한 정보 탐색 목적의 완성된 문장\n"
        "   - 예시: '연금저축과 IRP의 중도해지 시 불이익 차이는 무엇인가요?'\n"
        "3. 비정형 의도형 ({vague_ratio}%): 구어체, 실제 자산 관리 고객의 고민 표현\n"
        "   - 예시: '노후 자금 안전하게 굴리고 싶은데 어떤 상품이 좋은지'\n"
        "4. 비교형 ({comparison_ratio}%): 상품이나 세제 혜택 간의 장단점 비교\n"
        "   - 예시: '일반 적금과 청년도약계좌 수익률 비교'\n"
        "5. 규제·법률형 ({regulatory_ratio}%): 금융소비자보호법, 세법 규정 관련 질문\n"
        "   - 예시: '금소법상 적합성 원칙 위반하면 어떤 제재를 받나요?'\n\n"
        "## 출력 형식\n"
        "아래와 같은 순수 JSON 배열 형식으로만 출력하세요. 마크다운 기호(```)나 설명, 번호를 쓰지 마세요.\n"
        '["쿼리1", "쿼리2", "쿼리3"]'
    )

    # 쿼리 품질 검증용 프롬프트 (2차 필터링)
    query_validation_system: str = (
        "당신은 금융 정보 검색 품질 전문가입니다. "
        "주어진 쿼리가 해당 금융 문서 단락과 실제로 밀접하게 연관되어 있고, "
        "그 단락을 검색해 내기에 타당한 쿼리인지 검증합니다."
    )

    query_validation_user: str = (
        "다음 쿼리가 주어진 금융 단락을 검색하기에 적합한지 객관적으로 검증하세요.\n\n"
        "## 단락\n{passage}\n\n"
        "## 후보 쿼리\n{query}\n\n"
        "해당 단락을 통해 후보 쿼리의 의도가 해결되거나 답변될 수 있으면 적합(true), "
        "전혀 무관하거나 거짓 정보(Hallucination), 또는 단락과 전혀 의미적으로 연관되지 않은 쿼리라면 부적합(false)으로 판단하세요.\n\n"
        "반드시 아래 JSON 형식으로만 응답하세요. 설명 없이 JSON 구조만 출력하세요:\n"
        '{{"is_valid": true 또는 false, "reason": "검증 이유 1문장"}}'
    )


# ---------------------------------------------------------------------------
# 전역 설정 싱글턴 (파이프라인 전체에서 단일 인스턴스 사용)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PipelineConfig:
    """파이프라인 전체 설정 컨테이너."""

    nim: NIMConfig = field(default_factory=NIMConfig)
    teacher_model: TeacherModelConfig = field(default_factory=TeacherModelConfig)
    hard_negative: HardNegativeConfig = field(default_factory=HardNegativeConfig)
    query_synthesis: QuerySynthesisConfig = field(default_factory=QuerySynthesisConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    lora: LoraConfig = field(default_factory=LoraConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    prompts: PromptTemplates = field(default_factory=PromptTemplates)

    # 전체 파이프라인 로그 레벨
    log_level: str = field(
        default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO")
    )

    # 재현성을 위한 랜덤 시드
    seed: int = 42

    # 평가셋 분리 비율
    eval_split_ratio: float = 0.05

    def validate(self) -> None:
        """필수 설정값 검증."""
        try:
            from shared.utils.api_key_rotator import APIKeyRotator
            APIKeyRotator()
        except ValueError as exc:
            raise ValueError(
                "NVIDIA API Key가 환경변수에서 감지되지 않았습니다. "
                "NVIDIA_API_KEY 또는 NVIDIA_API_KEY_2 등을 설정해 주세요."
            ) from exc
        if not (0.0 < self.eval_split_ratio < 0.5):
            raise ValueError(
                f"eval_split_ratio는 0과 0.5 사이여야 합니다. 현재값: {self.eval_split_ratio}"
            )


# 모듈 임포트 시 바로 사용 가능한 기본 설정 인스턴스
DEFAULT_CONFIG = PipelineConfig()
