"""DB·LLM·네트워크 없이 도는 순수 로직 회귀 테스트.

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_unit.py -v

이번 리팩터로 추가/변경된 로직(세법 필터·시장지표 게이팅·intent short-circuit·ChatService
프로필/404·세션 목록 매핑·GraphRAG 질의 재사용)을 외부 의존성 스텁으로 검증한다.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# tax_and_market_lookup — 자산 필터 + 시장지표 게이팅
# ---------------------------------------------------------------------------
class TestTaxTool(unittest.TestCase):
    def setUp(self) -> None:
        import backend.app.services.agent.tools.tax_lookup as tl

        self.tl = tl
        self._orig_rules = tl.get_all_tax_rules
        self._orig_snaps = tl.get_latest_market_snapshots
        tl.get_all_tax_rules = lambda: [
            {"asset_type": "주식", "income_type": "양도", "tax_rate": 0.22, "local_tax_rate": 0.022,
             "deduction_limit": None, "description": "주식 양도", "legal_basis": "소득세법"},
            {"asset_type": "채권", "income_type": "이자", "tax_rate": 0.15, "local_tax_rate": 0.015,
             "deduction_limit": None, "description": "채권 이자", "legal_basis": "소득세법"},
            {"asset_type": "부동산", "income_type": "양도", "tax_rate": 0.40, "local_tax_rate": 0.04,
             "deduction_limit": None, "description": "부동산 양도", "legal_basis": "소득세법"},
        ]
        tl.get_latest_market_snapshots = lambda: [
            {"data_type": "exchange_rate", "sub_key": "USD/KRW", "value": 1350.0,
             "unit": "원", "snapshot_date": "2026-06-18"},
        ]

    def tearDown(self) -> None:
        self.tl.get_all_tax_rules = self._orig_rules
        self.tl.get_latest_market_snapshots = self._orig_snaps

    def test_no_filter_returns_all_assets(self) -> None:
        out = self.tl.tax_and_market_lookup.invoke({"asset_types": []})
        for a in ("주식", "채권", "부동산"):
            self.assertIn(a, out)

    def test_single_asset_filter(self) -> None:
        out = self.tl.tax_and_market_lookup.invoke({"asset_types": ["주식"]})
        self.assertIn("주식", out)
        self.assertNotIn("채권", out)
        self.assertNotIn("부동산", out)

    def test_multi_asset_filter(self) -> None:
        out = self.tl.tax_and_market_lookup.invoke({"asset_types": ["주식", "채권"]})
        self.assertIn("주식", out)
        self.assertIn("채권", out)
        self.assertNotIn("부동산", out)

    def test_include_market_true_dumps_indicators(self) -> None:
        out = self.tl.tax_and_market_lookup.invoke({"asset_types": [], "include_market": True})
        self.assertIn("최신 시장 지표", out)
        self.assertIn("USD/KRW", out)

    def test_include_market_false_omits_indicators(self) -> None:
        out = self.tl.tax_and_market_lookup.invoke({"asset_types": ["주식"], "include_market": False})
        self.assertNotIn("최신 시장 지표", out)
        self.assertNotIn("USD/KRW", out)


# ---------------------------------------------------------------------------
# tax_lookup_node._needs_market — 시장지표 포함 판단
# ---------------------------------------------------------------------------
class TestNeedsMarket(unittest.TestCase):
    def test_market_keyword_forces_include(self) -> None:
        from backend.app.services.agent.nodes.tax_lookup import _needs_market

        self.assertTrue(_needs_market("주식 양도세랑 환율 알려줘", ["주식"]))

    def test_asset_specific_without_market_excludes(self) -> None:
        from backend.app.services.agent.nodes.tax_lookup import _needs_market

        self.assertFalse(_needs_market("주식 양도세 얼마야", ["주식"]))

    def test_general_query_includes(self) -> None:
        from backend.app.services.agent.nodes.tax_lookup import _needs_market

        self.assertTrue(_needs_market("세금 전반 알려줘", []))


# ---------------------------------------------------------------------------
# intent — smalltalk short-circuit + 키워드 폴백
# ---------------------------------------------------------------------------
class TestIntentRouting(unittest.TestCase):
    def test_smalltalk_detected(self) -> None:
        from backend.app.services.agent.nodes.intent import _is_smalltalk

        for t in ("안녕하세요", "고마워요", "반갑습니다", "하이"):
            self.assertTrue(_is_smalltalk(t), t)

    def test_data_question_not_smalltalk(self) -> None:
        from backend.app.services.agent.nodes.intent import _is_smalltalk

        for t in ("주식 양도세 얼마야?", "안녕, 환율 알려줘", "포트폴리오 추천해줘"):
            self.assertFalse(_is_smalltalk(t), t)

    def test_long_message_not_smalltalk(self) -> None:
        from backend.app.services.agent.nodes.intent import _is_smalltalk

        self.assertFalse(_is_smalltalk("안녕하세요 " * 5))

    def test_keyword_route_buckets(self) -> None:
        from backend.app.services.agent.nodes.intent import _keyword_route

        self.assertIn("persona_rag", _keyword_route("또래 자산배분 알려줘"))
        self.assertIn("tax_and_market_lookup", _keyword_route("세율 공제 한도"))
        self.assertIn("graph_rag", _keyword_route("법령 근거가 뭐야"))
        # 모호하면 graph_rag로 근거 확보
        self.assertEqual(_keyword_route("음 글쎄"), ["graph_rag"])

    def test_keyword_route_doc_rag(self) -> None:
        from backend.app.services.agent.nodes.intent import _keyword_route

        self.assertIn("doc_rag", _keyword_route("국내 상장주식 양도소득세 대주주 기준"))
        self.assertIn("doc_rag", _keyword_route("증여재산공제 한도가 얼마인가요"))
        self.assertNotIn("doc_rag", _keyword_route("음 글쎄"))


class TestPassageCleanupHeuristic(unittest.TestCase):
    """emb_passages 쓰레기 판정 — 한글 비율이 낮아도 유효한 표는 살아남아야 한다."""

    def test_junk_detected(self) -> None:
        from pipelines.embedding.cleanup_passages import is_junk

        self.assertTrue(is_junk("-" * 200))  # 표 구분선
        self.assertTrue(is_junk("| | | |\n" * 50))  # 빈 표 셀
        self.assertTrue(is_junk("+IV+o9H4hX6j0fiFvqPR" * 30))  # base64 이미지 잔해

    def test_valid_low_hangul_table_kept(self) -> None:
        from pipelines.embedding.cleanup_passages import is_junk

        # 한글 비율 0.2 미만이지만 실제 세율표 — 살아남아야 한다.
        self.assertFalse(
            is_junk(
                "표 2: 1세대 1주택 장기보유특별공제율\n\n"
                "| 구 분 | 3년~ | 4년~ | 5년~ |\n|---|---|---|---|\n"
                "| 보유기간 | 12% | 16% | 20% |\n| 거주기간 | 12(8)% | 16% | 20% |"
            )
        )


# ---------------------------------------------------------------------------
# ChatService — 프로필 포맷 / 404 / 제목 절삭
# ---------------------------------------------------------------------------
class TestChatService(unittest.TestCase):
    def test_profile_context_formats_amounts(self) -> None:
        import backend.app.services.chat_service as cs

        prof = dict(
            age=35, sex="남", occupation="개발자", family_type="1인", housing_type="전세",
            district="강남", total_amount=100000000, monthly_income=5000000,
            monthly_investable=2000000, stock_amount=50000000, bond_amount=10000000,
            deposit_amount=30000000, real_estate_amount=10000000, aggressiveness=7,
            financial_literacy=8, preferred_asset="주식", specific_items="삼성전자",
            target_return_percent=10, investable_period_months=24,
        )
        ctx = cs._build_profile_context(prof)
        self.assertIn("100,000,000", ctx)
        self.assertIn("개발자", ctx)

    def test_require_profile_raises_404(self) -> None:
        import backend.app.services.chat_service as cs
        from fastapi import HTTPException

        svc = object.__new__(cs.ChatService)  # __init__(에이전트 생성) 우회
        orig = cs.get_user_by_uuid
        cs.get_user_by_uuid = lambda u: None
        try:
            with self.assertRaises(HTTPException) as ctx:
                svc._require_profile("nope")
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            cs.get_user_by_uuid = orig

    def test_title_trim(self) -> None:
        import backend.app.services.chat_service as cs

        self.assertEqual(len(("가" * 100)[: cs._TITLE_MAX]), 40)


# ---------------------------------------------------------------------------
# /chat/sessions 매핑 — 테이블 행 → 응답(제목 폴백, updated_at ISO)
# ---------------------------------------------------------------------------
class TestSessionsEndpoint(unittest.TestCase):
    def test_sessions_mapping(self) -> None:
        import backend.app.api.chat as chat

        orig = chat.list_chat_sessions
        chat.list_chat_sessions = lambda user_uuid=None, limit=50: [
            {"session_id": "s1", "user_uuid": "u1", "title": "주식 질문",
             "message_count": 4, "updated_at": datetime(2026, 6, 18, tzinfo=timezone.utc)},
            {"session_id": "s2", "user_uuid": None, "title": None,
             "message_count": 0, "updated_at": None},
        ]
        try:
            out = chat.chat_sessions(user_uuid=None, limit=50)
        finally:
            chat.list_chat_sessions = orig

        sessions = out["sessions"]
        self.assertEqual(sessions[0]["title"], "주식 질문")
        self.assertTrue(sessions[0]["updated_at"].startswith("2026-06-18"))
        # title None → 폴백, updated_at None 유지
        self.assertEqual(sessions[1]["title"], "새 대화")
        self.assertIsNone(sessions[1]["updated_at"])


# ---------------------------------------------------------------------------
# /api/v1/query — GraphRAG 검색 재사용 + 응답 직렬화
# ---------------------------------------------------------------------------
class TestQueryRouter(unittest.TestCase):
    def test_query_reuses_retrieval_and_serializes(self) -> None:
        import backend.app.api.query as q

        orig_retrieve = q.retrieve_graph_context
        orig_llm = q.build_chat_model
        q.retrieve_graph_context = lambda query: (["(A:Tax) -[R]-> (B:Law)"], ["근거 본문1", "근거 본문2"])

        class _Reply:
            content = "최종 답변"

        class _LLM:
            def invoke(self, prompt):
                # 프롬프트에 검색 컨텍스트가 주입됐는지 확인
                assert "(A:Tax)" in prompt and "근거 본문1" in prompt
                return _Reply()

        q.build_chat_model = lambda temperature=0.0: _LLM()
        try:
            resp = q.query_graph_rag(q.QueryRequest(query="질문"))
        finally:
            q.retrieve_graph_context = orig_retrieve
            q.build_chat_model = orig_llm

        self.assertEqual(resp.response, "최종 답변")
        self.assertEqual(resp.subgraph_triplets, ["(A:Tax) -[R]-> (B:Law)"])
        self.assertEqual(resp.source_texts, ["근거 본문1", "근거 본문2"])


if __name__ == "__main__":
    unittest.main()
