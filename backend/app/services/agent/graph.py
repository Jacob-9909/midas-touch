"""백엔드 에이전트 그래프 조립 (배선 전용).

현재 구성: **intent 분기 그래프 (StateGraph)**.
  START → intent(필요 도구 분류) → 필요한 도구 노드들만 fan-out 실행 → synthesize(최종 작문) → END

도구 선택을 LLM ReAct 루프에 맡기는 대신, 앞단 intent 분류기가 "어떤 도구를 쓸지"를 한 번에
판정하고, 해당 도구 노드만 결정적으로 실행한다. 복합 질문은 여러 도구를 동시에(fan-out) 태워
컨텍스트를 누적한 뒤 synthesize 노드가 한 번의 LLM 호출로 답변을 작성한다.

각 노드의 구현은 nodes/ 패키지에 파일 단위로 분리돼 있고, 이 파일은 노드를 import해
**연결(배선)만** 한다. 노드 수정은 nodes/ 안에서, 그래프 토폴로지 변경은 여기서 한다.

멀티턴 영속화는 체크포인터(PostgresSaver)로 처리한다. 체크포인트 테이블은 Alembic으로 관리하므로
setup()은 호출하지 않는다(DESIGN §6, Q3).

----------------------------------------------------------------------------------------------------
NOTE: 이전 구성(ReAct, langchain.agents.create_agent)은 아래 [LEGACY] 블록에 주석으로 보존한다.
----------------------------------------------------------------------------------------------------
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from .nodes import (
    TOOL_NODES,
    classify_intent,
    dispatch,
    graph_rag_node,
    persona_rag_node,
    synthesize_node,
    tax_lookup_node,
)
from .state import AgentState


def build_agent(checkpointer):
    """intent 분기 StateGraph를 구성해 컴파일한다."""
    builder = StateGraph(AgentState)

    builder.add_node("intent", classify_intent)
    builder.add_node("persona_rag", persona_rag_node)
    builder.add_node("graph_rag", graph_rag_node)
    builder.add_node("tax_and_market_lookup", tax_lookup_node)
    builder.add_node("synthesize", synthesize_node)

    builder.add_edge(START, "intent")
    # intent → 필요한 도구 노드들(fan-out) 또는 곧장 synthesize
    builder.add_conditional_edges(
        "intent",
        dispatch,
        [*TOOL_NODES, "synthesize"],
    )
    # 각 도구 노드 → synthesize (여러 도구가 떴으면 모두 끝난 뒤 synthesize가 1회 실행됨)
    for tool_node in TOOL_NODES:
        builder.add_edge(tool_node, "synthesize")
    builder.add_edge("synthesize", END)

    return builder.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_agent():
    """컴파일된 그래프(CompiledStateGraph)를 1회 생성 후 캐시한다.

    체크포인터는 PostgresSaver(영속·다중워커 공유)를 사용한다. 체크포인트 테이블은 Alembic으로
    관리하므로 setup()은 호출하지 않는다(DESIGN Q3).
    """
    from .checkpointer import get_checkpointer

    return build_agent(checkpointer=get_checkpointer())


# ══════════════════════════════════════════════════════════════════════════════════════════════
# [LEGACY] 이전 구성: ReAct agent (langchain.agents.create_agent)
# ──────────────────────────────────────────────────────────────────────────────────────────────
# 도구 선택을 LLM에 위임하는 prebuilt ReAct 루프(agent ↔ tools). multi-hop/복합 도구 조합에
# 강하지만, 도구 호출마다 LLM 라운드가 추가되어 지연·비용이 누적된다. 위 intent 분기로 대체했다.
# 되돌리려면 위 intent 배선을 주석 처리하고 아래를 복구하면 된다.
# ══════════════════════════════════════════════════════════════════════════════════════════════
#
# from langchain.agents import create_agent
# from langchain.agents.middleware import dynamic_prompt
# from .llm import build_chat_model
# from .prompts import SYSTEM_PROMPT
# from .tools import ALL_TOOLS
#
#
# @dynamic_prompt
# def _prompt_with_profile(request) -> str:
#     """기본 시스템 프롬프트에 세션 사용자 프로필을 동적으로 합쳐 system prompt로 사용한다."""
#     state = getattr(request, "state", {}) or {}
#     summary = (state.get("profile_summary") or "").strip()
#     if summary:
#         return f"{SYSTEM_PROMPT}\n\n{summary}"
#     return SYSTEM_PROMPT
#
#
# def build_agent(checkpointer):
#     """주어진 체크포인터로 ReAct 에이전트를 구성한다."""
#     return create_agent(
#         model=build_chat_model(),
#         tools=ALL_TOOLS,
#         middleware=[_prompt_with_profile],
#         state_schema=AgentState,
#         checkpointer=checkpointer,
#     )
