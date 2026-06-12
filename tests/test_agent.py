"""Midas Touch 백엔드 에이전트 & DB 헬퍼 통합 테스트.

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_agent.py -v

DB(localhost Postgres/Neo4j)와 NVIDIA NIM 연동을 전제로 하는 통합 테스트다.
NVIDIA_API_KEY가 없으면 LLM이 필요한 테스트는 skip된다.
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage

from backend.app.services.agent.tools import graph_rag, persona_rag, tax_and_market_lookup
from shared.database.connector import (
    get_all_tax_rules,
    get_latest_market_snapshots,
    get_user_by_uuid,
    search_similar_personas_db,
)


def _first_user_uuid() -> str | None:
    """테스트용으로 persona_embeddings에 존재하는 실제 user_uuid 하나를 가져온다."""
    import psycopg2

    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        with conn.cursor() as cur:
            cur.execute("SELECT azure_user_uuid FROM persona_embeddings LIMIT 1")
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


class TestDatabaseHelpers(unittest.TestCase):
    """shared.database.connector 조회 헬퍼 검증."""

    def test_get_all_tax_rules(self) -> None:
        rules = get_all_tax_rules()
        self.assertIsInstance(rules, list)
        if rules:
            self.assertIn("asset_type", rules[0])
            self.assertIn("tax_rate", rules[0])

    def test_get_latest_market_snapshots(self) -> None:
        snapshots = get_latest_market_snapshots()
        self.assertIsInstance(snapshots, list)
        if snapshots:
            self.assertIn("snapshot_date", snapshots[0])
            self.assertIn("data_type", snapshots[0])
            self.assertIn("value", snapshots[0])

    def test_persona_vector_search_and_join(self) -> None:
        """pgvector 유사도 검색 + Users 프로필 조인 (1024차원 bge-m3 공간)."""
        mock_embedding = [0.01] * 1024
        results = search_similar_personas_db(mock_embedding, top_k=2)
        self.assertIsInstance(results, list)
        if results:
            res = results[0]
            self.assertIn("azure_user_uuid", res)
            self.assertIn("similarity", res)
            profile = get_user_by_uuid(res["azure_user_uuid"])
            self.assertIsNotNone(profile)


class TestAgentTools(unittest.TestCase):
    """LangGraph 도구가 독립적으로 정상 컨텍스트를 반환하는지 검증."""

    def test_persona_rag_tool(self) -> None:
        out = persona_rag.invoke({"query": "30대 직장인, 주식·부동산 투자 성향", "top_k": 2})
        self.assertIsInstance(out, str)
        self.assertIn("유사 성향 투자자", out)

    def test_tax_and_market_lookup_tool(self) -> None:
        out = tax_and_market_lookup.invoke({})
        self.assertIsInstance(out, str)
        self.assertIn("세법 규칙", out)

    def test_graph_rag_tool(self) -> None:
        """Neo4j 1024차원 인덱스에 대해 차원 불일치 없이 검색되는지 확인."""
        out = graph_rag.invoke({"query": "주식 양도소득세 근거 법령"})
        self.assertIsInstance(out, str)
        self.assertIn("지식 그래프 관계망", out)


class TestAgentEndToEnd(unittest.TestCase):
    """create_react_agent 멀티턴 + 도구 라우팅 end-to-end 검증."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.uuid = _first_user_uuid()

    def setUp(self) -> None:
        if not os.environ.get("NVIDIA_API_KEY"):
            self.skipTest("NVIDIA_API_KEY 미설정 — LLM 통합 테스트 skip")
        if not self.uuid:
            self.skipTest("persona_embeddings에 테스트용 user_uuid 없음")

    def test_multiturn_and_tool_routing(self) -> None:
        from backend.app.api.chat import ChatRequest, chat
        from backend.app.services.agent.graph import get_agent

        thread = "test-e2e-multiturn"
        config = {"configurable": {"thread_id": thread}}
        agent = get_agent()

        # 턴 1: 유사 투자자 벤치마크 → persona_rag 라우팅 기대
        r1 = chat(ChatRequest(session_id=thread, message="나와 비슷한 투자자들의 자산 배분을 보여줘.", user_uuid=self.uuid))
        self.assertTrue(r1.reply)

        # 턴 2: 멀티턴 메모리 — 이전 맥락 참조
        r2 = chat(ChatRequest(session_id=thread, message="방금 내용 중 핵심 하나만 다시 짚어줘.", user_uuid=self.uuid))
        self.assertTrue(r2.reply)

        state = agent.get_state(config)
        tools_called = [
            tc["name"]
            for m in state.values["messages"]
            if isinstance(m, AIMessage)
            for tc in (m.tool_calls or [])
        ]
        # 적어도 하나의 검색 도구가 호출되어야 한다
        self.assertTrue(set(tools_called) & {"persona_rag", "graph_rag", "tax_and_market_lookup"})
        # 멀티턴 누적(턴1 user + 응답 + 턴2 user + 응답)으로 4개 초과
        self.assertGreater(len(state.values["messages"]), 4)

    def test_unknown_user_returns_404(self) -> None:
        from fastapi import HTTPException

        from backend.app.api.chat import ChatRequest, chat

        with self.assertRaises(HTTPException) as ctx:
            chat(ChatRequest(session_id="test-404", message="안녕", user_uuid="nonexistent-uuid-0000"))
        self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
