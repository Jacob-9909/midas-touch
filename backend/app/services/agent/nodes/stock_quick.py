"""stock_quick 도구 노드 — 대화로 종목의 현재 기술적 지표를 분석한다.

intent가 추출한 ticker(state["ticker"])가 있으면 StockAnalyzer.quick_analysis()로 RSI·MACD·KDJ·
이동평균·볼린저·ATR 스냅샷을 계산해 tool_context에 넣는다. ticker가 없으면 그래프를 죽이지 않고
"티커를 알려달라"는 안내를 넣는다. yfinance/계산 예외도 모두 잡아 컨텍스트 문구로 흡수한다.

여기서는 LLM 호출 없이 지표 스냅샷만 제공한다(최종 작문·해석은 synthesize 노드가 담당).
상세 차트·다중 시간축 전망은 웹 `/api/v1/stocks/quick-analysis`가 담당한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..state import AgentState

_LOOKBACK_DAYS = 400  # SMA200 계산 가능하도록 충분히


def stock_quick_node(state: AgentState) -> dict:
    ticker = (state.get("ticker") or "").strip().upper()
    if not ticker:
        return {
            "tool_context": [
                "[stock_quick 안내] 기술적 분석할 종목 티커(예: AAPL, 005930.KS)를 알려주시면 "
                "RSI·MACD·KDJ·이동평균·볼린저 밴드 등 현재 지표를 분석해 드립니다."
            ]
        }

    try:
        from backend.app.services.trading import StockAnalyzer

        end = datetime.today().strftime("%Y-%m-%d")
        start = (datetime.today() - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        analyzer = StockAnalyzer(ticker=ticker, start_date=start, end_date=end)
        analyzer.fetch_data()
        qa = analyzer.quick_analysis()

        rsi = qa["rsi"]
        macd = qa["macd"]
        kdj = qa["kdj"]
        ma = qa["moving_averages"]
        bb = qa["bollinger"]
        atr = qa["atr"]
        lvl = qa["levels"]
        summary = (
            f"[stock_quick·{ticker}·현재 기술지표]\n"
            f"- 현재가: {qa['current_price']:,} ({qa['change_pct'] * 100:+.2f}%)\n"
            f"- RSI(14): {rsi['value']} ({rsi['signal']})\n"
            f"- MACD: 히스토그램 {macd['histogram']:.4f} ({macd['signal']})\n"
            f"- KDJ: K={kdj['k']}, D={kdj['d']}, J={kdj['j']}\n"
            f"- 이동평균 추세: {ma['trend']} (SMA20={ma['sma20']}, SMA50={ma['sma50']}, SMA200={ma['sma200']})\n"
            f"- 볼린저 %B: {bb['pct_b']} (상단={bb['upper']}, 하단={bb['lower']})\n"
            f"- ATR 변동성: {atr['volatility']} ({atr['pct'] * 100:.2f}%/일)\n"
            f"- 지지선: {lvl['support']}, 저항선: {lvl['resistance']}\n"
            "(현재 시점 스냅샷. 다중 시간축 전망·차트는 '주식분석'의 빠른 분석 탭 참고.)"
        )
        return {"tool_context": [summary]}
    except Exception as exc:  # noqa: BLE001 - 외부 데이터/계산 실패는 컨텍스트로 흡수
        return {"tool_context": [f"[stock_quick 실패·{ticker}] {exc}"]}
