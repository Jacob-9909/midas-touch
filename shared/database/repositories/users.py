"""Users 레포지토리 — 사용자 프로필 upsert/조회."""

from typing import Any

from .connection import db_cursor, fetchall_dicts, fetchone_dict

_USERS_UPSERT_SQL = """
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


def upsert_user(row: dict[str, Any]) -> str:
    """Insert or update a user row. Returns the user UUID."""
    vals = _user_params(row)
    with db_cursor() as (_, cursor):
        cursor.execute(_USERS_UPSERT_SQL, [row.get("uuid")] + vals)
    return row.get("uuid", "")


def bulk_upsert_users(rows: list[dict[str, Any]]) -> int:
    """Batch upsert. Returns count of rows processed."""
    with db_cursor() as (_, cursor):
        batch_params = [[row.get("uuid")] + _user_params(row) for row in rows]
        cursor.executemany(_USERS_UPSERT_SQL, batch_params)
    return len(rows)


def get_user_by_uuid(uuid: str) -> dict | None:
    with db_cursor() as (_, cursor):
        cursor.execute("SELECT * FROM users WHERE uuid = %s", [uuid])
        return fetchone_dict(cursor)


def list_users(limit: int = 50, offset: int = 0) -> list[dict]:
    """웹 콘솔 유저 선택용 요약 목록. uuid가 있는 사용자만 노출한다."""
    sql = """
    SELECT uuid, age, sex, occupation, family_type, district,
           total_amount, monthly_income, aggressiveness, financial_literacy,
           preferred_asset
    FROM users
    WHERE uuid IS NOT NULL
    ORDER BY created_at DESC
    LIMIT %s OFFSET %s
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [limit, offset])
        return fetchall_dicts(cursor)


def get_portfolios_by_user_uuid(uuid: str) -> list[dict]:
    """해당 유저의 포트폴리오와 각 포트폴리오의 개별 종목(items)을 함께 반환한다."""
    pf_sql = """
    SELECT p.id, p.name, p.strategy_name, p.stock_ratio, p.bond_ratio,
           p.deposit_ratio, p.real_estate_ratio, p.gold_ratio, p.cash_ratio,
           p.is_active
    FROM portfolios p
    JOIN users u ON u.id = p.user_id
    WHERE u.uuid = %s
    ORDER BY p.is_active DESC, p.created_at DESC
    """
    item_sql = """
    SELECT asset_type, ticker, name, allocation_pct, currency, note
    FROM portfolio_items
    WHERE portfolio_id = %s
    ORDER BY allocation_pct DESC
    """
    with db_cursor() as (_, cursor):
        cursor.execute(pf_sql, [uuid])
        portfolios = fetchall_dicts(cursor)
        for pf in portfolios:
            cursor.execute(item_sql, [pf["id"]])
            pf["items"] = fetchall_dicts(cursor)
    return portfolios
