"""wealth_advisor 이식 기능 단위 테스트 (오프라인·결정적).

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_wealth_integration.py -v

외부 네트워크/DB/LLM에 의존하지 않는다:
- 라이브 리서치 노드는 키를 빈 값으로 강제해 graceful degrade(명확한 미수행 문구)만 검증.
- 주식 백테스트 엔진은 합성 가격 데이터로 결정적으로 검증(yfinance 미호출).
- 청약 응답 평탄화/상태 판정은 가짜 row dict로 검증.
"""

import os
import sys
import unittest
from datetime import date, timedelta
from unittest import mock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import numpy as np
import pandas as pd
from langchain_core.messages import HumanMessage

_EMPTY_KEYS = {
    "NAVER_CLIENT_ID": "",
    "NAVER_CLIENT_SECRET": "",
    "TAVILY_API_KEY": "",
    "LAW_GO_KR_OC": "",
}


class TestResearchNodesGracefulDegrade(unittest.TestCase):
    """키 미설정 시 그래프를 죽이지 않고 명확한 '미수행' 문구를 tool_context에 넣는지."""

    def _state(self) -> dict:
        return {"messages": [HumanMessage(content="연금저축 금리 동향과 국세청 유권해석")], "tax_asset_types": []}

    @mock.patch.dict(os.environ, _EMPTY_KEYS, clear=False)
    def test_all_three_nodes_degrade(self) -> None:
        from backend.app.services.agent.nodes import (
            news_research_node,
            nts_law_research_node,
            product_research_node,
        )

        for node, marker in (
            (product_research_node, "product_research 미수행"),
            (news_research_node, "news_research 미수행"),
            (nts_law_research_node, "nts_law_research 미수행"),
        ):
            ctx = node(self._state())["tool_context"]
            self.assertEqual(len(ctx), 1)
            self.assertIn(marker, ctx[0])

    def test_nts_query_derivation(self) -> None:
        from backend.app.services.agent.nodes.nts_law_research import _derive_queries

        state = {
            "messages": [HumanMessage(content="연금저축이랑 양도소득세 절세 방법 알려줘")],
            "tax_asset_types": ["주식"],
        }
        q = _derive_queries(state)
        self.assertIn("연금저축", q)
        self.assertIn("양도소득세", q)  # 텍스트 + 자산매핑(주식→양도소득세) 중복 제거
        self.assertEqual(len(q), len(set(q)))  # 중복 없음


class TestIntentRoutingExtended(unittest.TestCase):
    """키워드 폴백이 신규 라이브 리서치 노드로 라우팅되는지(LLM 미사용)."""

    def test_keyword_fallback_routes_live_tools(self) -> None:
        from backend.app.services.agent.nodes.intent import _keyword_route

        self.assertIn("product_research", _keyword_route("정기예금 우대금리 가입 조건"))
        self.assertIn("news_research", _keyword_route("기준금리 인상 전망과 흐름"))
        self.assertIn("nts_law_research", _keyword_route("국세청 유권해석 예규 좀"))


class TestConversationalActionNodes(unittest.TestCase):
    """대화형 액션 노드(stock_backtest·cheongyak_lookup) graceful 동작."""

    def test_stock_backtest_no_ticker_guides(self) -> None:
        from backend.app.services.agent.nodes import stock_backtest_node

        ctx = stock_backtest_node({"messages": [HumanMessage(content="백테스트 해줘")]})["tool_context"]
        self.assertEqual(len(ctx), 1)
        self.assertIn("stock_backtest 안내", ctx[0])

    @mock.patch.dict(os.environ, {"CHEONGYAK_API_KEY": "", "DATA_GO_KR_API_KEY": ""}, clear=False)
    def test_cheongyak_lookup_no_key_degrades(self) -> None:
        from backend.app.services.agent.nodes import cheongyak_lookup_node

        ctx = cheongyak_lookup_node({"messages": [HumanMessage(content="청약 알려줘")]})["tool_context"]
        self.assertEqual(len(ctx), 1)
        self.assertIn("cheongyak_lookup 미수행", ctx[0])

    def test_stock_quick_no_ticker_guides(self) -> None:
        from backend.app.services.agent.nodes import stock_quick_node

        ctx = stock_quick_node({"messages": [HumanMessage(content="기술적 분석 해줘")]})["tool_context"]
        self.assertEqual(len(ctx), 1)
        self.assertIn("stock_quick 안내", ctx[0])

    def test_keyword_route_action_tools(self) -> None:
        from backend.app.services.agent.nodes.intent import _keyword_route

        self.assertIn("stock_backtest", _keyword_route("삼성전자 백테스트 해줘"))
        self.assertIn("cheongyak_lookup", _keyword_route("요즘 분양 청약 뭐 있어"))

    def test_keyword_route_stock_quick(self) -> None:
        from backend.app.services.agent.nodes.intent import _keyword_route

        self.assertIn("stock_quick", _keyword_route("엔비디아 지금 어때?"))
        self.assertIn("stock_quick", _keyword_route("삼성전자 RSI 알려줘"))  # 대문자 RSI
        # 백테스트와 구분되는지(서로 침범 안 함)
        self.assertNotIn("stock_backtest", _keyword_route("엔비디아 지금 어때?"))


class TestStockAnalyzer(unittest.TestCase):
    """백테스트 엔진을 합성 데이터로 결정적으로 검증(yfinance 미호출)."""

    def _analyzer(self):
        from backend.app.services.trading import StockAnalyzer

        n = 80
        idx = pd.date_range("2023-01-01", periods=n, freq="D")
        # 상승 추세 + 사인파 → 교차/시그널이 실제로 발생하도록.
        close = 100 + np.linspace(0, 20, n) + 5 * np.sin(np.linspace(0, 6 * np.pi, n))
        df = pd.DataFrame(
            {
                "Open": close,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": np.full(n, 1_000_000),
            },
            index=idx,
        )
        a = StockAnalyzer("TEST", "2023-01-01", "2023-03-22", initial_capital=10_000_000)
        a.data = df
        return a

    def test_backtest_metrics_and_chart(self) -> None:
        res = self._analyzer().backtest("sma_crossover")
        self.assertEqual(res["ticker"], "TEST")
        self.assertEqual(res["strategy"], "sma_crossover")
        for key in ("total_return", "buy_hold_return", "annual_return", "max_drawdown", "total_trades", "final_value"):
            self.assertIn(key, res["metrics"])
        self.assertIsInstance(res["chart_data"], list)
        self.assertGreater(len(res["chart_data"]), 0)
        self.assertIn("date", res["chart_data"][0])
        self.assertIn("close", res["chart_data"][0])

    def test_all_strategies_run(self) -> None:
        from backend.app.services.trading import STRATEGY_LABELS

        for strat in STRATEGY_LABELS:
            res = self._analyzer().backtest(strat)
            self.assertEqual(res["strategy"], strat)

    def test_unknown_strategy_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._analyzer().backtest("does_not_exist")


class TestQuickAnalysis(unittest.TestCase):
    """quick_analysis() + 지표 헬퍼 결정적 검증 (yfinance 미호출)."""

    def _analyzer_with_data(self):
        from backend.app.services.trading import StockAnalyzer

        n = 250
        idx = pd.date_range("2022-01-01", periods=n, freq="D")
        close = 100 + np.linspace(0, 30, n) + 8 * np.sin(np.linspace(0, 8 * np.pi, n))
        df = pd.DataFrame(
            {"Open": close, "High": close + 1.5, "Low": close - 1.5, "Close": close, "Volume": np.full(n, 1_000_000)},
            index=idx,
        )
        a = StockAnalyzer("QA_TEST", "2022-01-01", "2022-09-07")
        a.data = df
        return a

    def test_quick_analysis_keys(self) -> None:
        qa = self._analyzer_with_data().quick_analysis()
        for key in ("ticker", "current_price", "change_pct", "rsi", "macd", "kdj",
                    "moving_averages", "bollinger", "atr", "levels"):
            self.assertIn(key, qa)
        self.assertIn("value", qa["rsi"])
        self.assertIn("signal", qa["rsi"])
        self.assertIn("histogram", qa["macd"])
        self.assertIn("k", qa["kdj"])
        self.assertIsNotNone(qa["moving_averages"]["sma200"])  # 250봉 → SMA200 가능

    def test_rsi_range(self) -> None:
        qa = self._analyzer_with_data().quick_analysis()
        self.assertGreaterEqual(qa["rsi"]["value"], 0)
        self.assertLessEqual(qa["rsi"]["value"], 100)

    def test_enhanced_backtest_metrics(self) -> None:
        """win_rate, sharpe_ratio, profit_factor, trades 목록 포함 검증."""
        a = self._analyzer_with_data()
        res = a.backtest("sma_crossover")
        m = res["metrics"]
        for key in ("win_rate", "sharpe_ratio", "profit_factor", "avg_win_pct", "avg_loss_pct"):
            self.assertIn(key, m)
        self.assertGreaterEqual(m["win_rate"], 0.0)
        self.assertLessEqual(m["win_rate"], 1.0)
        self.assertIsInstance(res["trades"], list)
        if res["trades"]:
            t = res["trades"][0]
            self.assertIn("entry_date", t)
            self.assertIn("exit_date", t)
            self.assertIn("pnl_pct", t)


class TestAnalysisMemory(unittest.TestCase):
    """분석 메모리 유사도 로직 + graceful degrade (DB 미사용)."""

    def _ind(self, rsi=55, macd="bullish", ma="bullish", vol="medium") -> dict:
        return {
            "rsi": {"value": rsi},
            "macd": {"signal": macd},
            "moving_averages": {"trend": ma},
            "atr": {"volatility": vol},
        }

    def test_extract(self) -> None:
        from backend.app.services.trading.analysis_memory import _extract

        rsi, macd, ma, vol = _extract(self._ind(62, "bullish", "mixed", "high"))
        self.assertEqual(rsi, 62)
        self.assertEqual(macd, "bullish")
        self.assertEqual(ma, "mixed")
        self.assertEqual(vol, "high")

    def test_extract_defaults_on_empty(self) -> None:
        from backend.app.services.trading.analysis_memory import _extract

        rsi, macd, ma, vol = _extract({})
        self.assertEqual(rsi, 50)
        self.assertEqual((macd, ma, vol), ("neutral", "mixed", "medium"))

    def test_similarity_identical_is_max(self) -> None:
        from backend.app.services.trading.analysis_memory import _similarity

        a = self._ind(55, "bullish", "bullish", "medium")
        # 동일 지표 → 0.3(rsi 만점) + 0.3 + 0.25 + 0.15 = 1.0
        self.assertAlmostEqual(_similarity(a, a), 1.0, places=6)

    def test_similarity_opposite_low(self) -> None:
        from backend.app.services.trading.analysis_memory import _SIM_THRESHOLD, _similarity

        cur = self._ind(20, "bullish", "bullish", "low")
        hist = self._ind(80, "bearish", "bearish", "high")  # RSI 60차 → rsi_score 0, 나머지 불일치
        sim = _similarity(cur, hist)
        self.assertLess(sim, _SIM_THRESHOLD)

    def test_similarity_rsi_partial(self) -> None:
        from backend.app.services.trading.analysis_memory import _similarity

        cur = self._ind(50, "bearish", "mixed", "low")
        hist = self._ind(65, "bullish", "bullish", "high")  # RSI 15차 → 0.3*(1-0.5)=0.15
        self.assertAlmostEqual(_similarity(cur, hist), 0.15, places=6)

    def test_vol_similar(self) -> None:
        from backend.app.services.trading.analysis_memory import _vol_similar

        self.assertTrue(_vol_similar("high", "high"))
        self.assertTrue(_vol_similar("medium", "high"))  # medium은 약하게 근접
        self.assertFalse(_vol_similar("high", "low"))

    def test_safe_json(self) -> None:
        from backend.app.services.trading.analysis_memory import _safe_json

        self.assertEqual(_safe_json({"a": 1}, {}), {"a": 1})  # 이미 dict
        self.assertEqual(_safe_json('{"a": 1}', {}), {"a": 1})  # 문자열 파싱
        self.assertEqual(_safe_json("not json", {"d": 1}), {"d": 1})  # 실패 → default
        self.assertEqual(_safe_json(None, []), [])

    def test_format_similar_patterns(self) -> None:
        from backend.app.services.trading.ai_analysis import _format_similar_patterns

        self.assertEqual(_format_similar_patterns([]), "")
        self.assertEqual(_format_similar_patterns(None), "")
        txt = _format_similar_patterns([
            {"decision": "BUY", "similarity": 0.8, "created_at": "2024-01-02T00:00:00",
             "was_correct": True, "actual_return_pct": 3.5, "summary": "상승 모멘텀"},
        ])
        self.assertIn("BUY", txt)
        self.assertIn("적중", txt)
        self.assertIn("+3.5%", txt)

    def test_memory_graceful_degrade(self) -> None:
        """_available=False면 모든 작업이 안전한 기본값(빈 결과)을 반환."""
        from backend.app.services.trading.analysis_memory import AnalysisMemory

        m = AnalysisMemory.__new__(AnalysisMemory)  # __init__(DB 접근) 건너뜀
        m._available = False
        self.assertEqual(m.get_similar_patterns("AAPL", self._ind()), [])
        self.assertIsNone(m.store("AAPL", self._ind(), {"decision": "BUY"}))
        self.assertEqual(m.validate_recent()["validated"], 0)
        self.assertEqual(m.get_stats()["total"], 0)


class TestCheongyakParsing(unittest.TestCase):
    """공공데이터 row → 프론트 dict 평탄화 + 상태 판정(네트워크 미사용)."""

    def test_status_for(self) -> None:
        from backend.app.services.cheongyak.api_client import _status_for

        today = date.today()
        future = (today + timedelta(days=5)).isoformat()
        past = (today - timedelta(days=5)).isoformat()

        self.assertEqual(_status_for({"RCEPT_BGNDE": future, "RCEPT_ENDDE": future}), "접수예정")
        self.assertEqual(_status_for({"RCEPT_BGNDE": past, "RCEPT_ENDDE": past}), "마감")
        self.assertEqual(_status_for({"RCEPT_BGNDE": past, "RCEPT_ENDDE": future}), "접수중")
        self.assertEqual(_status_for({}), "일정미정")

    def test_row_to_summary(self) -> None:
        from backend.app.services.cheongyak.api_client import _row_to_summary

        row = {
            "HOUSE_MANAGE_NO": "2024000001",
            "PBLANC_NO": "2024000001",
            "HOUSE_NM": "테스트 아파트",
            "HOUSE_SECD_NM": "APT",
            "SUBSCRPT_AREA_CODE_NM": "서울",
            "HSSPLY_ADRES": "서울시 강남구",
            "TOT_SUPLY_HSHLDCO": 100,
            "RCRIT_PBLANC_DE": "2024-01-01",
        }
        out = _row_to_summary(row)
        self.assertEqual(out["house_nm"], "테스트 아파트")
        self.assertEqual(out["region"], "서울")
        self.assertEqual(out["total_supply"], 100)
        self.assertIn("status", out)


if __name__ == "__main__":
    unittest.main()
