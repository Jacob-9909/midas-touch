"""과거 시점 주가 전망 백필 — 캘리브레이션 루프에 채점된 표본을 채운다.

문제: stock_analysis_memory에 채점된(was_correct) 표본이 0건이라 UI 적중률이 계속 '—'로 뜬다.
전망은 기록 후 최소 1일~1개월이 지나야 채점되므로, 실시간 트래픽만으로는 숫자가 차지 않는다.

해결: (종목 × 과거 날짜) 그리드를 돌며 **그 시점 기준으로** 실제 파이프라인을 그대로 재현한다.
    backend/app/api/stocks.py:quick_analysis()와 같은 순서·같은 함수를 쓴다.
      StockAnalyzer(그 시점 데이터만) → quick_analysis()
      → generate_quick_report()(NIM LLM) → store()
    저장 시 created_at을 그 과거 날짜로 백데이팅하고, 전량 적재 후 채점(validate)까지 돌린다.

룩어헤드(미래 정보 누출) 차단 — 이게 이 스크립트의 존재 이유이자 가장 중요한 제약:
  1. 지표 — StockAnalyzer는 yf.download(start, end)로 받은 봉만 쓴다. yfinance의 end는 배타적이라
     end=기준일+1일로 두면 기준일 종가가 마지막 봉이 된다. quick_analysis()는 마지막 봉과 그 이전
     구간만 참조하므로 기준일 이후 데이터가 섞일 경로가 없다.
  2. 메모리 컨텍스트 — get_similar_patterns/get_level_accuracy에 as_of를 넘긴다. 그 시점 이후에
     기록된 분석은 물론, '그 시점엔 아직 채점 전이었을' 결과(was_correct)까지 가려진다.
  3. 시장 컨텍스트 — generate_quick_report(as_of=)가 오늘의 FNG·기업프로필을 빼고 VIX만 그 시점
     종가로 받는다.
  4. 처리 순서 — 날짜 오름차순. 같은 날짜 건끼리도 서로 안 보인다(as_of는 그 날 00:00, 저장된
     created_at도 그 날 00:00 → `created_at < as_of`가 거짓).

LLM은 우회하지 않는다. 지표 룰로 decision을 만들면 측정 대상이 'LLM의 캘리브레이션'에서
'룰의 캘리브레이션'으로 바뀐다. 느려도 실제 NIM 경로를 탄다(레이트리밋은 NIMChatOpenAI._generate가
shared/utils/nim_rate_limit.reserve()로 이미 프로세스 간 공유 슬롯을 예약하므로 별도 처리 불필요).

사용 예:
    python -m pipelines.data_ingestion.backfill_stock_analysis --self-check
    python -m pipelines.data_ingestion.backfill_stock_analysis --dry-run
    python -m pipelines.data_ingestion.backfill_stock_analysis --limit 40
    python -m pipelines.data_ingestion.backfill_stock_analysis --tickers AAPL,NVDA --every-days 3
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, time as dtime, timedelta

from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.app.services.trading.ai_analysis import generate_quick_report  # noqa: E402
from backend.app.services.trading.analysis_memory import (  # noqa: E402
    AnalysisMemory,
    _asof_window,
    get_analysis_memory,
)
from backend.app.services.trading.stock_analyzer import StockAnalyzer  # noqa: E402

# 유동성 있고 히트맵/관심종목에도 이미 올라와 있는 종목들. 미국 + 한국을 섞어 교차종목 유사검색이
# 의미 있게 돌도록 한다. --tickers 로 갈아끼울 수 있다.
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AMD",
    "005930.KS", "000660.KS",
]

# 기본 백필 창. get_stats(days=90)·get_level_accuracy(days=180) 등 통계 API 기본 윈도우 안에
# 들어가야 UI에 바로 숫자가 뜬다. 끝은 오늘-2일(마지막 봉 확보). 시작은 88일 전(90일 경계 회피).
# ponytail: 더 옛날까지 밀어 넣으려면 --start 를 주고, 통계 엔드포인트의 days 도 같이 키워야 한다.
DEFAULT_START_DAYS_AGO = 88
DEFAULT_END_DAYS_AGO = 2

# quick_analysis가 SMA200까지 계산하려면 200 거래일 ≈ 290 달력일. stocks.py와 같은 400일을 쓴다.
DEFAULT_LOOKBACK_DAYS = 400


def _grid_dates(start: date, end: date, every_days: int) -> list[date]:
    """start~end를 every_days 간격으로 훑은 날짜 목록(오름차순, 중복 제거).

    주말에 걸리면 다음 월요일로 민다(토·일은 새 봉이 없어 직전 거래일과 같은 스냅샷이 된다).
    오름차순이 핵심이다 — 과거→미래 순으로 처리해야 메모리에 미래 분석이 섞이지 않는다.
    """
    out: list[date] = []
    d = start
    while d <= end:
        snapped = d + timedelta(days=7 - d.weekday()) if d.weekday() >= 5 else d
        if snapped <= end and (not out or out[-1] != snapped):
            out.append(snapped)
        d += timedelta(days=max(1, every_days))
    return out


def _existing_pairs() -> set[tuple[str, date]]:
    """이미 적재된 (종목, 날짜) 조합. 중단 후 이어서 돌릴 때 LLM 호출 전에 걸러낸다."""
    from shared.database.repositories.connection import db_cursor

    with db_cursor() as (_, cur):
        cur.execute("SELECT ticker, created_at::date FROM stock_analysis_memory")
        return {(str(r[0]).upper(), r[1]) for r in (cur.fetchall() or [])}


def _fmt_eta(done: int, total: int, elapsed: float) -> str:
    if done <= 0:
        return "?"
    remain = (elapsed / done) * (total - done)
    return f"{int(remain // 60)}분 {int(remain % 60)}초"


def backfill(
    tickers: list[str],
    dates: list[date],
    lookback_days: int,
    limit: int | None,
    memory: AnalysisMemory,
) -> dict:
    """(날짜 오름차순 × 종목) 순회하며 과거 시점 분석을 생성·적재한다."""
    existing = _existing_pairs()
    print(f"[백필] 이미 적재된 (종목,날짜) {len(existing)}건 — 건너뜁니다.")

    todo = [(d, t) for d in dates for t in tickers if (t.upper(), d) not in existing]
    if limit is not None:
        todo = todo[:limit]
    total = len(todo)
    print(f"[백필] 대상 {total}건 (종목 {len(tickers)} × 날짜 {len(dates)})\n")

    stats = {"stored": 0, "skipped": 0, "llm_error": 0, "data_error": 0}
    t0 = time.time()

    for i, (d, ticker) in enumerate(todo, 1):
        prefix = f"[{i}/{total}] {d} {ticker}"
        try:
            # yfinance의 end는 배타적 → 기준일 종가를 마지막 봉으로 만들려면 +1일.
            analyzer = StockAnalyzer(
                ticker=ticker,
                start_date=(d - timedelta(days=lookback_days)).isoformat(),
                end_date=(d + timedelta(days=1)).isoformat(),
            )
            df = analyzer.fetch_data()
            indicators = analyzer.quick_analysis()
        except Exception as exc:  # noqa: BLE001 - 상장 전/거래 정지/티커 오류 등
            stats["data_error"] += 1
            print(f"{prefix} — 데이터 실패: {exc}")
            continue

        # 실제 마지막 봉 날짜로 스냅. 휴장일에 걸리면 기준일과 달라지므로 여기서 맞춰야
        # created_at(=진입 시점)과 price_at_analysis(=그 봉의 종가)가 어긋나지 않는다.
        bar_date = df.index[-1].date()
        if (ticker.upper(), bar_date) in existing:
            stats["skipped"] += 1
            print(f"{prefix} — 이미 적재됨(봉 날짜 {bar_date})")
            continue
        as_of = datetime.combine(bar_date, dtime.min)

        # 그 시점까지의 메모리만 컨텍스트로. as_of가 룩어헤드를 막는 유일한 장치다.
        similar = memory.get_similar_patterns(ticker, indicators, as_of=as_of)
        level_accuracy = memory.get_level_accuracy(ticker=ticker, as_of=as_of)

        outlook = generate_quick_report(
            ticker,
            indicators,
            similar_patterns=similar,
            level_accuracy=level_accuracy,
            as_of=bar_date.isoformat(),
        )
        if outlook.get("error"):
            stats["llm_error"] += 1
            print(f"{prefix} — LLM 실패: {str(outlook['error'])[:120]}")
            continue

        # stocks.py와 동일하게 '보정 전 원본 confidence'를 저장한다. 보정값을 저장하면
        # 다음 캘리브레이션이 자기 보정 결과를 다시 채점하게 돼 측정이 순환한다.
        mem_id = memory.store(
            ticker,
            indicators,
            outlook,
            price=indicators.get("current_price"),
            created_at=as_of,
        )
        if mem_id is None:
            stats["data_error"] += 1
            print(f"{prefix} — 저장 실패(DB)")
            continue

        existing.add((ticker.upper(), bar_date))
        stats["stored"] += 1
        print(
            f"{prefix} → {outlook.get('decision')}/{outlook.get('confidence')} "
            f"(id={mem_id}, 유사표본 {len(similar)}건, "
            f"남은시간 ~{_fmt_eta(i, total, time.time() - t0)})"
        )

    return stats


def validate_all(memory: AnalysisMemory, since_days: int, batch: int = 50) -> dict:
    """채점을 더 이상 진행되지 않을 때까지 반복 호출한다(한 번에 limit건씩만 처리하므로).

    validate_recent()는 부모 테이블의 was_correct(=캘리브레이션 입력)를,
    validate_horizons()는 24h/3d/1w/1m 자식 테이블(=UI 시간축별 적중률)을 채운다. 둘 다 필요하다.
    """
    totals = {"decision_validated": 0, "horizon_validated": 0}
    for label, fn, key in (
        ("결정", lambda: memory.validate_recent(limit=batch), "decision_validated"),
        ("시간축", lambda: memory.validate_horizons(limit=batch, since_days=since_days),
         "horizon_validated"),
    ):
        # ponytail: 진행이 멈추면 종료. 무한루프 방지로 라운드 상한만 둔다.
        for _ in range(200):
            r = fn()
            n = r.get("validated", 0)
            totals[key] += n
            print(f"[채점·{label}] +{n}건 (적중 {r.get('correct')} / 빗나감 {r.get('incorrect')}, "
                  f"대기 {r.get('pending')}, 오류 {r.get('errors')})")
            if n == 0:
                break
    return totals


def _self_check() -> None:
    """as-of 필터가 미래 데이터를 절대 집지 않는지 DB·네트워크 없이 검증한다."""
    # 1) 날짜 그리드는 항상 오름차순이고 주말이 없다.
    g = _grid_dates(date(2025, 1, 1), date(2025, 3, 1), 7)
    assert g == sorted(g), g
    assert all(x.weekday() < 5 for x in g), g
    assert len(set(g)) == len(g), "중복 날짜"

    # 2) _asof_window: as_of를 주면 '채점 결과가 이미 나와 있던' 구간으로 상한이 걸려야 한다.
    live_sql, live_p = _asof_window(None, 180)
    assert len(live_sql) == 1 and live_p == [180], (live_sql, live_p)
    past = datetime(2025, 6, 1)
    past_sql, past_p = _asof_window(past, 180)
    assert len(past_sql) == 2, past_sql
    assert sum(s.count("%s") for s in past_sql) == len(past_p), (past_sql, past_p)
    assert past_p[0] is past and past_p[2] is past, past_p
    assert "created_at <" in past_sql[1], past_sql  # 미래 방향 상한이 실제로 존재

    # 3) 유사 패턴 검색: as_of 이후 분석은 나오면 안 되고, 그 시점에 아직 채점 안 된 건의
    #    결과(was_correct/actual_return_pct)는 가려져야 한다.
    mem = AnalysisMemory.__new__(AnalysisMemory)  # __init__(DB 접속) 우회
    mem._available = True
    mem._vec_available = False
    ind = {
        "rsi": {"value": 55.0},
        "macd": {"signal": "bullish"},
        "moving_averages": {"trend": "bullish"},
        "atr": {"volatility": "medium"},
    }
    # (id, decision, confidence, price, summary, snapshot, created_at, was_correct, ret, ticker)
    rows = [
        (1, "BUY", "high", 100.0, "채점 끝난 과거", ind,
         datetime(2025, 1, 10), True, 5.0, "AAPL"),
        (2, "BUY", "high", 100.0, "과거지만 채점 전", ind,
         datetime(2025, 5, 29), True, 5.0, "AAPL"),
        (3, "SELL", "low", 100.0, "미래", ind,
         datetime(2025, 9, 1), False, -9.0, "AAPL"),
    ]
    mem._fetch_candidates = lambda *a, **k: rows  # type: ignore[method-assign]

    got = mem.get_similar_patterns("AAPL", ind, limit=5, as_of=past)
    ids = sorted(p["id"] for p in got)
    assert 3 not in ids, f"as-of 이후 분석이 유사패턴으로 샜다: {ids}"
    assert ids == [1, 2], ids
    by_id = {p["id"]: p for p in got}
    assert by_id[1]["was_correct"] is True, by_id[1]
    assert by_id[1]["actual_return_pct"] == 5.0, by_id[1]
    assert by_id[2]["was_correct"] is None, "as-of 시점엔 아직 없던 채점 결과가 노출됐다"
    assert by_id[2]["actual_return_pct"] is None, by_id[2]

    # as_of 없이(실시간 경로) 부르면 기존 동작 그대로 — 전부 후보에 남는다.
    assert len(mem.get_similar_patterns("AAPL", ind, limit=5)) == 3

    print("self-check OK — as-of 필터가 미래 분석·미공개 채점 결과를 모두 차단합니다.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="과거 시점 주가 전망 백필 (캘리브레이션 표본 생성)"
                    " — 날짜 오름차순, as-of 룩어헤드 차단"
    )
    parser.add_argument("--tickers", help=f"쉼표 구분 종목 [기본값: {','.join(DEFAULT_TICKERS)}]")
    parser.add_argument(
        "--start", help=f"그리드 시작일 YYYY-MM-DD [기본값: {DEFAULT_START_DAYS_AGO}일 전]")
    parser.add_argument(
        "--end", help=f"그리드 종료일 YYYY-MM-DD [기본값: {DEFAULT_END_DAYS_AGO}일 전]")
    parser.add_argument("--every-days", type=int, default=7, help="그리드 간격(일) [기본값: 7]")
    parser.add_argument(
        "--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS,
        help=f"지표 계산용 과거 데이터 길이(일) [기본값: {DEFAULT_LOOKBACK_DAYS}]",
    )
    parser.add_argument(
        "--limit", type=int, help="이번 실행에서 생성할 최대 건수 (중단 후 이어서 실행 가능)")
    parser.add_argument("--dry-run", action="store_true", help="LLM 호출 없이 대상 건수만 계산")
    parser.add_argument("--no-validate", action="store_true", help="적재 후 채점(validate) 생략")
    parser.add_argument("--validate-only", action="store_true", help="적재 없이 채점만 실행")
    parser.add_argument(
        "--self-check", action="store_true", help="as-of 누출 방지 자체 점검만 실행")
    args = parser.parse_args()

    if args.self_check:
        _self_check()
        return

    today = date.today()
    start = (date.fromisoformat(args.start) if args.start
             else today - timedelta(days=DEFAULT_START_DAYS_AGO))
    end = (date.fromisoformat(args.end) if args.end
           else today - timedelta(days=DEFAULT_END_DAYS_AGO))
    tickers = ([t.strip().upper() for t in args.tickers.split(",")]
               if args.tickers else DEFAULT_TICKERS)
    dates = _grid_dates(start, end, args.every_days)

    memory = get_analysis_memory()
    if not memory._available:
        print("DB에 연결할 수 없습니다 (Postgres가 떠 있는지 확인하세요).", file=sys.stderr)
        sys.exit(1)

    # 채점은 백필 구간 전체를 덮어야 한다(기본값은 최근 60일만 훑는다).
    since_days = (today - start).days + 30

    if args.validate_only:
        print(validate_all(memory, since_days=since_days))
        return

    if args.dry_run:
        existing = _existing_pairs()
        todo = [(d, t) for d in dates for t in tickers if (t.upper(), d) not in existing]
        print(f"[dry-run] 날짜 {len(dates)}개 ({dates[0]} ~ {dates[-1]}), 종목 {len(tickers)}개")
        print(f"[dry-run] 이미 적재 {len(existing)}건 → 남은 LLM 호출 {len(todo)}건")
        return

    try:
        stats = backfill(tickers, dates, args.lookback_days, args.limit, memory)
    except KeyboardInterrupt:
        print("\n중단됨 — 지금까지 적재된 분은 보존됩니다. "
              "같은 명령을 다시 실행하면 이어서 진행합니다.")
        return

    print(f"\n[백필 완료] {stats}")
    if not args.no_validate:
        print(validate_all(memory, since_days=since_days))
    print(f"[통계] {memory.get_stats(days=since_days)}")
    print(f"[시간축] {memory.get_horizon_stats(days=since_days)}")


if __name__ == "__main__":
    main()
