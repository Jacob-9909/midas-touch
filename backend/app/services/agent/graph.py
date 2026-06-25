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
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from .nodes import (
    TOOL_NODES,
    cheongyak_lookup_node,
    classify_intent,
    dispatch,
    graph_rag_node,
    news_research_node,
    nts_law_research_node,
    persona_rag_node,
    product_research_node,
    stock_backtest_node,
    stock_quick_node,
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
    # 라이브 웹 리서치 도구 노드(wealth_advisor 이식)
    builder.add_node("product_research", product_research_node)
    builder.add_node("news_research", news_research_node)
    builder.add_node("nts_law_research", nts_law_research_node)
    # 대화형 액션 노드(주식 백테스트·기술지표 분석·청약 조회)
    builder.add_node("stock_backtest", stock_backtest_node)
    builder.add_node("stock_quick", stock_quick_node)
    builder.add_node("cheongyak_lookup", cheongyak_lookup_node)
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
