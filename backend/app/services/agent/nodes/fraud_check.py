"""fraud_check 도구 노드 — 최근 사용자 발화를 사기 휴리스틱으로 검증한다.

휴리스틱 스캔은 오프라인으로 완결되고, 웹 검색 보강(Tavily)은 키가 있을 때만 붙는다.
모든 예외는 안내/실패 문구로 흡수해 그래프를 보호한다.
"""

from __future__ import annotations

from ..state import AgentState
from ..tools import fraud_check
from ._common import latest_user_text


def fraud_check_node(state: AgentState) -> dict:
    try:
        result = fraud_check.invoke({"message_text": latest_user_text(state)})
        return {"tool_context": [f"[fraud_check 결과]\n{result}"]}
    except Exception as exc:
        return {"tool_context": [f"[fraud_check 검증 실패] {exc}"]}
