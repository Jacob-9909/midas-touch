"""synthesize 노드 — 모인 검색 컨텍스트로 최종 답변을 1회 작문한다."""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from ..llm import build_chat_model
from ..prompts import SYSTEM_PROMPT
from ..state import AgentState


def synthesize_node(state: AgentState) -> dict:
    system_parts = [SYSTEM_PROMPT]

    summary = (state.get("profile_summary") or "").strip()
    if summary:
        system_parts.append(summary)

    contexts = state.get("tool_context") or []
    if contexts:
        joined = "\n\n".join(contexts)
        system_parts.append(
            "다음은 이번 질문을 위해 검색된 컨텍스트입니다. 이 컨텍스트에 근거해서만 "
            "수치·법령·세율을 제시하고, 임의 가정을 하지 마십시오.\n\n" + joined
        )

    system_prompt = "\n\n".join(system_parts)

    # 시스템 프롬프트 + 누적 대화 이력으로 1회 작문
    messages = [SystemMessage(content=system_prompt)] + list(state.get("messages") or [])
    reply: AIMessage = build_chat_model().invoke(messages)
    return {"messages": [reply]}
