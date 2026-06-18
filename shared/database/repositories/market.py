"""Market 레포지토리 — 거시경제/시장 지표 스냅샷 upsert/조회."""

from typing import Any

from .connection import db_cursor

_MARKET_UPSERT_SQL = """
INSERT INTO market_snapshots (
    snapshot_date, data_type, sub_key, value, unit, source, created_at
) VALUES (
    %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
)
ON CONFLICT (snapshot_date, data_type, sub_key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    source = EXCLUDED.source,
    created_at = CURRENT_TIMESTAMP;
"""


def upsert_market_snapshot(
    date: str,          # 'YYYY-MM-DD'
    data_type: str,     # 'exchange_rate' | 'interest_rate' | 'oil_price' | ...
    sub_key: str,       # 'USD/KRW' | 'KR_CD' | 'WTI' | ...
    value: float,
    unit: str,
    source: str,
) -> None:
    with db_cursor() as (_, cursor):
        cursor.execute(_MARKET_UPSERT_SQL, [date, data_type, sub_key, value, unit, source])


def bulk_upsert_market_snapshots(rows: list[dict[str, Any]]) -> int:
    """Bulk upsert market snapshots in a single transaction. Returns count of rows processed."""
    with db_cursor() as (_, cursor):
        batch_params = [
            [
                row.get("snapshot_date"),
                row.get("data_type"),
                row.get("sub_key"),
                row.get("value"),
                row.get("unit"),
                row.get("source"),
            ]
            for row in rows
        ]
        cursor.executemany(_MARKET_UPSERT_SQL, batch_params)
    return len(rows)


def get_latest_market_value(data_type: str, sub_key: str) -> dict | None:
    sql = """
    SELECT snapshot_date, value, unit, source
    FROM market_snapshots
    WHERE data_type = %s AND sub_key = %s
    ORDER BY snapshot_date DESC
    LIMIT 1
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [data_type, sub_key])
        row = cursor.fetchone()
        if row is None:
            return None
        return {"date": row[0], "value": row[1], "unit": row[2], "source": row[3]}


def get_latest_market_snapshots() -> list[dict]:
    """Retrieve the latest snapshot value for every unique (data_type, sub_key) pair."""
    sql = """
    WITH RankedSnapshots AS (
        SELECT snapshot_date, data_type, sub_key, value, unit, source,
               ROW_NUMBER() OVER (PARTITION BY data_type, sub_key ORDER BY snapshot_date DESC) as rn
        FROM market_snapshots
    )
    SELECT snapshot_date, data_type, sub_key, value, unit, source
    FROM RankedSnapshots
    WHERE rn = 1
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]
