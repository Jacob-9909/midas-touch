"""Azure SQL Database connector for Midas Touch."""

import os
from contextlib import contextmanager
from typing import Any

import pyodbc
from dotenv import load_dotenv

load_dotenv()

_DRIVER = "ODBC Driver 18 for SQL Server"


def _build_connection_string() -> str:
    server   = os.environ["AZURE_SQL_SERVER"]    # e.g. midas-touch.database.windows.net
    database = os.environ["AZURE_SQL_DATABASE"]  # e.g. midas-touch
    user     = os.environ["AZURE_SQL_USER"]
    password = os.environ["AZURE_SQL_PASSWORD"]
    return (
        f"DRIVER={{{_DRIVER}}};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )


def get_connection() -> pyodbc.Connection:
    """Raw pyodbc connection (caller must close)."""
    return pyodbc.connect(_build_connection_string())


@contextmanager
def db_cursor():
    """Context manager: yields (conn, cursor), auto-commits or rolls back."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def apply_schema(schema_path: str | None = None) -> None:
    """Run schema.sql against the target database (idempotent-safe)."""
    if schema_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        schema_path = os.path.join(project_root, "database", "schema", "azure_schema.sql")

    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()

    # SQL Server doesn't support multi-statement execution via pyodbc directly;
    # split on GO or semicolons between top-level statements.
    statements = [s.strip() for s in sql.split(";") if s.strip()]

    with db_cursor() as (conn, cursor):
        for stmt in statements:
            # Filter out comment-only lines from the statement
            cleaned_lines = []
            for line in stmt.splitlines():
                stripped = line.strip()
                if not stripped.startswith("--") and stripped:
                    cleaned_lines.append(line)
            cleaned_stmt = "\n".join(cleaned_lines).strip()
            
            if not cleaned_stmt:
                continue
            try:
                cursor.execute(cleaned_stmt)
            except pyodbc.ProgrammingError as e:
                # 객체가 이미 존재하면 건너뜀 (idempotent)
                if "already an object" in str(e) or "There is already" in str(e):
                    continue
                raise


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def upsert_user(row: dict[str, Any]) -> str:
    """Insert or update a user row. Returns the user UUID."""
    sql = """
    MERGE users AS target
    USING (SELECT ? AS uuid) AS source ON target.uuid = source.uuid
    WHEN MATCHED THEN UPDATE SET
        age = ?, sex = ?, marital_status = ?, education_level = ?,
        bachelors_field = ?, occupation = ?, family_type = ?,
        housing_type = ?, district = ?,
        persona = ?, professional_persona = ?, family_persona = ?,
        career_goals_and_ambitions = ?,
        total_amount = ?, monthly_income = ?, monthly_investable = ?,
        specific_items = ?,
        has_stock = ?, has_bond = ?, has_deposit = ?, has_real_estate = ?,
        stock_amount = ?, bond_amount = ?, deposit_amount = ?, real_estate_amount = ?,
        aggressiveness = ?, preferred_asset = ?, financial_literacy = ?,
        target_return_percent = ?, investable_period_months = ?,
        requires_liquidity = ?,
        updated_at = GETDATE()
    WHEN NOT MATCHED THEN INSERT (
        uuid, age, sex, marital_status, education_level,
        bachelors_field, occupation, family_type, housing_type, district,
        persona, professional_persona, family_persona,
        career_goals_and_ambitions,
        total_amount, monthly_income, monthly_investable, specific_items,
        has_stock, has_bond, has_deposit, has_real_estate,
        stock_amount, bond_amount, deposit_amount, real_estate_amount,
        aggressiveness, preferred_asset, financial_literacy,
        target_return_percent, investable_period_months, requires_liquidity
    ) VALUES (
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?,
        ?, ?, ?
    );
    """
    vals = _user_params(row)
    # MERGE requires params twice (WHEN MATCHED + WHEN NOT MATCHED)
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [row.get("uuid")] + vals + [row.get("uuid")] + vals)
    return row.get("uuid", "")


def bulk_upsert_users(rows: list[dict[str, Any]]) -> int:
    """Batch upsert. Returns count of rows processed."""
    count = 0
    for row in rows:
        upsert_user(row)
        count += 1
    return count


def _user_params(row: dict[str, Any]) -> list:
    return [
        row.get("age"),
        row.get("sex"),
        row.get("marital_status"),
        row.get("education_level"),
        row.get("bachelors_field"),
        row.get("occupation"),
        row.get("family_type"),
        row.get("housing_type"),
        row.get("district"),
        row.get("persona"),
        row.get("professional_persona"),
        row.get("family_persona"),
        row.get("career_goals_and_ambitions"),
        row.get("total_amount"),
        row.get("monthly_income"),
        row.get("monthly_investable"),
        row.get("specific_items"),
        int(row.get("has_stock", 0)),
        int(row.get("has_bond", 0)),
        int(row.get("has_deposit", 0)),
        int(row.get("has_real_estate", 0)),
        int(row.get("stock_amount", 0)),
        int(row.get("bond_amount", 0)),
        int(row.get("deposit_amount", 0)),
        int(row.get("real_estate_amount", 0)),
        row.get("aggressiveness"),
        row.get("preferred_asset"),
        row.get("financial_literacy"),
        row.get("target_return_percent"),
        row.get("investable_period_months"),
        int(row.get("requires_liquidity", 0)),
    ]


# ---------------------------------------------------------------------------
# Market snapshots
# ---------------------------------------------------------------------------

def upsert_market_snapshot(
    date: str,          # 'YYYY-MM-DD'
    data_type: str,     # 'exchange_rate' | 'interest_rate' | 'oil_price' | ...
    sub_key: str,       # 'USD/KRW' | 'KR_CD' | 'WTI' | ...
    value: float,
    unit: str,
    source: str,
) -> None:
    sql = """
    MERGE market_snapshots AS target
    USING (SELECT ? AS snapshot_date, ? AS data_type, ? AS sub_key) AS src
        ON  target.snapshot_date = src.snapshot_date
        AND target.data_type     = src.data_type
        AND target.sub_key       = src.sub_key
    WHEN MATCHED THEN UPDATE SET value = ?, unit = ?, source = ?
    WHEN NOT MATCHED THEN INSERT
        (snapshot_date, data_type, sub_key, value, unit, source)
        VALUES (?, ?, ?, ?, ?, ?);
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [
            date, data_type, sub_key,       # key (USING)
            value, unit, source,            # WHEN MATCHED
            date, data_type, sub_key, value, unit, source,  # WHEN NOT MATCHED
        ])


def bulk_upsert_market_snapshots(rows: list[dict[str, Any]]) -> int:
    """Bulk upsert market snapshots in a single transaction. Returns count of rows processed."""
    sql = """
    MERGE market_snapshots AS target
    USING (SELECT ? AS snapshot_date, ? AS data_type, ? AS sub_key) AS src
        ON  target.snapshot_date = src.snapshot_date
        AND target.data_type     = src.data_type
        AND target.sub_key       = src.sub_key
    WHEN MATCHED THEN UPDATE SET value = ?, unit = ?, source = ?
    WHEN NOT MATCHED THEN INSERT
        (snapshot_date, data_type, source, sub_key, value, unit)
        VALUES (?, ?, ?, ?, ?, ?);
    """
    # Wait, check if INSERT columns match the SELECT/VALUES order!
    # Table schema: (snapshot_date, data_type, sub_key, value, unit, source)
    # Let's write the INSERT explicitly:
    sql = """
    MERGE market_snapshots AS target
    USING (SELECT ? AS snapshot_date, ? AS data_type, ? AS sub_key) AS src
        ON  target.snapshot_date = src.snapshot_date
        AND target.data_type     = src.data_type
        AND target.sub_key       = src.sub_key
    WHEN MATCHED THEN UPDATE SET value = ?, unit = ?, source = ?
    WHEN NOT MATCHED THEN INSERT
        (snapshot_date, data_type, sub_key, value, unit, source)
        VALUES (?, ?, ?, ?, ?, ?);
    """
    count = 0
    with db_cursor() as (_, cursor):
        for row in rows:
            dt = row.get("snapshot_date")
            dtype = row.get("data_type")
            skey = row.get("sub_key")
            val = row.get("value")
            unit = row.get("unit")
            src = row.get("source")
            
            cursor.execute(sql, [
                dt, dtype, skey,       # USING keys
                val, unit, src,        # MATCHED
                dt, dtype, skey, val, unit, src  # INSERT
            ])
            count += 1
    return count


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_user_by_uuid(uuid: str) -> dict | None:
    with db_cursor() as (_, cursor):
        cursor.execute("SELECT * FROM users WHERE uuid = ?", [uuid])
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


def get_latest_market_value(data_type: str, sub_key: str) -> dict | None:
    sql = """
    SELECT TOP 1 snapshot_date, value, unit, source
    FROM market_snapshots
    WHERE data_type = ? AND sub_key = ?
    ORDER BY snapshot_date DESC
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [data_type, sub_key])
        row = cursor.fetchone()
        if row is None:
            return None
        return {"date": row[0], "value": row[1], "unit": row[2], "source": row[3]}
