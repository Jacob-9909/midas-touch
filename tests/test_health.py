"""/health 가 실제 상태를 반영하는지 — DB 없이 분기만 검증한다.

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_health.py -v

이 엔드포인트는 두 가지로 거짓말을 하고 있었다:
  1) `status` 가 무조건 "healthy" 라 DB 가 죽어도 초록이었다.
  2) `neo4j` 필드가 NEO4J_URL(설정값)이라 Neo4j 가 죽어도 멀쩡해 보였다.
배포 스크립트(vm.sh·vm-autodeploy.sh)가 이 응답으로 롤백 여부를 판단하므로
거짓 초록은 곧 "깨진 배포를 성공으로 오해"가 된다. 그래서 회귀 테스트를 남긴다.
"""

import os
import sys
import unittest
from unittest.mock import patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)

_NEO4J = "shared.database.neo4j_client.get_driver"
_PG = "backend.app.main.get_connection"


class HealthTest(unittest.TestCase):
    def test_all_up_is_healthy(self):
        with patch(_PG), patch(_NEO4J):
            body = client.get("/health").json()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["database"], "healthy")
        self.assertEqual(body["neo4j"], "healthy")

    def test_postgres_down_is_degraded(self):
        with patch(_PG, side_effect=RuntimeError("connection refused")), patch(_NEO4J):
            body = client.get("/health").json()
        self.assertEqual(body["status"], "degraded")
        self.assertIn("unhealthy", body["database"])
        self.assertEqual(body["neo4j"], "healthy")

    def test_neo4j_down_is_degraded(self):
        # 이게 예전에 안 잡히던 경우다 — Postgres 만 보고 초록을 줬다.
        with patch(_PG), patch(_NEO4J, side_effect=RuntimeError("bolt unreachable")):
            body = client.get("/health").json()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["database"], "healthy")
        self.assertIn("unhealthy", body["neo4j"])

    def test_still_returns_200_when_degraded(self):
        # 200 을 유지한다. 앞단(Caddy)이나 모니터링이 상태코드로 라우팅하고 있을 수 있어
        # 본문만 정직하게 바꾼다 — 상태코드 변경은 별도 판단거리다.
        with patch(_PG, side_effect=RuntimeError("down")), patch(_NEO4J, side_effect=RuntimeError("down")):
            self.assertEqual(client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
