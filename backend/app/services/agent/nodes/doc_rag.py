"""doc_rag 도구 노드 — 국세청 세법 해설서 원문 검색을 결정적으로 실행한다."""

from __future__ import annotations

from ..state import AgentState
from ..tools import doc_rag
from ._common import latest_user_text


def doc_rag_node(state: AgentState) -> dict:
    try:
        result = doc_rag.invoke({"query": latest_user_text(state)})
        return {"tool_context": [f"[doc_rag 결과]\n{result}"]}
    except Exception as exc:
        return {"tool_context": [f"[doc_rag 조회 실패] {exc}"]}
