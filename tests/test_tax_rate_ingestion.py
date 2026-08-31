"""세율 개정안 인입 미리보기 검증 — 추출→검증→현행 대비 비교(DB·네트워크 불필요).

추출은 휴리스틱 경로(use_llm=False)만 검증한다(오프라인 결정론). 반영(승인) 단계는 없다 —
세율은 코드 상수(rates.RATE_REGISTRY)로만 결정되는 결정론 불변식을 지키기 위해 런타임 오버레이
변경 경로를 제거했다. 이 파이프라인은 근거 확인용 읽기 전용 미리보기다.

실행:
    PYTHONPATH=. uv run pytest tests/test_tax_rate_ingestion.py -q
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()

from backend.app.services.tax.rate_diff import diff_against_current
from backend.app.services.tax.rate_extraction import (
    ProposedRate,
    ProposedRateSet,
    extract_rate_set,
    heuristic_extract,
)
from backend.app.services.tax.rate_validation import validate_proposed

_SAMPLE_AMENDMENT = (
    "2026년 귀속 세법개정안 요약\n"
    "- 해외주식 양도소득세율을 20%에서 22%로 상향한다.\n"
    "- 이자·배당 분리과세율은 15.4%로 유지한다.\n"
    "- 금융소득종합과세 기준을 2,000만원에서 3,000만원으로 상향한다.\n"
)


class TestHeuristicExtraction(unittest.TestCase):
    def test_extracts_new_rate_from_amendment(self) -> None:
        proposed = heuristic_extract(_SAMPLE_AMENDMENT, year="2026")
        changed = proposed.changed_fields()
        # "20%에서 22%로" → 개정 후 22%
        self.assertAlmostEqual(changed["foreign_stock_national_rate"].value, 0.22)
        # 단일 값 15.4% 그대로
        self.assertAlmostEqual(changed["interest_dividend_withholding_rate"].value, 0.154)
        # "2,000만원에서 3,000만원으로" → 3천만
        self.assertEqual(
            changed["financial_income_total_tax_threshold"].value, 30_000_000
        )

    def test_extract_rate_set_falls_back_to_heuristic_without_llm(self) -> None:
        proposed = extract_rate_set(_SAMPLE_AMENDMENT, year="2026", use_llm=False)
        self.assertEqual(proposed.year, "2026")
        self.assertIn("foreign_stock_national_rate", proposed.changed_fields())


class TestValidation(unittest.TestCase):
    def test_valid_set_passes(self) -> None:
        proposed = heuristic_extract(_SAMPLE_AMENDMENT, year="2026")
        self.assertEqual(validate_proposed(proposed), [])

    def test_rate_over_one_is_flagged(self) -> None:
        bad = ProposedRateSet(
            year="2026", foreign_stock_national_rate=ProposedRate(value=1.5)
        )
        issues = validate_proposed(bad)
        self.assertTrue(any("0~1" in i for i in issues))

    def test_empty_extraction_is_flagged(self) -> None:
        issues = validate_proposed(ProposedRateSet(year="2026"))
        self.assertTrue(any("하나도" in i for i in issues))

    def test_bad_year_is_flagged(self) -> None:
        proposed = ProposedRateSet(
            year="26", foreign_stock_national_rate=ProposedRate(value=0.22)
        )
        self.assertTrue(any("귀속연도" in i for i in validate_proposed(proposed)))


class TestDiff(unittest.TestCase):
    def test_diff_shows_old_and_new(self) -> None:
        proposed = heuristic_extract(_SAMPLE_AMENDMENT, year="2026")
        diffs = {d.field: d for d in diff_against_current(proposed)}
        fx = diffs["foreign_stock_national_rate"]
        self.assertEqual(fx.old_value, 0.20)
        self.assertEqual(fx.new_value, 0.22)
        self.assertTrue(fx.changed)
        # 유지된 항목은 변화 없음으로 표시
        self.assertFalse(diffs["interest_dividend_withholding_rate"].changed)


class TestDetectYear(unittest.TestCase):
    def test_detect_year_from_utterance(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import _detect_year

        self.assertEqual(_detect_year("2024년 기준 양도세 알려줘"), "2024")
        self.assertIsNone(_detect_year("해외주식 양도세 계산해줘"))


class TestApiFlow(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from backend.app.main import app

        self.client = TestClient(app)

    def test_extract_preview_flow(self) -> None:
        res = self.client.post(
            "/api/v1/tax-rates/extract",
            json={"text": _SAMPLE_AMENDMENT, "year": "2026", "use_llm": False},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["validation_passed"])
        self.assertEqual(body["issues"], [])
        self.assertTrue(any(d["field"] == "foreign_stock_national_rate" for d in body["diff"]))

    def test_current_returns_code_constants(self) -> None:
        # 반영 경로가 없으므로 현행 세율은 항상 코드 상수(해외주식 20%)다 — 결정론 불변식.
        res = self.client.get("/api/v1/tax-rates/current", params={"year": "2026"})
        self.assertEqual(res.status_code, 200)
        rate = res.json()["rates"]["foreign_stock_national_rate"]["value"]
        self.assertAlmostEqual(rate, 0.20)

    def test_text_file_upload(self) -> None:
        res = self.client.post(
            "/api/v1/tax-rates/extract/upload",
            files={"file": ("amend.txt", _SAMPLE_AMENDMENT.encode("utf-8"), "text/plain")},
            data={"year": "2026", "use_llm": "false"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(
            any(d["field"] == "foreign_stock_national_rate" for d in res.json()["diff"])
        )

    def test_pdf_upload_uses_parser(self) -> None:
        # 실제 PDF·파서 라이브러리 없이, PDF→텍스트 추출 지점만 주입해 배선을 검증한다.
        from backend.app.api import tax_rates as tr

        original = tr._pdf_to_text
        tr._pdf_to_text = lambda _raw: _SAMPLE_AMENDMENT
        try:
            res = self.client.post(
                "/api/v1/tax-rates/extract/upload",
                files={"file": ("amend.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={"year": "2026", "use_llm": "false"},
            )
        finally:
            tr._pdf_to_text = original
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["validation_passed"])

    def test_unsupported_suffix_rejected(self) -> None:
        res = self.client.post(
            "/api/v1/tax-rates/extract/upload",
            files={"file": ("amend.docx", b"x", "application/octet-stream")},
            data={"year": "2026"},
        )
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
