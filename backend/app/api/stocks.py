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
    GRID_RANGES,
    STRATEGY_LABELS,
    StockAnalyzer,
)
from backend.app.services.trading.ai_analysis import generate_analysis, generate_quick_report
from backend.app.services.trading.analysis_memory import get_analysis_memory

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


class GridSearchRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    strategy: str = "sma_crossover"
    period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "1y"
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: int = 100_000_000


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

    # 과거 유사 패턴 검색 → LLM 프롬프트 컨텍스트로 주입(메모리 미가용이면 빈 리스트).
    memory = get_analysis_memory()
    similar = memory.get_similar_patterns(symbol, indicators)

    outlook = generate_quick_report(symbol, indicators, similar_patterns=similar)

    # 이번 분석을 메모리에 저장(다음 분석의 유사 패턴 후보가 됨). 실패해도 응답엔 영향 없음.
    if not outlook.get("error"):
        memory.store(symbol, indicators, outlook, price=indicators.get("current_price"))

    return {**indicators, "outlook": outlook, "similar_patterns": similar}


@router.get("/strategies")
def list_strategies() -> dict:
    """지원 전략 목록(라벨 + 기본 파라미터 + 그리드서치 지원 여부)."""
    return {
        "strategies": [
            {
                "name": name,
                "label": label,
                "default_params": DEFAULT_PARAMS.get(name, {}),
                "grid_supported": name in GRID_RANGES,
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


@router.post("/grid-search")
def grid_search(req: GridSearchRequest) -> dict:
    """전략 파라미터 그리드 서치 → 최적 파라미터 + 수익률.

    GRID_RANGES에 정의된 전략(sma_crossover/macd/rsi/bollinger/obv)만 지원한다.
    데이터를 1회 받아 모든 조합을 재사용 시뮬레이션한다.
    """
    if req.strategy not in GRID_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"그리드 서치를 지원하지 않는 전략: {req.strategy} (지원: {', '.join(GRID_RANGES)})",
        )

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
    )
    try:
        analyzer.fetch_data()
        result = analyzer.grid_search(req.strategy)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"그리드 서치 실패: {exc}")

    return {
        "ticker": req.ticker.upper(),
        "strategy": req.strategy,
        "default_params": DEFAULT_PARAMS.get(req.strategy, {}),
        **result,  # best_params, best_return, results_count
    }


@router.post("/analysis")
def run_analysis(req: AnalysisRequest) -> dict:
    """백테스트 메트릭 → NIM LLM 한국어 투자 리포트(마크다운)."""
    try:
        report = generate_analysis(req.ticker, req.strategy, req.metrics)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"리포트 생성 실패: {exc}")
    return {"ticker": req.ticker, "strategy": req.strategy, "report": report}


@router.get("/memory/stats")
def memory_stats(ticker: str | None = None, days: int = 90) -> dict:
    """분석 메모리 정확도·분포 통계. DB 미가용이면 0 통계(200)."""
    return get_analysis_memory().get_stats(ticker=ticker, days=days)


@router.post("/memory/validate")
def memory_validate(min_age_days: int = 7, limit: int = 50) -> dict:
    """미검증 과거 분석을 현재가와 비교해 적중 여부를 채운다(best-effort)."""
    return get_analysis_memory().validate_recent(min_age_days=min_age_days, limit=limit)
