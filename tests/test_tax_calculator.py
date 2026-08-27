"""tax_calculator 결정론 검증 — 손으로 계산한 기대값과 비교한다(DB·LLM·네트워크 불필요).

실행:
    PYTHONPATH=. uv run pytest tests/test_tax_calculator.py -q
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv

load_dotenv()

# 노드 테스트는 regex 경로를 결정론적으로 검증한다 — LLM 슬롯필링을 꺼 네트워크·비결정성을 배제.
os.environ["TAX_SLOT_LLM"] = "0"

from backend.app.services.tax.calculator import (
    DISCLAIMER,
    ForeignStockSaleInput,
    HousingSaleInput,
    InterestDividendInput,
    calc_foreign_stock_sale,
    calc_housing_sale,
    calc_interest_dividend,
)


# ---------------------------------------------------------------------------
# a) 국내 주택 양도소득세 — 비과세 경계·공제 한도·세율 구간
# ---------------------------------------------------------------------------
class TestHousingSaleCalc(unittest.TestCase):
    def test_exempt_boundary_exactly_12eok_non_adjusted(self) -> None:
        """양도가액 정확히 12억(비조정지역 한도 경계) + 보유 5년 → 전액 비과세."""
        result = calc_housing_sale(
            HousingSaleInput(
                sale_price=1_200_000_000, acquisition_cost=800_000_000, holding_years=5
            )
        )
        self.assertEqual(result.total_tax, 0)

    def test_exempt_boundary_adjusted_area_9eok(self) -> None:
        """조정대상지역 9억 이하 + 보유 3년 → 전액 비과세."""
        result = calc_housing_sale(
            HousingSaleInput(
                sale_price=900_000_000,
                acquisition_cost=400_000_000,
                holding_years=3,
                adjusted_area=True,
            )
        )
        self.assertEqual(result.total_tax, 0)

    def test_over_limit_proportional_tax_lbts_and_bracket_40pct(self) -> None:
        """12억 초과 비례 과세 + 장기보유특별공제 8% + 기본공제 750만 + 40% 구간.

        차익 10억 × (20억−12억)/20억 = 4억 과세대상
        → LBTS 8%(32,000,000 공제) → 368,000,000
        → 기본공제 7,500,000 → 과세표준 360,500,000
        → 본세 40%−누진공제 23,900,000 = 120,300,000
        → 지방교육세 10% = 12,030,000
        """
        result = calc_housing_sale(
            HousingSaleInput(
                sale_price=2_000_000_000, acquisition_cost=1_000_000_000, holding_years=3
            )
        )
        self.assertEqual(result.total_tax, 132_330_000)

    def test_adjusted_area_over_9eok_deductions_floor_to_zero(self) -> None:
        """조정대상지역 10억(9억 초과): 과세차익 15,000,000 → LBTS 64%(9,600,000) →
        기본공제 2,500만이 남은 금액을 초과해 과세표준 0원."""
        result = calc_housing_sale(
            HousingSaleInput(
                sale_price=1_000_000_000,
                acquisition_cost=850_000_000,
                holding_years=10,
                adjusted_area=True,
            )
        )
        self.assertEqual(result.total_tax, 0)
        # LBTS 최대 한도 캡 확인: 12년 보유여도 80%
        capped = calc_housing_sale(
            HousingSaleInput(
                sale_price=1_000_000_000,
                acquisition_cost=850_000_000,
                holding_years=12,
                adjusted_area=True,
            )
        )
        self.assertEqual(capped.total_tax, 0)

    def test_bracket_boundary_exactly_12m_six_pct(self) -> None:
        """비과세 미적용(보유 1년) + 과세표준 정확히 1,200만(6% 구간 상단 경계).

        차익 14,500,000 − 기본공제 2,500,000 = 12,000,000
        → 본세 6% = 720,000, 교육세 72,000
        """
        result = calc_housing_sale(
            HousingSaleInput(
                sale_price=114_500_000, acquisition_cost=100_000_000, holding_years=1
            )
        )
        self.assertEqual(result.total_tax, 792_000)

    def test_bracket_boundary_exactly_46m_fifteen_pct(self) -> None:
        """과세표준 정확히 4,600만(15% 구간 상단 경계): 6,900,000 − 누진공제 1,080,000.

        차익 48,500,000 − 기본공제 2,500,000 = 46,000,000 → 교육세 포함 6,402,000
        """
        result = calc_housing_sale(
            HousingSaleInput(
                sale_price=148_500_000, acquisition_cost=100_000_000, holding_years=1
            )
        )
        self.assertEqual(result.total_tax, 6_402_000)


# ---------------------------------------------------------------------------
# b) 해외주식 양도소득세 — 22%(기본공제 250만)
# ---------------------------------------------------------------------------
class TestForeignStockCalc(unittest.TestCase):
    def test_small_gain_after_basic_deduction(self) -> None:
        """차익 5,250,000 − 2,500,000 = 2,750,000 × 22% = 605,000."""
        result = calc_foreign_stock_sale(
            ForeignStockSaleInput(sale_price=10_250_000, acquisition_cost=5_000_000)
        )
        self.assertEqual(result.total_tax, 605_000)

    def test_gain_below_basic_deduction_is_zero(self) -> None:
        """차익 1,000,000 < 기본공제 2,500,000 → 세액 0."""
        result = calc_foreign_stock_sale(
            ForeignStockSaleInput(sale_price=2_000_000, acquisition_cost=1_000_000)
        )
        self.assertEqual(result.total_tax, 0)

    def test_large_gain_flat_22pct(self) -> None:
        """차익 102,500,000 − 2,500,000 = 100,000,000 × 22% = 22,000,000."""
        result = calc_foreign_stock_sale(
            ForeignStockSaleInput(sale_price=152_500_000, acquisition_cost=50_000_000)
        )
        self.assertEqual(result.total_tax, 22_000_000)


# ---------------------------------------------------------------------------
# c) 이자·배당 분리과세 — 15.4% / 연 2,000만 초과 종합과세 안내
# ---------------------------------------------------------------------------
class TestInterestDividendCalc(unittest.TestCase):
    def test_below_threshold_separate_taxation(self) -> None:
        result = calc_interest_dividend(InterestDividendInput(annual_income=10_000_000))
        self.assertEqual(result.total_tax, 1_540_000)
        self.assertFalse(any("종합과세" in n for n in result.notes))

    def test_threshold_boundary_still_separate(self) -> None:
        """연 2,000만원 정도(초과 아님)는 분리과세 유지."""
        result = calc_interest_dividend(InterestDividendInput(annual_income=20_000_000))
        self.assertEqual(result.total_tax, 3_080_000)
        joined = "\n".join(result.notes)
        self.assertIn("분리과세", joined)
        self.assertNotIn("**금융소득종합과세** 대상입니다", joined)

    def test_above_threshold_flags_synthetic_taxation(self) -> None:
        result = calc_interest_dividend(InterestDividendInput(annual_income=30_000_000))
        self.assertEqual(result.total_tax, 4_620_000)
        self.assertTrue(any("**금융소득종합과세** 대상입니다" in n for n in result.notes))


# ---------------------------------------------------------------------------
# 도구 래퍼 / 노드 파서
# ---------------------------------------------------------------------------
class TestTaxCalculatorToolAndNode(unittest.TestCase):
    def test_tool_renders_breakdown_and_disclaimer(self) -> None:
        from backend.app.services.agent.tools import tax_calculator

        out = tax_calculator.invoke(
            {
                "calc_type": "housing_sale",
                "sale_price": 1_200_000_000,
                "acquisition_cost": 800_000_000,
                "holding_years": 5,
            }
        )
        self.assertIn("예상 세액 합계: 0원", out)
        self.assertIn("단순 계산기", out)
        self.assertIn(DISCLAIMER[:10], out)

    def test_tool_missing_required_arg_raises_value_error(self) -> None:
        from backend.app.services.agent.tools import tax_calculator

        with self.assertRaises(ValueError):
            tax_calculator.invoke({"calc_type": "interest_dividend"})

    def test_parse_amounts_units_and_bare_won(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import parse_amounts

        self.assertEqual(parse_amounts("아파트를 3억에 샀는데 5억에 팔았어"), [300_000_000, 500_000_000])
        self.assertEqual(parse_amounts("보증금 1,000만원"), [10_000_000])
        self.assertEqual(parse_amounts("150000000원에 팔았어요"), [150_000_000])
        self.assertEqual(parse_amounts("1,500,000원"), [1_500_000])

    def test_parse_holding_years_filters_calendar_year_noise(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import parse_holding_years

        self.assertEqual(parse_holding_years("5년 보유했어"), 5.0)
        self.assertEqual(parse_holding_years("18개월 보유"), 1.5)
        self.assertIsNone(parse_holding_years("2025년에 샀는데"))  # 연도 표기 오인 방지

    def test_split_sale_and_acquisition_uses_verb_hints(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import split_sale_and_acquisition

        amounts = [300_000_000, 500_000_000]
        # 매수→매도 어순이라도 동사 힌트로 양도가액(팔 때)을 바로잡는다.
        sale, acq = split_sale_and_acquisition("3억에 샀는데 5억에 팔았어", amounts)
        self.assertEqual((sale, acq), (500_000_000, 300_000_000))
        # 힌트가 없으면 위치 폴백(첫 금액=양도가액).
        sale2, acq2 = split_sale_and_acquisition("집값이 3억에서 5억이 됐다", amounts)
        self.assertEqual((sale2, acq2), (300_000_000, 500_000_000))
        # 금액 하나면 취득가액 미확정.
        self.assertEqual(split_sale_and_acquisition("5억에 팔았어", [500_000_000]), (500_000_000, None))

    def test_detect_calc_type_priority(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import _detect_calc_type

        self.assertEqual(_detect_calc_type("배당금 세금 얼마야"), "interest_dividend")
        self.assertEqual(_detect_calc_type("테슬라 팔면 양도세 얼마?"), "foreign_stock_sale")
        self.assertEqual(_detect_calc_type("아파트 팔 때 세금"), "housing_sale")
        self.assertIsNone(_detect_calc_type("국내 주식 사고파는 세금"))

    def test_node_asks_back_when_info_missing(self) -> None:
        from langchain_core.messages import HumanMessage

        from backend.app.services.agent.nodes.tax_calculator import tax_calculator_node

        state = {"messages": [HumanMessage(content="아파트 팔면 세금 얼마나 내야 해?")]}
        ctx = tax_calculator_node(state)["tool_context"]
        self.assertIn("필요한 정보가 부족합니다", ctx[0])
        self.assertIn("양도가액", ctx[0])

    def test_node_returns_code_computed_result(self) -> None:
        from langchain_core.messages import HumanMessage

        from backend.app.services.agent.nodes.tax_calculator import tax_calculator_node

        state = {
            "messages": [
                HumanMessage(content="아파트를 3억에 샀는데 5억에 팔았어. 5년 보유했어.")
            ]
        }
        ctx = tax_calculator_node(state)["tool_context"]
        # 5억 ≤ 12억 + 보유 5년 → 비과세 판정(코드가 계산한 결과)
        self.assertIn("[tax_calculator 결과]", ctx[0])
        self.assertIn("비과세 판정", ctx[0])
        self.assertIn("단순 계산기", ctx[0])


# ---------------------------------------------------------------------------
# LLM 슬롯필링 — 입력만 추출, 계산은 여전히 코드(네트워크 없이 monkeypatch로 검증)
# ---------------------------------------------------------------------------
class TestLlmSlotFilling(unittest.TestCase):
    def test_kwargs_from_slots_sufficient_and_insufficient(self) -> None:
        from backend.app.services.agent.nodes.tax_calculator import (
            TaxSlots,
            _kwargs_from_slots,
        )

        ok = TaxSlots(calc_type="foreign_stock_sale", sale_price=100, acquisition_cost=10)
        self.assertEqual(
            _kwargs_from_slots(ok),
            {"calc_type": "foreign_stock_sale", "sale_price": 100, "acquisition_cost": 10},
        )
        # housing인데 보유연수 없음 → 불충분(None)
        self.assertIsNone(
            _kwargs_from_slots(TaxSlots(calc_type="housing_sale", sale_price=1, acquisition_cost=1))
        )

    def test_node_uses_llm_slots_when_available(self) -> None:
        from langchain_core.messages import HumanMessage

        from backend.app.services.agent.nodes import tax_calculator as node_mod

        # regex는 놓칠 자연어를 LLM이 슬롯으로 뽑았다고 가정(네트워크 없이 주입).
        slots = node_mod.TaxSlots(
            calc_type="foreign_stock_sale", sale_price=152_500_000, acquisition_cost=50_000_000
        )
        original = node_mod._llm_slots
        node_mod._llm_slots = lambda _text: slots
        try:
            state = {"messages": [HumanMessage(content="작년에 엔비디아 정리했는데 세금 궁금해")]}
            ctx = node_mod.tax_calculator_node(state)["tool_context"]
        finally:
            node_mod._llm_slots = original
        self.assertIn("[tax_calculator 결과]", ctx[0])
        # 과세표준 1억 × 22%/20% 계열 — 코드가 계산한 결과가 들어온다
        self.assertIn("해외주식 양도소득세", ctx[0])


# ---------------------------------------------------------------------------
# 세율 레지스트리 — 세율이 코드가 아닌 데이터에서 오고, 근거를 들고 다닌다
# ---------------------------------------------------------------------------
class TestRateRegistry(unittest.TestCase):
    def test_default_rates_carry_basis_and_source(self) -> None:
        """기본 세트의 세율은 법령 근거(조문)와 출처를 함께 보관한다."""
        from backend.app.services.tax.rates import get_rates

        r = get_rates()
        self.assertEqual(r.foreign_stock_national_rate.value, 0.20)
        self.assertEqual(r.foreign_stock_national_rate.basis, "소득세법 §155①")
        self.assertIn("귀속", r.provenance)

    def test_unknown_year_falls_back_to_default(self) -> None:
        from backend.app.services.tax.rates import DEFAULT_YEAR, get_rates

        self.assertIs(get_rates("1999"), get_rates(DEFAULT_YEAR))

    def test_injected_rateset_changes_output(self) -> None:
        """세율을 데이터로 주입하면 로직 수정 없이 결과가 바뀐다(외부화 증명)."""
        import dataclasses

        from backend.app.services.tax.rates import Rate, get_rates

        # 해외주식 국세율만 20% → 30%로 갈아끼운 가상 세트
        base = get_rates()
        hiked = dataclasses.replace(
            base, foreign_stock_national_rate=Rate(0.30, "가상 개정")
        )
        p = ForeignStockSaleInput(sale_price=152_500_000, acquisition_cost=50_000_000)
        # 과세표준 1억 × 30% = 3천만 본세 + 지방 10% = 3,300만
        self.assertEqual(calc_foreign_stock_sale(p, hiked).total_tax, 33_000_000)
        # 기본 세트(20%)는 그대로 2,200만 — 주입이 격리됨
        self.assertEqual(calc_foreign_stock_sale(p).total_tax, 22_000_000)

    def test_provenance_appears_in_render(self) -> None:
        """계산 결과에 적용 세율 출처가 남는다(감사 가능성)."""
        out = calc_interest_dividend(InterestDividendInput(annual_income=10_000_000)).render()
        self.assertIn("적용 세율 기준", out)


if __name__ == "__main__":
    unittest.main()
