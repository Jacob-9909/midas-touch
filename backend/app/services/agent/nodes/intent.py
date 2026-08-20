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
- product_research: 국내 금융상품의 '현재 금리/조건'을 라이브로(네이버 검색) — 정기예금·적금·연금저축·국채 ETF 등 실시간 상품 비교가 필요할 때.
- news_research: 미국·일본·한국 기준금리/거시 금리 '동향'을 라이브로(웹 검색) — 최신 금리 흐름·정책 맥락이 필요할 때.
- nts_law_research: 국세청 법령해석(유권해석) 목록을 포털에서 라이브로 — 특정 세목의 최신 해석 사례·근거가 필요할 때.
- stock_backtest: 사용자가 특정 종목의 과거 성과/백테스트를 물을 때(예: "애플 백테스트 해줘", "테슬라 1년 수익률"). 이때 ticker도 함께 채우십시오.
- stock_quick: 사용자가 특정 종목의 '현재' 기술적 지표/상태를 물을 때(예: "엔비디아 지금 어때?", "삼성전자 RSI 알려줘", "테슬라 기술적 분석"). 과거 시뮬레이션이 아니라 현 시점 지표(RSI·MACD·이동평균 등) 진단. 이때 ticker도 함께 채우십시오.
- cheongyak_lookup: 최근/예정 청약(분양) 공고를 물을 때(예: "요즘 청약 뭐 있어?", "분양 공고 알려줘").

복합 질문이면 필요한 도구를 여러 개 고르십시오. 단순 인사·잡담 등 데이터가 필요 없는 질문이면
아무 도구도 고르지 마십시오. 내부 DB(persona_rag/graph_rag/tax_and_market_lookup)로 충분하면
라이브 도구(product_research/news_research/nts_law_research/stock_backtest/stock_quick/cheongyak_lookup)는 굳이 고르지 마십시오.

tax_and_market_lookup을 골랐고 질문이 특정 자산 종류(예: 주식·채권·예금·부동산)에 한정되면,
asset_types에 해당 자산 종류명을 적으십시오(세법 조회를 그 자산으로 좁힘). 자산을 특정하지 않은
일반 질문이면 asset_types는 비워 두십시오(전체 세법 조회)."""


# 데이터 검색이 필요함을 시사하는 토큰(짧은 메시지라도 이게 있으면 잡담이 아니다).
_DATA_TOKENS = (
    "유사", "또래", "비슷한", "트윈", "페르소나", "자산배분", "포트폴리오", "추천",
    "근거", "출처", "법적", "법령", "조항", "관계",
    "세율", "세금", "절세", "공제", "환율", "금리", "시세", "시장", "지표",
    "투자", "자산", "주식", "채권", "부동산", "예금", "수익", "전략", "얼마", "어떻게",
)
# 데이터가 필요 없는 인사·잡담 토큰.
_SMALLTALK_TOKENS = (
    "안녕", "반가", "반갑", "고마", "감사", "수고", "하이", "ㅎㅇ", "잘 지내", "좋은 아침",
    "hello", "hi", "thanks",
)


def _is_smalltalk(text: str) -> bool:
    """짧은 순수 인사·잡담이면 True. 보수적으로 판정한다(애매하면 False → 정상 분류).

    분류 LLM 호출을 아끼기 위한 short-circuit용. 데이터 토큰이나 물음표가 있으면 잡담이 아니다.
    """
    stripped = text.strip()
    if not stripped or len(stripped) > 15:
        return False
    if "?" in stripped or "？" in stripped:
        return False
    lowered = stripped.lower()
    if any(tok in lowered for tok in _DATA_TOKENS):
        return False
    return any(tok in lowered for tok in _SMALLTALK_TOKENS)


def _keyword_route(text: str) -> List[str]:
    """structured-output 실패 시 키워드 기반 폴백 라우팅. 모호하면 graph_rag로 근거를 확보한다."""
    route: List[str] = []
    if any(k in text for k in ("유사", "또래", "비슷한", "트윈", "페르소나", "자산배분", "포트폴리오", "추천")):
        route.append("persona_rag")
    if any(k in text for k in ("근거", "출처", "법적", "법령", "조항", "관계")):
        route.append("graph_rag")
    if any(k in text for k in ("세율", "세금", "절세", "공제", "환율", "금리", "시세", "시장", "지표")):
        route.append("tax_and_market_lookup")
    # 라이브 웹 리서치(현재 금리/상품·금리 동향·국세청 해석)
    if any(k in text for k in ("예금", "적금", "연금저축", "국채", "상품", "가입", "이율", "우대")):
        route.append("product_research")
    if any(k in text for k in ("동향", "전망", "흐름", "인상", "인하", "기준금리", "연준", "한국은행")):
        route.append("news_research")
    if any(k in text for k in ("유권해석", "법령해석", "국세청", "홈택스", "예규", "판례")):
        route.append("nts_law_research")
    if any(k in text for k in ("백테스트", "백테스팅", "backtest", "수익률 시뮬", "전략 수익")):
        route.append("stock_backtest")
    if any(k in text.lower() for k in ("기술적 분석", "기술분석", "rsi", "macd", "지금 어때", "현재 지표", "이동평균", "볼린저", "kdj")):
        route.append("stock_quick")
    if any(k in text for k in ("청약", "분양", "분양가", "당첨", "경쟁률")):
        route.append("cheongyak_lookup")
    return route or ["graph_rag"]


def classify_intent(state: AgentState) -> dict:
    """필요한 도구 목록을 판정하고, 이전 턴의 tool_context를 리셋한다."""
    from typing import Literal

    from pydantic import BaseModel, Field

    class _Route(BaseModel):
        """답변에 필요한 검색 도구 목록과 세법 조회 대상 자산 종류."""

        tools: List[
            Literal[
                "persona_rag",
                "graph_rag",
                "tax_and_market_lookup",
                "product_research",
                "news_research",
                "nts_law_research",
                "stock_backtest",
                "stock_quick",
                "cheongyak_lookup",
            ]
        ] = Field(default_factory=list)
        asset_types: List[str] = Field(
            default_factory=list,
            description="tax_and_market_lookup의 세법 조회를 특정 자산(예: 주식, 채권)으로 좁힐 때만 채운다.",
        )
        ticker: str = Field(
            default="",
            description=(
                "stock_backtest 또는 stock_quick을 골랐고 사용자가 특정 종목을 지목하면 야후 파이낸스 "
                "티커로 변환해 적는다 (예: 애플→AAPL, 삼성전자→005930.KS, 테슬라→TSLA). 종목이 불명확하면 빈 문자열."
            ),
        )

    user_text = latest_user_text(state)
    asset_types: List[str] = []
    ticker: str = ""

    # 순수 인사·잡담이면 분류 LLM을 건너뛰고 곧장 작문(도구 없음)으로 보낸다(지연·비용 절감).
    if _is_smalltalk(user_text):
        return {"route": [], "tax_asset_types": [], "ticker": None, "tool_context": None}

    try:
        # 라우터 출력은 도구 이름 몇 개짜리 JSON이라 300토큰이면 충분하다. 기본값(4000)을
        # 두면 모델이 structured output에서 폭주할 때 4000토큰을 다 태우고서야 끝난다
        # (실측 45초). 상한을 낮추면 폭주해도 금방 끝나고 아래 _keyword_route로 폴백된다.
        router = build_chat_model(temperature=0.0, max_tokens=300).with_structured_output(_Route)
        result = router.invoke(
            [SystemMessage(content=_INTENT_PROMPT), HumanMessage(content=user_text)]
        )
        tools = list(dict.fromkeys(result.tools))  # 중복 제거, 순서 유지
        asset_types = list(dict.fromkeys(result.asset_types))
    except Exception:  # noqa: BLE001 - 분류 실패 시 키워드 폴백
        tools = _keyword_route(user_text)
        if "stock_backtest" in tools or "stock_quick" in tools:
            import re
            m = re.search(r"\b([A-Za-z]{1,5}|\d{6}(?:\.KS|\.KQ)?)\b", user_text)
            if m:
                ticker = m.group(1).upper()
        if "tax_and_market_lookup" in tools:
            found_types = []
            for at in ("주식", "채권", "부동산", "예금", "가상자산", "연금"):
                if at in user_text:
                    found_types.append(at)
            asset_types = found_types

    # tool_context=None → 리듀서가 빈 리스트로 리셋(이전 턴 컨텍스트 제거)
    # tax_asset_types/ticker는 매 턴 새로 덮어써 이전 턴 값이 남지 않게 한다.
    return {
        "route": tools,
        "tax_asset_types": asset_types,
        "ticker": ticker or None,
        "tool_context": None,
    }
