"""Embeddings 레포지토리 — 임베딩 파인튜닝 파이프라인 데이터셋 테이블 적재."""

import json as _json
from typing import Any

from psycopg2.extras import execute_values

from .connection import db_cursor


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


def bulk_upsert_emb_queries(queries: list[dict[str, Any]]) -> int:
    """Upsert synthetic queries into emb_synthetic_queries. Returns count."""
    sql = """
    INSERT INTO emb_synthetic_queries (query_id, passage_id, query_text, query_type, source_passage)
    VALUES %s
    ON CONFLICT (query_id) DO UPDATE SET
        query_text     = EXCLUDED.query_text,
        query_type     = EXCLUDED.query_type,
        source_passage = EXCLUDED.source_passage;
    """
    with db_cursor() as (_, cursor):
        params = [
            (
                q["query_id"],
                q["passage_id"],
                q["query_text"],
                q["query_type"],
                q["source_passage"],
            )
            for q in queries
        ]
        execute_values(cursor, sql, params)
    return len(queries)


def bulk_upsert_emb_triplets(triplets: list[dict[str, Any]], split: str) -> int:
    """Upsert training/eval triplets into emb_training_triplets. Returns count."""
    sql = """
    INSERT INTO emb_training_triplets (
        triplet_id, query_id, query_text,
        positive_passage_id, positive_text,
        negative_passage_id, negative_text,
        query_type, negative_similarity_score, positive_similarity_score, margin,
        split
    ) VALUES %s
    ON CONFLICT (triplet_id) DO UPDATE SET
        negative_similarity_score = EXCLUDED.negative_similarity_score,
        positive_similarity_score = EXCLUDED.positive_similarity_score,
        margin                    = EXCLUDED.margin,
        split                     = EXCLUDED.split;
    """
    with db_cursor() as (_, cursor):
        params = [
            (
                t["triplet_id"],
                t["query_id"],
                t["query_text"],
                t["positive_passage_id"],
                t["positive_text"],
                t["negative_passage_id"],
                t["negative_text"],
                t["query_type"],
                t["negative_similarity_score"],
                t["positive_similarity_score"],
                t["margin"],
                split,
            )
            for t in triplets
        ]
        execute_values(cursor, sql, params)
    return len(triplets)
