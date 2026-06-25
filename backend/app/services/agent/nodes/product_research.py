"""product_research 도구 노드 — 네이버 검색으로 국내 금융상품 금리를 라이브 조회한다.

wealth_advisor의 product_research_agent 이식. midas에는 구조화된 user_profile dict가 없으므로
검색어 꼬리(기간·월납입액) 부착은 생략하고, 카테고리(예금·적금·연금저축·국채 ETF) 병렬 검색만
수행해 tool_context에 누적한다. 네이버 키 미설정 시 명확한 안내 문구를 반환한다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from functools import partial

from ..state import AgentState
from ..tools.web import naver_web_snippets, require_naver_search_keys

# (라벨, 1차 검색어, 폴백 검색어)
_QUERY_SPECS: list[tuple[str, str, str]] = [
    ("예금·정기예금", "정기예금 금리", "정기예금 금리"),
    ("적금·정기적금", "정기적금 금리", "적금 금리"),
    ("보험·연금저축", "연금저축 세액공제 비교", "연금저축 세액공제"),
    ("채권·국채 ETF", "월금액별 국채 ETF 추천", "국채 ETF 추천"),
]


def product_research_node(state: AgentState) -> dict:
    try:
        require_naver_search_keys()
    except ValueError as exc:
        return {"tool_context": [f"[product_research 미수행] {exc}"]}

    with ThreadPoolExecutor(max_workers=len(_QUERY_SPECS)) as pool:
        futures = {
            label: pool.submit(
                partial(naver_web_snippets, primary, 4, fallback_query=fallback)
            )
            for label, primary, fallback in _QUERY_SPECS
        }
        sections = {label: futures[label].result() for label, _, _ in _QUERY_SPECS}

    blocks = [f"### {label}\n{body[:3000]}" for label, body in sections.items()]
    notes = "\n\n".join(blocks)[:20_000]
    return {"tool_context": [f"[product_research·네이버 금융상품]\n{notes}"]}
