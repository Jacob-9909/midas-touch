"""intent 분류 노드.

답변에 필요한 검색 도구 부분집합을 LLM structured-output으로 판정한다(실패 시 키워드 폴백).
이전 턴의 tool_context를 리셋해 턴 간 컨텍스트 오염을 막는다.
"""

from __future__ import annotations

from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import build_chat_model
from ..state import AgentState
from ._common import latest_user_text

_INTENT_PROMPT = """당신은 한국인 자산관리 AI의 라우터입니다. 사용자의 질문을 읽고, 답변에 필요한
검색 도구를 모두 고르십시오(없으면 비워두십시오).

- persona_rag: 또래 벤치마킹 — "나와 비슷한 투자자들은 어떻게 하나", 권장 자산배분 비율, 또래의 종목/섹터 선호. (의뢰인 본인 유형은 이미 알고 있으니, '비교 대상 또래'가 필요할 때만.)
- graph_rag: 세법 조항의 법적 근거, 세율·공제 한도의 '출처/근거', 자산 간 관계.
- tax_and_market_lookup: 특정 자산의 절세 조건이나 현재 시장 수치만 빠르게 확인.

복합 질문이면 필요한 도구를 여러 개 고르십시오. 단순 인사·잡담 등 데이터가 필요 없는 질문이면
아무 도구도 고르지 마십시오.

tax_and_market_lookup을 골랐고 질문이 특정 자산 종류(예: 주식·채권·예금·부동산)에 한정되면,
asset_types에 해당 자산 종류명을 적으십시오(세법 조회를 그 자산으로 좁힘). 자산을 특정하지 않은
일반 질문이면 asset_types는 비워 두십시오(전체 세법 조회)."""


def _keyword_route(text: str) -> List[str]:
    """structured-output 실패 시 키워드 기반 폴백 라우팅. 모호하면 graph_rag로 근거를 확보한다."""
    route: List[str] = []
    if any(k in text for k in ("유사", "또래", "비슷한", "트윈", "페르소나", "자산배분", "포트폴리오", "추천")):
        route.append("persona_rag")
    if any(k in text for k in ("근거", "출처", "법적", "법령", "조항", "관계")):
        route.append("graph_rag")
    if any(k in text for k in ("세율", "세금", "절세", "공제", "환율", "금리", "시세", "시장", "지표")):
        route.append("tax_and_market_lookup")
    return route or ["graph_rag"]


def classify_intent(state: AgentState) -> dict:
    """필요한 도구 목록을 판정하고, 이전 턴의 tool_context를 리셋한다."""
    from typing import Literal

    from pydantic import BaseModel, Field

    class _Route(BaseModel):
        """답변에 필요한 검색 도구 목록과 세법 조회 대상 자산 종류."""

        tools: List[Literal["persona_rag", "graph_rag", "tax_and_market_lookup"]] = Field(
            default_factory=list
        )
        asset_types: List[str] = Field(
            default_factory=list,
            description="tax_and_market_lookup의 세법 조회를 특정 자산(예: 주식, 채권)으로 좁힐 때만 채운다.",
        )

    user_text = latest_user_text(state)
    asset_types: List[str] = []
    try:
        router = build_chat_model(temperature=0.0).with_structured_output(_Route)
        result = router.invoke(
            [SystemMessage(content=_INTENT_PROMPT), HumanMessage(content=user_text)]
        )
        tools = list(dict.fromkeys(result.tools))  # 중복 제거, 순서 유지
        asset_types = list(dict.fromkeys(result.asset_types))
    except Exception:  # noqa: BLE001 - 분류 실패 시 키워드 폴백
        tools = _keyword_route(user_text)

    # tool_context=None → 리듀서가 빈 리스트로 리셋(이전 턴 컨텍스트 제거)
    # tax_asset_types는 매 턴 새로 덮어써 이전 턴 값이 남지 않게 한다.
    return {"route": tools, "tax_asset_types": asset_types, "tool_context": None}
