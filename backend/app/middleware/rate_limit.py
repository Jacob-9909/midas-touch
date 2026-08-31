"""IP별 요청 속도 제한 미들웨어 — 공개 URL(무인증)에서의 스팸·DoS 완화.

배경: 심사 기간 공개 URL은 `AUTH_ENABLED=false`라 `/chat`·`/query`·`/stocks/*` 같은
LLM·연산 비용 엔드포인트가 무인증으로 열린다. 한 방문자가 이를 난사하면 NIM 40RPM 키풀이
그 트래픽으로 차서 심사위원의 정상 요청이 뒤에서 굶는다. 이 미들웨어는 IP별 고정 창(fixed
window)으로 상한을 걸어 그런 고갈을 막는다.

설계: 단일 워커(BACKEND_WORKERS=1) 운영이라 프로세스 내 dict로 충분하다. 두 버킷으로 나눈다 —
일반 API는 넉넉히(사람의 클릭 흐름 방해 없음), LLM·연산 무거운 경로는 더 좁게(키풀 보호).
프록시(Vercel/nginx) 뒤에서는 X-Forwarded-For의 첫 홉을 클라이언트 IP로 본다.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# LLM 호출·무거운 연산·상태 변경이 걸린 경로 — 좁은 상한으로 키풀·자원을 보호한다.
_HEAVY_PREFIXES = (
    "/api/v1/chat",
    "/api/v1/query",
    "/api/v1/graph/upload",
    "/api/v1/graph/ingest",
    "/api/v1/graph/build",
    "/api/v1/tax-rates/extract",
    "/api/v1/stocks/backtest",
    "/api/v1/stocks/grid-search",
    "/api/v1/stocks/analysis",
    "/api/v1/stocks/memory/validate",
)
_CLEANUP_EVERY = 300.0  # 초 — 빈 버킷을 주기적으로 정리해 메모리 상한을 둔다.


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """IP+버킷별 고정 창 카운터. 상한 초과 시 429 + Retry-After.

    한도·창·비활성화는 인스턴스 인자로 받되, 미지정 시 환경변수로 폴백한다
    (`RATE_LIMIT_PER_MIN`·`RATE_LIMIT_HEAVY_PER_MIN`·`RATE_LIMIT_DISABLED`).
    테스트 스위트는 공용 TestClient가 한도에 걸리지 않게 `RATE_LIMIT_DISABLED=1`로 끈다.
    """

    def __init__(
        self,
        app,
        *,
        global_max: int | None = None,
        heavy_max: int | None = None,
        window: float = 60.0,
        disabled: bool | None = None,
    ) -> None:
        super().__init__(app)
        self.global_max = global_max if global_max is not None else int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
        self.heavy_max = heavy_max if heavy_max is not None else int(os.getenv("RATE_LIMIT_HEAVY_PER_MIN", "20"))
        self.window = window
        self.disabled = disabled if disabled is not None else _env_flag("RATE_LIMIT_DISABLED")
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._last_cleanup = time.monotonic()

    @staticmethod
    def _client_ip(request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < _CLEANUP_EVERY:
            return
        cutoff = now - self.window
        for key in [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]:
            del self._hits[key]
        self._last_cleanup = now

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 비활성화·프리플라이트·헬스체크·비 API 경로는 제한 대상 아님.
        if (
            self.disabled
            or request.method == "OPTIONS"
            or not path.startswith("/api/")
            or path.endswith("/health")
        ):
            return await call_next(request)

        heavy = path.startswith(_HEAVY_PREFIXES)
        limit = self.heavy_max if heavy else self.global_max
        ip = self._client_ip(request)
        now = time.monotonic()
        self._cleanup(now)

        key = (ip, "heavy" if heavy else "global")
        dq = self._hits[key]
        cutoff = now - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()

        if len(dq) >= limit:
            retry_after = int(self.window - (now - dq[0])) + 1
            logger.warning(
                "rate limit 초과 — ip=%s bucket=%s path=%s (%d/%ds)",
                ip, key[1], path, limit, int(self.window),
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."},
                headers={"Retry-After": str(retry_after)},
            )

        dq.append(now)
        return await call_next(request)
