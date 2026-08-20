"""graph_rag 도구 노드 — Neo4j 지식그래프 검색을 결정적으로 실행한다."""

from __future__ import annotations

from ..state import AgentState
from ..tools import graph_rag
from ._common import latest_user_text


def graph_rag_node(state: AgentState) -> dict:
    try:
        result = graph_rag.invoke({"query": latest_user_text(state)})
        return {"tool_context": [f"[graph_rag 결과]\n{result}"]}
    except Exception as exc:  # noqa: BLE001
        return {"tool_context": [f"[graph_rag 조회 실패] {exc}"]}
