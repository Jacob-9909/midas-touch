"""stock_backtest 도구 노드 — 대화로 종목 백테스트를 실행한다.

intent가 추출한 ticker(state["ticker"])가 있으면 StockAnalyzer로 sma_crossover·최근 1년 백테스트를
돌려 메트릭 요약을 tool_context에 넣는다. ticker가 없으면 그래프를 죽이지 않고 "티커를 알려달라"는
안내를 넣는다. yfinance/계산 예외도 모두 잡아 컨텍스트 문구로 흡수한다.

상세 분석/차트는 웹 `/api/v1/stocks`가 담당하고, 이 노드는 대화 맥락용 요약만 제공한다.
"""

from __future__ import annotations

from datetime import timedelta

from shared.utils.timez import now_kst

from ..state import AgentState

_LOOKBACK_DAYS = 365
_STRATEGY = "sma_crossover"


def stock_backtest_node(state: AgentState) -> dict:
    ticker = (state.get("ticker") or "").strip().upper()
    if not ticker:
        return {
            "tool_context": [
                ("[stock_backtest 안내] 백테스트할 종목 티커(예: AAPL, 005930.KS)를 알려주시면 "
                "최근 1년 SMA 교차 전략으로 시뮬레이션해 드립니다.")
            ]
        }

    try:
        from backend.app.services.trading import StockAnalyzer

        end = now_kst().strftime("%Y-%m-%d")
        start = (now_kst() - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        analyzer = StockAnalyzer(ticker=ticker, start_date=start, end_date=end)
        analyzer.fetch_data()
        res = analyzer.backtest(_STRATEGY)
        m = res["metrics"]
        summary = (
            f"[stock_backtest·{ticker}·SMA교차·최근1년]\n"
            f"- 전략 수익률: {m['total_return'] * 100:.2f}%\n"
            f"- 매수후보유 수익률: {m['buy_hold_return'] * 100:.2f}%\n"
            f"- 연간 수익률: {m['annual_return'] * 100:.2f}%\n"
            f"- 최대 낙폭: {m['max_drawdown'] * 100:.2f}%\n"
            f"- 총 거래 횟수: {m['total_trades']}회\n"
            f"- 최종 포트폴리오 가치: {m['final_value']:,}원\n"
            "(단일 전략·기본 파라미터 기준. 상세 차트·전략비교는 '주식분석' 페이지 참고.)"
        )
        return {"tool_context": [summary]}
    except Exception as exc:
        return {"tool_context": [f"[stock_backtest 실패·{ticker}] {exc}"]}
