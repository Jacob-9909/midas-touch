"""Watchlist 레포지토리 — 유저별 관심종목.

최초 사용 시 CREATE TABLE IF NOT EXISTS로 자기완결 생성(analysis_memory와 동일 패턴).
모든 함수는 갱신된 ticker 목록을 돌려줘 호출자가 재조회할 필요가 없게 한다.
"""

from .connection import db_cursor

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_uuid VARCHAR(64) NOT NULL,
    ticker VARCHAR(32) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (user_uuid, ticker)
);
"""


def list_watchlist(user_uuid: str) -> list[str]:
    """최근 추가 순 관심종목 티커 목록."""
    with db_cursor() as (_, cur):
        cur.execute(_CREATE_SQL)
        cur.execute(
            "SELECT ticker FROM watchlist WHERE user_uuid = %s ORDER BY created_at DESC",
            [user_uuid],
        )
        return [r[0] for r in cur.fetchall()]


def add_watchlist(user_uuid: str, ticker: str) -> list[str]:
    """관심종목 추가(중복은 무시) 후 갱신된 목록 반환."""
    with db_cursor() as (_, cur):
        cur.execute(_CREATE_SQL)
        cur.execute(
            "INSERT INTO watchlist (user_uuid, ticker) VALUES (%s, %s) "
            "ON CONFLICT (user_uuid, ticker) DO NOTHING",
            [user_uuid, ticker.upper()],
        )
    return list_watchlist(user_uuid)


def remove_watchlist(user_uuid: str, ticker: str) -> list[str]:
    """관심종목 제거 후 갱신된 목록 반환."""
    with db_cursor() as (_, cur):
        cur.execute(_CREATE_SQL)
        cur.execute(
            "DELETE FROM watchlist WHERE user_uuid = %s AND ticker = %s",
            [user_uuid, ticker.upper()],
        )
    return list_watchlist(user_uuid)
