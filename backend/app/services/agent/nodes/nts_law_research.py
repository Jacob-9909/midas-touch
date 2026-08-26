"""nts_law_research 도구 노드 — 국세청 법령해석(ntsCgmExpc)을 라이브 검색한다.

wealth_advisor의 tax_research_agent 이식. wealth는 Gemini가 프로필에서 뽑아둔
nts_law_api_queries 를 썼지만, midas에는 그 필드가 없으므로 **사용자 질문 텍스트에서 세법 키워드를
결정적으로 추출**해 검색어로 쓴다(추출 0건이면 폴백). 결과는 tool_context에 누적한다.
LAW_GO_KR_OC 미설정 시 명확한 안내 문구를 반환한다.

midas에 이미 있는 graph_rag/tax_and_market_lookup이 '내부 DB 근거'라면, 이 노드는 '국세청 포털의
라이브 유권해석 목록'을 보완적으로 더한다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ..state import AgentState
from ..tools.web import (
    nts_cgm_search_once,
    require_law_go_kr_oc,
    resolve_nts_law_search_specs,
)
from ._common import latest_user_text

# 질문 텍스트에 등장하면 검색어로 쓸 세법 용어(포털 검색에 잘 걸리는 표준 용어).
_TAX_TERMS: tuple[str, ...] = (
    "연금저축", "퇴직연금", "IRP", "개인형퇴직연금", "ISA",
    "연말정산", "세액공제", "소득공제", "비과세",
    "양도소득세", "종합소득세", "근로소득", "금융소득", "배당소득세", "이자소득",
    "부가가치세", "상속세", "증여세", "취득세", "재산세", "종합부동산세",
    "절세", "원천징수", "기타소득",
)
# 자산 종류 → 관련 세법 검색어 매핑(intent가 tax_asset_types를 채웠을 때 보강).
_ASSET_TO_QUERY: dict[str, str] = {
    "주식": "양도소득세",
    "채권": "이자소득",
    "예금": "금융소득",
    "적금": "금융소득",
    "부동산": "양도소득세",
    "펀드": "배당소득세",
}


def _derive_queries(state: AgentState) -> list[str]:
    """질문 텍스트 + intent가 추출한 자산종류에서 국세청 검색 키워드를 도출한다(중복 제거)."""
    text = latest_user_text(state)
    queries: list[str] = [term for term in _TAX_TERMS if term in text]
    for asset in state.get("tax_asset_types") or []:
        mapped = _ASSET_TO_QUERY.get(str(asset).strip())
        if mapped:
            queries.append(mapped)
    # 순서 유지 중복 제거
    return list(dict.fromkeys(queries))


def nts_law_research_node(state: AgentState) -> dict:
    try:
        require_law_go_kr_oc()
    except ValueError as exc:
        return {"tool_context": [f"[nts_law_research 미수행] {exc}"]}

    try:
        # 도출된 키워드를 wealth의 spec 리졸버에 그대로 전달(비면 내부 폴백 사용).
        specs = resolve_nts_law_search_specs({"nts_law_api_queries": _derive_queries(state)})

        def one(section: tuple[str, str]) -> str:
            label, query = section
            return f"### {label}: {query}\n{nts_cgm_search_once(query, display=8)}"

        with ThreadPoolExecutor(max_workers=max(1, len(specs))) as pool:
            sections = list(pool.map(one, specs))

        header = "국세청 법령해석 '목록' 스니펫(유권해석 아님). 세액·요건은 국세청·홈택스 확인."
        notes = (header + "\n\n" + "\n\n".join(sections))[:18_000]
    except Exception as exc:
        # chromium 미설치 등 라이브 검색 실패가 그래프 superstep까지 번지지 않게 흡수한다.
        return {
            "tool_context": [f"[nts_law_research 미수행] 국세청 법령해석 검색 실패: {exc}"]
        }

    return {"tool_context": [f"[nts_law_research·국세청 법령해석]\n{notes}"]}
