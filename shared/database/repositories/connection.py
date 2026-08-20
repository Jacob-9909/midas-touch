"""DB 연결 프리미티브 — 커넥션 풀·커서·스키마 부트스트랩.

도메인 레포지토리(users/market/tax/...)는 모두 여기의 db_cursor를 통해 DB에 접근한다.
db_cursor는 프로세스 단위 ThreadedConnectionPool에서 커넥션을 빌려 재사용한다(요청마다 새로
psycopg2.connect 하던 비용 제거). FastAPI는 sync 핸들러를 스레드풀에서 돌리므로 스레드 안전한
ThreadedConnectionPool이 적합하다. 풀 크기는 PG_POOL_MIN/PG_POOL_MAX(.env)로 조정한다.
"""

import os
import threading
from contextlib import contextmanager
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2 import pool as _pg_pool

load_dotenv()

_pool: _pg_pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


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


def _get_pool() -> _pg_pool.ThreadedConnectionPool:
    """프로세스 수명 동안 유지되는 커넥션 풀을 1회 생성해 반환한다(지연 초기화·스레드 안전)."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                minconn = int(os.environ.get("PG_POOL_MIN", "1"))
                maxconn = int(os.environ.get("PG_POOL_MAX", "20"))
                _pool = _pg_pool.ThreadedConnectionPool(
                    minconn, maxconn, dsn=_get_database_url()
                )
    return _pool


def get_connection() -> psycopg2.extensions.connection:
    """Raw psycopg2 connection (caller must close). 풀을 거치지 않는 직접 연결.

    헬스체크 등 짧은 수명·직접 close가 명확한 호출자용. 반복 쿼리는 db_cursor를 쓰라.
    """
    return psycopg2.connect(_get_database_url())


@contextmanager
def db_cursor():
    """Context manager: 풀에서 커넥션을 빌려 (conn, cursor)를 yield하고, 자동 커밋/롤백 후 반납한다."""
    pool = _get_pool()
    conn = pool.getconn()
    cursor = None
    try:
        cursor = conn.cursor()
        yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:  # noqa: BLE001
                pass
        pool.putconn(conn)


def fetchall_dicts(cursor) -> list[dict]:
    """cursor.fetchall() 결과를 컬럼명 키의 dict 리스트로 매핑."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in cursor.fetchall()]


def fetchone_dict(cursor) -> dict | None:
    """cursor.fetchone() 결과를 컬럼명 키의 dict로 매핑(없으면 None)."""
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))


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

    with db_cursor() as (_conn, cursor):
        cursor.execute(sql)
    print("Schema applied successfully!")


__all__ = [
    "Any",
    "_get_database_url",
    "apply_schema",
    "db_cursor",
    "fetchall_dicts",
    "fetchone_dict",
    "get_connection",
]
