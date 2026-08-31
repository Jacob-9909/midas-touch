"""RateLimitMiddleware 단위 검증 — 자체 앱에 낮은 한도로 걸어 429/Retry-After를 확인한다.

스위트 전체는 conftest에서 RATE_LIMIT_DISABLED=1로 꺼두므로, 여기선 미들웨어를 명시적으로
disabled=False + 낮은 한도로 인스턴스화해 격리 검증한다.
"""

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.middleware.rate_limit import RateLimitMiddleware


def _app(*, global_max: int, heavy_max: int) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware, global_max=global_max, heavy_max=heavy_max, disabled=False
    )

    @app.get("/api/v1/ping")
    def ping() -> dict:
        return {"ok": True}

    @app.post("/api/v1/chat")  # heavy prefix
    def chat() -> dict:
        return {"ok": True}

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"ok": True}

    return app


class TestRateLimit(unittest.TestCase):
    def test_global_bucket_trips_after_limit(self) -> None:
        client = TestClient(_app(global_max=3, heavy_max=2))
        for _ in range(3):
            self.assertEqual(client.get("/api/v1/ping").status_code, 200)
        blocked = client.get("/api/v1/ping")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked.headers)

    def test_heavy_bucket_is_stricter(self) -> None:
        client = TestClient(_app(global_max=100, heavy_max=2))
        self.assertEqual(client.post("/api/v1/chat").status_code, 200)
        self.assertEqual(client.post("/api/v1/chat").status_code, 200)
        self.assertEqual(client.post("/api/v1/chat").status_code, 429)

    def test_health_is_exempt(self) -> None:
        client = TestClient(_app(global_max=1, heavy_max=1))
        for _ in range(5):
            self.assertEqual(client.get("/api/v1/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
