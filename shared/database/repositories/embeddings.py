"""Embeddings 레포지토리 — 임베딩 파인튜닝 파이프라인 데이터셋 테이블 적재."""

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


def get_emb_corpus_stats(preview_limit: int = 20) -> dict[str, Any]:
    """DB에 적재된 대조학습 코퍼스 현황(트리플렛·합성쿼리·단락) + train 트리플렛 샘플.

    /finetune 페이지가 "구축한 학습 데이터셋 현황"을 보여줄 때 쓴다.
    """
    with db_cursor() as (_, cursor):
        cursor.execute(
            "SELECT split, COUNT(*) AS n FROM emb_training_triplets GROUP BY split"
        )
        by_split = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute(
            "SELECT query_type, COUNT(*) AS n FROM emb_training_triplets "
            "GROUP BY query_type ORDER BY n DESC"
        )
        by_type = [{"query_type": t, "count": n} for t, n in cursor.fetchall()]

        cursor.execute(
            "SELECT (SELECT COUNT(*) FROM emb_synthetic_queries), "
            "       (SELECT COUNT(*) FROM emb_passages), "
            "       (SELECT COUNT(DISTINCT source) FROM emb_passages), "
            "       (SELECT AVG(margin) FROM emb_training_triplets)"
        )
        query_count, passage_count, source_count, avg_margin = cursor.fetchone()

        # ponytail: 마진 상위만 뽑으면 PDF 표 잔해(`| | |`)가 positive로 올라와 데모에서 지저분하다.
        #   길이 하한 + 파이프로 시작하는 단락 제외로 걸러낸다. 청킹 품질이 좋아지면 필터 제거 가능.
        cursor.execute(
            "SELECT query_text, positive_text, negative_text, query_type, margin "
            "FROM emb_training_triplets WHERE split = 'train' "
            "  AND length(positive_text) >= 120 AND positive_text !~ '^[\\s|]*\\|' "
            "ORDER BY margin DESC LIMIT %s",
            [preview_limit],
        )
        preview = fetchall_dicts(cursor)

    return {
        "train_count": by_split.get("train", 0),
        "eval_count": by_split.get("eval", 0),
        "query_count": query_count or 0,
        "passage_count": passage_count or 0,
        "source_count": source_count or 0,
        "avg_margin": float(avg_margin) if avg_margin is not None else 0.0,
        "by_type": by_type,
        "train_preview": preview,
    }


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
