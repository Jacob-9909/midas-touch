"""LangGraph 체크포인터 (PostgresSaver) 구성.

멀티턴 대화 상태를 Postgres에 영속화한다 — MemorySaver와 달리 프로세스 재시작/다중 uvicorn
워커 간에도 세션(thread_id)이 공유된다.

체크포인트 테이블(checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations)은
**Alembic 마이그레이션이 단일 진실원천**이다(DESIGN Q3). 따라서 여기서는 setup()을 호출하지 않는다.
장수(long-lived) 커넥션 풀을 사용한다(from_conn_string은 contextmanager라 서빙에 부적합).
"""

from __future__ import annotations

import os
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@lru_cache(maxsize=1)
def get_checkpointer() -> PostgresSaver:
    """앱 수명 동안 유지되는 PostgresSaver(커넥션 풀 기반)를 1회 생성해 캐시한다."""
    pool = ConnectionPool(
        conninfo=os.environ["DATABASE_URL"],
        max_size=10,
        # PostgresSaver는 autocommit + dict_row 커넥션을 요구한다.
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=True,
    )
    return PostgresSaver(pool)
