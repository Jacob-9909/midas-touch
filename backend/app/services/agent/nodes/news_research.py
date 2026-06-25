"""news_research 도구 노드 — Tavily로 미·일·한 기준금리/거시 동향을 라이브 조회한다.

wealth_advisor의 news_research_agent 이식. midas는 결과를 tool_context에 누적해 synthesize가
1회 작문하므로, macro_market_notes 대신 tool_context 리스트를 반환한다. TAVILY_API_KEY 미설정 시
예외를 잡아 명확한 안내 문구를 넣어 그래프가 죽지 않게 한다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..state import AgentState
from ..tools.web import require_tavily_api_key, tavily_search_body

# (라벨, 검색어) — 미·일·한 기준금리 맥락.
_SPECS: list[tuple[str, str]] = [
    ("미국", "Federal Reserve Fed funds target rate benchmark interest rate current"),
    ("일본", "Bank of Japan BOJ policy interest rate yield curve control latest"),
    ("한국", "Bank of Korea BOK base rate policy rate 한국은행 기준금리 최신"),
]


def news_research_node(state: AgentState) -> dict:
    try:
        require_tavily_api_key()
    except ValueError as exc:
        return {"tool_context": [f"[news_research 미수행] {exc}"]}

    from langchain_tavily import TavilySearch

    tool = TavilySearch(
        max_results=4,
        topic="finance",
        search_depth="basic",
        include_answer=True,
    )

    def one(section: tuple[str, str]) -> str:
        label, query = section
        return f"### {label}\n{tavily_search_body(tool, query)}"

    with ThreadPoolExecutor(max_workers=len(_SPECS)) as pool:
        sections = list(pool.map(one, _SPECS))

    notes = "\n\n".join(sections)[:16_000]
    return {"tool_context": [f"[news_research·Tavily 금리 동향]\n{notes}"]}
