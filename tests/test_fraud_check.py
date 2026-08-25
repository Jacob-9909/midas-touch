"""fraud_check 휴리스틱 스코어러 결정론 검증 — 오프라인에서 완결된다.

실행:
    PYTHONPATH=. uv run pytest tests/test_fraud_check.py -q
"""

import os
import sys
import unittest
from unittest import mock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()

from backend.app.services.agent.tools.fraud_check import (
    VERDICT_CAUTION_MIN,
    VERDICT_DANGER_MIN,
    format_report,
    fraud_check,
    scan_message,
    web_enrichment,
)

_DANGER_MESSAGE = (
    "절대 손실 없습니다! 월 30% 수익률을 보장합니다. "
    "https://bit.ly/xyzabc 에서 확인하고 오픈채팅으로 들어와 상담받으세요. "
    "가입 보증금 선입금 후 이용 가능합니다."
)
_CAUTION_MESSAGE = (
    "저희 리서치 그룹에서 수익률 보장은 어려워도 좋은 종목 알려드려요. "
    "자세한 건 텔레그램에서 만나요."
)
_BENIGN_MESSAGE = "코스피 지수 오늘 얼마야?"


class TestFraudScanVerdicts(unittest.TestCase):
    def test_danger_message_multi_category(self) -> None:
        """고수익 보장 + SNS 유도 + 선입금 + 짧은링크 → 위험."""
        report = scan_message(_DANGER_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertGreaterEqual(report.total_score, VERDICT_DANGER_MIN)
        categories = {s.category for s in report.signals}
        for expected in ("URL 위험", "고수익 보장", "SNS·오픈채팅 유도", "선입금 요구"):
            self.assertIn(expected, categories)

    def test_caution_message_single_category_mix(self) -> None:
        """수익률 보장(25) + 텔레그램 유도(10) = 35 → 주의."""
        report = scan_message(_CAUTION_MESSAGE)
        self.assertEqual(report.verdict, "주의")
        self.assertGreaterEqual(report.total_score, VERDICT_CAUTION_MIN)
        self.assertLess(report.total_score, VERDICT_DANGER_MIN)

    def test_benign_message_never_asserts_safety(self) -> None:
        """위험 신호 0점 → 확인필요(안전 단정 금지)."""
        report = scan_message(_BENIGN_MESSAGE)
        self.assertEqual(report.total_score, 0)
        self.assertEqual(report.verdict, "확인필요")
        body = format_report(report)
        self.assertIn("탐지된 위험 신호 없음", body)
        self.assertIn("안전을 보장하지 않습니다", body)

    def test_category_cap_limits_score(self) -> None:
        """같은 카테고리 다중 적중은 상한까지만 인정한다."""
        spam = " ".join(["선입금 필수", "먼저 입금 바람", "보증금 필요", "검증금 내세요"] * 3)
        report = scan_message(spam)
        advance_signals = [s for s in report.signals if s.category == "선입금 요구"]
        self.assertEqual(len(advance_signals), 1)
        self.assertLessEqual(advance_signals[0].score, 50)


class TestFraudScanUrlSignals(unittest.TestCase):
    def test_ip_host_url_flagged(self) -> None:
        report = scan_message("http://203.113.45.10/login 여기서 확인하세요")
        ip_signals = [s for s in report.signals if "IP 주소" in s.detail]
        self.assertEqual(len(ip_signals), 1)
        self.assertEqual(ip_signals[0].score, 30)

    def test_typosquat_brand_domain_flagged(self) -> None:
        report = scan_message("https://naver-secure-login.com/auth 에서 로그인하세요")
        typo_signals = [s for s in report.signals if "사칭 의심" in s.detail]
        self.assertEqual(len(typo_signals), 1)
        self.assertIn("naver", typo_signals[0].detail)

    def test_official_brand_domain_not_flagged(self) -> None:
        report = scan_message("https://www.naver.com 공식 사이트입니다")
        self.assertFalse(any("사칭 의심" in s.detail for s in report.signals))

    def test_shortener_alone_stays_low(self) -> None:
        report = scan_message("결과는 https://bit.ly/3xYz 에서 확인")
        self.assertTrue(any("짧은 링크" in s.detail for s in report.signals))
        self.assertEqual(report.verdict, "확인필요")


class TestFraudScanImpersonation(unittest.TestCase):
    def test_institution_with_coercion_and_advance_payment(self) -> None:
        """국세청 언급(15) + 압박 맥락(20) + 계좌 입금 요구(25) = 60 → 위험."""
        msg = "국세청입니다. 체납 혐의로 압류될 예정입니다. 즉시 아래 계좌로 입금하세요."
        report = scan_message(msg)
        impersonation = [s for s in report.signals if s.category == "정부기관 사칭 의심"]
        self.assertEqual(len(impersonation), 1)
        self.assertEqual(impersonation[0].score, 35)
        self.assertEqual(report.verdict, "위험")

    def test_explicit_sa_ching_word_scores_high(self) -> None:
        report = scan_message("금융감독원 사칭 문자가 돌고 있습니다")
        impersonation = [s for s in report.signals if s.category == "정부기관 사칭 의심"]
        # 기관명 언급(15) + "사칭"(30)
        self.assertEqual(impersonation[0].score, 45)


class TestFraudCheckToolAndNode(unittest.TestCase):
    def _offline_tool_output(self, message: str) -> str:
        env = dict(os.environ)
        env["FRAUD_CHECK_DISABLE_WEB"] = "1"
        with mock.patch.dict(os.environ, env, clear=True):
            return fraud_check.invoke({"message_text": message})

    def test_tool_output_has_verdict_and_report_guide(self) -> None:
        out = self._offline_tool_output(_DANGER_MESSAGE)
        self.assertIn("판정: 위험", out)
        self.assertIn("112", out)
        self.assertIn("1332", out)
        self.assertIn("절대 단정하지 않", out)

    def test_node_emits_tool_context_offline(self) -> None:
        from langchain_core.messages import HumanMessage

        from backend.app.services.agent.nodes.fraud_check import fraud_check_node

        state = {"messages": [HumanMessage(content=_DANGER_MESSAGE)]}
        ctx = fraud_check_node(state)["tool_context"]
        self.assertIn("[fraud_check 결과]", ctx[0])
        self.assertIn("판정: 위험", ctx[0])

    def test_web_enrichment_skips_gracefully_without_key(self) -> None:
        env = dict(os.environ)
        env.pop("TAVILY_API_KEY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            note = web_enrichment(_DANGER_MESSAGE)
        self.assertIn("웹 검색 보강 생략", note)


if __name__ == "__main__":
    unittest.main()
