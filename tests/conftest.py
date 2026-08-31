"""pytest 공용 설정.

이 저장소의 test_agent.py / test_api.py 일부는 localhost Postgres·Neo4j 연결을
전제로 하는 통합 테스트다. DB가 없으면 예외로 죽는 대신 깔끔히 skip 하도록 가드한다.
DB가 살아 있으면(로컬/CI에 인프라 준비된 환경) 평소대로 전부 실행된다.
"""

from __future__ import annotations

import logging
import os

try:
    import truststore
    truststore.inject_into_ssl()
except Exception as exc:
    # truststore가 없거나 주입에 실패해도 테스트는 돈다(certifi 번들로 폴백). 다만 사내망 등
    # 시스템 인증서가 필요한 환경에선 이후 TLS 실패의 원인이 되므로 조용히 넘기지 않는다.
    logging.getLogger(__name__).debug("truststore 미적용 — 시스템 인증서 대신 기본 번들 사용: %s", exc)

import pytest
from dotenv import load_dotenv

# graph_rag / knowledge_graph 빌더는 NIM_GENERATION_MODEL 을 필수로 읽는다(하드코딩 기본값 금지 정책).
# 로컬은 .env 로 채워지지만 CI 엔 없어서 죽는다. 실제 값(.env/시스템 환경변수)을 우선하고,
# 없을 때만 테스트용 placeholder 를 주입한다.
load_dotenv()
os.environ.setdefault("NIM_GENERATION_MODEL", "ci-test-placeholder")

# 공용 TestClient가 단일 IP로 heavy 경로를 다수 호출하면 속도 제한(20/분)에 걸려
# 무관한 테스트가 429로 깨진다. 스위트 전체는 제한을 끄고, 전용 테스트만 자체 앱에서 켠다.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

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
