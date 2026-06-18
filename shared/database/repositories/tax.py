"""Tax 레포지토리 — 세법 규칙 조회."""

from .connection import db_cursor


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
