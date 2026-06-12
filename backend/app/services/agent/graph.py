"""백엔드 에이전트 그래프 조립 (langchain.agents.create_agent).

ReAct 루프(agent ↔ tools)를 prebuilt로 구성한다. 멀티턴 영속화는 체크포인터로 처리하며,
개발 단계에서는 MemorySaver를 쓴다. 운영 전환 시 PostgresSaver로 교체하고 체크포인트
테이블은 Alembic으로 관리한다(DESIGN §6, Q3).

NOTE: LangGraph V1.0에서 create_react_agent는 langchain.agents.create_agent로 이전됨
(create_react_agent는 V2.0에서 제거 예정). prompt → system_prompt로 변경, version 파라미터 제거.
"""

from __future__ import annotations

from functools import lru_cache

from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt

from .llm import build_chat_model
from .prompts import SYSTEM_PROMPT
from .state import AgentState
from .tools import ALL_TOOLS


@dynamic_prompt
def _prompt_with_profile(request) -> str:
    """기본 시스템 프롬프트에 세션 사용자 프로필을 동적으로 합쳐 system prompt로 사용한다.

    프로필은 state.profile_summary(첫 턴에 API 레이어가 채움)에서 읽는다 — 가짜 user 메시지로
    주입하지 않으므로 대화 히스토리가 오염되지 않는다.
    """
    state = getattr(request, "state", {}) or {}
    summary = (state.get("profile_summary") or "").strip()
    if summary:
        return f"{SYSTEM_PROMPT}\n\n{summary}"
    return SYSTEM_PROMPT


@lru_cache(maxsize=1)
def get_agent():
    """컴파일된 에이전트(CompiledStateGraph)를 1회 생성 후 캐시한다.

    체크포인터는 PostgresSaver(영속·다중워커 공유)를 사용한다. 체크포인트 테이블은 Alembic으로
    관리하므로 setup()은 호출하지 않는다(DESIGN Q3).
    """
    from .checkpointer import get_checkpointer

    return build_agent(checkpointer=get_checkpointer())


def build_agent(checkpointer):
    """주어진 체크포인터로 에이전트를 구성한다."""
    return create_agent(
        model=build_chat_model(),
        tools=ALL_TOOLS,
        middleware=[_prompt_with_profile],
        state_schema=AgentState,
        checkpointer=checkpointer,
    )
