"""세율 개정안 인입 파이프라인 검증 — 추출→검증→비교→승인→반영(DB·네트워크 불필요).

추출은 휴리스틱 경로(use_llm=False)만 검증한다(오프라인 결정론). 오버레이는 임시 파일로
격리해 기존 2025 계산·테스트에 영향을 주지 않는다.

실행:
    PYTHONPATH=. uv run pytest tests/test_tax_rate_ingestion.py -q
"""

import os
import sys
import tempfile
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
from backend.app.services.tax.rate_overlay import apply_overlay, build_overlaid_set
from backend.app.services.tax.rate_validation import validate_proposed
from backend.app.services.tax.rates import get_rates

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


class TestOverlayApplyAndGetRates(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — setUp/tearDown 수명주기라 컨텍스트 매니저 부적합
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.close()
        os.environ["TAX_RATE_OVERLAY_PATH"] = self._tmp.name

    def tearDown(self) -> None:
        os.environ.pop("TAX_RATE_OVERLAY_PATH", None)
        os.unlink(self._tmp.name)

    def test_apply_then_get_rates_reflects_new_rate(self) -> None:
        proposed = heuristic_extract(_SAMPLE_AMENDMENT, year="2026")
        apply_overlay(proposed)

        r2026 = get_rates("2026")
        self.assertEqual(r2026.year, "2026")
        self.assertAlmostEqual(r2026.foreign_stock_national_rate.value, 0.22)
        # 개정 안 된 필드는 기본(2025) 세트에서 이어받음
        self.assertEqual(
            r2026.foreign_stock_basic_deduction.value, 2_500_000
        )

    def test_default_year_unaffected_by_overlay(self) -> None:
        apply_overlay(heuristic_extract(_SAMPLE_AMENDMENT, year="2026"))
        # 2025는 오버레이 대상이 아니므로 20% 유지
        self.assertAlmostEqual(get_rates("2025").foreign_stock_national_rate.value, 0.20)

    def test_no_overlay_returns_none(self) -> None:
        self.assertIsNone(build_overlaid_set("2099"))


class TestChatCalcUsesApprovedRates(unittest.TestCase):
    """승인된 개정 세율이 챗봇 계산 경로(tax_calculator 툴)에도 반영되는지."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — setUp/tearDown 수명주기라 컨텍스트 매니저 부적합
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.close()
        os.environ["TAX_RATE_OVERLAY_PATH"] = self._tmp.name

    def tearDown(self) -> None:
        os.environ.pop("TAX_RATE_OVERLAY_PATH", None)
        os.unlink(self._tmp.name)

    def test_tool_uses_latest_approved_year_by_default(self) -> None:
        from backend.app.services.agent.tools import tax_calculator

        apply_overlay(heuristic_extract(_SAMPLE_AMENDMENT, year="2026"))
        out = tax_calculator.invoke(
            {
                "calc_type": "foreign_stock_sale",
                "sale_price": 152_500_000,
                "acquisition_cost": 50_000_000,
            }
        )
        # 개정 후 22%: 과세표준 1억 × 22% + 지방 10% = 24,200,000
        self.assertIn("24,200,000", out)
        self.assertIn("2026 귀속", out)

    def test_explicit_past_year_overrides_latest(self) -> None:
        from backend.app.services.agent.tools import tax_calculator

        apply_overlay(heuristic_extract(_SAMPLE_AMENDMENT, year="2026"))
        out = tax_calculator.invoke(
            {
                "calc_type": "foreign_stock_sale",
                "sale_price": 152_500_000,
                "acquisition_cost": 50_000_000,
                "year": "2025",
            }
        )
        # 2025 명시 → 20%: 과세표준 1억 × 20% + 지방 10% = 22,000,000
        self.assertIn("22,000,000", out)

    def test_detect_year_from_utterance(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import _detect_year

        self.assertEqual(_detect_year("2024년 기준 양도세 알려줘"), "2024")
        self.assertIsNone(_detect_year("해외주식 양도세 계산해줘"))


class TestApiFlow(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — setUp/tearDown 수명주기라 컨텍스트 매니저 부적합
            suffix=".json", delete=False, mode="w", encoding="utf-8"
        )
        self._tmp.close()
        os.environ["TAX_RATE_OVERLAY_PATH"] = self._tmp.name
        from fastapi.testclient import TestClient

        from backend.app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("TAX_RATE_OVERLAY_PATH", None)
        os.unlink(self._tmp.name)

    def test_extract_then_apply_flow(self) -> None:
        res = self.client.post(
            "/api/v1/tax-rates/extract",
            json={"text": _SAMPLE_AMENDMENT, "year": "2026", "use_llm": False},
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["can_apply"])
        self.assertEqual(body["issues"], [])
        self.assertTrue(any(d["field"] == "foreign_stock_national_rate" for d in body["diff"]))

        apply_res = self.client.post(
            "/api/v1/tax-rates/apply", json={"proposed": body["proposed"]}
        )
        self.assertEqual(apply_res.status_code, 200)
        self.assertTrue(apply_res.json()["applied"])

        current = self.client.get("/api/v1/tax-rates/current", params={"year": "2026"})
        rate = current.json()["rates"]["foreign_stock_national_rate"]["value"]
        self.assertAlmostEqual(rate, 0.22)

    def test_apply_rejects_invalid(self) -> None:
        bad = ProposedRateSet(
            year="2026", foreign_stock_national_rate=ProposedRate(value=9.9)
        ).model_dump()
        res = self.client.post("/api/v1/tax-rates/apply", json={"proposed": bad})
        self.assertEqual(res.status_code, 400)

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
        self.assertTrue(res.json()["can_apply"])

    def test_unsupported_suffix_rejected(self) -> None:
        res = self.client.post(
            "/api/v1/tax-rates/extract/upload",
            files={"file": ("amend.docx", b"x", "application/octet-stream")},
            data={"year": "2026"},
        )
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
