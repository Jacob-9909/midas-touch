"""Supabase (pgvector) connector for Midas Touch."""

import os
from typing import Any

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def upsert_news(
    client: Client,
    title: str,
    content: str,
    published_at: str,      # ISO 8601
    source: str,
    embedding: list[float],
    source_url: str | None = None,
    language: str = "ko",
    category: str | None = None,
    sentiment_score: float | None = None,
) -> dict:
    row = {
        "title": title,
        "content": content,
        "published_at": published_at,
        "source": source,
        "source_url": source_url,
        "language": language,
        "category": category,
        "sentiment_score": sentiment_score,
        "embedding": embedding,
    }
    result = (
        client.table("news_embeddings")
        .upsert(row, on_conflict="source_url")
        .execute()
    )
    return result.data[0] if result.data else {}


def search_news(
    client: Client,
    query_embedding: list[float],
    top_k: int = 10,
    category: str | None = None,
    days_back: int = 30,
) -> list[dict]:
    result = client.rpc(
        "search_news",
        {
            "query_embedding": query_embedding,
            "top_k": top_k,
            "category_filter": category,
            "days_back": days_back,
        },
    ).execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Strategy docs
# ---------------------------------------------------------------------------

def upsert_strategy_doc(
    client: Client,
    title: str,
    chunk_text: str,
    embedding: list[float],
    author: str | None = None,
    published_year: int | None = None,
    strategy_type: str | None = None,
    chunk_index: int = 0,
    source_url: str | None = None,
    azure_legal_id: int | None = None,
) -> dict:
    row = {
        "title": title,
        "author": author,
        "published_year": published_year,
        "strategy_type": strategy_type,
        "chunk_index": chunk_index,
        "chunk_text": chunk_text,
        "embedding": embedding,
        "source_url": source_url,
        "azure_legal_id": azure_legal_id,
    }
    result = client.table("strategy_docs").insert(row).execute()
    return result.data[0] if result.data else {}


def search_strategies(
    client: Client,
    query_embedding: list[float],
    top_k: int = 5,
    strategy_type: str | None = None,
) -> list[dict]:
    result = client.rpc(
        "search_strategies",
        {
            "query_embedding": query_embedding,
            "top_k": top_k,
            "strategy_filter": strategy_type,
        },
    ).execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Macro indicators
# ---------------------------------------------------------------------------

def upsert_macro_indicator(
    client: Client,
    indicator_name: str,
    indicator_date: str,    # 'YYYY-MM-DD'
    numeric_value: float,
    unit: str,
    source: str,
    analysis_text: str | None = None,
    embedding: list[float] | None = None,
) -> dict:
    row: dict[str, Any] = {
        "indicator_name": indicator_name,
        "indicator_date": indicator_date,
        "numeric_value": numeric_value,
        "unit": unit,
        "source": source,
        "analysis_text": analysis_text,
        "embedding": embedding,
    }
    result = (
        client.table("macro_indicators")
        .upsert(row, on_conflict="indicator_name,indicator_date")
        .execute()
    )
    return result.data[0] if result.data else {}


# ---------------------------------------------------------------------------
# Persona embeddings
# ---------------------------------------------------------------------------

def upsert_persona_embedding(
    client: Client,
    azure_user_uuid: str,
    persona_text: str,
    embedding: list[float],
) -> dict:
    row = {
        "azure_user_uuid": azure_user_uuid,
        "persona_text": persona_text,
        "embedding": embedding,
    }
    result = (
        client.table("persona_embeddings")
        .upsert(row, on_conflict="azure_user_uuid")
        .execute()
    )
    return result.data[0] if result.data else {}


def search_similar_personas(
    client: Client,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    result = client.rpc(
        "search_similar_personas",
        {"query_embedding": query_embedding, "top_k": top_k},
    ).execute()
    return result.data or []
