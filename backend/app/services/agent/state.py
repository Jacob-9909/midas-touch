"""백엔드 에이전트 상태 스키마.

intent 분기 그래프(StateGraph)용 상태. 세션 동안 고정되는 사용자 식별자/프로필 요약에 더해,
턴마다 갱신되는 라우팅 결과(route)와 도구 검색 컨텍스트(tool_context)를 함께 보관한다.
user_uuid는 필수(Q5) — API 레이어에서 보장한다.

NOTE: remaining_steps는 ReAct(create_react_agent) 시절 재귀 한도 관리용 필드였다. 현재 intent
분기 그래프에서는 쓰지 않지만, 체크포인터에 남은 기존 세션과의 호환을 위해 선택 필드로 남겨둔다.
"""

from __future__ import annotations

from typing import Annotated, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def merge_tool_context(left: Optional[List[str]], right: Optional[List[str]]) -> List[str]:
    """도구 노드들의 컨텍스트를 누적하는 리듀서.

    - right is None  → 리셋(빈 리스트). intent 노드가 매 턴 시작 시 이전 턴 컨텍스트를 비운다.
    - right is list  → 기존 컨텍스트에 누적. fan-out된 여러 도구 노드가 같은 superstep에서
      각자 결과를 더해도 순차적으로 병합되어 충돌하지 않는다.
    """
    if right is None:
        return []
    return (left or []) + list(right)


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    remaining_steps: int  # (레거시) ReAct 재귀 한도 관리 필드 — 현 그래프에선 미사용
    user_uuid: str  # 필수: Users DB 프로필 연결 키
    profile_summary: Optional[str]  # 첫 턴에 구성 후 재사용
    route: List[str]  # intent 노드가 고른 필요 도구 이름 목록
    tool_context: Annotated[List[str], merge_tool_context]  # 도구 노드들이 누적한 검색 컨텍스트
