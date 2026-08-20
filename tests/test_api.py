"""웹 콘솔 신규 API 라우터 통합 테스트 (FastAPI TestClient).

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_api.py -v

localhost Postgres 연결을 전제로 한다. LLM(NVIDIA NIM)이나 장시간 배치(파이프라인/그래프
빌드)는 트리거하지 않고, 조회·검증·에러 응답(400/404)과 스키마 형태만 확인한다.
"""

import io
import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


class TestDashboardRoutes(unittest.TestCase):
    def test_users_list(self) -> None:
        r = client.get("/api/v1/users?limit=5")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("users", body)
        self.assertIsInstance(body["users"], list)

    def test_user_detail_404(self) -> None:
        r = client.get("/api/v1/users/nonexistent-uuid-0000")
        self.assertEqual(r.status_code, 404)

    def test_market_snapshots(self) -> None:
        r = client.get("/api/v1/market/snapshots")
        self.assertEqual(r.status_code, 200)
        self.assertIn("snapshots", r.json())

    def test_tax_rules(self) -> None:
        r = client.get("/api/v1/tax-rules")
        self.assertEqual(r.status_code, 200)
        self.assertIn("tax_rules", r.json())


class TestGraphUploadRoute(unittest.TestCase):
    def test_upload_rejects_bad_extension(self) -> None:
        files = {"file": ("malware.exe", io.BytesIO(b"x"), "application/octet-stream")}
        r = client.post("/api/v1/graph/upload", files=files)
        self.assertEqual(r.status_code, 400)

    def test_ingest_job_missing_file_404(self) -> None:
        r = client.post("/api/v1/graph/ingest/jobs", json={"filename": "__no_such_file__.pdf"})
        self.assertEqual(r.status_code, 404)


class TestChatRoutes(unittest.TestCase):
    def test_sessions_list(self) -> None:
        r = client.get("/api/v1/chat/sessions")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json().get("sessions"), list)

    def test_history_unknown_session_empty(self) -> None:
        r = client.get("/api/v1/chat/history/__no_such_session__")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("messages"), [])

    def test_chat_unknown_user_404(self) -> None:
        r = client.post(
            "/api/v1/chat",
            json={"session_id": "t-404", "message": "안녕", "user_uuid": "nope-0000"},
        )
        self.assertEqual(r.status_code, 404)


class TestGraphRoutes(unittest.TestCase):
    def test_snapshot_shape(self) -> None:
        r = client.get("/api/v1/graph/snapshot?limit=5")
        if r.status_code == 500:
            self.skipTest("Neo4j 연결 불가 — 그래프 스냅샷 테스트 skip")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("nodes", body)
        self.assertIn("links", body)


if __name__ == "__main__":
    unittest.main()
