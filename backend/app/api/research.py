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
# 원문 소스가 영문이라 검색어는 영문을 유지하고(리콜이 좋다), 노출 문구는 아래 _ko_brief가 한국어로 접는다.
_RATE_SPECS: list[tuple[str, str]] = [
    ("미국", "Federal Reserve Fed funds target rate benchmark interest rate current 미국 기준금리"),
    ("일본", "Bank of Japan BOJ policy interest rate yield curve control latest 일본 기준금리"),
    ("한국", "Bank of Korea BOK base rate policy rate 한국은행 기준금리 최신"),
]

_CACHE_TTL = 3600
_cache: dict[str, tuple[float, dict]] = {}


# 라벨별로 DB(market_snapshots)에 이미 있는 확정 금리. Tavily가 수치를 못 물어오는 일이 잦아
# ("검색 결과에 수치가 제시되지 않아…" 응답) 우리가 이미 적재해 둔 값을 프롬프트에 먼저 박는다.
# ponytail: 일본은 BOK/FRED 어느 쪽에도 없어 매핑이 비어 있다 — 그때는 검색 결과만으로 요약한다.
_RATE_KEYS: dict[str, list[tuple[str, str]]] = {
    "미국": [("US_FED_RATE", "연방기금금리"), ("US_10Y_BOND", "미 국채 10년"), ("US_2Y_BOND", "미 국채 2년")],
    "한국": [("KR_BASE_RATE", "한국은행 기준금리"), ("KR_CD_3M", "CD 91일")],
    "일본": [],
}


def _known_rates(label: str) -> str:
    """market_snapshots의 최신 확정 수치를 '이름 값% (기준일)' 줄로 만든다. 없으면 빈 문자열."""
    keys = _RATE_KEYS.get(label) or []
    if not keys:
        return ""
    try:
        from shared.database.connector import get_latest_market_snapshots

        latest = {
            r["sub_key"]: r
            for r in get_latest_market_snapshots()
            if r.get("data_type") == "interest_rate"
        }
        lines = [
            f"- {ko}: {latest[k]['value']:g}{latest[k].get('unit') or '%'} ({latest[k]['snapshot_date']} 기준)"
            for k, ko in keys
            if k in latest
        ]
        return "\n".join(lines)
    except Exception:  # noqa: BLE001 — DB가 없어도 검색 결과만으로 요약한다
        return ""


def _ko_brief(label: str, body: str) -> str:
    """Tavily 원문(대부분 영문)을 한국어 요약으로 접는다. LLM 실패 시 원문을 그대로 돌려준다.

    ponytail: 섹션당 LLM 1회(총 3회, 병렬). 1시간 캐시가 있어 재호출 비용은 거의 없다.
    """
    rates = _known_rates(label)
    if not body.strip() and not rates:
        return body
    try:
        from backend.app.services.agent.llm import build_chat_model

        system = (
            "너는 한국 투자자에게 브리핑하는 금융 리서치 애널리스트다. "
            "출력은 언제나 한국어 평문이며, 원문이 영어여도 영어 문장을 그대로 옮기지 않는다."
        )
        human = (
            f"아래 자료에 근거해 '{label} 기준금리' 브리핑을 한국어 3문장 이내로 작성하라.\n"
            "[확정 수치]는 우리 DB의 실측값이니 그대로 쓰고, [검색 결과]는 최근 방향·배경에만 참고하라.\n"
            "[확정 수치]가 있으면 '수치를 알 수 없다'는 식으로 답하지 마라.\n"
            "머리말·목록·마크다운 없이 요약문만 출력하라.\n\n"
            f"[확정 수치]\n{rates or '(없음)'}\n\n"
            f"[검색 결과]\n{body[:4000]}"
        )
        msg = build_chat_model(temperature=0.2, max_tokens=500).invoke(
            [("system", system), ("human", human)]
        )
        return str(msg.content).strip() or body
    except Exception:  # noqa: BLE001 — LLM이 죽어도 위젯은 원문으로 뜬다
        return body


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
        return {"label": label, "body": _ko_brief(label, tavily_search_body(tool, query))[:2000]}

    with ThreadPoolExecutor(max_workers=len(_RATE_SPECS)) as pool:
        sections = list(pool.map(one, _RATE_SPECS))

    result = {"available": True, "message": "", "sections": sections}
    _cache["rate"] = (now, result)
    return result
