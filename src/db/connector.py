"""Consolidated PostgreSQL & pgvector Database connector for Midas Touch."""

import os
from contextlib import contextmanager
from typing import Any

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _get_database_url() -> str:
    """Retrieve the unified PostgreSQL database URL from environment variables."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        user = os.environ.get("POSTGRES_USER", "postgres")
        password = os.environ.get("POSTGRES_PASSWORD", "postgres")
        database = os.environ.get("POSTGRES_DB", "postgres")
        url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    return url


def get_connection() -> psycopg2.extensions.connection:
    """Raw psycopg2 connection (caller must close)."""
    return psycopg2.connect(_get_database_url())


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
    """Run consolidated postgres_schema.sql against the database."""
    if schema_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        schema_path = os.path.join(project_root, "database", "schema", "postgres_schema.sql")

    print(f"Applying schema from {schema_path}...")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with db_cursor() as (conn, cursor):
        cursor.execute(sql)
    print("Schema applied successfully!")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def upsert_user(row: dict[str, Any]) -> str:
    """Insert or update a user row. Returns the user UUID."""
    sql = """
    INSERT INTO users (
        uuid, age, sex, marital_status, education_level,
        bachelors_field, occupation, family_type, housing_type, district,
        persona, professional_persona, family_persona,
        career_goals_and_ambitions,
        total_amount, monthly_income, monthly_investable, specific_items,
        has_stock, has_bond, has_deposit, has_real_estate,
        stock_amount, bond_amount, deposit_amount, real_estate_amount,
        aggressiveness, preferred_asset, financial_literacy,
        target_return_percent, investable_period_months, requires_liquidity,
        updated_at
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (uuid) DO UPDATE SET
        age = EXCLUDED.age,
        sex = EXCLUDED.sex,
        marital_status = EXCLUDED.marital_status,
        education_level = EXCLUDED.education_level,
        bachelors_field = EXCLUDED.bachelors_field,
        occupation = EXCLUDED.occupation,
        family_type = EXCLUDED.family_type,
        housing_type = EXCLUDED.housing_type,
        district = EXCLUDED.district,
        persona = EXCLUDED.persona,
        professional_persona = EXCLUDED.professional_persona,
        family_persona = EXCLUDED.family_persona,
        career_goals_and_ambitions = EXCLUDED.career_goals_and_ambitions,
        total_amount = EXCLUDED.total_amount,
        monthly_income = EXCLUDED.monthly_income,
        monthly_investable = EXCLUDED.monthly_investable,
        specific_items = EXCLUDED.specific_items,
        has_stock = EXCLUDED.has_stock,
        has_bond = EXCLUDED.has_bond,
        has_deposit = EXCLUDED.has_deposit,
        has_real_estate = EXCLUDED.has_real_estate,
        stock_amount = EXCLUDED.stock_amount,
        bond_amount = EXCLUDED.bond_amount,
        deposit_amount = EXCLUDED.deposit_amount,
        real_estate_amount = EXCLUDED.real_estate_amount,
        aggressiveness = EXCLUDED.aggressiveness,
        preferred_asset = EXCLUDED.preferred_asset,
        financial_literacy = EXCLUDED.financial_literacy,
        target_return_percent = EXCLUDED.target_return_percent,
        investable_period_months = EXCLUDED.investable_period_months,
        requires_liquidity = EXCLUDED.requires_liquidity,
        updated_at = CURRENT_TIMESTAMP;
    """
    vals = _user_params(row)
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [row.get("uuid")] + vals)
    return row.get("uuid", "")


def bulk_upsert_users(rows: list[dict[str, Any]]) -> int:
    """Batch upsert. Returns count of rows processed."""
    sql = """
    INSERT INTO users (
        uuid, age, sex, marital_status, education_level,
        bachelors_field, occupation, family_type, housing_type, district,
        persona, professional_persona, family_persona,
        career_goals_and_ambitions,
        total_amount, monthly_income, monthly_investable, specific_items,
        has_stock, has_bond, has_deposit, has_real_estate,
        stock_amount, bond_amount, deposit_amount, real_estate_amount,
        aggressiveness, preferred_asset, financial_literacy,
        target_return_percent, investable_period_months, requires_liquidity,
        updated_at
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        CURRENT_TIMESTAMP
    )
    ON CONFLICT (uuid) DO UPDATE SET
        age = EXCLUDED.age,
        sex = EXCLUDED.sex,
        marital_status = EXCLUDED.marital_status,
        education_level = EXCLUDED.education_level,
        bachelors_field = EXCLUDED.bachelors_field,
        occupation = EXCLUDED.occupation,
        family_type = EXCLUDED.family_type,
        housing_type = EXCLUDED.housing_type,
        district = EXCLUDED.district,
        persona = EXCLUDED.persona,
        professional_persona = EXCLUDED.professional_persona,
        family_persona = EXCLUDED.family_persona,
        career_goals_and_ambitions = EXCLUDED.career_goals_and_ambitions,
        total_amount = EXCLUDED.total_amount,
        monthly_income = EXCLUDED.monthly_income,
        monthly_investable = EXCLUDED.monthly_investable,
        specific_items = EXCLUDED.specific_items,
        has_stock = EXCLUDED.has_stock,
        has_bond = EXCLUDED.has_bond,
        has_deposit = EXCLUDED.has_deposit,
        has_real_estate = EXCLUDED.has_real_estate,
        stock_amount = EXCLUDED.stock_amount,
        bond_amount = EXCLUDED.bond_amount,
        deposit_amount = EXCLUDED.deposit_amount,
        real_estate_amount = EXCLUDED.real_estate_amount,
        aggressiveness = EXCLUDED.aggressiveness,
        preferred_asset = EXCLUDED.preferred_asset,
        financial_literacy = EXCLUDED.financial_literacy,
        target_return_percent = EXCLUDED.target_return_percent,
        investable_period_months = EXCLUDED.investable_period_months,
        requires_liquidity = EXCLUDED.requires_liquidity,
        updated_at = CURRENT_TIMESTAMP;
    """
    count = 0
    with db_cursor() as (_, cursor):
        batch_params = []
        for row in rows:
            vals = _user_params(row)
            batch_params.append([row.get("uuid")] + vals)
        cursor.executemany(sql, batch_params)
        count = len(rows)
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
        bool(row.get("has_stock", 0)),
        bool(row.get("has_bond", 0)),
        bool(row.get("has_deposit", 0)),
        bool(row.get("has_real_estate", 0)),
        row.get("stock_amount", 0),
        row.get("bond_amount", 0),
        row.get("deposit_amount", 0),
        row.get("real_estate_amount", 0),
        row.get("aggressiveness"),
        row.get("preferred_asset"),
        row.get("financial_literacy"),
        row.get("target_return_percent"),
        row.get("investable_period_months"),
        bool(row.get("requires_liquidity", 0)),
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
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [date, data_type, sub_key, value, unit, source])


def bulk_upsert_market_snapshots(rows: list[dict[str, Any]]) -> int:
    """Bulk upsert market snapshots in a single transaction. Returns count of rows processed."""
    sql = """
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
    count = 0
    with db_cursor() as (_, cursor):
        batch_params = []
        for row in rows:
            dt = row.get("snapshot_date")
            dtype = row.get("data_type")
            skey = row.get("sub_key")
            val = row.get("value")
            unit = row.get("unit")
            src = row.get("source")
            batch_params.append([dt, dtype, skey, val, unit, src])
        cursor.executemany(sql, batch_params)
        count = len(rows)
    return count


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_user_by_uuid(uuid: str) -> dict | None:
    with db_cursor() as (_, cursor):
        cursor.execute("SELECT * FROM users WHERE uuid = %s", [uuid])
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))


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


def get_all_tax_rules() -> list[dict]:
    """Retrieve all current active tax rules."""
    sql = """
    SELECT asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate, deduction_limit, description, legal_basis
    FROM tax_rules
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]


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


def search_similar_personas_db(embedding: list[float], top_k: int = 3) -> list[dict]:
    """Search similar personas in our PostgreSQL database using the custom pgvector search function."""
    sql = """
    SELECT azure_user_uuid, persona_text, similarity
    FROM search_similar_personas(%s::vector, %s)
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, (embedding, top_k))
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Embedding pipeline dataset tables
# ---------------------------------------------------------------------------

def bulk_upsert_emb_passages(passages: list[dict[str, Any]]) -> int:
    """Upsert parsed document passages into emb_passages. Returns count."""
    import json as _json
    sql = """
    INSERT INTO emb_passages (passage_id, text, source, metadata)
    VALUES (%s, %s, %s, %s)
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
        cursor.executemany(sql, params)
    return len(passages)


def bulk_upsert_emb_queries(queries: list[dict[str, Any]]) -> int:
    """Upsert synthetic queries into emb_synthetic_queries. Returns count."""
    sql = """
    INSERT INTO emb_synthetic_queries (query_id, passage_id, query_text, query_type, source_passage)
    VALUES (%s, %s, %s, %s, %s)
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
        cursor.executemany(sql, params)
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
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        cursor.executemany(sql, params)
    return len(triplets)
