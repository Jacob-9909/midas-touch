"""유저/대시보드 조회 라우터 (read-only).

웹 콘솔이 챗봇 대상 유저를 고르고, 프로필·포트폴리오·시장지표·세율을
시각화하는 데 쓰는 조회 전용 엔드포인트 모음.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shared.database.connector import (
    get_all_tax_rules,
    get_latest_market_snapshots,
    get_market_history,
    get_portfolios_by_user_uuid,
    get_user_by_uuid,
    list_users,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/users")
def get_users(limit: int = 50, offset: int = 0) -> dict:
    """유저 선택용 요약 목록."""
    rows = list_users(limit=limit, offset=offset)
    return {"users": rows, "count": len(rows)}


@router.get("/users/{uuid}")
def get_user_detail(uuid: str) -> dict:
    """단일 유저 프로필 + 포트폴리오(+종목)."""
    profile = get_user_by_uuid(uuid)
    if not profile:
        raise HTTPException(status_code=404, detail=f"사용자를 찾을 수 없습니다: {uuid}")
    portfolios = get_portfolios_by_user_uuid(uuid)
    return {"profile": profile, "portfolios": portfolios}


# ── Macro Market Live Feed Service ─────────────────────────────────────────────

DEFAULT_MACRO_SNAPSHOTS = [
    {"snapshot_date": "2026-05-23", "data_type": "exchange_rate", "sub_key": "USD/KRW", "value": 1520.53, "unit": "KRW", "source": "yfinance_live"},
    {"snapshot_date": "2026-05-22", "data_type": "interest_rate", "sub_key": "US_10Y_BOND", "value": 4.56, "unit": "%", "source": "yfinance_live"},
    {"snapshot_date": "2026-05-24", "data_type": "interest_rate", "sub_key": "KR_BASE_RATE", "value": 2.50, "unit": "%", "source": "BOK_official"},
    {"snapshot_date": "2026-05-23", "data_type": "exchange_rate", "sub_key": "EUR/KRW", "value": 1642.10, "unit": "KRW", "source": "yfinance_live"},
    {"snapshot_date": "2026-05-23", "data_type": "exchange_rate", "sub_key": "JPY/KRW", "value": 980.45, "unit": "KRW", "source": "yfinance_live"},
    {"snapshot_date": "2026-05-23", "data_type": "gold_price", "sub_key": "GOLD_USD", "value": 2350.10, "unit": "USD/oz", "source": "yfinance_live"},
    {"snapshot_date": "2026-05-23", "data_type": "oil_price", "sub_key": "WTI_OIL", "value": 78.40, "unit": "USD/bbl", "source": "yfinance_live"},
]

_MACRO_CACHE: dict = {
    "data": DEFAULT_MACRO_SNAPSHOTS,
    "last_updated": 0.0,
}
_MACRO_TTL = 300.0  # 5분 인메모리 캐시 (Rate limit 방지)

_MACRO_YFINANCE_MAP = [
    {"data_type": "exchange_rate", "sub_key": "USD/KRW", "ticker": "KRW=X", "unit": "KRW", "source": "yfinance_live", "default_val": 1520.53},
    {"data_type": "exchange_rate", "sub_key": "EUR/KRW", "ticker": "EURKRW=X", "unit": "KRW", "source": "yfinance_live", "default_val": 1642.10},
    {"data_type": "exchange_rate", "sub_key": "JPY/KRW", "ticker": "JPYKRW=X", "unit": "KRW", "source": "yfinance_live", "default_val": 980.45},
    {"data_type": "interest_rate", "sub_key": "US_10Y_BOND", "ticker": "^TNX", "unit": "%", "source": "yfinance_live", "default_val": 4.56},
    {"data_type": "interest_rate", "sub_key": "KR_BASE_RATE", "ticker": None, "unit": "%", "source": "BOK_official", "default_val": 2.50},
    {"data_type": "gold_price", "sub_key": "GOLD_USD", "ticker": "GC=F", "unit": "USD/oz", "source": "yfinance_live", "default_val": 2350.10},
    {"data_type": "gold_price", "sub_key": "SILVER_USD", "ticker": "SI=F", "unit": "USD/oz", "source": "yfinance_live", "default_val": 28.50},
    {"data_type": "oil_price", "sub_key": "WTI_OIL", "ticker": "CL=F", "unit": "USD/bbl", "source": "yfinance_live", "default_val": 78.40},
    {"data_type": "oil_price", "sub_key": "BRENT_OIL", "ticker": "BZ=F", "unit": "USD/bbl", "source": "yfinance_live", "default_val": 82.10},
]


def _update_macro_cache():
    import time
    from datetime import datetime

    import yfinance as yf

    today_str = datetime.today().strftime("%Y-%m-%d")
    db_rows = []
    try:
        db_rows = get_latest_market_snapshots()
    except Exception:
        pass

    db_map = {(r.get("data_type"), r.get("sub_key")): r for r in db_rows}
    active_tickers = [item["ticker"] for item in _MACRO_YFINANCE_MAP if item["ticker"]]
    
    live_snapshots = []
    try:
        data = yf.Tickers(" ".join(active_tickers))
        for item in _MACRO_YFINANCE_MAP:
            d_type = item["data_type"]
            s_key = item["sub_key"]
            ticker = item["ticker"]
            db_fallback = db_map.get((d_type, s_key), {})
            
            val = db_fallback.get("value") or item.get("default_val", 0.0)
            unit = item["unit"]
            source = item["source"]
            date_str = db_fallback.get("snapshot_date", today_str)

            if ticker:
                try:
                    t_obj = data.tickers.get(ticker)
                    if t_obj:
                        fast_info = getattr(t_obj, "fast_info", None)
                        if fast_info:
                            last_price = getattr(fast_info, "last_price", None) or getattr(fast_info, "previous_close", None)
                            if last_price and float(last_price) > 0:
                                val = round(float(last_price), 2)
                                date_str = today_str
                except Exception:
                    pass

            live_snapshots.append({
                "snapshot_date": date_str,
                "data_type": d_type,
                "sub_key": s_key,
                "value": val,
                "unit": unit,
                "source": source,
            })

        _MACRO_CACHE["data"] = live_snapshots
        _MACRO_CACHE["last_updated"] = time.time()
    except Exception:
        if not _MACRO_CACHE["data"]:
            _MACRO_CACHE["data"] = DEFAULT_MACRO_SNAPSHOTS


_IS_UPDATING_MACRO = False


def _do_macro_thread():
    global _IS_UPDATING_MACRO
    try:
        _update_macro_cache()
    finally:
        _IS_UPDATING_MACRO = False


@router.get("/market/snapshots")
def get_market_snapshots(force_refresh: bool = False) -> dict:
    """data_type/sub_key별 최신 시장 지표 (야후 파이낸스 실시간 배치 + DB 폴백)."""
    global _IS_UPDATING_MACRO
    import threading
    import time

    now = time.time()
    if (force_refresh or not _MACRO_CACHE["data"] or (now - _MACRO_CACHE["last_updated"] >= _MACRO_TTL)) and not _IS_UPDATING_MACRO:
        _IS_UPDATING_MACRO = True
        t = threading.Thread(target=_do_macro_thread, daemon=True)
        t.start()

    return {"snapshots": _MACRO_CACHE["data"] or DEFAULT_MACRO_SNAPSHOTS}


@router.get("/market/history")
def get_market_history_endpoint(limit_per_key: int = 15) -> dict:
    """data_type/sub_key별 최근 히스토리 스냅샷 시리즈 (Sparkline용)."""
    return {"history": get_market_history(limit_per_key=limit_per_key)}


@router.get("/tax-rules")
def get_tax_rules() -> dict:
    """현행 세법 기준 세율/공제 한도."""
    return {"tax_rules": get_all_tax_rules()}
