"""주식 백테스트/분석 라우터.

- GET  /quick-analysis?ticker=AAPL  → 기술적 지표 스냅샷 + LLM 다중 시간축 전망
- GET  /strategies                  → 지원 전략 목록
- GET  /ticker-search               → 야후 파이낸스 티커 자동완성
- POST /backtest                    → 전략 백테스트 (기간 선택 + 강화 메트릭 + 거래 목록)
- POST /analysis                    → 백테스트 메트릭 → NIM LLM 리포트
"""

from __future__ import annotations

import logging
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
from backend.app.services.trading.analysis_memory import calibrated_level, get_analysis_memory
from shared.database.repositories.watchlist import (
    add_watchlist,
    list_watchlist,
    remove_watchlist,
)
from shared.utils.timez import KST, now_kst

router = APIRouter(prefix="/api/v1/stocks", tags=["stocks"])

_PERIOD_DAYS: dict[str, int] = {
    "1mo": 35,
    "3mo": 95,
    "6mo": 185,
    "1y": 370,
    "2y": 740,
}


def _resolve_window(req) -> tuple[str, str]:
    """(start, end) 날짜 문자열을 계산한다. start_date가 있으면 그대로, 없으면 period로 역산."""
    end = req.end_date or now_kst().strftime("%Y-%m-%d")
    if req.start_date:
        return req.start_date, end
    days = _PERIOD_DAYS.get(req.period, 370)
    start = (now_kst() - timedelta(days=days)).strftime("%Y-%m-%d")
    return start, end


class BacktestRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    strategy: str = "sma_crossover"
    period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "1y"
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD; overrides period
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_capital: int = Field(default=100_000_000, gt=0)
    params: dict | None = None


class AnalysisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    strategy: str = "sma_crossover"
    metrics: dict


class GridSearchRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    strategy: str = "sma_crossover"
    period: Literal["1mo", "3mo", "6mo", "1y", "2y"] = "1y"
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_capital: int = Field(default=100_000_000, gt=0)


@router.get("/quick-analysis")
def quick_analysis(ticker: str = Query(min_length=1, max_length=20)) -> dict:
    """현재 기술적 지표 스냅샷 + NIM LLM 다중 시간축 전망 (QuantDinger fast-analysis 스타일).

    항상 최근 400일 데이터로 SMA200 포함 전 지표를 계산한다.
    LLM 전망 실패 시 outlook:{error:...} 로 graceful degrade.
    """
    symbol = ticker.strip().upper()
    end = now_kst().strftime("%Y-%m-%d")
    start = (now_kst() - timedelta(days=400)).strftime("%Y-%m-%d")

    analyzer = StockAnalyzer(ticker=symbol, start_date=start, end_date=end)
    try:
        analyzer.fetch_data()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"데이터 조회 실패: {exc}")

    try:
        indicators = analyzer.quick_analysis()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"지표 계산 실패: {exc}")

    # 과거 유사 패턴(교차종목) + 자신감별 적중률 → LLM 프롬프트 컨텍스트로 주입(미가용이면 빈 값).
    memory = get_analysis_memory()
    similar = memory.get_similar_patterns(symbol, indicators)
    level_accuracy = memory.get_level_accuracy(ticker=symbol)

    outlook = generate_quick_report(
        symbol, indicators, similar_patterns=similar, level_accuracy=level_accuracy
    )

    # 이번 분석을 메모리에 저장(다음 분석의 유사 패턴 후보가 됨). 실패해도 응답엔 영향 없음.
    if not outlook.get("error"):
        memory.store(symbol, indicators, outlook, price=indicators.get("current_price"))
        # 신뢰도 캘리브레이션: 같은 자신감 레벨의 과거 적중률로 보정(표본 부족 시 None).
        calibration = memory.calibrate(outlook.get("confidence"), ticker=symbol)
        if calibration:
            outlook["calibration"] = calibration
            # 보정 적중률을 실제 자신감 레벨로 반영(결정에 피드백). 원본은 raw_confidence로 보존.
            adjusted = calibrated_level(calibration.get("calibrated_pct"))
            if adjusted and adjusted != outlook.get("confidence"):
                outlook["raw_confidence"] = outlook.get("confidence")
                outlook["confidence"] = adjusted

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


# 야후 파이낸스는 한글 사명을 색인하지 않아 "삼성전자"로 검색하면 0건이 나온다.
# 그래서 국내 대표 종목만 한글명 → 야후 심볼로 직접 매핑해 폴백한다.
# ponytail: 데모에 나올 법한 시총 상위·친숙한 종목 50여 개로 범위를 못 박았다. 전체 상장사
#   커버는 KRX 종목마스터 적재가 필요해 과하다 — 검색 누락이 실제로 문제되면 그때 교체.
_KR_TICKERS: tuple[tuple[str, str], ...] = (
    ("삼성전자", "005930.KS"), ("삼성전자우", "005935.KS"), ("SK하이닉스", "000660.KS"),
    ("LG에너지솔루션", "373220.KS"), ("삼성바이오로직스", "207940.KS"), ("현대차", "005380.KS"),
    ("기아", "000270.KS"), ("셀트리온", "068270.KS"), ("POSCO홀딩스", "005490.KS"),
    ("NAVER", "035420.KS"), ("네이버", "035420.KS"), ("LG화학", "051910.KS"),
    ("삼성SDI", "006400.KS"), ("카카오", "035720.KS"), ("KB금융", "105560.KS"),
    ("신한지주", "055550.KS"), ("하나금융지주", "086790.KS"), ("우리금융지주", "316140.KS"),
    ("삼성물산", "028260.KS"), ("현대모비스", "012330.KS"), ("SK이노베이션", "096770.KS"),
    ("삼성생명", "032830.KS"), ("삼성화재", "000810.KS"), ("한국전력", "015760.KS"),
    ("KT&G", "033780.KS"), ("LG전자", "066570.KS"), ("SK텔레콤", "017670.KS"),
    ("KT", "030200.KS"), ("포스코퓨처엠", "003670.KS"), ("HMM", "011200.KS"),
    ("크래프톤", "259960.KS"), ("삼성전기", "009150.KS"), ("에스오일", "010950.KS"),
    ("두산에너빌리티", "034020.KS"), ("한화에어로스페이스", "012450.KS"),
    ("HD현대중공업", "329180.KS"), ("대한항공", "003490.KS"), ("LG", "003550.KS"),
    ("아모레퍼시픽", "090430.KS"), ("CJ제일제당", "097950.KS"), ("하이브", "352820.KS"),
    ("넷마블", "251270.KS"), ("미래에셋증권", "006800.KS"), ("기업은행", "024110.KS"),
    ("유한양행", "000100.KS"), ("한미약품", "128940.KS"), ("현대건설", "000720.KS"),
    ("에코프로비엠", "247540.KQ"), ("에코프로", "086520.KQ"), ("알테오젠", "196170.KQ"),
    ("HLB", "028300.KQ"), ("JYP Ent.", "035900.KQ"),
    ("KODEX 200", "069500.KS"), ("TIGER 미국S&P500", "360750.KS"),
    ("KOSEF 국고채10년", "148070.KS"), ("ACE KRX금현물", "411060.KS"),
)


def _kr_name_matches(query: str) -> list[dict]:
    """한글/한국어 사명 부분일치로 국내 종목을 찾는다(야후 검색 실패분 보완)."""
    key = query.replace(" ", "").upper()
    return [
        {"symbol": symbol, "name": name, "exchange": "KRX", "type": "EQUITY"}
        for name, symbol in _KR_TICKERS
        if key in name.replace(" ", "").upper()
    ][:8]


@router.get("/ticker-search")
def ticker_search(q: str = "") -> list[dict]:
    """야후 파이낸스 티커 자동완성 프록시 (+ 국내 종목 한글명 폴백)."""
    query = q.strip()
    if len(query) < 1:
        return []
    import requests

    local = _kr_name_matches(query)

    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": False},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=4,
        )
        resp.raise_for_status()
        quotes = resp.json().get("quotes", [])
    except Exception:
        return local
    remote = [
        {
            "symbol": item.get("symbol", ""),
            "name": item.get("shortname") or item.get("longname") or "",
            "exchange": item.get("exchDisp") or "",
            "type": item.get("quoteType") or "",
        }
        for item in quotes
        if item.get("symbol")
    ]
    seen = {r["symbol"] for r in local}
    return (local + [r for r in remote if r["symbol"] not in seen])[:8]


@router.post("/backtest")
def run_backtest(req: BacktestRequest) -> dict:
    """전략 백테스트 실행 → 강화 메트릭 + 차트 데이터 + 거래 목록."""
    if req.strategy not in STRATEGY_LABELS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 전략: {req.strategy}")

    start, end = _resolve_window(req)
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
    except Exception as exc:
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

    start, end = _resolve_window(req)
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
    except Exception as exc:
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
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"리포트 생성 실패: {exc}")
    return {"ticker": req.ticker, "strategy": req.strategy, "report": report}


@router.get("/memory/stats")
def memory_stats(ticker: str | None = None, days: int = 90) -> dict:
    """분석 메모리 정확도·분포 통계. DB 미가용이면 0 통계(200)."""
    return get_analysis_memory().get_stats(ticker=ticker, days=days)


@router.get("/memory/horizon-stats")
def memory_horizon_stats(ticker: str | None = None, days: int = 180) -> dict:
    """다중 시간축(24h/3d/1w/1m)별 적중률·평균수익. DB 미가용이면 빈 horizons(200)."""
    return get_analysis_memory().get_horizon_stats(ticker=ticker, days=days)


@router.post("/memory/validate")
def memory_validate(horizon_days: int = 7, limit: int = 50) -> dict:
    """미검증 과거 분석을 '분석시점 +horizon_days 영업일' 종가와 비교해 적중 여부를 채운다.

    백그라운드 스케줄러(main.py lifespan)가 주기적으로 같은 작업을 돌리며, 이 엔드포인트는 수동 트리거용.
    """
    return get_analysis_memory().validate_recent(horizon_days=horizon_days, limit=limit)


@router.post("/memory/validate-horizons")
def memory_validate_horizons(limit: int = 50) -> dict:
    """다중 시간축(24h/3d/1w/1m) 전망을 각 구간 종가로 개별 채점한다(스케줄러가 주기 실행, 수동 트리거용)."""
    return get_analysis_memory().validate_horizons(limit=limit)


class WatchlistRequest(BaseModel):
    user_uuid: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=20)


@router.get("/watchlist")
def get_watchlist(user_uuid: str) -> list[str]:
    """유저 관심종목 티커 목록(최근 추가 순)."""
    return list_watchlist(user_uuid)


@router.post("/watchlist")
def post_watchlist(req: WatchlistRequest) -> list[str]:
    """관심종목 추가 후 갱신된 목록 반환."""
    return add_watchlist(req.user_uuid, req.ticker)


@router.delete("/watchlist")
def delete_watchlist(user_uuid: str, ticker: str) -> list[str]:
    """관심종목 제거 후 갱신된 목록 반환."""
    return remove_watchlist(user_uuid, ticker)


# ── Finviz Heatmap Live Batch Service ──────────────────────────────────────────

_HEATMAP_STOCKS = [
    {"ticker": "NVDA", "name": "NVIDIA", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "$124.50", "defaultPct": 3.53, "defaultCapB": 3100},
    {"ticker": "AAPL", "name": "Apple", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "$225.20", "defaultPct": 1.85, "defaultCapB": 3450},
    {"ticker": "MSFT", "name": "Microsoft", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "$448.90", "defaultPct": 0.42, "defaultCapB": 3300},
    {"ticker": "AVGO", "name": "Broadcom", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "$1,680.10", "defaultPct": -2.69, "defaultCapB": 780},
    {"ticker": "005930.KS", "name": "삼성전자", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "78,500원", "defaultPct": 1.42, "defaultCapB": 410},
    {"ticker": "AMD", "name": "AMD", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "$152.30", "defaultPct": -3.29, "defaultCapB": 240},
    {"ticker": "000660.KS", "name": "SK하이닉스", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "215,000원", "defaultPct": 2.87, "defaultCapB": 140},
    {"ticker": "MU", "name": "Micron", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "$118.40", "defaultPct": -6.99, "defaultCapB": 130},

    {"ticker": "GOOGL", "name": "Alphabet", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "$182.60", "defaultPct": 0.65, "defaultCapB": 2250},
    {"ticker": "AMZN", "name": "Amazon", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "$186.40", "defaultPct": -0.66, "defaultCapB": 1950},
    {"ticker": "META", "name": "Meta", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "$498.50", "defaultPct": -1.80, "defaultCapB": 1250},
    {"ticker": "NFLX", "name": "Netflix", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "$642.10", "defaultPct": 1.74, "defaultCapB": 280},
    {"ticker": "035420.KS", "name": "NAVER", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "172,000원", "defaultPct": 0.88, "defaultCapB": 30},

    {"ticker": "BRK-B", "name": "Berkshire", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "$412.30", "defaultPct": 0.83, "defaultCapB": 900},
    {"ticker": "JPM", "name": "JPMorgan", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "$208.40", "defaultPct": 0.95, "defaultCapB": 600},
    {"ticker": "V", "name": "Visa", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "$274.50", "defaultPct": 1.18, "defaultCapB": 560},
    {"ticker": "MA", "name": "Mastercard", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "$452.10", "defaultPct": 1.77, "defaultCapB": 420},
    {"ticker": "BAC", "name": "Bank of America", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "$41.80", "defaultPct": 1.26, "defaultCapB": 320},

    {"ticker": "TSLA", "name": "Tesla", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "$248.50", "defaultPct": -2.08, "defaultCapB": 800},
    {"ticker": "GE", "name": "GE Aerospace", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "$168.20", "defaultPct": 1.35, "defaultCapB": 180},
    {"ticker": "CAT", "name": "Caterpillar", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "$345.80", "defaultPct": -0.65, "defaultCapB": 170},
    {"ticker": "005380.KS", "name": "현대차", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "254,000원", "defaultPct": 3.15, "defaultCapB": 160},

    {"ticker": "LLY", "name": "Eli Lilly", "sector": "bio", "sectorName": "HEALTHCARE & BIO", "defaultPrice": "$948.50", "defaultPct": 0.86, "defaultCapB": 900},
    {"ticker": "UNH", "name": "UnitedHealth", "sector": "bio", "sectorName": "HEALTHCARE & BIO", "defaultPrice": "$528.10", "defaultPct": -0.67, "defaultCapB": 490},
    {"ticker": "207940.KS", "name": "삼성바이오", "sector": "bio", "sectorName": "HEALTHCARE & BIO", "defaultPrice": "812,000원", "defaultPct": 1.25, "defaultCapB": 60},
    {"ticker": "068270.KS", "name": "셀트리온", "sector": "bio", "sectorName": "HEALTHCARE & BIO", "defaultPrice": "182,000원", "defaultPct": -0.82, "defaultCapB": 28},
    {"ticker": "196170.KQ", "name": "알테오젠", "sector": "bio", "sectorName": "HEALTHCARE & BIO", "defaultPrice": "352,000원", "defaultPct": 2.41, "defaultCapB": 14},

    # 국내 대형주 (코스피/코스닥). defaultCapB는 USD 10억 달러 단위 — 라이브 배치가 환율로 환산해 덮어씀
    {"ticker": "373220.KS", "name": "LG에너지솔루션", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "382,000원", "defaultPct": 1.12, "defaultCapB": 62},
    {"ticker": "006400.KS", "name": "삼성SDI", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "298,000원", "defaultPct": -1.44, "defaultCapB": 14},
    {"ticker": "247540.KQ", "name": "에코프로비엠", "sector": "tech", "sectorName": "SEMICONDUCTOR & TECH", "defaultPrice": "101,800원", "defaultPct": -2.15, "defaultCapB": 7},
    {"ticker": "035720.KS", "name": "카카오", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "42,300원", "defaultPct": 0.71, "defaultCapB": 13},
    {"ticker": "259960.KQ", "name": "크래프톤", "sector": "comm", "sectorName": "COMMUNICATION SERVICES", "defaultPrice": "312,000원", "defaultPct": 1.86, "defaultCapB": 11},
    {"ticker": "000270.KS", "name": "기아", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "104,500원", "defaultPct": 2.24, "defaultCapB": 30},
    {"ticker": "012450.KS", "name": "한화에어로스페이스", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "742,000원", "defaultPct": 3.42, "defaultCapB": 24},
    {"ticker": "329180.KS", "name": "HD현대중공업", "sector": "auto", "sectorName": "AUTO & MOBILITY", "defaultPrice": "398,000원", "defaultPct": 1.58, "defaultCapB": 25},
    {"ticker": "105560.KS", "name": "KB금융", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "108,500원", "defaultPct": 1.34, "defaultCapB": 30},
    {"ticker": "055550.KS", "name": "신한지주", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "62,400원", "defaultPct": 0.92, "defaultCapB": 22},
    {"ticker": "086790.KS", "name": "하나금융지주", "sector": "finance", "sectorName": "FINANCIAL SERVICES", "defaultPrice": "78,900원", "defaultPct": 1.05, "defaultCapB": 18},

    # 크립토 (yfinance는 -USD 접미사, market_cap 미제공 시 defaultCapB로 폴백)
    {"ticker": "BTC-USD", "name": "Bitcoin", "sector": "crypto", "sectorName": "CRYPTO", "defaultPrice": "$118,400.00", "defaultPct": 2.14, "defaultCapB": 2350},
    {"ticker": "ETH-USD", "name": "Ethereum", "sector": "crypto", "sectorName": "CRYPTO", "defaultPrice": "$4,120.50", "defaultPct": -1.32, "defaultCapB": 497},
]

_HEATMAP_CACHE: dict = {
    "data": [],
    "last_updated": 0.0,
    "source": "init",
}
_CACHE_TTL_SECONDS = 300.0  # 5분 인메모리 캐시 (Rate limit 방지)


import threading

_IS_UPDATING_HEATMAP = False
_HEATMAP_LOCK = threading.Lock()


def _do_update_heatmap():
    global _IS_UPDATING_HEATMAP
    import time

    import yfinance as yf

    try:
        now = time.time()
        items = []
        tickers_space = " ".join(s["ticker"] for s in _HEATMAP_STOCKS) + " KRW=X"
        data = yf.Tickers(tickers_space)

        # 국내 종목 시총은 원화로 오므로 달러로 환산해야 트리맵 면적이 미국 종목과 같은 축에 놓인다.
        usdkrw = 1400.0
        try:
            fx = getattr(data.tickers.get("KRW=X"), "fast_info", None)
            rate = getattr(fx, "last_price", None) or getattr(fx, "previous_close", None)
            if rate and rate > 0:
                usdkrw = float(rate)
        except Exception as exc:
            logging.getLogger(__name__).warning("USD/KRW 환율 조회 실패, 기본값 사용: %s", exc)

        for s in _HEATMAP_STOCKS:
            t_symbol = s["ticker"]
            price_str = s["defaultPrice"]
            pct = s["defaultPct"]
            cap = s["defaultCapB"]

            try:
                t_obj = data.tickers.get(t_symbol)
                if t_obj:
                    fast_info = getattr(t_obj, "fast_info", None)
                    if fast_info:
                        last_price = getattr(fast_info, "last_price", None) or getattr(fast_info, "previous_close", None)
                        prev_close = getattr(fast_info, "previous_close", None)
                        mcap = getattr(fast_info, "market_cap", None)

                        if last_price and prev_close and prev_close > 0:
                            pct = round(((last_price - prev_close) / prev_close) * 100, 2)

                        is_kr = t_symbol.endswith((".KS", ".KQ"))

                        if last_price:
                            if is_kr:
                                price_str = f"{int(last_price):,}원"
                            else:
                                price_str = f"${last_price:,.2f}"

                        if mcap:
                            # 원화 시총 → 달러 10억 단위 (미국 종목과 동일 축)
                            cap = round(mcap / usdkrw / 1_000_000_000, 1) if is_kr else round(mcap / 1_000_000_000, 1)
            except Exception as exc:
                logging.getLogger(__name__).debug("히트맵 종목 처리 건너뜀: %s", exc)

            items.append({
                "ticker": t_symbol,
                "name": s["name"],
                "price": price_str,
                "changePct": pct,
                "marketCapB": cap,
                "sector": s["sector"],
                "sectorName": s["sectorName"],
            })

        _HEATMAP_CACHE["data"] = items
        _HEATMAP_CACHE["last_updated"] = now
        _HEATMAP_CACHE["source"] = "yfinance_live_batch"
    except Exception as exc:
        if not _HEATMAP_CACHE["data"]:
            _HEATMAP_CACHE["data"] = [
                {
                    "ticker": s["ticker"],
                    "name": s["name"],
                    "price": s["defaultPrice"],
                    "changePct": s["defaultPct"],
                    "marketCapB": s["defaultCapB"],
                    "sector": s["sector"],
                    "sectorName": s["sectorName"],
                }
                for s in _HEATMAP_STOCKS
            ]
            _HEATMAP_CACHE["last_updated"] = time.time()
            _HEATMAP_CACHE["source"] = f"fallback_sample ({exc})"
    finally:
        _IS_UPDATING_HEATMAP = False


@router.get("/price-history")
def get_price_history(
    ticker: str = Query(min_length=1, max_length=20),
    period: str = "3mo",
) -> dict:
    """종가 시계열 (차트용). 지표·LLM 없이 yfinance 종가만 뽑는다."""
    import yfinance as yf

    symbol = ticker.strip().upper()
    if period not in {"1mo", "3mo", "6mo", "1y", "5y"}:
        raise HTTPException(status_code=422, detail=f"지원하지 않는 기간: {period}")

    try:
        hist = yf.Ticker(symbol).history(period=period)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"시세 조회 실패: {exc}")

    if hist.empty:
        raise HTTPException(status_code=404, detail=f"{symbol} 시세 데이터가 없습니다.")

    points = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 2)}
        for idx, row in hist.iterrows()
    ]
    first, last = points[0]["close"], points[-1]["close"]
    return {
        "ticker": symbol,
        "period": period,
        "points": points,
        "changePct": round((last - first) / first * 100, 2) if first else 0.0,
    }


@router.get("/heatmap")
def get_stock_heatmap(force_refresh: bool = False) -> dict:
    """Finviz 히트맵용 대표 종목 시가총액 & 등락률 정보 (초고속 캐시 + 비동기 라이브 백그라운드 배치)."""
    global _IS_UPDATING_HEATMAP
    import time

    now = time.time()
    # 1. 최초 데이터가 없으면 즉시 샘플 데이터로 선초기화 (0초 응답)
    if not _HEATMAP_CACHE["data"]:
        _HEATMAP_CACHE["data"] = [
            {
                "ticker": s["ticker"],
                "name": s["name"],
                "price": s["defaultPrice"],
                "changePct": s["defaultPct"],
                "marketCapB": s["defaultCapB"],
                "sector": s["sector"],
                "sectorName": s["sectorName"],
            }
            for s in _HEATMAP_STOCKS
        ]
        _HEATMAP_CACHE["last_updated"] = now
        _HEATMAP_CACHE["source"] = "sample_initial"

    # 2. 캐시 만료 시 백그라운드 스레드로 비동기 갱신 (메인 스레드 블로킹 방지)
    if force_refresh or (now - _HEATMAP_CACHE["last_updated"] >= _CACHE_TTL_SECONDS):
        if _HEATMAP_LOCK.acquire(blocking=False):
            try:
                if not _IS_UPDATING_HEATMAP:
                    _IS_UPDATING_HEATMAP = True
                    threading.Thread(target=_do_update_heatmap, daemon=True).start()
            finally:
                _HEATMAP_LOCK.release()

    return {
        "stocks": _HEATMAP_CACHE["data"],
        "source": _HEATMAP_CACHE["source"],
        "last_updated": datetime.fromtimestamp(_HEATMAP_CACHE["last_updated"], tz=KST).strftime("%Y-%m-%d %H:%M:%S") if _HEATMAP_CACHE["last_updated"] > 0 else "",
    }
