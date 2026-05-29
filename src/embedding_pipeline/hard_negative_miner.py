"""
hard_negative_miner.py
----------------------
KURE-v1 / bge-m3 교사 임베딩 모델 기반 하드 네거티브 마이닝 모듈.

NV-Retriever 마진 공식 적용:
    S_neg <= S_pos * margin_ratio  (상한: 긍정과 너무 유사한 후보 제외)
    S_neg >= similarity_floor      (하한: 무관한 후보 제거)

[고도화]
대량의 쿼리/단락 마이닝 시 메모리 OOM 방지를 위해 배치(Batch-wise) 유사도 연산 기법을 탑재.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from .config import PipelineConfig
from .document_parser import Passage
from .query_synthesizer import SyntheticQuery

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------
class SimilarityScore(NamedTuple):
    """단일 (쿼리 ↔ 단락) 유사도 계산 결과."""

    passage_id: str
    score: float


@dataclass
class HardNegativeCandidate:
    """선별된 하드 네거티브 후보."""

    query_id: str
    passage_id: str          # 하드 네거티브 단락 ID
    passage_text: str
    similarity_score: float  # 교사 모델 유사도
    positive_score: float    # 긍정 단락 유사도 (참조용)
    margin: float            # positive_score - similarity_score


@dataclass
class MiningResult:
    """쿼리 하나에 대한 하드 네거티브 마이닝 결과."""

    query_id: str
    passage_id: str                            # 긍정 단락 ID
    hard_negatives: list[HardNegativeCandidate]
    rejected_too_similar: int = 0              # 상한 초과로 제거된 수
    rejected_too_dissimilar: int = 0           # 하한 미달로 제거된 수


# ---------------------------------------------------------------------------
# 교사 임베딩 모델 래퍼
# ---------------------------------------------------------------------------
class TeacherEmbedder:
    """
    sentence-transformers 기반 교사 임베딩 모델 래퍼.
    배치 처리 + 정규화 + GPU/CPU 자동 선택.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config.teacher_model
        logger.info("교사 모델 로드 중: %s (device=%s)", self._cfg.model_name, self._cfg.device)

        self._model = SentenceTransformer(
            self._cfg.model_name,
            device=self._cfg.device,
        )
        self._model.max_seq_length = self._cfg.max_seq_length

        # 모델 파라미터 동결 (추론 전용)
        for param in self._model.parameters():
            param.requires_grad = False

        logger.info("교사 모델 로드 완료.")

    def encode(
        self,
        texts: list[str],
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        """텍스트 리스트를 배치 임베딩으로 변환."""
        with torch.no_grad():
            embeddings = self._model.encode(
                texts,
                batch_size=self._cfg.batch_size,
                normalize_embeddings=self._cfg.normalize_embeddings,
                show_progress_bar=show_progress_bar,
                convert_to_numpy=True,
            )
        return embeddings  # type: ignore[return-value]

    def similarity_matrix(
        self,
        query_embeddings: np.ndarray,
        passage_embeddings: np.ndarray,
    ) -> np.ndarray:
        """코사인 유사도 행렬 계산."""
        return np.dot(query_embeddings, passage_embeddings.T)


# ---------------------------------------------------------------------------
# NV-Retriever 마진 필터
# ---------------------------------------------------------------------------
class NVRetrieverMarginFilter:
    """
    NV-Retriever 논문 방식의 양적 여유도(quantile margin) 기반 필터.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config.hard_negative

    def filter(
        self,
        query_id: str,
        positive_passage_id: str,
        positive_score: float,
        candidates: list[SimilarityScore],
    ) -> tuple[list[SimilarityScore], int, int]:
        """후보 단락에서 유효한 하드 네거티브를 선별."""
        upper_threshold = positive_score * self._cfg.margin_ratio
        lower_threshold = self._cfg.similarity_floor

        valid: list[SimilarityScore] = []
        rejected_high = 0
        rejected_low = 0

        for candidate in candidates:
            # 긍정 단락 자기 자신 제외
            if candidate.passage_id == positive_passage_id:
                continue

            if candidate.score > upper_threshold:
                # 긍정과 너무 유사 → 오탐 가능성 높음
                rejected_high += 1
                logger.debug(
                    "[%s] 상한 초과 제거 (%.4f > %.4f): %s",
                    query_id, candidate.score, upper_threshold, candidate.passage_id,
                )
            elif candidate.score < lower_threshold:
                # 너무 무관 → 학습 신호 약함
                rejected_low += 1
            else:
                valid.append(candidate)

        return valid, rejected_high, rejected_low


# ---------------------------------------------------------------------------
# 하드 네거티브 마이너 메인 클래스
# ---------------------------------------------------------------------------
class HardNegativeMiner:
    """
    교사 임베딩 모델 + NV-Retriever 마진 필터를 결합한 하드 네거티브 마이닝.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config
        self._hn_cfg = config.hard_negative
        self._embedder = TeacherEmbedder(config)
        self._margin_filter = NVRetrieverMarginFilter(config)

        # 단락 임베딩 캐시 (ID → index 매핑)
        self._passage_embeddings: np.ndarray | None = None
        self._passage_index: list[Passage] = []
        self._passage_id_to_idx: dict[str, int] = {}

    def index_passages(self, passages: list[Passage]) -> None:
        """전체 단락 코퍼스를 한 번에 임베딩하여 인덱싱."""
        logger.info("%d개 단락 임베딩 중 (교사: %s)...", len(passages), self._cfg.teacher_model.model_name)

        texts = [p.text for p in passages]
        self._passage_embeddings = self._embedder.encode(texts, show_progress_bar=True)
        self._passage_index = passages
        self._passage_id_to_idx = {p.passage_id: idx for idx, p in enumerate(passages)}

        logger.info("단락 인덱싱 완료. Shape: %s", self._passage_embeddings.shape)

    def mine(
        self,
        queries: list[SyntheticQuery],
    ) -> list[MiningResult]:
        """
        쿼리 리스트 전체에 대해 하드 네거티브 마이닝 수행 (배치 유사도 연산으로 OOM 보호).
        """
        if self._passage_embeddings is None:
            raise RuntimeError("index_passages()를 먼저 호출하세요.")

        logger.info("%d개 쿼리에 대해 하드 네거티브 마이닝 시작...", len(queries))

        # 쿼리 임베딩 (배치)
        query_texts = [q.query_text for q in queries]
        query_embeddings = self._embedder.encode(query_texts, show_progress_bar=True)

        results: list[MiningResult] = []
        batch_size = self._hn_cfg.mining_batch_size

        # OOM 방지를 위해 쿼리를 지정된 배치 크기 단위로 쪼개어 연산
        for start_idx in range(0, len(queries), batch_size):
            end_idx = min(start_idx + batch_size, len(queries))
            q_batch = queries[start_idx:end_idx]
            q_emb_batch = query_embeddings[start_idx:end_idx]

            # 부분 유사도 행렬 계산 (배치 사이즈 x 단락 전체 개수)
            sim_matrix_batch = self._embedder.similarity_matrix(
                q_emb_batch, self._passage_embeddings
            )

            for local_idx, query in enumerate(q_batch):
                q_idx = start_idx + local_idx
                result = self._mine_single(query, sim_matrix_batch[local_idx])
                results.append(result)

                if (q_idx + 1) % 500 == 0 or (q_idx + 1) == len(queries):
                    logger.info(
                        "마이닝 진행: %d/%d (%.1f%%)",
                        q_idx + 1, len(queries), (q_idx + 1) / len(queries) * 100,
                    )

        total_hn = sum(len(r.hard_negatives) for r in results)
        logger.info(
            "하드 네거티브 마이닝 완료. 총 %d개 삼중쌍 생성 가능.", total_hn
        )
        return results

    def _mine_single(
        self,
        query: SyntheticQuery,
        similarity_scores: np.ndarray,
    ) -> MiningResult:
        """단일 쿼리에 대한 하드 네거티브 마이닝."""
        positive_idx = self._passage_id_to_idx.get(query.passage_id)
        if positive_idx is None:
            logger.warning("긍정 단락 ID를 찾을 수 없음: %s", query.passage_id)
            return MiningResult(
                query_id=query.query_id,
                passage_id=query.passage_id,
                hard_negatives=[],
            )

        positive_score = float(similarity_scores[positive_idx])

        # top-K 후보 추출 (긍정 단락 포함, 이후 필터에서 제거)
        top_k = self._hn_cfg.top_k_candidates
        top_k = min(top_k, len(similarity_scores))
        
        top_k_indices = np.argpartition(similarity_scores, -top_k)[-top_k:]
        top_k_indices = top_k_indices[np.argsort(similarity_scores[top_k_indices])[::-1]]

        candidates = [
            SimilarityScore(
                passage_id=self._passage_index[idx].passage_id,
                score=float(similarity_scores[idx]),
            )
            for idx in top_k_indices
        ]

        # NV-Retriever 마진 필터 적용
        valid_candidates, rejected_high, rejected_low = self._margin_filter.filter(
            query_id=query.query_id,
            positive_passage_id=query.passage_id,
            positive_score=positive_score,
            candidates=candidates,
        )

        # 상위 N개 선택
        selected = valid_candidates[: self._hn_cfg.num_hard_negatives_per_query]

        hard_negatives = [
            HardNegativeCandidate(
                query_id=query.query_id,
                passage_id=cand.passage_id,
                passage_text=self._passage_index[
                    self._passage_id_to_idx[cand.passage_id]
                ].text,
                similarity_score=cand.score,
                positive_score=positive_score,
                margin=positive_score - cand.score,
            )
            for cand in selected
        ]

        return MiningResult(
            query_id=query.query_id,
            passage_id=query.passage_id,
            hard_negatives=hard_negatives,
            rejected_too_similar=rejected_high,
            rejected_too_dissimilar=rejected_low,
        )

    def save_embeddings_cache(self, cache_path: Path) -> None:
        """단락 임베딩을 numpy 파일로 캐싱 (재실행 시 재사용)."""
        if self._passage_embeddings is None:
            raise RuntimeError("임베딩이 아직 계산되지 않았습니다.")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache_path, self._passage_embeddings)
        logger.info("임베딩 캐시 저장: %s", cache_path)

    def load_embeddings_cache(
        self, cache_path: Path, passages: list[Passage]
    ) -> bool:
        """캐싱된 임베딩 로드. 파일이 없으면 False 반환."""
        if not cache_path.exists():
            return False

        self._passage_embeddings = np.load(cache_path)
        self._passage_index = passages
        self._passage_id_to_idx = {p.passage_id: idx for idx, p in enumerate(passages)}
        logger.info("임베딩 캐시 로드 완료: %s (shape=%s)", cache_path, self._passage_embeddings.shape)
        return True


# ---------------------------------------------------------------------------
# 마이닝 통계 리포트
# ---------------------------------------------------------------------------
def compute_mining_stats(results: list[MiningResult]) -> dict:
    """마이닝 결과 통계 요약."""
    total_queries = len(results)
    total_hn = sum(len(r.hard_negatives) for r in results)
    queries_with_hn = sum(1 for r in results if r.hard_negatives)
    total_rejected_high = sum(r.rejected_too_similar for r in results)
    total_rejected_low = sum(r.rejected_too_dissimilar for r in results)

    margin_values = [
        hn.margin
        for r in results
        for hn in r.hard_negatives
    ]

    return {
        "total_queries": total_queries,
        "total_hard_negatives": total_hn,
        "queries_with_hard_negatives": queries_with_hn,
        "coverage_ratio": queries_with_hn / total_queries if total_queries else 0.0,
        "avg_hn_per_query": total_hn / total_queries if total_queries else 0.0,
        "total_rejected_too_similar": total_rejected_high,
        "total_rejected_too_dissimilar": total_rejected_low,
        "margin_mean": float(np.mean(margin_values)) if margin_values else 0.0,
        "margin_std": float(np.std(margin_values)) if margin_values else 0.0,
        "margin_min": float(np.min(margin_values)) if margin_values else 0.0,
        "margin_max": float(np.max(margin_values)) if margin_values else 0.0,
    }
