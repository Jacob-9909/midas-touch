"""tax_and_market_lookup 도구 노드 — 세법/시장 지표 조회를 결정적으로 실행한다."""

from __future__ import annotations

from ..state import AgentState
from ..tools import tax_and_market_lookup
from ._common import latest_user_text

# 거시경제 지표가 실제로 필요함을 시사하는 토큰.
_MARKET_TOKENS = ("환율", "금리", "시세", "시장", "지표", "거시", "물가", "유가", "달러", "원화")


def _needs_market(user_text: str, asset_types: list[str]) -> bool:
    """시장지표 섹션 포함 여부. 질문에 거시 키워드가 있거나, 자산을 특정하지 않은 일반 질문이면 포함."""
    if any(tok in user_text for tok in _MARKET_TOKENS):
        return True
    # 자산 한정 세법 질문(asset_types 존재)이면 거시 지표 전량 덤프를 생략한다.
    return not asset_types


def tax_lookup_node(state: AgentState) -> dict:
    # intent가 자산 종류를 특정했으면 그 자산으로 세법 조회를 좁힌다(없으면 전체 조회).
    asset_types = state.get("tax_asset_types") or []
    include_market = _needs_market(latest_user_text(state), asset_types)
    result = tax_and_market_lookup.invoke(
        {"asset_types": asset_types, "include_market": include_market}
    )
    return {"tool_context": [f"[tax_and_market_lookup 결과]\n{result}"]}
