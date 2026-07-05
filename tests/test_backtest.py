"""백테스트 리스크·비용 오버레이 회귀 테스트 (네트워크 불필요).

_simulate의 손절/추격손절/비용 처리와 combined 앙상블이 실제로 동작하는지 검증한다.
실행: PYTHONPATH=. uv run python -m unittest tests/test_backtest.py -v
"""

import os
import sys
import unittest

import pandas as pd

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.app.services.trading.stock_analyzer import StockAnalyzer


def mkdf(closes, position=None):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    df = pd.DataFrame(
        {"Close": closes, "High": closes, "Low": closes, "Volume": [1000] * len(closes)},
        index=idx,
    )
    if position is not None:
        df["Position"] = position
    return df


class TestRiskOverlay(unittest.TestCase):
    def test_stop_loss_caps_loss_and_no_immediate_reentry(self):
        # i=1 진입(px=100) → i=2 px=90 (-10%)로 -8% 손절 발동
        df = mkdf([100, 100, 90, 95, 99], position=[0, 1, 1, 1, 1])
        out, trades = StockAnalyzer._simulate(df, 1_000_000, {"stop_loss_pct": 0.08, "fee_bps": 0})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["exit_reason"], "stop_loss")
        self.assertLessEqual(trades[0]["pnl_pct"], -0.08)
        # 손절 후 Position이 계속 1이어도 재진입하지 않음 → 마지막엔 현금(보유 0)
        self.assertEqual(int(out["Shares"].iloc[-1]), 0)

    def test_trailing_stop(self):
        # 고점 130 후 110으로 -15% → -12% 추격손절
        df = mkdf([100, 100, 120, 130, 110], position=[0, 1, 1, 1, 1])
        _, trades = StockAnalyzer._simulate(df, 1_000_000, {"trailing_stop_pct": 0.12, "fee_bps": 0})
        self.assertTrue(trades)
        self.assertEqual(trades[-1]["exit_reason"], "trailing_stop")

    def test_fees_reduce_final_value(self):
        pos = [0, 1, 1]
        no_fee, _ = StockAnalyzer._simulate(mkdf([100, 100, 110], pos), 1_000_000, {"fee_bps": 0})
        with_fee, _ = StockAnalyzer._simulate(mkdf([100, 100, 110], pos), 1_000_000, {"fee_bps": 100})
        self.assertLess(
            with_fee["Portfolio_Value"].iloc[-1], no_fee["Portfolio_Value"].iloc[-1]
        )

    def test_signal_exit_still_works_without_risk(self):
        # 리스크 미설정: 신호(-1)로만 청산
        df = mkdf([100, 100, 110, 120], position=[0, 1, 1, -1])
        _, trades = StockAnalyzer._simulate(df, 1_000_000, {})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["exit_reason"], "signal")
        self.assertGreater(trades[0]["pnl_pct"], 0)

    def test_combined_actually_trades_on_trend(self):
        # 평탄 구간 뒤 상승 — 교차가 웜업 경계가 아닌 내부 바에서 발생하도록(실데이터 근사)
        closes = [100.0] * 25 + [100.0 + i for i in range(1, 41)]
        a = StockAnalyzer("X", "2024-01-01", "2024-06-01")
        a.data = mkdf(closes)
        out = a._combined(a.data.copy())
        self.assertTrue((out["Signal"] == 1).any(), "상승 추세에서 combined가 진입 신호를 내야 함")


if __name__ == "__main__":
    unittest.main()
