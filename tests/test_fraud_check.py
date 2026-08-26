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

# 2026 금융 AI Challenge 실측 회귀 샘플 — 보이스피싱 상위 유형 미탐지("확인필요") 갭 검증용.
_FAMILY_IMPERSONATION_MESSAGE = (
    "엄마 나 사고났어. 경찰서에 있는데 지금 당장 300만원 이체해줘. 전화하지 마세요."
)
_LOAN_BINGJIP_MESSAGE = "저신용자·무직도 가능! 즉시대출 승인. 수수료 먼저 입금하시면 바로 송금드립니다."
_CRYPTO_LEADING_ROOM_MESSAGE = "비트코인 선물 리딩방 입장하세요. USDT 입금 후 수익 10배 보장합니다."
_REFUND_IMPERSONATION_MESSAGE = (
    "[국세청] 2025년 환급금 1,240,000원이 확정되었습니다. "
    "오늘까지 아래 링크에서 계좌를 입력하세요."
)
_PARTTIME_DEPOSIT_MESSAGE = "재택 부업 모집. 간단한 좋아요 작업으로 일당 15만원. 시작 전 보증금 5만원 필요합니다."
_CUSTOMS_NAME_THEFT_MESSAGE = "[국제우편] 세관 통관 중 명의도용 의심. 경찰 수사 협조를 위해 계좌 확인이 필요합니다."
_OFFICIAL_DOMAIN_MESSAGE = "네이버 메인 페이지가 잘 안 열려요. https://www.naver.com 여기서 로그아웃했다가 다시 해보세요."


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


class TestFraudScanVoicePhishingRegression(unittest.TestCase):
    """실측 회귀: 보이스피싱 상위 유형 6종이 기존에는 '확인필요'로 미탐지되었다."""

    def test_family_impersonation_is_danger(self) -> None:
        """지인 호칭 + 사고 + 이체 요구 + 은폐 지시 → 가족·지인 사칭 위험."""
        report = scan_message(_FAMILY_IMPERSONATION_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("가족·지인 사칭", {s.category for s in report.signals})

    def test_loan_bingjip_scam_is_danger(self) -> None:
        """저신용 타깃 + 즉시대출 + 수수료 선입금 → 대출 빙집 위험."""
        report = scan_message(_LOAN_BINGJIP_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("대출 빙집 사기", {s.category for s in report.signals})

    def test_crypto_leading_room_is_danger(self) -> None:
        """리딩방 + USDT 입금 + 10배 보장 → 가상자산 리딩방 위험."""
        report = scan_message(_CRYPTO_LEADING_ROOM_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("가상자산 리딩방", {s.category for s in report.signals})

    def test_refund_impersonation_is_danger(self) -> None:
        """국세청 환급금 + 오늘까지 링크 계좌 입력 → 환급·지원금 사칭 위험(60 이상)."""
        report = scan_message(_REFUND_IMPERSONATION_MESSAGE)
        self.assertGreaterEqual(report.total_score, VERDICT_DANGER_MIN)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("환급·지원금 사칭", {s.category for s in report.signals})

    def test_parttime_deposit_scam_is_danger(self) -> None:
        """재택 부업 모집 + 시작 전 보증금 → 알바·부업 보증금 사기 위험."""
        report = scan_message(_PARTTIME_DEPOSIT_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("알바·부업 보증금 사기", {s.category for s in report.signals})
        # 보증금 토큰은 선입금 요구 카테고리와 독립 가산된다.
        self.assertIn("선입금 요구", {s.category for s in report.signals})

    def test_customs_name_theft_stays_at_least_caution(self) -> None:
        """세관 통관 + 명의도용 + 경찰 수사 협조 → 정부기관 사칭 주의 이상."""
        report = scan_message(_CUSTOMS_NAME_THEFT_MESSAGE)
        self.assertGreaterEqual(report.total_score, VERDICT_CAUTION_MIN)
        self.assertLess(report.total_score, VERDICT_DANGER_MIN)
        self.assertIn("정부기관 사칭 의심", {s.category for s in report.signals})


# 2026-08 실측 평가(scripts/evaluate_fraud_detection.py, n=32)에서 미탐지였던 FN 5건 원문 —
# 어휘 갭 해소 회귀 검증용. 이 샘플은 verdict=="위험"을 유지해야 한다.
_FN_SURGERY_MOM_MESSAGE = (
    "엄마 나 폰 액정 깨져서 친구 폰으로 문자한다. 오늘 오후까지 수술비 200만원이 급하게 필요해. "
    "기존 번호는 연결이 안 되니 일단 계좌로 입금해주면 저녁에 전화할게. http://bit.ly/mom-help"
)
_FN_SON_TEMP_NUMBER_MESSAGE = (
    "[아들] 휴대폰 분실로 임시번호 사용 중. 회사 보증보험 해지 처리에 150만원 선입금이 "
    "필요하다고 한다. 내일까지 꼭 보내줘. 자세한 건 카톡으로 설명할게."
)
_FN_ACQUAINTANCE_BORROW_MESSAGE = (
    "저번에 밥 산 거 기억하지? 급하게 80만원만 빌려줘, 카드값 때문에 오늘까지만 필요해. "
    "번호 바꿨어. 먼저 송금해주면 이번 주 안에 정확히 갚을게."
)
_FN_SAMEDAY_LOAN_MESSAGE = (
    "[당일대출] 서류 없이 신청 즉시 500만원 입금. 신용등록·연체 이력 전부 가능. 조건 확인 후 "
    "수수료 먼저 입금해 주세요. 상담 http://t.ly/xYz9"
)
_FN_CYBER_POLICE_SAFE_ACCOUNT_MESSAGE = (
    "[경찰청 사이버수사과] 귀하 명의 불법 통장 적발로 자금 환수 절차가 진행 중입니다. "
    "금융감독원 지정 안전계좌로 즉시 입금하지 않으면 계좌 동결 및 압류됩니다."
)


class TestFraudScanEvalFnRegression(unittest.TestCase):
    """실측 평가 FN 5건 회귀 — 어휘 갭 해소 후에도 전부 '위험'으로 탐지되어야 한다."""

    def test_mom_surgery_transfer_is_danger(self) -> None:
        """엄마 호칭 + 수술비·폰 액정 긴급 + 입금해주면 → 가족·지인 사칭 위험."""
        report = scan_message(_FN_SURGERY_MOM_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("가족·지인 사칭", {s.category for s in report.signals})

    def test_son_lost_phone_temp_number_is_danger(self) -> None:
        """아들 호칭 + 휴대폰 분실·임시번호 + 선입금 요구 → 가족·지인 사칭 위험."""
        report = scan_message(_FN_SON_TEMP_NUMBER_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("가족·지인 사칭", {s.category for s in report.signals})

    def test_acquaintance_borrow_with_number_change_is_danger(self) -> None:
        """호칭이 없어도 급전 요구(빌려줘) + 번호 변경 결합으로 지인 사칭 위험."""
        report = scan_message(_FN_ACQUAINTANCE_BORROW_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("가족·지인 사칭", {s.category for s in report.signals})

    def test_same_day_loan_no_docs_is_danger(self) -> None:
        """당일대출·서류 없이·신청 즉시 문구 → 대출 빙집 위험."""
        report = scan_message(_FN_SAMEDAY_LOAN_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("대출 빙집 사기", {s.category for s in report.signals})

    def test_police_safe_account_threat_is_danger(self) -> None:
        """경찰청 사칭 + 안전계좌 입금 압박 → 정부기관 사칭 위험."""
        report = scan_message(_FN_CYBER_POLICE_SAFE_ACCOUNT_MESSAGE)
        self.assertEqual(report.verdict, "위험")
        self.assertIn("정부기관 사칭 의심", {s.category for s in report.signals})

    def test_borrow_request_without_contact_change_stays_low(self) -> None:
        """급전 요구 동사 단독은 조합이 아니므로 위험 판정하지 않는다(오탐 방지 가드)."""
        report = scan_message("급하게 10만원만 빌려줘, 주말까지 갚을게.")
        self.assertLess(report.total_score, VERDICT_DANGER_MIN)


class TestOfficialDomainRelief(unittest.TestCase):
    def test_all_official_hosts_get_relief_and_stay_unjudged(self) -> None:
        """공식 도메인만 있으면 URL 안심 감쇠 1회와 함께 확인필요를 유지한다."""
        report = scan_message(_OFFICIAL_DOMAIN_MESSAGE)
        relief = [s for s in report.signals if s.category == "URL 안심"]
        self.assertEqual(len(relief), 1)
        self.assertEqual(relief[0].score, -10)
        self.assertEqual(report.total_score, 0)
        self.assertEqual(report.verdict, "확인필요")

    def test_relief_not_given_when_non_official_host_present(self) -> None:
        """공식 도메인과 짧은링크가 섞이면 감쇠 없이 짧은링크 플래그만 부여된다."""
        report = scan_message("공식 공지 https://www.naver.com 요약본은 https://bit.ly/abc 참조")
        self.assertFalse(any(s.category == "URL 안심" for s in report.signals))
        self.assertTrue(any("짧은 링크" in s.detail for s in report.signals))


class TestDeterministicActionGuides(unittest.TestCase):
    def test_family_guide_rendered_with_report_numbers(self) -> None:
        """가족사칭 적중 시 결정론 행동 요령(1332 지급정지 안내)이 말미에 붙는다."""
        body = format_report(scan_message(_FAMILY_IMPERSONATION_MESSAGE))
        self.assertIn("### 권장 행동 요령", body)
        self.assertIn("1332", body)

    def test_guides_merge_without_duplication(self) -> None:
        """복수 카테고리 적중 시 각 요령이 한 번씩만 출력된다."""
        body = format_report(scan_message(_CRYPTO_LEADING_ROOM_MESSAGE))
        self.assertEqual(body.count("### 권장 행동 요령"), 1)
        self.assertIn("리딩방 수익 보장은 전부 사기입니다", body)

    def test_no_guide_section_without_matched_category(self) -> None:
        """매칭된 카테고리가 없으면 행동 요령 섹션 자체를 출력하지 않는다."""
        body = format_report(scan_message(_BENIGN_MESSAGE))
        self.assertNotIn("권장 행동 요령", body)


if __name__ == "__main__":
    unittest.main()
