"""DB 연결 프리미티브 — 커넥션·커서·스키마 부트스트랩.

도메인 레포지토리(users/market/tax/...)는 모두 여기의 db_cursor를 통해 DB에 접근한다.
"""

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


def apply_schema(schema_path: str | None = None) -> None:
    """Run consolidated postgres_schema.sql against the database.

    기본 경로는 이 패키지 기준 `shared/database/schema/postgres_schema.sql`을 가리킨다.
    (이전 connector.py는 존재하지 않는 `<root>/database/schema/`를 가리키는 버그가 있었다.)
    """
    if schema_path is None:
        # __file__ = shared/database/repositories/connection.py → 두 단계 위가 shared/database
        db_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        schema_path = os.path.join(db_dir, "schema", "postgres_schema.sql")

    print(f"Applying schema from {schema_path}...")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    with db_cursor() as (conn, cursor):
        cursor.execute(sql)
    print("Schema applied successfully!")


__all__ = ["_get_database_url", "get_connection", "db_cursor", "apply_schema", "Any"]
