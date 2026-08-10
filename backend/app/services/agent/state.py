"""백엔드 에이전트 상태 스키마.

intent 분기 그래프(StateGraph)용 상태. 세션 동안 고정되는 사용자 식별자/프로필 요약에 더해,
턴마다 갱신되는 라우팅 결과(route)와 도구 검색 컨텍스트(tool_context)를 함께 보관한다.
user_uuid는 필수(Q5) — API 레이어에서 보장한다.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def merge_tool_context(left: list[str] | None, right: list[str] | None) -> list[str]:
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
    user_uuid: str  # 필수: Users DB 프로필 연결 키
    profile_summary: str | None  # 첫 턴에 구성 후 재사용
    route: list[str]  # intent 노드가 고른 필요 도구 이름 목록
    tax_asset_types: list[str]  # intent가 추출한 세법 조회 대상 자산 종류(없으면 전체)
    ticker: str | None  # intent가 추출한 종목 티커(stock_backtest용; 없으면 None)
    tool_context: Annotated[list[str], merge_tool_context]  # 도구 노드들이 누적한 검색 컨텍스트
