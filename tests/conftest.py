"""pytest 공용 설정.

이 저장소의 test_agent.py / test_api.py 일부는 localhost Postgres·Neo4j 연결을
전제로 하는 통합 테스트다. DB가 없으면 예외로 죽는 대신 깔끔히 skip 하도록 가드한다.
DB가 살아 있으면(로컬/CI에 인프라 준비된 환경) 평소대로 전부 실행된다.
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

# pipelines.embedding.config 는 import 시점에 NIM_GENERATION_MODEL 을 필수로 요구한다
# (하드코딩 기본값 금지 정책). 로컬은 .env 로 채워지지만 CI 엔 없어서 test 수집이 죽는다.
# 실제 값(.env/시스템 환경변수)을 우선하고, 없을 때만 테스트용 placeholder 를 주입한다.
load_dotenv()
os.environ.setdefault("NIM_GENERATION_MODEL", "ci-test-placeholder")

# DB 연결을 실제로 필요로 하는 통합 테스트 클래스.
# ponytail: 클래스명이 곧 스킵 스위치다. 클래스 rename 시 여기도 갱신.
_DB_DEPENDENT_CLASSES = {
    "TestDatabaseHelpers",
    "TestAgentTools",
    "TestAgentEndToEnd",
    "TestDashboardRoutes",
    "TestChatRoutes",
    "TestGraphRoutes",
}


def _postgres_reachable() -> bool:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return False
    try:
        import psycopg2

        conn = psycopg2.connect(dsn, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config, items) -> None:
    if _postgres_reachable():
        return
    skip = pytest.mark.skip(
        reason="Postgres 미가용 — 통합 테스트 skip (DATABASE_URL 설정 시 실행)"
    )
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is not None and cls.__name__ in _DB_DEPENDENT_CLASSES:
            item.add_marker(skip)
