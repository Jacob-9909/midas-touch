"""persona_rag 도구 노드 — 트윈 페르소나 검색을 결정적으로 실행한다."""

from __future__ import annotations

from ..state import AgentState
from ..tools import persona_rag
from ._common import latest_user_text


def persona_rag_node(state: AgentState) -> dict:
    try:
        # 트윈 매칭은 프로필 텍스트가 있으면 더 정확하므로 프로필 요약 + 질문을 함께 넘긴다.
        query = latest_user_text(state)
        summary = (state.get("profile_summary") or "").strip()
        if summary:
            query = f"{summary}\n\n[현재 질문]\n{query}"
        result = persona_rag.invoke({"query": query})
        return {"tool_context": [f"[persona_rag 결과]\n{result}"]}
    except Exception as exc:
        return {"tool_context": [f"[persona_rag 조회 실패] {exc}"]}
