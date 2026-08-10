"""주식 분석 메모리 레이어 (QuantDinger analysis_memory 이식 + midas 적응).

quick_analysis()의 기술지표 스냅샷과 AI 전망(decision/outlook)을 Postgres에 저장하고, 현재 지표와
'유사한 과거 분석'을 가중 유사도로 검색해 LLM 프롬프트에 컨텍스트로 주입한다. 과거 결정의 실제
결과(가격 변동)는 best-effort로 검증해 was_correct를 채워, 유사 패턴 검색 시 적중 사례에 가산점을 준다.

설계:
- 테이블 stock_analysis_memory는 최초 사용 시 CREATE TABLE IF NOT EXISTS로 자동 생성(자기완결).
- DB 미가용(연결 실패 등)이면 self._available=False → 모든 작업이 안전한 기본값([]/None)을 반환해
  quick_analysis 본류를 절대 죽이지 않는다(graceful degrade).
- midas 컨벤션: shared.database의 db_cursor(psycopg2 풀, 튜플 커서, %s 파라미터)를 사용한다.
- 지표 스냅샷은 StockAnalyzer.quick_analysis() 출력 형태를 따른다
  (rsi.value / macd.signal / moving_averages.trend / atr.volatility).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS stock_analysis_memory (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(32) NOT NULL,
    decision VARCHAR(10),
    confidence VARCHAR(10),
    price_at_analysis DOUBLE PRECISION,
    summary TEXT,
    indicators_snapshot JSONB,
    outlook JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP,
    actual_return_pct DOUBLE PRECISION,
    was_correct BOOLEAN
);
"""

_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_sam_ticker ON stock_analysis_memory(ticker);
CREATE INDEX IF NOT EXISTS idx_sam_created ON stock_analysis_memory(created_at DESC);
"""

# 다중 시간축(24h/3d/1w/1m) 개별 검증 결과를 분석 1건에 1행씩 적재하는 자식 테이블.
# (analysis_id, horizon) 유니크 → 같은 구간 중복 채점 방지. 분석 삭제 시 함께 정리(CASCADE).
_CREATE_HORIZON_SQL = """
CREATE TABLE IF NOT EXISTS stock_analysis_horizon_outcome (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER NOT NULL REFERENCES stock_analysis_memory(id) ON DELETE CASCADE,
    horizon VARCHAR(8) NOT NULL,
    predicted_trend VARCHAR(10),
    actual_return_pct DOUBLE PRECISION,
    was_correct BOOLEAN,
    validated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (analysis_id, horizon)
);
CREATE INDEX IF NOT EXISTS idx_saho_analysis ON stock_analysis_horizon_outcome(analysis_id);
"""

# 유사도 검증 임계값/가중치 (QuantDinger get_similar_patterns 기준).
_RSI_WEIGHT = 0.3
_MACD_WEIGHT = 0.3
_MA_WEIGHT = 0.25
_VOL_WEIGHT = 0.15
_SIM_THRESHOLD = 0.25
_CORRECT_BONUS = 0.1
_SAME_TICKER_BONUS = 0.05  # 교차종목 검색 시 같은 종목 사례를 살짝 우대
_DEDUP_SIM_THRESHOLD = 0.97  # 같은 종목·같은 날 이만큼 비슷하면 중복 저장 스킵

# pgvector 특징 벡터 차원. 지표 스냅샷을 결정적 수치 벡터로 인코딩해 교차종목 유사검색에 쓴다.
_FEATURE_DIM = 8

# 신뢰도 캘리브레이션: AI가 텍스트(high/medium/low)로 내는 자신감의 '암묵적 %'.
# 보정값은 같은 레벨 과거 분석의 실제 적중률로 대체한다(QuantDinger get_adjusted_confidence 적응).
_LEVEL_RAW_PCT = {"high": 80, "medium": 65, "low": 50}
_MIN_CALIB_SAMPLES = 5  # 이만큼 검증돼야 보정(콜드스타트 방지)
# 보정된 적중률(%) → 자신감 레벨. 캘리브레이션 결과를 결정에 실제 반영할 때 쓴다.
_HIGH_PCT_CUT = 70
_MEDIUM_PCT_CUT = 55

# 예측 평가용 고정 forward 구간(일). 분석시점 +N영업일의 종가로 채점해, 검증을 언제 돌리든
# 라벨(수익률·적중여부)이 동일하도록 한다. 과거엔 '현재가'와 비교해 경과일에 따라 라벨이 흔들렸다.
_VALIDATION_HORIZON_DAYS = 7
_BUY_SELL_BAND_PCT = 2.0  # BUY: +2%↑ 적중, SELL: -2%↓ 적중
_HOLD_BAND_PCT = 5.0  # HOLD: |수익률| ≤ 5% 적중

# 다중 시간축 라벨 → 평가 구간(일). outlook.outlook 의 키와 일치해야 한다.
_HORIZON_DAYS = {"24h": 1, "3d": 3, "1w": 7, "1m": 30}


def _safe_json(val: Any, default: Any) -> Any:
    """psycopg2가 JSONB를 dict/list로 줄 수도, 문자열로 줄 수도 있어 둘 다 처리."""
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def _extract(indicators: dict) -> tuple[float, str, str, str]:
    """지표 스냅샷에서 유사도 비교용 4개 축을 뽑는다(quick_analysis 출력 형태)."""
    rsi = float((indicators.get("rsi") or {}).get("value") or 50)
    macd = str((indicators.get("macd") or {}).get("signal") or "neutral").lower()
    ma = str((indicators.get("moving_averages") or {}).get("trend") or "mixed").lower()
    vol = str((indicators.get("atr") or {}).get("volatility") or "medium").lower()
    return rsi, macd, ma, vol


def _vol_similar(a: str, b: str) -> bool:
    """변동성 밴드 근접 여부(high/medium/low)."""
    if a == b:
        return True
    mid = {"medium", "normal"}
    return a in mid or b in mid  # medium은 high/low 어느 쪽과도 약하게 근접


def _similarity(current: dict, hist: dict) -> float:
    """현재 지표 vs 과거 스냅샷의 가중 유사도(0~약1.0). DB 없이도 검증 가능한 순수 함수.

    RSI(±30 정규화·0.3) + MACD 시그널 일치(0.3) + MA 추세 일치(0.25) + 변동성 밴드(0.15).
    """
    rsi, macd, ma, vol = _extract(current)
    h_rsi, h_macd, h_ma, h_vol = _extract(hist)
    rsi_score = max(0.0, 1 - abs(h_rsi - rsi) / 30) * _RSI_WEIGHT
    macd_score = _MACD_WEIGHT if h_macd == macd else 0.0
    ma_score = _MA_WEIGHT if h_ma == ma else 0.0
    vol_score = _VOL_WEIGHT if h_vol == vol else (_VOL_WEIGHT * 0.5 if _vol_similar(vol, h_vol) else 0.0)
    return rsi_score + macd_score + ma_score + vol_score


def _accuracy_by_level(rows: list[tuple[str, bool]]) -> dict[str, dict]:
    """(confidence_level, was_correct) 목록 → 레벨별 {적중률, 표본수}. 순수 함수(DB 무관).

    예: [("high", True), ("high", False), ("low", True)]
        → {"high": {"accuracy": 0.5, "n": 2}, "low": {"accuracy": 1.0, "n": 1}}
    """
    agg: dict[str, list[bool]] = {}
    for level, correct in rows:
        agg.setdefault(str(level or "").lower(), []).append(bool(correct))
    out: dict[str, dict] = {}
    for level, results in agg.items():
        if not results:
            continue
        out[level] = {"accuracy": sum(results) / len(results), "n": len(results)}
    return out


def _close_on_or_after(dates: list, closes: list, target) -> float | None:
    """target(날짜) 이상인 첫 봉의 종가. 주말·휴일이면 그 다음 거래일로 자동 이월.

    dates는 오름차순 가정. target 이후 봉이 아직 없으면(미래) None → 호출부가 다음 사이클로 미룸.
    순수 함수(yfinance 무관) — 테스트 가능.
    """
    for d, c in zip(dates, closes):
        if d >= target:
            return c
    return None


def _judge_outcome(
    decision: str | None,
    ret_pct: float,
    move_band: float = _BUY_SELL_BAND_PCT,
    hold_band: float = _HOLD_BAND_PCT,
) -> bool:
    """결정(BUY/SELL/HOLD)이 forward 수익률(%) 대비 적중했는지. 순수 함수.

    BUY → +move_band% 초과, SELL → -move_band% 미만, HOLD → |수익률| ≤ hold_band%.
    알 수 없는 결정은 미적중(False).
    """
    d = str(decision or "").upper()
    if d == "BUY":
        return ret_pct > move_band
    if d == "SELL":
        return ret_pct < -move_band
    if d == "HOLD":
        return abs(ret_pct) <= hold_band
    return False


def _clip01(x: float) -> float:
    """[0,1]로 클리핑."""
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _feature_vector(indicators: dict) -> list[float]:
    """지표 스냅샷을 고정 차원 수치 벡터로 인코딩(pgvector 교차종목 유사검색용). 순수 함수.

    축(0~1 정규화): RSI, MACD 시그널, MA 추세, 변동성, 볼린저 %B, KDJ J, 일변동률, ATR%.
    범주형은 bullish=1/neutral=0.5/bearish=0 식으로 인코딩한다. 결정적이라 같은 입력은 같은 벡터.
    """
    rsi, macd, ma, vol = _extract(indicators)
    macd_v = {"bullish": 1.0, "bearish": 0.0}.get(macd, 0.5)
    ma_v = {"bullish": 1.0, "bearish": 0.0}.get(ma, 0.5)
    vol_v = {"high": 1.0, "low": 0.0}.get(vol, 0.5)
    bb = indicators.get("bollinger") or {}
    pct_b = _clip01(float(bb.get("pct_b") if bb.get("pct_b") is not None else 0.5))
    kdj = indicators.get("kdj") or {}
    j = _clip01(float(kdj.get("j") if kdj.get("j") is not None else 50.0) / 100.0)
    chg = float(indicators.get("change_pct") or 0.0)
    chg_v = _clip01(0.5 + chg * 5.0)  # ±10% → 0/1 양끝
    atr = indicators.get("atr") or {}
    atr_v = _clip01(float(atr.get("pct") or 0.0) / 0.05)
    return [
        round(_clip01(rsi / 100.0), 6),
        round(macd_v, 6),
        round(ma_v, 6),
        round(vol_v, 6),
        round(pct_b, 6),
        round(j, 6),
        round(chg_v, 6),
        round(atr_v, 6),
    ]


def _asof_window(as_of: datetime | None, days: int) -> tuple[list[str], list]:
    """'해당 시점에 이미 결과가 공개돼 있던' 분석만 고르는 WHERE 조각 + 파라미터. 순수 함수.

    as_of=None(실시간 경로)이면 기존과 동일하게 NOW() 기준 최근 days일.
    as_of가 주어지면(과거 시점 재현·백필) 그 시점보다 최소 _VALIDATION_HORIZON_DAYS 이전 건만
    남긴다. 채점 결과는 분석시점 +N일이 지나야 나오므로, 그보다 최근 건을 쓰면 '미래를 보고
    자신감을 보정'하는 룩어헤드가 된다.
    """
    if as_of is None:
        return ["created_at > NOW() - (%s || ' days')::interval"], [int(days)]
    return (
        [
            "created_at > %s::timestamp - (%s || ' days')::interval",
            "created_at < %s::timestamp - (%s || ' days')::interval",
        ],
        [as_of, int(days), as_of, _VALIDATION_HORIZON_DAYS],
    )


def calibrated_level(pct: float | None) -> str | None:
    """보정 적중률(%) → 자신감 레벨. None이면 None(보정 불가). 결정에 실제 반영하는 매핑."""
    if pct is None:
        return None
    if pct >= _HIGH_PCT_CUT:
        return "high"
    if pct >= _MEDIUM_PCT_CUT:
        return "medium"
    return "low"


class AnalysisMemory:
    """주식 분석 메모리 — Postgres 영속. DB 미가용 시 전부 graceful no-op."""

    def __init__(self) -> None:
        self._available = False
        self._vec_available = False  # pgvector 교차종목 검색 가용 여부(선택적)
        self._ensure()

    def _ensure(self) -> None:
        try:
            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute(_CREATE_SQL)
                cur.execute(_INDEX_SQL)
                cur.execute(_CREATE_HORIZON_SQL)
            self._available = True
        except Exception:
            self._available = False
            return

        # pgvector는 선택적: 확장/컬럼이 없거나 권한이 없으면 파이썬 유사도로 폴백한다.
        try:
            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    f"ALTER TABLE stock_analysis_memory "
                    f"ADD COLUMN IF NOT EXISTS feature_vec vector({_FEATURE_DIM})"
                )
            self._vec_available = True
        except Exception:
            self._vec_available = False

    # ── 저장 ────────────────────────────────────────────
    def _find_duplicate(
        self, ticker: str, indicators: dict, as_of: datetime | None = None
    ) -> int | None:
        """같은 종목·같은 날 직전 분석과 거의 동일(≥_DEDUP_SIM_THRESHOLD)하면 그 id 반환(중복 방지).

        as_of를 주면 '오늘'이 아니라 그 날짜를 기준으로 본다(과거 시점 백필의 재실행 안전장치).
        """
        try:
            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute(
                    """
                    SELECT id, indicators_snapshot
                    FROM stock_analysis_memory
                    WHERE ticker = %s
                      AND created_at::date = COALESCE(%s::timestamp, NOW()::timestamp)::date
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (ticker.upper(), as_of),
                )
                row = cur.fetchone()
            if not row:
                return None
            sim = _similarity(indicators, _safe_json(row[1], {}))
            return int(row[0]) if sim >= _DEDUP_SIM_THRESHOLD else None
        except Exception:
            return None

    def store(
        self,
        ticker: str,
        indicators: dict,
        outlook: dict,
        price: float | None = None,
        created_at: datetime | None = None,
    ) -> int | None:
        """분석 1건을 저장하고 id를 반환. 실패/미가용 시 None.

        같은 종목·같은 날 거의 동일한 스냅샷이면 새로 적재하지 않고 기존 id를 반환한다(메모리 오염 방지).
        pgvector 가용 시 교차종목 유사검색용 특징 벡터(feature_vec)도 함께 적재한다.
        created_at을 주면 그 시각으로 백데이팅한다(과거 시점 백필). 없으면 기존대로 NOW().
        """
        if not self._available:
            return None
        try:
            from shared.database.repositories.connection import db_cursor

            dup_id = self._find_duplicate(ticker, indicators, as_of=created_at)
            if dup_id is not None:
                return dup_id

            decision = str(outlook.get("decision") or "HOLD")[:10]
            confidence = str(outlook.get("confidence") or "low")[:10]
            summary = outlook.get("summary") or ""
            px = price if price is not None else indicators.get("current_price")
            params = [
                ticker.upper(),
                decision,
                confidence,
                px,
                summary,
                json.dumps(indicators, ensure_ascii=False),
                json.dumps(outlook, ensure_ascii=False),
            ]

            if self._vec_available:
                sql = """
                    INSERT INTO stock_analysis_memory
                        (ticker, decision, confidence, price_at_analysis, summary,
                         indicators_snapshot, outlook, feature_vec, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::vector,
                            COALESCE(%s::timestamp, NOW()))
                    RETURNING id
                """
                params.append(_feature_vector(indicators))
            else:
                sql = """
                    INSERT INTO stock_analysis_memory
                        (ticker, decision, confidence, price_at_analysis, summary,
                         indicators_snapshot, outlook, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb,
                            COALESCE(%s::timestamp, NOW()))
                    RETURNING id
                """
            params.append(created_at)

            with db_cursor() as (_, cur):
                cur.execute(sql, tuple(params))
                row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception:
            return None

    # ── 유사 패턴 검색 ───────────────────────────────────
    def _fetch_candidates(
        self,
        ticker: str,
        indicators: dict,
        limit: int,
        cross_ticker: bool,
        as_of: datetime | None = None,
    ) -> list[tuple]:
        """유사 후보 행을 가져온다. pgvector 가용 시 특징벡터 거리순(교차종목), 아니면 최근 동일종목.

        as_of를 주면 그 시점 이전에 기록된 분석만 후보로 삼는다(과거 시점 재현 시 룩어헤드 차단).
        """
        from shared.database.repositories.connection import db_cursor

        cols = (
            "id, decision, confidence, price_at_analysis, summary, "
            "indicators_snapshot, created_at, was_correct, actual_return_pct, ticker"
        )
        asof_sql = "" if as_of is None else "AND created_at < %s"
        asof_p: list = [] if as_of is None else [as_of]
        with db_cursor() as (_, cur):
            if self._vec_available:
                # 교차종목: feature_vec 코사인 거리순. cross_ticker=False면 동일종목으로 제한.
                cur.execute(
                    f"""
                    SELECT {cols}
                    FROM stock_analysis_memory
                    WHERE feature_vec IS NOT NULL AND (%s OR ticker = %s) {asof_sql}
                    ORDER BY feature_vec <=> %s::vector
                    LIMIT %s
                    """,
                    (
                        bool(cross_ticker),
                        ticker.upper(),
                        *asof_p,
                        _feature_vector(indicators),
                        limit * 8,
                    ),
                )
            else:
                cur.execute(
                    f"""
                    SELECT {cols}
                    FROM stock_analysis_memory
                    WHERE ticker = %s {asof_sql}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (ticker.upper(), *asof_p, limit * 8),
                )
            return cur.fetchall() or []

    def get_similar_patterns(
        self,
        ticker: str,
        current_indicators: dict,
        limit: int = 3,
        cross_ticker: bool = True,
        as_of: datetime | None = None,
    ) -> list[dict]:
        """현재 지표와 유사한 과거 분석을 검색.

        pgvector 가용 시 특징벡터 거리로 교차종목 후보를 뽑고(cross_ticker), 파이썬 가중유사도로 재점수화.
        축: RSI(±, 0.3)·MACD(0.3)·MA(0.25)·변동성(0.15). 검증 적중 +0.1, 같은 종목 +0.05. 없으면 빈 리스트.

        as_of를 주면 그 시점 이후에 생긴 분석은 물론, '그 시점엔 아직 채점되지 않았을 결과'
        (was_correct/actual_return_pct)까지 가려서 넘긴다 — 과거 재현 시 미래 정보 누출 차단.
        """
        if not self._available:
            return []
        try:
            rows = self._fetch_candidates(
                ticker, current_indicators, limit, cross_ticker, as_of=as_of
            )
            # 채점 결과가 as-of 시점에 공개돼 있었을 경계(분석시점 + 검증 지평).
            known_by = (
                None if as_of is None else as_of - timedelta(days=_VALIDATION_HORIZON_DAYS)
            )

            scored: list[tuple[float, dict]] = []
            for r in rows:
                created = r[6]
                # SQL 필터가 빠져도 as-of 이후 분석은 컨텍스트에 넣지 않는다(이중 안전장치).
                if as_of is not None and created is not None and created >= as_of:
                    continue
                ind = _safe_json(r[5], {})
                sim = _similarity(current_indicators, ind)
                if sim < _SIM_THRESHOLD:
                    continue

                correct, ret = r[7], r[8]
                if known_by is not None and (created is None or created > known_by):
                    correct, ret = None, None  # 그 시점엔 아직 결과를 알 수 없었다

                if correct is True:
                    sim += _CORRECT_BONUS
                if (r[9] or "").upper() == ticker.upper():  # 같은 종목 우대
                    sim += _SAME_TICKER_BONUS

                scored.append((
                    sim,
                    {
                        "id": int(r[0]),
                        "decision": r[1],
                        "confidence": r[2],
                        "price": float(r[3]) if r[3] is not None else None,
                        "summary": r[4],
                        "created_at": created.isoformat() if created else None,
                        "was_correct": correct,
                        "actual_return_pct": float(ret) if ret is not None else None,
                        "ticker": r[9],
                        "similarity": round(min(sim, 1.0), 3),
                    },
                ))

            scored.sort(key=lambda x: -x[0])
            return [p[1] for p in scored[:limit]]
        except Exception:
            return []

    # ── 결과 검증 (best-effort) ──────────────────────────
    def validate_recent(
        self,
        horizon_days: int = _VALIDATION_HORIZON_DAYS,
        limit: int = 50,
    ) -> dict:
        """미검증 분석을 '분석시점 +horizon_days 영업일'의 종가와 비교해 적중 여부를 채운다.

        과거엔 '현재가'와 비교해 경과일이 길수록 라벨이 흔들렸다(60일 된 건=60일 수익률). 이제는
        분석시점부터 고정 구간만큼 앞선 봉의 종가로 채점해, 언제 돌리든 동일한 forward 수익률을 쓴다.

        BUY → +2% 초과 적중, SELL → -2% 미만 적중, HOLD → |수익률| ≤ 5% 적중.
        target 봉이 아직 없으면(미래) pending으로 남겨 다음 사이클에 재시도. 건별 실패는 흡수.
        """
        stats = {"validated": 0, "correct": 0, "incorrect": 0, "pending": 0, "errors": 0}
        if not self._available:
            return stats
        try:
            from datetime import timedelta

            import yfinance as yf

            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute(
                    """
                    SELECT id, ticker, decision, price_at_analysis, created_at
                    FROM stock_analysis_memory
                    WHERE validated_at IS NULL
                      AND price_at_analysis IS NOT NULL
                      AND created_at < NOW() - (%s || ' days')::interval
                    LIMIT %s
                    """,
                    (int(horizon_days), int(limit)),
                )
                rows = cur.fetchall() or []

                for r in rows:
                    mem_id, ticker, decision, entry, created = r[0], r[1], r[2], r[3], r[4]
                    try:
                        entry_px = float(entry or 0)
                        if entry_px <= 0 or created is None:
                            continue
                        target = created + timedelta(days=int(horizon_days))
                        # 주말·휴일로 target 봉이 밀릴 수 있어 앞뒤로 버퍼를 두고 받는다.
                        start = (created - timedelta(days=2)).strftime("%Y-%m-%d")
                        end = (target + timedelta(days=8)).strftime("%Y-%m-%d")
                        # 진입가(price_at_analysis)는 StockAnalyzer.fetch_data의 auto_adjust=False
                        # 종가다. 여기서 기본값(auto_adjust=True)으로 받으면 배당·분할 소급조정된
                        # 종가와 비교하게 돼 수익률이 체계적으로 왜곡된다(KO 1년 기준 약 -4%).
                        hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
                        if hist.empty:
                            continue
                        dates = [d.date() for d in hist.index]
                        closes = [float(c) for c in hist["Close"].values]
                        exit_px = _close_on_or_after(dates, closes, target.date())
                        if exit_px is None:
                            stats["pending"] += 1  # horizon 봉이 아직 미래 → 다음 사이클
                            continue

                        ret = (exit_px - entry_px) / entry_px * 100.0
                        ok = _judge_outcome(decision, ret)
                        cur.execute(
                            """
                            UPDATE stock_analysis_memory
                            SET validated_at = NOW(), actual_return_pct = %s, was_correct = %s
                            WHERE id = %s
                            """,
                            (ret, ok, int(mem_id)),
                        )
                        stats["validated"] += 1
                        stats["correct" if ok else "incorrect"] += 1
                    except Exception:
                        stats["errors"] += 1
            return stats
        except Exception:
            return stats

    # ── 다중 시간축 검증 ─────────────────────────────────
    def validate_horizons(self, limit: int = 50, since_days: int | None = None) -> dict:
        """outlook의 24h/3d/1w/1m 전망을 각 구간 종가로 개별 채점해 자식 테이블에 적재한다.

        구간마다 경과 시점이 달라(24h=1일, 1m=30일) 점진적으로 채워진다. 분석 1건당 yfinance를 한 번만
        받아 모든 due 구간을 처리한다. 아직 도래 안 한 구간은 pending으로 남겨 다음 사이클에 재시도.

        since_days는 '얼마나 오래된 분석까지 훑을지'(기본 1m+30일). 과거 시점 백필분을 채점하려면
        백필 구간을 덮을 만큼 크게 준다.
        """
        stats = {"validated": 0, "correct": 0, "incorrect": 0, "pending": 0, "errors": 0}
        if not self._available:
            return stats
        try:
            from datetime import timedelta

            import yfinance as yf

            from shared.database.repositories.connection import db_cursor

            max_days = max(_HORIZON_DAYS.values())
            since = max_days + 30 if since_days is None else int(since_days)
            with db_cursor() as (_, cur):
                # 적어도 24h 경과 + 1m(+버퍼) 이내 + 아직 4개 구간 다 안 채워진 분석만.
                cur.execute(
                    """
                    SELECT a.id, a.ticker, a.price_at_analysis, a.created_at, a.outlook
                    FROM stock_analysis_memory a
                    WHERE a.price_at_analysis IS NOT NULL
                      AND a.outlook IS NOT NULL
                      AND a.created_at < NOW() - interval '1 day'
                      AND a.created_at > NOW() - (%s || ' days')::interval
                      AND (SELECT COUNT(*) FROM stock_analysis_horizon_outcome h
                           WHERE h.analysis_id = a.id) < %s
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (since, len(_HORIZON_DAYS), int(limit)),
                )
                rows = cur.fetchall() or []

                for r in rows:
                    aid, ticker, entry, created, outlook_raw = r[0], r[1], r[2], r[3], r[4]
                    try:
                        entry_px = float(entry or 0)
                        if entry_px <= 0 or created is None:
                            continue
                        horizons = (_safe_json(outlook_raw, {}) or {}).get("outlook") or {}
                        if not isinstance(horizons, dict):
                            continue

                        start = (created - timedelta(days=2)).strftime("%Y-%m-%d")
                        end = (created + timedelta(days=max_days + 8)).strftime("%Y-%m-%d")
                        # 진입가와 같은 기준(미조정 종가)으로 받아야 배당·분할 소급조정 때문에
                        # 수익률이 체계적으로 밀리지 않는다. validate_recent와 동일한 이유.
                        hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
                        if hist.empty:
                            continue
                        dates = [d.date() for d in hist.index]
                        closes = [float(c) for c in hist["Close"].values]

                        cur.execute(
                            "SELECT horizon FROM stock_analysis_horizon_outcome WHERE analysis_id = %s",
                            (int(aid),),
                        )
                        done = {x[0] for x in (cur.fetchall() or [])}

                        for hz, days in _HORIZON_DAYS.items():
                            if hz in done:
                                continue
                            node = horizons.get(hz) or {}
                            trend = node.get("trend") if isinstance(node, dict) else None
                            if not trend:
                                continue
                            target = (created + timedelta(days=days)).date()
                            exit_px = _close_on_or_after(dates, closes, target)
                            if exit_px is None:
                                stats["pending"] += 1
                                continue
                            ret = (exit_px - entry_px) / entry_px * 100.0
                            ok = _judge_outcome(trend, ret)
                            cur.execute(
                                """
                                INSERT INTO stock_analysis_horizon_outcome
                                    (analysis_id, horizon, predicted_trend, actual_return_pct, was_correct)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT (analysis_id, horizon) DO NOTHING
                                """,
                                (int(aid), hz, str(trend).upper()[:10], ret, ok),
                            )
                            stats["validated"] += 1
                            stats["correct" if ok else "incorrect"] += 1
                    except Exception:
                        stats["errors"] += 1
            return stats
        except Exception:
            return stats

    # ── 통계 ────────────────────────────────────────────
    def get_stats(self, ticker: str | None = None, days: int = 90) -> dict:
        """검증된 분석의 정확도·분포 통계. 미가용/없으면 0 통계."""
        empty = {"total": 0, "validated": 0, "accuracy_pct": 0.0, "avg_return_pct": 0.0}
        if not self._available:
            return empty
        try:
            from shared.database.repositories.connection import db_cursor

            where = ["created_at > NOW() - (%s || ' days')::interval"]
            params: list[Any] = [int(days)]
            if ticker:
                where.append("ticker = %s")
                params.append(ticker.upper())

            with db_cursor() as (_, cur):
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*),
                        COUNT(validated_at),
                        SUM(CASE WHEN was_correct THEN 1 ELSE 0 END),
                        AVG(actual_return_pct)
                    FROM stock_analysis_memory
                    WHERE {" AND ".join(where)}
                    """,
                    tuple(params),
                )
                row = cur.fetchone()

            total = int(row[0] or 0)
            validated = int(row[1] or 0)
            correct = int(row[2] or 0)
            avg_ret = float(row[3]) if row[3] is not None else 0.0
            return {
                "total": total,
                "validated": validated,
                "accuracy_pct": round(correct / validated * 100, 2) if validated else 0.0,
                "avg_return_pct": round(avg_ret, 2),
            }
        except Exception:
            return empty

    def get_horizon_stats(self, ticker: str | None = None, days: int = 180) -> dict:
        """다중 시간축(24h/3d/1w/1m)별 적중률·평균수익 통계. 미가용/없으면 빈 horizons."""
        empty = {"horizons": {}}
        if not self._available:
            return empty
        try:
            from shared.database.repositories.connection import db_cursor

            where = ["h.validated_at > NOW() - (%s || ' days')::interval"]
            params: list[Any] = [int(days)]
            if ticker:
                where.append("a.ticker = %s")
                params.append(ticker.upper())

            with db_cursor() as (_, cur):
                cur.execute(
                    f"""
                    SELECT h.horizon, COUNT(*),
                           SUM(CASE WHEN h.was_correct THEN 1 ELSE 0 END),
                           AVG(h.actual_return_pct)
                    FROM stock_analysis_horizon_outcome h
                    JOIN stock_analysis_memory a ON a.id = h.analysis_id
                    WHERE {" AND ".join(where)}
                    GROUP BY h.horizon
                    """,
                    tuple(params),
                )
                rows = cur.fetchall() or []

            out: dict[str, dict] = {}
            for hz, n, correct, avg in rows:
                n = int(n or 0)
                out[hz] = {
                    "n": n,
                    "accuracy_pct": round((correct or 0) / n * 100, 2) if n else 0.0,
                    "avg_return_pct": round(float(avg or 0), 2),
                }
            return {"horizons": out}
        except Exception:
            return empty

    def get_level_accuracy(
        self,
        ticker: str | None = None,
        days: int = 180,
        as_of: datetime | None = None,
    ) -> dict:
        """검증된 분석의 자신감 레벨별 적중률 {level:{accuracy,n}}. LLM 프롬프트 피드백용.

        ticker 한정 표본이 부족하면 전체로 폴백한다(레벨별 표본을 최대한 확보).
        as_of를 주면 그 시점에 이미 채점이 끝나 있었을 분석만 센다(_asof_window 참조).
        """
        if not self._available:
            return {}
        try:
            from shared.database.repositories.connection import db_cursor

            def _rows(scope_ticker: str | None) -> list[tuple[str, bool]]:
                win, wparams = _asof_window(as_of, days)
                where = ["validated_at IS NOT NULL", "was_correct IS NOT NULL", *win]
                params: list[Any] = [*wparams]
                if scope_ticker:
                    where.append("ticker = %s")
                    params.append(scope_ticker.upper())
                with db_cursor() as (_, cur):
                    cur.execute(
                        f"SELECT confidence, was_correct FROM stock_analysis_memory "
                        f"WHERE {' AND '.join(where)}",
                        tuple(params),
                    )
                    return [(r[0], r[1]) for r in (cur.fetchall() or [])]

            rows = _rows(ticker) if ticker else _rows(None)
            acc = _accuracy_by_level(rows)
            # ticker 한정 표본이 빈약하면(레벨 합 < 최소표본) 전체로 폴백.
            if ticker and sum(v["n"] for v in acc.values()) < _MIN_CALIB_SAMPLES:
                acc = _accuracy_by_level(_rows(None))
            return acc
        except Exception:
            return {}

    # ── 신뢰도 캘리브레이션 ──────────────────────────────
    def calibrate(
        self,
        level: str | None,
        ticker: str | None = None,
        days: int = 180,
    ) -> dict | None:
        """AI 자신감(level)을 같은 레벨 과거 적중률로 보정한다.

        반환: {level, raw_pct(AI 암묵 자신감), calibrated_pct(과거 실제 적중률), sample_size}.
        표본이 _MIN_CALIB_SAMPLES 미만이거나 미가용/미지원 레벨이면 None(보정 불가 → 원본 사용).
        ticker 한정으로 먼저 보고, 표본 부족하면 전체로 폴백한다.
        """
        lvl = str(level or "").lower()
        if not self._available or lvl not in _LEVEL_RAW_PCT:
            return None
        try:
            from shared.database.repositories.connection import db_cursor

            def _rows(scope_ticker: str | None) -> list[tuple[str, bool]]:
                where = ["validated_at IS NOT NULL", "was_correct IS NOT NULL", "confidence = %s",
                         "created_at > NOW() - (%s || ' days')::interval"]
                params: list[Any] = [lvl, int(days)]
                if scope_ticker:
                    where.append("ticker = %s")
                    params.append(scope_ticker.upper())
                with db_cursor() as (_, cur):
                    cur.execute(
                        f"SELECT confidence, was_correct FROM stock_analysis_memory WHERE {' AND '.join(where)}",
                        tuple(params),
                    )
                    return [(r[0], r[1]) for r in (cur.fetchall() or [])]

            # ticker 한정 → 부족하면 전체 폴백
            rows = _rows(ticker) if ticker else []
            scope = "ticker"
            if len(rows) < _MIN_CALIB_SAMPLES:
                rows = _rows(None)
                scope = "global"

            acc = _accuracy_by_level(rows).get(lvl)
            if not acc or acc["n"] < _MIN_CALIB_SAMPLES:
                return None

            return {
                "level": lvl,
                "raw_pct": _LEVEL_RAW_PCT[lvl],
                "calibrated_pct": round(acc["accuracy"] * 100),
                "sample_size": acc["n"],
                "scope": scope,
            }
        except Exception:
            return None


# ── 싱글턴 ──────────────────────────────────────────────
_instance: AnalysisMemory | None = None


def get_analysis_memory() -> AnalysisMemory:
    """프로세스 단위 싱글턴. 최초 호출 시 테이블을 보장한다(graceful)."""
    global _instance
    if _instance is None:
        _instance = AnalysisMemory()
    return _instance
