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
from typing import Any, Optional

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

# 유사도 검증 임계값/가중치 (QuantDinger get_similar_patterns 기준).
_RSI_WEIGHT = 0.3
_MACD_WEIGHT = 0.3
_MA_WEIGHT = 0.25
_VOL_WEIGHT = 0.15
_SIM_THRESHOLD = 0.25
_CORRECT_BONUS = 0.1


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


class AnalysisMemory:
    """주식 분석 메모리 — Postgres 영속. DB 미가용 시 전부 graceful no-op."""

    def __init__(self) -> None:
        self._available = False
        self._ensure()

    def _ensure(self) -> None:
        try:
            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute(_CREATE_SQL)
                cur.execute(_INDEX_SQL)
            self._available = True
        except Exception:  # noqa: BLE001 - DB 없거나 권한 없으면 메모리 기능만 비활성
            self._available = False

    # ── 저장 ────────────────────────────────────────────
    def store(
        self,
        ticker: str,
        indicators: dict,
        outlook: dict,
        price: Optional[float] = None,
    ) -> Optional[int]:
        """분석 1건을 저장하고 id를 반환. 실패/미가용 시 None."""
        if not self._available:
            return None
        try:
            from shared.database.repositories.connection import db_cursor

            decision = str(outlook.get("decision") or "HOLD")[:10]
            confidence = str(outlook.get("confidence") or "low")[:10]
            summary = outlook.get("summary") or ""
            px = price if price is not None else indicators.get("current_price")

            with db_cursor() as (_, cur):
                cur.execute(
                    """
                    INSERT INTO stock_analysis_memory
                        (ticker, decision, confidence, price_at_analysis, summary,
                         indicators_snapshot, outlook)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    RETURNING id
                    """,
                    (
                        ticker.upper(),
                        decision,
                        confidence,
                        px,
                        summary,
                        json.dumps(indicators, ensure_ascii=False),
                        json.dumps(outlook, ensure_ascii=False),
                    ),
                )
                row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception:  # noqa: BLE001
            return None

    # ── 유사 패턴 검색 ───────────────────────────────────
    def get_similar_patterns(
        self,
        ticker: str,
        current_indicators: dict,
        limit: int = 3,
    ) -> list[dict]:
        """현재 지표와 유사한 과거 분석을 가중 유사도로 검색.

        축: RSI(±, 0.3) · MACD 시그널(일치, 0.3) · MA 추세(일치, 0.25) · 변동성(밴드, 0.15).
        검증된 적중 사례에는 가산점(+0.1). 미가용/없으면 빈 리스트.
        """
        if not self._available:
            return []
        try:
            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute(
                    """
                    SELECT id, decision, confidence, price_at_analysis, summary,
                           indicators_snapshot, created_at, was_correct, actual_return_pct
                    FROM stock_analysis_memory
                    WHERE ticker = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (ticker.upper(), limit * 8),
                )
                rows = cur.fetchall() or []

            scored: list[tuple[float, dict]] = []
            for r in rows:
                ind = _safe_json(r[5], {})
                sim = _similarity(current_indicators, ind)
                if sim < _SIM_THRESHOLD:
                    continue
                if r[7] is True:  # was_correct
                    sim += _CORRECT_BONUS

                scored.append((
                    sim,
                    {
                        "id": int(r[0]),
                        "decision": r[1],
                        "confidence": r[2],
                        "price": float(r[3]) if r[3] is not None else None,
                        "summary": r[4],
                        "created_at": r[6].isoformat() if r[6] else None,
                        "was_correct": r[7],
                        "actual_return_pct": float(r[8]) if r[8] is not None else None,
                        "similarity": round(min(sim, 1.0), 3),
                    },
                ))

            scored.sort(key=lambda x: -x[0])
            return [p[1] for p in scored[:limit]]
        except Exception:  # noqa: BLE001
            return []

    # ── 결과 검증 (best-effort) ──────────────────────────
    def validate_recent(self, min_age_days: int = 7, limit: int = 50) -> dict:
        """min_age_days 이상 지난 미검증 분석을, 현재가(yfinance)와 비교해 적중 여부를 채운다.

        BUY → +2% 초과 적중, SELL → -2% 미만 적중, HOLD → |수익률|<=5% 적중.
        DB/네트워크 실패는 건별로 흡수. 통계 dict 반환.
        """
        stats = {"validated": 0, "correct": 0, "incorrect": 0, "errors": 0}
        if not self._available:
            return stats
        try:
            import yfinance as yf

            from shared.database.repositories.connection import db_cursor

            with db_cursor() as (_, cur):
                cur.execute(
                    """
                    SELECT id, ticker, decision, price_at_analysis
                    FROM stock_analysis_memory
                    WHERE validated_at IS NULL
                      AND price_at_analysis IS NOT NULL
                      AND created_at < NOW() - (%s || ' days')::interval
                    LIMIT %s
                    """,
                    (int(min_age_days), int(limit)),
                )
                rows = cur.fetchall() or []

                for r in rows:
                    mem_id, ticker, decision, entry = r[0], r[1], r[2], r[3]
                    try:
                        entry_px = float(entry or 0)
                        if entry_px <= 0:
                            continue
                        hist = yf.Ticker(ticker).history(period="1d")
                        if hist.empty:
                            continue
                        cur_px = float(hist["Close"].iloc[-1])
                        ret = (cur_px - entry_px) / entry_px * 100.0

                        ok = (
                            (decision == "BUY" and ret > 2)
                            or (decision == "SELL" and ret < -2)
                            or (decision == "HOLD" and abs(ret) <= 5)
                        )
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
                    except Exception:  # noqa: BLE001 - 건별 실패 흡수
                        stats["errors"] += 1
            return stats
        except Exception:  # noqa: BLE001
            return stats

    # ── 통계 ────────────────────────────────────────────
    def get_stats(self, ticker: Optional[str] = None, days: int = 90) -> dict:
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
        except Exception:  # noqa: BLE001
            return empty


# ── 싱글턴 ──────────────────────────────────────────────
_instance: Optional[AnalysisMemory] = None


def get_analysis_memory() -> AnalysisMemory:
    """프로세스 단위 싱글턴. 최초 호출 시 테이블을 보장한다(graceful)."""
    global _instance
    if _instance is None:
        _instance = AnalysisMemory()
    return _instance
