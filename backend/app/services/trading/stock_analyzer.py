"""Stock backtesting engine — ported from Stock-trading/main.py for web use.

Thread-safe: all mutable state lives on the instance, never on the class.
No print/matplotlib — returns pure data dicts for JSON serialisation.

QuantDinger-inspired additions:
- quick_analysis(): technical indicator snapshot (RSI-Wilder, MACD, KDJ, SMA, BB, ATR)
- Enhanced backtest(): win_rate, sharpe_ratio, profit_factor + trades list
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from itertools import product

import numpy as np
import pandas as pd
import yfinance as yf


# ── Technical indicator helpers (QuantDinger-style, no external lib) ──────────

def _rsi_wilder_last(closes: np.ndarray, period: int = 14) -> float:
    """Wilder RSI for the last bar (matches QuantDinger compute_rsi_wilder)."""
    n = len(closes)
    if n < period + 1:
        return 50.0
    changes = np.diff(closes.astype(float))
    gains = np.where(changes > 0, changes, 0.0)
    losses = np.where(changes < 0, -changes, 0.0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100.0 - (100.0 / (1.0 + avg_gain / avg_loss)), 2)


def _ema_series(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average series."""
    k = 2.0 / (period + 1)
    ema = np.empty(len(values))
    ema[0] = values[0]
    for i in range(1, len(values)):
        ema[i] = values[i] * k + ema[i - 1] * (1 - k)
    return ema


def _kdj_last(
    high: np.ndarray, low: np.ndarray, close: np.ndarray,
    period: int = 9, k_smooth: int = 3, d_smooth: int = 3,
) -> tuple[float, float, float]:
    """KDJ last K/D/J (K/D seed=50, CN terminal convention, same as QuantDinger)."""
    n = len(close)
    if n < period:
        return 50.0, 50.0, 50.0
    k_prev, d_prev = 50.0, 50.0
    for i in range(period - 1, n):
        h_max = float(np.max(high[max(0, i - period + 1):i + 1]))
        l_min = float(np.min(low[max(0, i - period + 1):i + 1]))
        hl = h_max - l_min
        rsv = (float(close[i]) - l_min) / hl * 100.0 if hl > 0 else 50.0
        k_prev = (k_prev * (k_smooth - 1) + rsv) / k_smooth
        d_prev = (d_prev * (d_smooth - 1) + k_prev) / d_smooth
    j = 3.0 * k_prev - 2.0 * d_prev
    return round(k_prev, 2), round(d_prev, 2), round(j, 2)


def _atr_last(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
    """Average True Range for the last bar."""
    if len(close) < 2:
        return float(np.mean(high - low))
    h, l, pc = high[1:].astype(float), low[1:].astype(float), close[:-1].astype(float)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return round(float(np.mean(tr[-min(period, len(tr)):])), 6)

# ── Default parameters ────────────────────────────────────
DEFAULT_PARAMS: dict[str, dict] = {
    "sma_crossover": {"short_window": 3, "long_window": 15},
    "macd": {"fast": 8, "slow": 17, "signal": 12},
    "rsi": {"window": 14, "buy_th": 45, "sell_th": 65},
    "bollinger": {"bol_window": 20},
    "obv": {"obv_window": 10},
    # 리스크·비용 오버레이 — 전 전략 공통. 진입가 기준 손절/익절/추격손절과 편도 거래비용.
    # None = 해당 규칙 미적용. 신호 청산보다 리스크 청산이 우선한다.
    "risk": {
        "stop_loss_pct": 0.08,      # 진입가 대비 -8% 하드 손절
        "take_profit_pct": None,    # 익절 목표(미사용; 예: 0.25)
        "trailing_stop_pct": 0.12,  # 보유 중 고점 대비 -12% 추격 손절
        "fee_bps": 5,               # 편도 거래비용 5bp(0.05%) — 매수·매도 각각 적용
    },
}

GRID_RANGES: dict[str, dict] = {
    "sma_crossover": {
        "short_window": [3, 4, 5, 6, 7, 10],
        "long_window": [10, 13, 15, 17, 20, 25, 30],
    },
    "macd": {"fast": [5, 8, 12], "slow": [10, 17, 26], "signal": [5, 9, 12]},
    "rsi": {
        "window": [7, 10, 14, 20],
        "buy_th": [30, 35, 40, 45],
        "sell_th": [55, 60, 65, 70],
    },
    "bollinger": {"bol_window": [5, 7, 10, 15, 20, 25, 30]},
    "obv": {"obv_window": [3, 4, 5, 6, 7, 10]},
}

STRATEGY_LABELS: dict[str, str] = {
    "sma_crossover": "SMA 교차",
    "macd": "MACD",
    "rsi": "RSI",
    "bollinger": "볼린저 밴드",
    "obv": "OBV",
    "combined": "복합 전략",
}

COMBINED_THRESHOLD = 3


class StockAnalyzer:
    """Stateless-safe stock analyser."""

    def __init__(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        initial_capital: int = 100_000_000,
        params: dict[str, dict] | None = None,
    ) -> None:
        self.ticker = ticker.upper()
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.params = copy.deepcopy(params or DEFAULT_PARAMS)
        self.data: pd.DataFrame | None = None

    # ── data download ──────────────────────────────────
    def fetch_data(self) -> pd.DataFrame:
        df = yf.download(
            self.ticker,
            start=self.start_date,
            end=self.end_date,
            auto_adjust=False,
            progress=False,
        )
        if df.empty:
            raise ValueError(f"{self.ticker}에 대한 데이터를 가져올 수 없습니다.")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        self.data = df
        return df

    # ── strategy methods ───────────────────────────────
    def _sma(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params["sma_crossover"]
        data["SMA_short"] = data["Close"].rolling(p["short_window"]).mean()
        data["SMA_long"] = data["Close"].rolling(p["long_window"]).mean()
        data["Signal"] = 0
        data.loc[
            (data["SMA_short"] > data["SMA_long"])
            & (data["SMA_short"].shift(1) <= data["SMA_long"].shift(1)),
            "Signal",
        ] = 1
        data.loc[
            (data["SMA_short"] < data["SMA_long"])
            & (data["SMA_short"].shift(1) >= data["SMA_long"].shift(1)),
            "Signal",
        ] = -1
        data["Position"] = data["Signal"].replace(0, np.nan).ffill().fillna(0)
        return data

    def _macd(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params["macd"]
        data["EMA_fast"] = data["Close"].ewm(span=p["fast"], adjust=False).mean()
        data["EMA_slow"] = data["Close"].ewm(span=p["slow"], adjust=False).mean()
        data["MACD"] = data["EMA_fast"] - data["EMA_slow"]
        data["Signal_Line"] = data["MACD"].ewm(span=p["signal"], adjust=False).mean()
        data["Signal"] = 0
        data.loc[
            (data["MACD"] > data["Signal_Line"])
            & (data["MACD"].shift(1) <= data["Signal_Line"].shift(1)),
            "Signal",
        ] = 1
        data.loc[
            (data["MACD"] < data["Signal_Line"])
            & (data["MACD"].shift(1) >= data["Signal_Line"].shift(1)),
            "Signal",
        ] = -1
        data["Position"] = data["Signal"].replace(0, np.nan).ffill().fillna(0)
        return data

    def _rsi(self, data: pd.DataFrame) -> pd.DataFrame:
        p = self.params["rsi"]
        delta = data["Close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(p["window"]).mean()
        avg_loss = loss.rolling(p["window"]).mean()
        rs = avg_gain / avg_loss
        data["RSI"] = 100 - (100 / (1 + rs))
        data["Signal"] = 0
        data.loc[
            (data["RSI"] > p["buy_th"]) & (data["RSI"].shift(1) <= p["buy_th"]),
            "Signal",
        ] = 1
        data.loc[
            (data["RSI"] < p["sell_th"]) & (data["RSI"].shift(1) >= p["sell_th"]),
            "Signal",
        ] = -1
        data["Position"] = data["Signal"].replace(0, np.nan).ffill().fillna(0)
        return data

    def _bollinger(self, data: pd.DataFrame) -> pd.DataFrame:
        w = self.params["bollinger"]["bol_window"]
        data["BB_mid"] = data["Close"].rolling(w).mean()
        data["BB_std"] = data["Close"].rolling(w).std()
        data["Upper_band"] = data["BB_mid"] + data["BB_std"] * 2
        data["Lower_band"] = data["BB_mid"] - data["BB_std"] * 2
        data["Signal"] = 0
        data.loc[
            (data["Close"] > data["Lower_band"])
            & (data["Close"].shift(1) < data["Lower_band"].shift(1)),
            "Signal",
        ] = 1
        data.loc[
            (data["Close"] < data["Upper_band"])
            & (data["Close"].shift(1) > data["Upper_band"].shift(1)),
            "Signal",
        ] = -1
        data["Position"] = data["Signal"].replace(0, np.nan).ffill().fillna(0)
        return data

    def _obv(self, data: pd.DataFrame) -> pd.DataFrame:
        w = self.params["obv"]["obv_window"]
        data["OBV"] = np.where(
            data["Close"] > data["Close"].shift(1),
            data["Volume"],
            np.where(data["Close"] < data["Close"].shift(1), -data["Volume"], 0),
        )
        data["OBV"] = data["OBV"].cumsum()
        data["OBV_SMA"] = data["OBV"].rolling(w).mean()
        data["Signal"] = 0
        data.loc[
            (data["OBV"] > data["OBV_SMA"])
            & (data["OBV"].shift(1) <= data["OBV_SMA"].shift(1)),
            "Signal",
        ] = 1
        data.loc[
            (data["OBV"] < data["OBV_SMA"])
            & (data["OBV"].shift(1) >= data["OBV_SMA"].shift(1)),
            "Signal",
        ] = -1
        data["Position"] = data["Signal"].replace(0, np.nan).ffill().fillna(0)
        return data

    def _combined(self, data: pd.DataFrame) -> pd.DataFrame:
        # 종전엔 '같은 바에서 3개 이상이 동시에 교차 신호'를 요구해 사실상 거래가 거의 없었다.
        # 교차 신호는 순간적이라 동시 정렬이 드물기 때문. 대신 각 하위 전략의 '현재 스탠스'
        # (Position: 매수 후 +1 유지, 매도 후 -1)를 다수결로 합산해 3표 이상 강세면 진입,
        # 3표 이상 약세면 청산하는 히스테리시스 앙상블로 바꾼다(휩쏘 억제 + 실제 거래 발생).
        stances = []
        for name, fn in self._strat_map().items():
            if name == "combined":
                continue
            tmp = fn(data.copy())
            stances.append(tmp["Position"].fillna(0))

        net = sum(stances)  # 대략 -5..+5 범위의 순 강세표
        data["Signal"] = 0
        data.loc[net >= COMBINED_THRESHOLD, "Signal"] = 1
        data.loc[net <= -COMBINED_THRESHOLD, "Signal"] = -1
        data["Position"] = data["Signal"].replace(0, np.nan).ffill().fillna(0)
        return data

    def _strat_map(self) -> dict:
        return {
            "sma_crossover": self._sma,
            "macd": self._macd,
            "rsi": self._rsi,
            "bollinger": self._bollinger,
            "obv": self._obv,
            "combined": self._combined,
        }

    # ── quick technical analysis (QuantDinger fast-analysis style) ────────────
    def quick_analysis(self) -> dict:
        """Technical indicator snapshot of the most recent bar.

        Returns RSI-Wilder, MACD, KDJ, SMA20/50/200, Bollinger Bands, ATR,
        support/resistance — no backtest, just current state.
        """
        if self.data is None or self.data.empty:
            raise ValueError("데이터가 비어 있습니다. fetch_data()를 먼저 호출하세요.")

        df = self.data
        close = df["Close"].values.astype(float)
        high = df["High"].values.astype(float)
        low = df["Low"].values.astype(float)
        n = len(close)

        current_price = float(close[-1])
        prev_price = float(close[-2]) if n > 1 else current_price
        change_pct = (current_price - prev_price) / prev_price if prev_price else 0.0

        # RSI Wilder(14)
        rsi_val = _rsi_wilder_last(close, 14)
        rsi_signal = "oversold" if rsi_val < 30 else "overbought" if rsi_val > 70 else "neutral"

        # MACD (12, 26, 9)
        ema12 = _ema_series(close, 12)
        ema26 = _ema_series(close, 26)
        macd_arr = ema12 - ema26
        sig_arr = _ema_series(macd_arr, 9)
        hist_val = float(macd_arr[-1] - sig_arr[-1])

        # KDJ (9, 3, 3)
        kdj_k, kdj_d, kdj_j = _kdj_last(high, low, close)

        # SMA 20 / 50 / 200
        close_s = pd.Series(close)
        sma20 = float(close_s.rolling(20).mean().iloc[-1]) if n >= 20 else None
        sma50 = float(close_s.rolling(50).mean().iloc[-1]) if n >= 50 else None
        sma200 = float(close_s.rolling(200).mean().iloc[-1]) if n >= 200 else None

        def _gt(a: float | None, b: float | None) -> bool:
            return a is not None and b is not None and a > b

        if _gt(current_price, sma20) and _gt(sma20, sma50):
            ma_trend = "bullish"
        elif not _gt(current_price, sma20) and not _gt(current_price, sma50):
            ma_trend = "bearish"
        else:
            ma_trend = "mixed"

        # Bollinger Bands (20, 2σ)
        if n >= 20:
            bb_mid = float(close_s.rolling(20).mean().iloc[-1])
            bb_std = float(close_s.rolling(20).std().iloc[-1])
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            pct_b = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        else:
            bb_mid = bb_upper = bb_lower = current_price
            pct_b = 0.5

        # ATR (14)
        atr_val = _atr_last(high, low, close)
        atr_pct = atr_val / current_price if current_price > 0 else 0.0
        volatility = "high" if atr_pct > 0.03 else "low" if atr_pct < 0.01 else "medium"

        # Support / Resistance (last 20 bars)
        lb = min(20, n)
        support = round(float(np.min(low[-lb:])), 4)
        resistance = round(float(np.max(high[-lb:])), 4)

        return {
            "ticker": self.ticker,
            "current_price": round(current_price, 4),
            "change_pct": round(change_pct, 6),
            "rsi": {"value": rsi_val, "signal": rsi_signal},
            "macd": {
                "line": round(float(macd_arr[-1]), 6),
                "signal_line": round(float(sig_arr[-1]), 6),
                "histogram": round(hist_val, 6),
                "signal": "bullish" if hist_val > 0 else "bearish",
            },
            "kdj": {"k": kdj_k, "d": kdj_d, "j": kdj_j},
            "moving_averages": {
                "sma20": round(sma20, 4) if sma20 is not None else None,
                "sma50": round(sma50, 4) if sma50 is not None else None,
                "sma200": round(sma200, 4) if sma200 is not None else None,
                "trend": ma_trend,
            },
            "bollinger": {
                "upper": round(bb_upper, 4),
                "mid": round(bb_mid, 4),
                "lower": round(bb_lower, 4),
                "pct_b": round(pct_b, 4),
            },
            "atr": {
                "value": round(atr_val, 4),
                "pct": round(atr_pct, 6),
                "volatility": volatility,
            },
            "levels": {"support": support, "resistance": resistance},
        }

    # ── simulation ─────────────────────────────────────
    @staticmethod
    def _simulate(
        data: pd.DataFrame, capital: int, risk: dict | None = None
    ) -> tuple[pd.DataFrame, list[dict]]:
        """신호 + 리스크·비용 오버레이로 체결을 시뮬레이션한다.

        리스크 청산(손절/익절/추격손절)은 신호 청산보다 우선한다. 리스크로 청산된 뒤에는
        하위 전략 스탠스(Position)가 새 교차로 다시 +1이 될 때까지 재진입하지 않는다(즉시 재매수 방지).
        실제 체결 기반 거래 목록(exit_reason 포함)을 함께 반환해 지표가 현실을 반영하게 한다.
        """
        risk = risk or {}
        sl = risk.get("stop_loss_pct")
        tp = risk.get("take_profit_pct")
        ts = risk.get("trailing_stop_pct")
        fee = (risk.get("fee_bps") or 0) / 10000.0

        cash = float(capital)
        shares = 0
        entry_px = 0.0
        peak_px = 0.0
        entry_date = ""

        n = len(data)
        cash_arr = np.zeros(n)
        shares_arr = np.zeros(n)
        port_arr = np.zeros(n)
        in_market = np.zeros(n)
        closes = data["Close"].values
        positions = data["Position"].values
        idx = data.index
        trades: list[dict] = []

        cash_arr[0] = cash
        port_arr[0] = cash

        for i in range(1, n):
            c, s = cash, shares
            px = float(closes[i])
            exit_reason = None

            # 1) 보유 중이면 리스크 청산을 먼저 판정하고, 없으면 신호 청산을 본다.
            if s > 0:
                if px > peak_px:
                    peak_px = px
                ret = (px - entry_px) / entry_px if entry_px else 0.0
                draw = (px - peak_px) / peak_px if peak_px else 0.0
                if sl is not None and ret <= -sl:
                    exit_reason = "stop_loss"
                elif tp is not None and ret >= tp:
                    exit_reason = "take_profit"
                elif ts is not None and draw <= -ts:
                    exit_reason = "trailing_stop"
                elif positions[i] == -1 and positions[i - 1] >= 0:
                    exit_reason = "signal"

            if s > 0 and exit_reason is not None:
                c += s * px * (1 - fee)
                pnl_pct = (px - entry_px) / entry_px if entry_px else 0.0
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": str(idx[i])[:10],
                    "entry_price": round(entry_px, 4),
                    "exit_price": round(px, 4),
                    "pnl_pct": round(pnl_pct, 6),
                    "exit_reason": exit_reason,
                })
                s = 0
            # 2) 미보유 + 신규 매수 교차면 진입(비용 반영해 매수 가능 수량 산정).
            elif s == 0 and positions[i] == 1 and positions[i - 1] <= 0:
                buy_shares = int(c // (px * (1 + fee)))
                if buy_shares > 0:
                    c -= buy_shares * px * (1 + fee)
                    s = buy_shares
                    entry_px = px
                    peak_px = px
                    entry_date = str(idx[i])[:10]

            cash, shares = c, s
            cash_arr[i] = cash
            shares_arr[i] = shares
            port_arr[i] = cash + shares * px
            in_market[i] = 1.0 if shares > 0 else 0.0

        data["Cash"] = cash_arr
        data["Shares"] = shares_arr
        data["Portfolio_Value"] = port_arr
        data["In_Market"] = in_market
        return data, trades

    # ── backtest ───────────────────────────────────────
    def backtest(self, strategy_name: str = "sma_crossover") -> dict:
        if self.data is None or self.data.empty:
            raise ValueError("데이터가 비어 있습니다. fetch_data()를 먼저 호출하세요.")

        strat_fn = self._strat_map().get(strategy_name)
        if not strat_fn:
            raise ValueError(f"지원하지 않는 전략: {strategy_name}")

        data = strat_fn(self.data.copy())
        data, trades = self._simulate(data, self.initial_capital, self.params.get("risk"))

        data["Returns"] = data["Close"].pct_change()
        data["Cumulative_Returns"] = (1 + data["Returns"]).cumprod()
        data["Strategy_Cumulative"] = data["Portfolio_Value"] / self.initial_capital

        total_return = float(data["Strategy_Cumulative"].iloc[-1] - 1)
        buy_hold = float(data["Cumulative_Returns"].iloc[-1] - 1)
        days = (data.index[-1] - data.index[0]).days
        annual = ((1 + total_return) ** (365 / days) - 1) if days > 0 else 0.0
        rolling_max = data["Strategy_Cumulative"].cummax()
        max_dd = float((data["Strategy_Cumulative"] / rolling_max - 1).min())

        # 거래 목록은 _simulate가 실제 체결(리스크 청산 포함) 기준으로 산출한다.
        total_trades = len(trades) * 2  # buy + sell = 2 signals per round trip

        # 시장 노출도(보유 바 비율)와 청산 사유 분포 — 전략의 실제 동작을 드러내는 지표.
        exposure = float(np.nanmean(data["In_Market"].values[1:])) if len(data) > 1 else 0.0
        exit_reasons: dict[str, int] = {}
        for t in trades:
            r = t.get("exit_reason", "signal")
            exit_reasons[r] = exit_reasons.get(r, 0) + 1

        # ── enhanced metrics ───────────────────────────
        win_ts = [t for t in trades if t["pnl_pct"] > 0]
        loss_ts = [t for t in trades if t["pnl_pct"] <= 0]
        win_rate = len(win_ts) / len(trades) if trades else 0.0
        total_win = sum(t["pnl_pct"] for t in win_ts)
        total_loss = abs(sum(t["pnl_pct"] for t in loss_ts))
        profit_factor = (total_win / total_loss) if total_loss > 0 else (float("inf") if total_win > 0 else 0.0)
        avg_win_pct = total_win / len(win_ts) if win_ts else 0.0
        avg_loss_pct = sum(t["pnl_pct"] for t in loss_ts) / len(loss_ts) if loss_ts else 0.0
        strat_rets = data["Portfolio_Value"].pct_change().dropna()
        sharpe = float(strat_rets.mean() / strat_rets.std() * (252 ** 0.5)) if float(strat_rets.std()) > 0 else 0.0

        # chart data — serialisable list[dict]
        chart = self._to_chart_data(data, strategy_name)

        self.data = data
        return {
            "metrics": {
                "total_return": round(total_return, 6),
                "buy_hold_return": round(buy_hold, 6),
                "annual_return": round(annual, 6),
                "max_drawdown": round(max_dd, 6),
                "total_trades": total_trades,
                "final_value": int(data["Portfolio_Value"].iloc[-1]),
                "win_rate": round(win_rate, 4),
                "sharpe_ratio": round(sharpe, 4),
                "profit_factor": round(min(profit_factor, 99.0), 4),
                "avg_win_pct": round(avg_win_pct, 6),
                "avg_loss_pct": round(avg_loss_pct, 6),
                "exposure_pct": round(exposure, 4),
                "exit_reasons": exit_reasons,
            },
            "trades": trades,
            "chart_data": chart,
            "strategy": strategy_name,
            "ticker": self.ticker,
            "params_used": self.params.get(strategy_name, {}),
            "risk_used": self.params.get("risk", {}),
        }

    def _to_chart_data(self, data: pd.DataFrame, strategy: str) -> list[dict]:
        cols = ["Close", "Signal", "Portfolio_Value", "Cumulative_Returns", "Strategy_Cumulative"]
        # add strategy-specific indicator columns
        extra = {
            "sma_crossover": ["SMA_short", "SMA_long"],
            "macd": ["MACD", "Signal_Line"],
            "rsi": ["RSI"],
            "bollinger": ["Upper_band", "Lower_band", "BB_mid"],
            "obv": ["OBV", "OBV_SMA"],
        }
        for c in extra.get(strategy, []):
            if c in data.columns:
                cols.append(c)

        subset = data[cols].copy()
        subset.index = subset.index.strftime("%Y-%m-%d")
        subset = subset.replace([np.inf, -np.inf], None)
        subset = subset.where(pd.notnull(subset), None)
        records = []
        for date, row in subset.iterrows():
            d = {"date": date}
            for c in cols:
                v = row[c]
                d[c.lower()] = round(float(v), 4) if v is not None else None
            records.append(d)
        return records

    # ── grid search ────────────────────────────────────
    def grid_search(self, strategy_name: str) -> dict:
        """Run grid search, return final summary."""
        results = list(self.grid_search_stream(strategy_name))
        if not results:
            return {"best_params": {}, "best_return": 0.0, "results_count": 0}
        best = max(results, key=lambda r: r["total_return"])
        return {
            "best_params": best["params"],
            "best_return": best["total_return"],
            "results_count": len(results),
        }

    def grid_search_stream(self, strategy_name: str):
        """Yield each result as it's computed — for SSE streaming."""
        if self.data is None or self.data.empty:
            raise ValueError("데이터가 비어 있습니다.")
        ranges = GRID_RANGES.get(strategy_name)
        if not ranges:
            raise ValueError(f"그리드 서치를 지원하지 않는 전략: {strategy_name}")

        keys = list(ranges.keys())
        all_combos = list(product(*[ranges[k] for k in keys]))

        # filter invalid combos upfront
        valid = []
        for vals in all_combos:
            p = dict(zip(keys, vals))
            if strategy_name == "sma_crossover" and p["short_window"] >= p["long_window"]:
                continue
            if strategy_name == "macd" and p["fast"] >= p["slow"]:
                continue
            if strategy_name == "rsi" and p["buy_th"] >= p["sell_th"]:
                continue
            valid.append(p)

        total = len(valid)
        best_ret = None
        best_params: dict = {}

        for i, p in enumerate(valid):
            analyzer = StockAnalyzer(
                self.ticker, self.start_date, self.end_date, self.initial_capital,
                params={**copy.deepcopy(self.params), strategy_name: p},
            )
            analyzer.data = self.data.copy()
            try:
                res = analyzer.backtest(strategy_name)
                ret = res["metrics"]["total_return"]
            except Exception:
                continue

            is_best = best_ret is None or ret > best_ret
            if is_best:
                best_ret = ret
                best_params = p

            yield {
                "index": i + 1,
                "total": total,
                "params": p,
                "total_return": round(ret, 6),
                "is_best": is_best,
                "current_best_params": best_params,
                "current_best_return": round(best_ret, 6),
            }
