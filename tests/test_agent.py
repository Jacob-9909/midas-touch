"""Midas Touch 백엔드 에이전트 & DB 헬퍼 통합 테스트.

실행:
    PYTHONPATH=. uv run python -m unittest tests/test_agent.py -v

DB(localhost Postgres/Neo4j)와 NVIDIA NIM 연동을 전제로 하는 통합 테스트다.
NVIDIA_API_KEY가 없으면 LLM이 필요한 테스트는 skip된다.
"""

import logging
import os
import sys
import unittest

try:
    import truststore
    truststore.inject_into_ssl()
except Exception as exc:
    # truststore가 없거나 주입에 실패해도 테스트는 돈다(certifi 번들로 폴백). 다만 사내망 등
    # 시스템 인증서가 필요한 환경에선 이후 TLS 실패의 원인이 되므로 조용히 넘기지 않는다.
    logging.getLogger(__name__).debug("truststore 미적용 — 시스템 인증서 대신 기본 번들 사용: %s", exc)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()

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
    """intent 분기 그래프 멀티턴 + 도구 라우팅 end-to-end 검증."""

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

        # 턴 1: 유사 투자자 벤치마크 → intent가 검색 도구를 라우팅해야 한다
        # 핸들러를 HTTP 없이 직접 부르므로 Depends가 주입되지 않는다 — auth_uuid를 명시로 넘긴다.
        r1 = chat(ChatRequest(session_id=thread, message="나와 비슷한 투자자들의 자산 배분을 보여줘.", user_uuid=self.uuid), auth_uuid=self.uuid)
        self.assertTrue(r1.reply)

        # 턴 1의 라우팅 결과 검증 (route 필드는 턴마다 갱신되므로 턴2 전에 확인)
        state_t1 = agent.get_state(config)
        self.assertTrue(
            set(state_t1.values.get("route") or []) & {"persona_rag", "graph_rag", "tax_and_market_lookup"}
        )

        # 턴 2: 멀티턴 메모리 — 이전 맥락 참조
        r2 = chat(ChatRequest(session_id=thread, message="방금 내용 중 핵심 하나만 다시 짚어줘.", user_uuid=self.uuid), auth_uuid=self.uuid)
        self.assertTrue(r2.reply)

        # 멀티턴 누적(턴1 user + 응답 + 턴2 user + 응답)으로 4개 초과
        state = agent.get_state(config)
        self.assertGreater(len(state.values["messages"]), 4)

    def test_anonymous_browser_uuid_chat(self) -> None:
        from backend.app.api.chat import ChatRequest, chat

        res = chat(ChatRequest(session_id="test-anon-session", message="간단히 인사해줘.", user_uuid="anon-browser-uuid-0000"), auth_uuid="anon-browser-uuid-0000")
        self.assertTrue(res.reply)


if __name__ == "__main__":
    unittest.main()
