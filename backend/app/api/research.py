"""라이브 리서치 라우터 — 대시보드 시장 브리핑 등 비대화형(non-chat) 리서치 노출.

에이전트 fan-out과 별개로, 대시보드 위젯이 직접 호출할 수 있는 온디맨드 엔드포인트.
`tools/web`의 Tavily 래퍼를 재사용하며, 비용/지연을 줄이려 1시간 TTL 캐시를 둔다.
TAVILY_API_KEY 미설정 시 200 + {available: false}로 graceful 응답(앱 안 죽음).
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from backend.app.services.agent.tools.web import (
    require_tavily_api_key,
    tavily_search_body,
)

router = APIRouter(prefix="/api/v1/research", tags=["research"])

# (라벨, 검색어) — 미·일·한 기준금리 맥락(news_research 노드와 동일 주제).
_RATE_SPECS: list[tuple[str, str]] = [
    ("미국", "Federal Reserve Fed funds target rate benchmark interest rate current"),
    ("일본", "Bank of Japan BOJ policy interest rate yield curve control latest"),
    ("한국", "Bank of Korea BOK base rate policy rate 한국은행 기준금리 최신"),
]

_CACHE_TTL = 3600
_cache: dict[str, tuple[float, dict]] = {}


@router.get("/rate-briefing")
def rate_briefing() -> dict:
    """미·일·한 기준금리 동향 라이브 브리핑(온디맨드). 키 없으면 available=false."""
    try:
        require_tavily_api_key()
    except ValueError as exc:
        return {"available": False, "message": str(exc), "sections": []}

    now = time.time()
    cached = _cache.get("rate")
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    from concurrent.futures import ThreadPoolExecutor

    from langchain_tavily import TavilySearch

    tool = TavilySearch(max_results=4, topic="finance", search_depth="basic", include_answer=True)

    def one(spec: tuple[str, str]) -> dict:
        label, query = spec
        return {"label": label, "body": tavily_search_body(tool, query)[:2000]}

    with ThreadPoolExecutor(max_workers=len(_RATE_SPECS)) as pool:
        sections = list(pool.map(one, _RATE_SPECS))

    result = {"available": True, "message": "", "sections": sections}
    _cache["rate"] = (now, result)
    return result
