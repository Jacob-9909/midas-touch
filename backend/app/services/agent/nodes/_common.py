"""노드 공용 헬퍼/상수."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from ..state import AgentState

# 도구 이름 == 그래프 노드 이름 (추적을 쉽게 하려고 동일하게 맞춘다).
TOOL_NODES = ("persona_rag", "graph_rag", "tax_and_market_lookup")


def latest_user_text(state: AgentState) -> str:
    """state.messages에서 가장 최근 사용자(HumanMessage) 텍스트를 꺼낸다."""
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    # 폴백: dict 형태(직렬화된 입력) 등도 처리
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content:
            return content if isinstance(content, str) else str(content)
    return ""
