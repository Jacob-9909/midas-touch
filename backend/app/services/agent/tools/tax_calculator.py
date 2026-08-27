"""tax_calculator 도구 — 결정론적 세금 계산기 얇은 래퍼.

실제 계산은 backend/app/services/tax/calculator.py(순수 코드, LLM 개입 없음)가 하고,
이 파일은 @tool 시그니처로 입력을 받아 결과를 텍스트로 포맷만 한다. LLM이 세율을 지어내지
않도록 계산 근거 내역과 면책 문구를 그대로 실어 반환한다.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from backend.app.services.tax.calculator import (
    ForeignStockSaleInput,
    HousingSaleInput,
    InterestDividendInput,
    TaxCalcResult,
    calc_foreign_stock_sale,
    calc_housing_sale,
    calc_interest_dividend,
)
from backend.app.services.tax.rates import get_rates, latest_year


@tool
def tax_calculator(
    calc_type: Literal["housing_sale", "foreign_stock_sale", "interest_dividend"],
    sale_price: int | None = None,
    acquisition_cost: int | None = None,
    holding_years: float | None = None,
    is_sole_home: bool = True,
    adjusted_area: bool = False,
    annual_financial_income: int | None = None,
    year: str | None = None,
) -> str:
    """세금을 코드로 **결정론적** 계산한다. 주택 양도소득세(1세대 1주택 비과세·장기보유특별공제
    포함), 해외주식 양도소득세, 이자·배당소득 분리과세를 지원하며 각 단계 금액과 법령 근거를
    함께 돌려준다. '실제 세액과 다를 수 있는 단순 계산기'다.

    Args:
        calc_type: 계산 종류. 'housing_sale'(국내 주택 양도), 'foreign_stock_sale'
            (해외주식 양도), 'interest_dividend'(이자·배당 분리과세).
        sale_price: 양도가액(원). housing_sale / foreign_stock_sale에서 필수.
        acquisition_cost: 취득가액 + 필요경비 합계(원). housing_sale / foreign_stock_sale에서 필수.
        holding_years: 보유연수(년). housing_sale에서 필수.
        is_sole_home: 1세대 1주택 여부(housing_sale, 기본 True).
        adjusted_area: 조정대상지역 여부(housing_sale, 기본 False — 비과세 한도 9억/12억 구분).
        annual_financial_income: 연간 이자·배당소득 합계(원). interest_dividend에서 필수.
        year: 적용 귀속연도. 미지정 시 등록된 최신 연도(승인 오버레이 포함)를 적용한다.
    """
    # 규정은 최신 연도가 기본. 발화에 과거 연도가 명시된 경우에만 노드가 그 연도를 넘긴다.
    rates = get_rates(year or latest_year())

    if calc_type == "housing_sale":
        if sale_price is None or acquisition_cost is None or holding_years is None:
            raise ValueError(
                "housing_sale 계산에는 sale_price(양도가액), acquisition_cost(취득가액+필요경비), "
                "holding_years(보유연수)가 모두 필요합니다."
            )
        result: TaxCalcResult = calc_housing_sale(
            HousingSaleInput(
                sale_price=sale_price,
                acquisition_cost=acquisition_cost,
                holding_years=holding_years,
                is_sole_home=is_sole_home,
                adjusted_area=adjusted_area,
            ),
            rates,
        )
    elif calc_type == "foreign_stock_sale":
        if sale_price is None or acquisition_cost is None:
            raise ValueError(
                "foreign_stock_sale 계산에는 sale_price(양도가액 합계)와 "
                "acquisition_cost(취득가액+필요경비 합계)가 필요합니다."
            )
        result = calc_foreign_stock_sale(
            ForeignStockSaleInput(sale_price=sale_price, acquisition_cost=acquisition_cost),
            rates,
        )
    elif calc_type == "interest_dividend":
        if annual_financial_income is None:
            raise ValueError("interest_dividend 계산에는 annual_financial_income(연간 금융소득)이 필요합니다.")
        result = calc_interest_dividend(
            InterestDividendInput(annual_income=annual_financial_income),
            rates,
        )
    else:
        raise ValueError(f"지원하지 않는 calc_type 입니다: {calc_type}")

    return result.render()
