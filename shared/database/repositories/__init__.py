"""도메인별 PostgreSQL 레포지토리.

이전의 단일 god-module(connector.py, 537줄)을 도메인 경계로 분해한 패키지.
하위 호환을 위해 shared.database.connector가 이 패키지의 함수들을 그대로 재노출한다.
"""

from .checkpoints import delete_checkpoint_thread, list_checkpoint_threads
from .connection import apply_schema, db_cursor, get_connection
from .embeddings import (
    bulk_upsert_emb_passages,
    list_emb_sources,
    search_similar_passages_db,
)
from .market import (
    bulk_upsert_market_snapshots,
    get_last_ingest_time,
    get_latest_market_snapshots,
    get_latest_market_value,
    get_market_history,
    upsert_market_snapshot,
)
from .personas import search_similar_personas_db
from .sessions import delete_chat_session, list_chat_sessions, upsert_chat_session
from .tax import get_all_tax_rules
from .users import (
    bulk_upsert_portfolios,
    bulk_upsert_users,
    get_portfolios_by_user_uuid,
    get_user_by_uuid,
    list_users,
    upsert_user,
)
from .watchlist import add_watchlist, list_watchlist, remove_watchlist

__all__ = [
    # watchlist
    "add_watchlist",
    "apply_schema",
    # embeddings
    "bulk_upsert_emb_passages",
    "bulk_upsert_market_snapshots",
    "bulk_upsert_portfolios",
    "bulk_upsert_users",
    "db_cursor",
    "delete_chat_session",
    "delete_checkpoint_thread",
    # tax
    "get_all_tax_rules",
    # connection
    "get_connection",
    "get_last_ingest_time",
    "get_latest_market_snapshots",
    "get_latest_market_value",
    "get_portfolios_by_user_uuid",
    "get_user_by_uuid",
    "list_chat_sessions",
    # checkpoints
    "list_checkpoint_threads",
    "list_emb_sources",
    "list_users",
    "list_watchlist",
    "remove_watchlist",
    "search_similar_passages_db",
    # personas
    "search_similar_personas_db",
    # sessions
    "upsert_chat_session",
    # market
    "upsert_market_snapshot",
    # users
    "upsert_user",
]
