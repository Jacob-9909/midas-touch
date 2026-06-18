"""Personas 레포지토리 — pgvector 유사 페르소나 검색."""

from .connection import db_cursor


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
