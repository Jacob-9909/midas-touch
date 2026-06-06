"""Consolidated supabase_connector routing vector operations directly to the unified PostgreSQL database.

This keeps 100% compatibility with existing method signatures while removing the slow, external Supabase REST HTTP API client.
All operations are now executed directly on the unified PostgreSQL DB via psycopg2.
"""

import os
from typing import Any, List, Dict
from db.connector import db_cursor


def get_client() -> Any:
    """Mock get_client for backward compatibility."""
    return None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def upsert_news(
    client: Any,
    title: str,
    content: str,
    published_at: str,      # ISO 8601
    source: str,
    embedding: List[float],
    source_url: str | None = None,
    language: str = "ko",
    category: str | None = None,
    sentiment_score: float | None = None,
) -> Dict[str, Any]:
    sql = """
    INSERT INTO news_embeddings (
        title, content, published_at, source, source_url, language, category, sentiment_score, embedding, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, CURRENT_TIMESTAMP
    )
    ON CONFLICT (source_url) DO UPDATE SET
        title = EXCLUDED.title,
        content = EXCLUDED.content,
        published_at = EXCLUDED.published_at,
        source = EXCLUDED.source,
        language = EXCLUDED.language,
        category = EXCLUDED.category,
        sentiment_score = EXCLUDED.sentiment_score,
        embedding = EXCLUDED.embedding,
        created_at = CURRENT_TIMESTAMP
    RETURNING id, title, content, published_at, source, source_url, language, category, sentiment_score, created_at;
    """
    with db_cursor() as (conn, cursor):
        cursor.execute(sql, (title, content, published_at, source, source_url, language, category, sentiment_score, embedding))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
    return {}


def search_news(
    client: Any,
    query_embedding: List[float],
    top_k: int = 10,
    category: str | None = None,
    days_back: int = 30,
) -> List[Dict[str, Any]]:
    sql = """
    SELECT id, title, content, published_at, source, category, sentiment_score, similarity
    FROM search_news(%s::vector, %s, %s, %s)
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, (query_embedding, top_k, category, days_back))
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Strategy docs
# ---------------------------------------------------------------------------

def upsert_strategy_doc(
    client: Any,
    title: str,
    chunk_text: str,
    embedding: List[float],
    author: str | None = None,
    published_year: int | None = None,
    strategy_type: str | None = None,
    chunk_index: int = 0,
    source_url: str | None = None,
    azure_legal_id: int | None = None,
) -> Dict[str, Any]:
    sql = """
    INSERT INTO strategy_docs (
        title, author, published_year, strategy_type, chunk_index, chunk_text, embedding, azure_legal_id, source_url, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, CURRENT_TIMESTAMP
    )
    RETURNING id, title, author, published_year, strategy_type, chunk_index, chunk_text, azure_legal_id, source_url, created_at;
    """
    with db_cursor() as (conn, cursor):
        cursor.execute(sql, (title, author, published_year, strategy_type, chunk_index, chunk_text, embedding, azure_legal_id, source_url))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
    return {}


def search_strategies(
    client: Any,
    query_embedding: List[float],
    top_k: int = 5,
    strategy_type: str | None = None,
) -> List[Dict[str, Any]]:
    sql = """
    SELECT id, title, chunk_text, strategy_type, author, similarity
    FROM search_strategies(%s::vector, %s, %s)
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, (query_embedding, top_k, strategy_type))
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Macro indicators
# ---------------------------------------------------------------------------

def upsert_macro_indicator(
    client: Any,
    indicator_name: str,
    indicator_date: str,    # 'YYYY-MM-DD'
    numeric_value: float,
    unit: str,
    source: str,
    analysis_text: str | None = None,
    embedding: List[float] | None = None,
) -> Dict[str, Any]:
    sql = """
    INSERT INTO macro_indicators (
        indicator_name, indicator_date, numeric_value, unit, source, analysis_text, embedding, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s::vector, CURRENT_TIMESTAMP
    )
    ON CONFLICT (indicator_name, indicator_date) DO UPDATE SET
        numeric_value = EXCLUDED.numeric_value,
        unit = EXCLUDED.unit,
        source = EXCLUDED.source,
        analysis_text = EXCLUDED.analysis_text,
        embedding = EXCLUDED.embedding,
        created_at = CURRENT_TIMESTAMP
    RETURNING id, indicator_name, indicator_date, numeric_value, unit, source, analysis_text, created_at;
    """
    with db_cursor() as (conn, cursor):
        cursor.execute(sql, (indicator_name, indicator_date, numeric_value, unit, source, analysis_text, embedding))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
    return {}


# ---------------------------------------------------------------------------
# Persona embeddings
# ---------------------------------------------------------------------------

def upsert_persona_embedding(
    client: Any,
    azure_user_uuid: str,
    persona_text: str,
    embedding: List[float],
) -> Dict[str, Any]:
    sql = """
    INSERT INTO persona_embeddings (
        azure_user_uuid, persona_text, embedding, created_at, updated_at
    ) VALUES (
        %s, %s, %s::vector, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    ON CONFLICT (azure_user_uuid) DO UPDATE SET
        persona_text = EXCLUDED.persona_text,
        embedding = EXCLUDED.embedding,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id, azure_user_uuid, persona_text, created_at, updated_at;
    """
    with db_cursor() as (conn, cursor):
        cursor.execute(sql, (azure_user_uuid, persona_text, embedding))
        row = cursor.fetchone()
        if row:
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
    return {}


def search_similar_personas(
    client: Any,
    query_embedding: List[float],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    sql = """
    SELECT azure_user_uuid, persona_text, similarity
    FROM search_similar_personas(%s::vector, %s)
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, (query_embedding, top_k))
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]
