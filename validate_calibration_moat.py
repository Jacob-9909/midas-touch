"""캘리브레이션 루프 '해자' 검증 프로브 (read-only, 일회성).

stock_analysis_memory / stock_analysis_horizon_outcome 에 이미 쌓인 라벨된 결과로,
자가 캘리브레이션 루프가 실제로 baseline 을 이기는지 데이터로 판정한다. 전략 방향(fork)을
정하기 전의 결정 게이트. DB만 읽고 아무것도 쓰지 않는다.

측정:
  1) 표본량 — 검증된 행 수, 티커 분포, 기간
  2) 모델 실제 적중률 vs 반사실 상수전략(항상 BUY/SELL/HOLD) — 같은 _judge_outcome 로 재계산
  3) 캘리브레이션 신뢰도 곡선 — stated confidence(high>medium>low)가 실현 적중률과 단조상관하나
  4) 시간축(24h/3d/1w/1m)별 적중률

실행:  uv run python validate_calibration_moat.py            # 전체
       uv run python validate_calibration_moat.py --days 90  # 최근 90일
       uv run python validate_calibration_moat.py --selftest # DB 없이 baseline 산식 검증

# ponytail: naive baseline(상수전략·시장상승률)만 본다. 부트스트랩 신뢰구간·거래비용은 붙이지 않음 —
#           1차 판정(edge가 있나/없나)엔 과함. edge가 보이면 그때 통계검정 추가.
"""

from __future__ import annotations

import argparse
import math

from backend.app.services.trading.analysis_memory import _MIN_CALIB_SAMPLES, _judge_outcome

_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def _rate(hits: int, n: int) -> str:
    return f"{hits / n * 100:5.1f}% (n={n})" if n else "  n/a (n=0)"


def _baselines(rows: list[tuple]) -> dict[str, float]:
    """행별 실현수익률로, '항상 X를 찍었다면' 상수전략의 적중률을 같은 채점기로 재계산."""
    n = len(rows)
    if not n:
        return {}
    out = {}
    for name, dec in (("always_BUY", "BUY"), ("always_SELL", "SELL"), ("always_HOLD", "HOLD")):
        out[name] = sum(_judge_outcome(dec, ret) for (_, _, ret, _) in rows) / n
    out["market_up_rate"] = sum(1 for (_, _, ret, _) in rows if ret > 0) / n
    return out


def _report(rows: list[tuple]) -> None:
    # rows: (decision, confidence, actual_return_pct, was_correct)
    n = len(rows)
    if not n:
        print("검증된 행이 없다. 아직 판정 불가 — 데이터를 더 쌓아야 한다.")
        return

    model_hits = sum(1 for r in rows if r[3])
    print(f"\n[1] 표본  검증행 {n}개")

    print("\n[2] 모델 vs 반사실 상수전략 (같은 _judge_outcome 채점)")
    model_rate = model_hits / n
    print(f"    모델 실제        {model_rate * 100:5.1f}%")
    base = _baselines([(None, None, r[2], None) for r in rows])
    best_const = max(base["always_BUY"], base["always_SELL"], base["always_HOLD"])
    for k in ("always_BUY", "always_SELL", "always_HOLD", "market_up_rate"):
        print(f"    {k:16s} {base[k] * 100:5.1f}%")
    edge = (model_rate - best_const) * 100
    se = math.sqrt(model_rate * (1 - model_rate) / n) * 100  # 적중률 표준오차(%p)
    sig = edge > 1.96 * se
    print(f"    → 최고 상수전략 대비 edge: {edge:+.1f}%p (1.96·SE≈{1.96 * se:.1f}%p)  "
          f"{'✅ 유의하게 이김' if sig else '❌ 노이즈 범위 — 상수전략과 구분 안 됨'}")

    print("\n[3] 캘리브레이션 신뢰도 곡선 (stated confidence → 실현 적중률)")
    by_conf: dict[str, list[bool]] = {}
    for dec, conf, ret, ok in rows:
        by_conf.setdefault(str(conf or "unknown").lower(), []).append(bool(ok))
    levels = sorted(by_conf, key=lambda c: _CONF_ORDER.get(c, 99))
    prev = None
    monotone = True
    for lv in levels:
        v = by_conf[lv]
        rate = sum(v) / len(v)
        flag = "" if len(v) >= _MIN_CALIB_SAMPLES else f"  ⚠️ 표본<{_MIN_CALIB_SAMPLES}(보정 미발화)"
        print(f"    {lv:8s} {_rate(sum(v), len(v))}{flag}")
        if lv in _CONF_ORDER and prev is not None and rate > prev:
            monotone = False  # 낮은 확신이 더 높은 적중 = 역전
        if lv in _CONF_ORDER:
            prev = rate
    graded = [lv for lv in levels if lv in _CONF_ORDER and len(by_conf[lv]) >= _MIN_CALIB_SAMPLES]
    if len(graded) < 2:
        print("    → ⚠️ confidence가 사실상 상수(레벨 1개) — 캘리브레이션 신호 없음, 단조성 판정 무의미")
    else:
        print(f"    → 단조성(high≥medium≥low): {'✅ 성립' if monotone else '❌ 역전 — 확신도가 신호가 아님'}")

    print("\n[4] 모델 결정별 정밀도 (어느 클래스가 성적을 캐리하나)")
    for dec in ("BUY", "SELL", "HOLD"):
        sub = [r for r in rows if str(r[0] or "").upper() == dec]
        print(f"    {dec:5s} {_rate(sum(1 for r in sub if r[3]), len(sub))}")


def _report_horizons(rows: list[tuple]) -> None:
    # rows: (horizon, predicted_trend, actual_return_pct, was_correct)
    # top-level decision은 HOLD로 축퇴돼 있어 여기(차등이 살아있는 horizon 뷰)가 진짜 edge 판정처.
    # 모델 적중률도 stored was_correct 대신 predicted_trend를 _judge_outcome로 재채점 —
    # baseline과 동일한 자(±2/5% 밴드)로 재서 사과 대 사과 비교가 되게 한다.
    if not rows:
        print("\n[5] 시간축 결과 없음")
        return
    print("\n[5] 시간축별 모델 vs 상수전략 (predicted_trend를 _judge_outcome로 동일 채점)")
    order = {"24h": 0, "3d": 1, "1w": 2, "1m": 3}
    by_h: dict[str, list[tuple]] = {}
    for h, trend, ret, _ in rows:
        by_h.setdefault(str(h), []).append((trend, ret))
    for h in sorted(by_h, key=lambda x: order.get(x, 99)):
        v = by_h[h]
        n = len(v)
        model = sum(_judge_outcome(t, r) for (t, r) in v) / n
        base = _baselines([(None, None, r, None) for (_, r) in v])
        best = max(base["always_BUY"], base["always_SELL"], base["always_HOLD"])
        edge = (model - best) * 100
        se = math.sqrt(model * (1 - model) / n) * 100
        tag = "✅유의" if edge > 1.96 * se else "✗노이즈"
        print(f"    {h:5s} 모델 {model * 100:5.1f}%  vs 최고상수 {best * 100:5.1f}%  "
              f"edge {edge:+5.1f}%p (1.96·SE≈{1.96 * se:.1f}) {tag}  (n={n})")


def _fetch(days: int | None):
    from shared.database.repositories.connection import db_cursor

    where = "was_correct IS NOT NULL AND actual_return_pct IS NOT NULL"
    params: list = []
    if days:
        where += " AND created_at > NOW() - (%s || ' days')::interval"
        params.append(days)
    with db_cursor() as (_, cur):
        cur.execute(
            f"SELECT decision, confidence, actual_return_pct, was_correct "
            f"FROM stock_analysis_memory WHERE {where}",
            tuple(params),
        )
        main = cur.fetchall()
        cur.execute(
            "SELECT horizon, predicted_trend, actual_return_pct, was_correct "
            "FROM stock_analysis_horizon_outcome "
            "WHERE was_correct IS NOT NULL AND actual_return_pct IS NOT NULL"
        )
        horizons = cur.fetchall()
    return main, horizons


def _selftest() -> None:
    # 밴드: BUY 적중 ret>+2, SELL 적중 ret<-2, HOLD 적중 |ret|≤5.
    # +3: BUY✓ SELL✗ HOLD✓ | -3: BUY✗ SELL✓ HOLD✓ | +6: BUY✓ SELL✗ HOLD✗ | +1: 전부 HOLD만✓
    rows = [(None, None, r, None) for r in (3.0, -3.0, 6.0, 1.0)]
    b = _baselines(rows)
    assert abs(b["always_BUY"] - 2 / 4) < 1e-9, b   # +3,+6
    assert abs(b["always_SELL"] - 1 / 4) < 1e-9, b  # -3
    assert abs(b["always_HOLD"] - 3 / 4) < 1e-9, b  # +3,-3,+1
    assert abs(b["market_up_rate"] - 3 / 4) < 1e-9, b  # +3,+6,+1
    assert _judge_outcome("BUY", 3.0) and not _judge_outcome("BUY", 1.0)
    print("selftest ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=None, help="최근 N일만 (기본: 전체)")
    ap.add_argument("--selftest", action="store_true", help="DB 없이 baseline 산식만 검증")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return
    main_rows, horizon_rows = _fetch(args.days)
    scope = f"최근 {args.days}일" if args.days else "전체"
    print(f"=== 캘리브레이션 해자 검증 ({scope}) ===")
    _report(main_rows)
    _report_horizons(horizon_rows)
    print("\n판정 기준: [2] edge가 노이즈(1.96·SE)를 넘고 [3] confidence가 실제로 변하며 단조 → "
          "해자 실재 → B2B2C 진행. 아니면 해자 미입증 → 축퇴 원인부터 고치고 재측정.")


if __name__ == "__main__":
    main()
