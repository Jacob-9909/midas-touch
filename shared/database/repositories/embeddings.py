"""Embeddings 레포지토리 — RAG 단락(emb_passages) 적재·검색."""

import json as _json
from typing import Any

from psycopg2.extras import execute_values

from .connection import db_cursor, fetchall_dicts


def search_similar_passages_db(embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """emb_passages를 pgvector 코사인 거리로 검색해 유사 단락을 반환한다(doc_rag 도구용).

    persona_embeddings와 동일한 bge-m3 1024차원 벡터를 쓴다. 백필 안 된 단락(embedding IS NULL)은
    자동으로 제외된다.
    """
    sql = """
    SELECT passage_id, source, text, 1 - (embedding <=> %s::vector) AS similarity
    FROM emb_passages
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> %s::vector
    LIMIT %s
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, (embedding, embedding, top_k))
        return fetchall_dicts(cursor)


def bulk_upsert_emb_passages(passages: list[dict[str, Any]]) -> int:
    """Upsert parsed document passages into emb_passages. Returns count."""
    sql = """
    INSERT INTO emb_passages (passage_id, text, source, metadata)
    VALUES %s
    ON CONFLICT (passage_id) DO UPDATE SET
        text     = EXCLUDED.text,
        source   = EXCLUDED.source,
        metadata = EXCLUDED.metadata;
    """
    with db_cursor() as (_, cursor):
        params = [
            (
                p["passage_id"],
                p["text"],
                p["source"],
                _json.dumps(p.get("metadata") or {}, ensure_ascii=False),
            )
            for p in passages
        ]
        execute_values(cursor, sql, params)
    return len(passages)


def list_emb_sources() -> list[dict[str, Any]]:
    """RAG에 반영된 문서(source)별 단락 수. 챗봇 지식베이스 패널의 '현재 반영된 파일' 목록용."""
    sql = "SELECT source, COUNT(*) AS passages FROM emb_passages GROUP BY source ORDER BY source;"
    with db_cursor() as (_, cursor):
        cursor.execute(sql)
        return [{"source": src, "passages": cnt} for src, cnt in cursor.fetchall()]


