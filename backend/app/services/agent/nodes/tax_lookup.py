"""tax_and_market_lookup 도구 노드 — 세법/시장 지표 조회를 결정적으로 실행한다."""

from __future__ import annotations

from ..state import AgentState
from ..tools import tax_and_market_lookup


def tax_lookup_node(state: AgentState) -> dict:
    result = tax_and_market_lookup.invoke({})  # asset_type 생략 → 전체 조회
    return {"tool_context": [f"[tax_and_market_lookup 결과]\n{result}"]}
