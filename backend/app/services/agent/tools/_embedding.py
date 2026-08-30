"""프로젝트 통합 임베딩(BAAI/bge-m3) 싱글톤.

이 모듈은 백엔드 에이전트의 모든 검색 도구가 공유하는 **단일** 임베딩 진입점이다.
- persona_rag: pgvector 검색용 raw 벡터 → `embed()`
- graph_rag: LlamaIndex VectorContextRetriever용 → `get_llamaindex_embedding()`

두 경로 모두 **같은 SentenceTransformer 인스턴스 하나**를 재사용한다(메모리에 bge-m3 1벌).
**중요**: 여기서 쓰는 모델은 `ingest_personas.py`(persona_embeddings 적재)와 Neo4j 지식그래프
인덱스가 사용하는 모델과 반드시 동일해야 한다(BAAI/bge-m3, 1024차원).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

try:
    import truststore
    truststore.inject_into_ssl()
except Exception as exc:
    # truststore가 없거나 주입에 실패해도 앱은 뜬다(certifi 번들로 폴백). 다만 사내망 등
    # 시스템 인증서가 필요한 환경에선 이후 TLS 실패의 원인이 되므로 조용히 넘기지 않는다.
    logging.getLogger(__name__).debug("truststore 미적용 — 시스템 인증서 대신 기본 번들 사용: %s", exc)

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = os.environ.get("AGENT_EMBEDDING_MODEL", "BAAI/bge-m3")

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """프로세스 전역에서 한 번만 로드되는 bge-m3 모델 인스턴스를 반환한다."""
    global _model
    if _model is None:
        print(f"[agent] 통합 임베딩 모델 로드 중: {EMBEDDING_MODEL_NAME}")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print("[agent] 임베딩 모델 로드 완료.")
    return _model


def embed(text: str) -> list[float]:
    """단일 텍스트를 1024차원 bge-m3 벡터로 인코딩한다 (persona_embeddings 적재와 동일 방식)."""
    return get_embedding_model().encode(text).tolist()


@lru_cache(maxsize=1)
def get_llamaindex_embedding():
    """위 단일 SentenceTransformer를 감싸는 LlamaIndex BaseEmbedding 어댑터(캐시).

    graph_rag가 별도 HuggingFaceEmbedding을 새로 로드하지 않고 동일 모델 인스턴스를 쓰게 한다.
    """
    from llama_index.core.embeddings import BaseEmbedding

    class _SharedBGEM3Embedding(BaseEmbedding):
        """모듈 전역 bge-m3 SentenceTransformer를 재사용하는 LlamaIndex 임베딩."""

        def _get_query_embedding(self, query: str) -> list[float]:
            return embed(query)

        def _get_text_embedding(self, text: str) -> list[float]:
            return embed(text)

        def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
            return get_embedding_model().encode(texts).tolist()

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._get_query_embedding(query)

        async def _aget_text_embedding(self, text: str) -> list[float]:
            return self._get_text_embedding(text)

    return _SharedBGEM3Embedding(model_name=EMBEDDING_MODEL_NAME, embed_batch_size=16)
