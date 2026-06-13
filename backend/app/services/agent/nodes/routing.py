"""조건부 라우팅(fan-out) — intent 결과에 따라 필요한 도구 노드들만 스케줄한다."""

from __future__ import annotations

from typing import List

from ..state import AgentState
from ._common import TOOL_NODES


def dispatch(state: AgentState) -> List[str]:
    route = [t for t in (state.get("route") or []) if t in TOOL_NODES]
    return route or ["synthesize"]  # 도구 불필요 시 곧장 작문
