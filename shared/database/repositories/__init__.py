"""도메인별 PostgreSQL 레포지토리.

이전의 단일 god-module(connector.py, 537줄)을 도메인 경계로 분해한 패키지.
하위 호환을 위해 shared.database.connector가 이 패키지의 함수들을 그대로 재노출한다.
"""

from .connection import apply_schema, db_cursor, get_connection
from .checkpoints import delete_checkpoint_thread, list_checkpoint_threads
from .embeddings import (
    bulk_upsert_emb_passages,
    bulk_upsert_emb_queries,
    bulk_upsert_emb_triplets,
)
from .market import (
    bulk_upsert_market_snapshots,
    get_latest_market_snapshots,
    get_latest_market_value,
    upsert_market_snapshot,
)
from .personas import search_similar_personas_db
from .sessions import delete_chat_session, list_chat_sessions, upsert_chat_session
from .tax import get_all_tax_rules
from .watchlist import add_watchlist, list_watchlist, remove_watchlist
from .users import (
    bulk_upsert_portfolios,
    bulk_upsert_users,
    get_portfolios_by_user_uuid,
    get_user_by_uuid,
    list_users,
    upsert_user,
)

__all__ = [
    # connection
    "get_connection",
    "db_cursor",
    "apply_schema",
    # users
    "upsert_user",
    "bulk_upsert_users",
    "bulk_upsert_portfolios",
    "get_user_by_uuid",
    "list_users",
    "get_portfolios_by_user_uuid",
    # market
    "upsert_market_snapshot",
    "bulk_upsert_market_snapshots",
    "get_latest_market_value",
    "get_latest_market_snapshots",
    # tax
    "get_all_tax_rules",
    # watchlist
    "add_watchlist",
    "list_watchlist",
    "remove_watchlist",
    # personas
    "search_similar_personas_db",
    # checkpoints
    "list_checkpoint_threads",
    "delete_checkpoint_thread",
    # sessions
    "upsert_chat_session",
    "list_chat_sessions",
    "delete_chat_session",
    # embeddings
    "bulk_upsert_emb_passages",
    "bulk_upsert_emb_queries",
    "bulk_upsert_emb_triplets",
]
