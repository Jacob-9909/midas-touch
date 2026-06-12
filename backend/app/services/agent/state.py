"""백엔드 에이전트 상태 스키마.

create_react_agent의 기본 AgentState(messages + remaining_steps)를 확장해, 세션 동안 고정되는
사용자 식별자/프로필 요약을 함께 보관한다. user_uuid는 필수(Q5) — API 레이어에서 보장한다.
"""

from __future__ import annotations

from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    remaining_steps: int  # create_react_agent 요구 필드 (재귀 한도 관리)
    user_uuid: str  # 필수: Users DB 프로필 연결 키
    profile_summary: Optional[str]  # 첫 턴에 구성 후 재사용
