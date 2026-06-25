"""주식 백테스트/분석 라우터.

- GET  /quick-analysis?ticker=AAPL  → 기술적 지표 스냅샷 + LLM 다중 시간축 전망
- GET  /strategies                  → 지원 전략 목록
- GET  /ticker-search               → 야후 파이낸스 티커 자동완성
- POST /backtest                    → 전략 백테스트 (기간 선택 + 강화 메트릭 + 거래 목록)
- POST /analysis                    → 백테스트 메트릭 → NIM LLM 리포트
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.trading import (
    DEFAULT_PARAMS,
    STRATEGY_LABELS,
    StockAnalyzer,
)
from backend.app.services.trading.ai_analysis import generate_analysis, generate_quick_report

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])

_PERIOD_DAYS: dict[str, int] = {
    "1mo": 35,
    "3mo": 95,
    "6mo": 185,
    "1y": 370,
    "2y": 740,
}


class BacktestRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    strategy: str = "sma_crossover"
    period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "1y"
    start_date: str | None = None  # YYYY-MM-DD; overrides period
    end_date: str | None = None
    initial_capital: int = 100_000_000
    params: dict | None = None


class AnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    strategy: str = "sma_crossover"
    metrics: dict


@router.get("/quick-analysis")
def quick_analysis(ticker: str = Query(min_length=1, max_length=20)) -> dict:
    """현재 기술적 지표 스냅샷 + NIM LLM 다중 시간축 전망 (QuantDinger fast-analysis 스타일).

    항상 최근 400일 데이터로 SMA200 포함 전 지표를 계산한다.
    LLM 전망 실패 시 outlook:{error:...} 로 graceful degrade.
    """
    symbol = ticker.strip().upper()
    end = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")

    analyzer = StockAnalyzer(ticker=symbol, start_date=start, end_date=end)
    try:
        analyzer.fetch_data()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"데이터 조회 실패: {exc}")

    try:
        indicators = analyzer.quick_analysis()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"지표 계산 실패: {exc}")

    outlook = generate_quick_report(symbol, indicators)
    return {**indicators, "outlook": outlook}


@router.get("/strategies")
def list_strategies() -> dict:
    """지원 전략 목록(라벨 + 기본 파라미터)."""
    return {
        "strategies": [
            {
                "name": name,
                "label": label,
                "default_params": DEFAULT_PARAMS.get(name, {}),
            }
            for name, label in STRATEGY_LABELS.items()
        ]
    }


@router.get("/ticker-search")
def ticker_search(q: str = "") -> list[dict]:
    """야후 파이낸스 티커 자동완성 프록시."""
    query = q.strip()
    if len(query) < 1:
        return []
    import requests

    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": False},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=4,
        )
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
    except Exception:  # noqa: BLE001
        return []
    return [
        {
            "symbol": item.get("symbol", ""),
            "name": item.get("shortname") or item.get("longname") or "",
            "exchange": item.get("exchDisp") or "",
            "type": item.get("quoteType") or "",
        }
        for item in quotes
        if item.get("symbol")
    ]


@router.post("/backtest")
def run_backtest(req: BacktestRequest) -> dict:
    """전략 백테스트 실행 → 강화 메트릭 + 차트 데이터 + 거래 목록."""
    if req.strategy not in STRATEGY_LABELS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 전략: {req.strategy}")

    end = req.end_date or datetime.today().strftime("%Y-%m-%d")
    if req.start_date:
        start = req.start_date
    else:
        days = _PERIOD_DAYS.get(req.period, 370)
        start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    analyzer = StockAnalyzer(
        ticker=req.ticker,
        start_date=start,
        end_date=end,
        initial_capital=req.initial_capital,
        params={**DEFAULT_PARAMS, **(req.params or {})} if req.params else None,
    )
    try:
        analyzer.fetch_data()
        return analyzer.backtest(req.strategy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"백테스트 실패: {exc}")


@router.post("/analysis")
def run_analysis(req: AnalysisRequest) -> dict:
    """백테스트 메트릭 → NIM LLM 한국어 투자 리포트(마크다운)."""
    try:
        report = generate_analysis(req.ticker, req.strategy, req.metrics)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"리포트 생성 실패: {exc}")
    return {"ticker": req.ticker, "strategy": req.strategy, "report": report}
