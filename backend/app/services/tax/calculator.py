"""결정론적 한국 세금 계산기 — LLM이 계산하지 않고 코드가 계산한다.

2025~2026 귀속 기준의 대표 세목(주택 양도소득세·해외주식 양도소득세·이자배당 분리과세)만
단순화해 계산한다. 세율·공제액·구간표 같은 **수치는 `rates.py` 레지스트리**에서 주입받고,
이 파일은 그 수치로 **산술만** 수행한다(곱셈·누진공제 계산은 전부 파이썬). 세법 개정 시에는
여기 로직이 아니라 레지스트리 데이터를 갱신한다.

감면·특례(일시적 2주택, 필요경비 인정 범위, 장기보유특별공제 세부 제한 등)는 반영하지 않은
'실제 세액과 다를 수 있는 단순 계산기'이며, 모든 결과에 DISCLAIMER와 적용 세율 출처가 함께 간다.

금액 반올림은 원단위 round()로 단순화한다(실무 신고 시의 절삭/반올림 규칙과 다를 수 있음).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from .rates import TaxRateSet, get_rates

# ---------------------------------------------------------------------------
# 공통 면책 문구 (모든 계산 결과에 필수로 붙인다)
# ---------------------------------------------------------------------------
DISCLAIMER = (
    "⚠️ 본 결과는 2025~2026 귀속 세법 기준을 단순화한 '실제 세액과 다를 수 있는 단순 계산기' "
    "출력입니다. 감면·특례·필요경비 인정 범위 등을 반영하지 않았으므로 실제 신고 전에는 "
    "반드시 세무 전문가 확인이 필요합니다."
)


# ---------------------------------------------------------------------------
# 입력 검증(pydantic) / 결과 구조(dataclass)
# ---------------------------------------------------------------------------
class HousingSaleInput(BaseModel):
    """국내 주택 양도 계산 입력."""

    sale_price: int = Field(ge=0, description="양도가액(원)")
    acquisition_cost: int = Field(
        ge=0, description="취득가액 + 필요경비 합계(원)"
    )
    holding_years: float = Field(gt=0, description="보유연수(년)")
    is_sole_home: bool = Field(default=True, description="1세대 1주택 여부")
    adjusted_area: bool = Field(default=False, description="조정대상지역 여부")


class ForeignStockSaleInput(BaseModel):
    """해외주식 양도 계산 입력(귀속연도 1개년 기준 합계)."""

    sale_price: int = Field(ge=0, description="양도가액 연간 합계(원)")
    acquisition_cost: int = Field(ge=0, description="취득가액 + 필요경비 연간 합계(원)")


class InterestDividendInput(BaseModel):
    """이자·배당 분리과세 입력."""

    annual_income: int = Field(ge=0, description="연간 이자·배당소득 합계(원)")


@dataclass(frozen=True)
class CalcLine:
    """계산 근거 내역의 한 단계."""

    label: str
    amount: int
    basis: str = ""  # 법령 근거


@dataclass(frozen=True)
class TaxCalcResult:
    """계산 결과 요약 + 단계별 내역 + 참고 안내."""

    title: str
    total_tax: int
    lines: list[CalcLine] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        out = [f"### {self.title} (단순 계산)"]
        for ln in self.lines:
            basis = f" — {ln.basis}" if ln.basis else ""
            out.append(f"- {ln.label}: {ln.amount:,}원{basis}")
        out.append(f"=> 예상 세액 합계: {self.total_tax:,}원")
        for note in self.notes:
            out.append(f"※ {note}")
        out.append(DISCLAIMER)
        return "\n".join(out)


def _round_won(value: float) -> int:
    return round(value)


def _progressive_tax(base: int, rates: TaxRateSet) -> int:
    """소득세법 §55① 세율표(누진공제 방식). 구간·세율·공제액은 레지스트리에서 온다."""
    for bracket in rates.income_tax_brackets:
        if bracket.upper is None or base <= bracket.upper:
            return max(_round_won(base * bracket.rate) - bracket.credit, 0)
    return 0  # 도달하지 않음(마지막 구간이 None 처리됨)


def _provenance_note(rates: TaxRateSet) -> str:
    """적용 세율의 출처·귀속연도를 결과에 남긴다(어느 근거 세트로 계산했는지 감사용)."""
    return f"적용 세율 기준: {rates.provenance}"


# ---------------------------------------------------------------------------
# a) 국내 주택 양도소득세 (1세대 1주택 중심 단순판단)
# ---------------------------------------------------------------------------
def calc_housing_sale(
    p: HousingSaleInput, rates: TaxRateSet | None = None
) -> TaxCalcResult:
    r = rates or get_rates()
    gain = p.sale_price - p.acquisition_cost
    lines: list[CalcLine] = []
    notes: list[str] = []

    if gain <= 0:
        return TaxCalcResult(
            title="주택 양도소득세",
            total_tax=0,
            lines=[
                CalcLine("양도차익", gain, "양도가액 − 취득가액·필요경비"),
                CalcLine("예상 세액", 0, "양도차익 없음 또는 손실"),
            ],
            notes=["양도차익이 없거나 손실이면 양도소득세는 발생하지 않습니다."],
        )

    taxable_gain = gain
    min_hold = r.housing_exempt_min_hold_years.value
    limit = (
        r.adjusted_area_exempt_price_limit.value
        if p.adjusted_area
        else r.general_area_exempt_price_limit.value
    )

    if p.is_sole_home and p.holding_years >= min_hold and p.sale_price <= limit:
        # 1세대 1주택 + 보유 2년 이상 + 비과세 가액 한도 이하 → 전액 비과세
        # — 소득세법 §97①2호·④
        area_note = "조정대상지역" if p.adjusted_area else "비조정지역"
        return TaxCalcResult(
            title=f"주택 양도소득세 (1세대 1주택 {area_note})",
            total_tax=0,
            lines=[
                CalcLine("양도차익", gain),
                CalcLine(
                    "비과세 판정", 0,
                    f"1세대 1주택 보유 {p.holding_years:g}년 + 양도가액 {limit:,.0f}원 이하 "
                    f"({r.general_area_exempt_price_limit.basis})",
                ),
            ],
            notes=[
                "장기보유특별공제·기본공제는 비과세 적용 시 계산에 들어가지 않습니다.",
                "※ 실제 비과세는 2년 이내 일시적 2주택·증여받은 주택 합산 등 요건 확인이 필요합니다.",
                _provenance_note(r),
            ],
        )

    if p.is_sole_home and p.holding_years >= min_hold and p.sale_price > limit:
        # 한도 초과분만 비례 과세(단순판단): 과세차익 = 차익 × (양도가액 − 한도)/양도가액
        # — 소득세법 §97④·시행령 §126의 비과세대상금액 방식 단순화
        ratio = (p.sale_price - limit) / p.sale_price
        taxable_gain = _round_won(gain * ratio)
        lines.append(CalcLine("양도차익", gain))
        lines.append(
            CalcLine(
                f"비과세 한도({limit:,.0f}원) 초과분 과세대상 차익", taxable_gain,
                f"{r.general_area_exempt_price_limit.basis} (한도 초과분 비례 과세)",
            )
        )
    else:
        reason = (
            f"보유 {p.holding_years:g}년(<{min_hold:g}년)"
            if not p.is_sole_home or p.holding_years < min_hold
            else ""
        )
        lines.append(CalcLine("양도차익", gain))
        if reason:
            notes.append(f"1세대 1주택 비과세 미적용({reason}).")

    # 장기보유특별공제 — 소득세법 §100의5 (보유연수별 연 8%p, 최대 80%/40%)
    lbts_rate = 0.0
    if p.holding_years >= r.lbts_min_hold_years.value:
        cap = (
            r.lbts_sole_home_max_rate.value
            if p.is_sole_home
            else r.lbts_general_max_rate.value
        )
        lbts_rate = min((int(p.holding_years) - 2) * r.lbts_yearly_rate.value, cap)
    lbts_amount = _round_won(taxable_gain * lbts_rate)
    after_lbts = taxable_gain - lbts_amount
    if lbts_amount > 0:
        lines.append(
            CalcLine(
                f"장기보유특별공제({lbts_rate:.0%})", -lbts_amount, r.lbts_yearly_rate.basis
            )
        )

    # 양도소득 기본공제 — 소득세법 §99 (보유·경과연수 × 연 250만원)
    per_year = r.capital_gain_basic_deduction_per_year.value
    basic_deduction = int(p.holding_years) * per_year
    base = max(after_lbts - basic_deduction, 0)
    if basic_deduction > 0:
        lines.append(
            CalcLine(
                f"기본공제({int(p.holding_years)}년 × 연 {per_year:,.0f}원)", -basic_deduction,
                r.capital_gain_basic_deduction_per_year.basis,
            )
        )

    national = _progressive_tax(base, r)
    education = _round_won(national * r.housing_local_education_tax_rate.value)
    total = national + education

    lines.append(CalcLine("과세표준", base))
    lines.append(CalcLine("양도소득세 본세(국세)", national, r.income_tax_brackets_basis))
    lines.append(
        CalcLine(
            "지방교육세(10%)", education, r.housing_local_education_tax_rate.basis
        )
    )

    if p.sale_price > r.general_area_exempt_price_limit.value:
        notes.append("12억 초과 1주택은 고가주택 추가 재산세·종부세 이슈가 별도로 있을 수 있습니다.")
    notes.append(_provenance_note(r))
    return TaxCalcResult(title="주택 양도소득세", total_tax=total, lines=lines, notes=notes)


# ---------------------------------------------------------------------------
# b) 해외주식 양도소득세
# ---------------------------------------------------------------------------
def calc_foreign_stock_sale(
    p: ForeignStockSaleInput, rates: TaxRateSet | None = None
) -> TaxCalcResult:
    r = rates or get_rates()
    gain = p.sale_price - p.acquisition_cost
    deduction = r.foreign_stock_basic_deduction.value
    taxable_base = max(gain - deduction, 0)
    national = _round_won(taxable_base * r.foreign_stock_national_rate.value)
    local = _round_won(national * r.local_income_tax_ratio.value)
    total = national + local

    combined_pct = (
        r.foreign_stock_national_rate.value * (1 + r.local_income_tax_ratio.value)
    )
    lines = [
        CalcLine("양도차익", gain),
        CalcLine(
            f"기본공제(연 {deduction:,.0f}원)",
            -min(gain, deduction),
            r.foreign_stock_basic_deduction.basis,
        ),
        CalcLine("과세표준", taxable_base),
        CalcLine(
            f"양도소득세({r.foreign_stock_national_rate.value:.0%})",
            national,
            r.foreign_stock_national_rate.basis,
        ),
        CalcLine(
            f"지방소득세(본세의 {r.local_income_tax_ratio.value:.0%})",
            local,
            r.local_income_tax_ratio.basis,
        ),
    ]
    notes: list[str] = []
    if gain < deduction:
        notes.append(f"양도차익이 기본공제 {deduction:,.0f}원 이하라면 납부할 세액이 없습니다.")
    notes.append(
        f"실효세율 약 {combined_pct:.1%}(국세+지방). "
        "해외주식 손실은 같은 해 해외주식 양도차익과만 통산됩니다(국내주식과 불가)."
    )
    notes.append(_provenance_note(r))
    return TaxCalcResult(
        title="해외주식 양도소득세", total_tax=total, lines=lines, notes=notes
    )


# ---------------------------------------------------------------------------
# c) 이자·배당소득 분리과세
# ---------------------------------------------------------------------------
def calc_interest_dividend(
    p: InterestDividendInput, rates: TaxRateSet | None = None
) -> TaxCalcResult:
    r = rates or get_rates()
    rate = r.interest_dividend_withholding_rate.value
    tax = _round_won(p.annual_income * rate)
    lines = [
        CalcLine("연간 이자·배당소득", p.annual_income),
        CalcLine(
            f"분리과세 세액({rate:.1%})",
            tax,
            r.interest_dividend_withholding_rate.basis,
        ),
    ]
    notes: list[str] = []
    threshold = r.financial_income_total_tax_threshold.value
    if p.annual_income > threshold:
        notes.append(
            f"연간 금융소득이 {threshold:,.0f}원을 초과하므로 "
            "분리과세가 아니라 **금융소득종합과세** 대상입니다: 타 소득과 합산해 종합소득세 "
            f"신고·납부가 필요합니다({r.financial_income_total_tax_threshold.basis})."
        )
    else:
        notes.append(
            f"연 {threshold:,.0f}원 이하 금융소득은 원천징수(분리과세)로 신고 의무가 없습니다."
        )
    notes.append(_provenance_note(r))
    return TaxCalcResult(
        title="이자·배당소득 세액 (분리과세)", total_tax=tax, lines=lines, notes=notes
    )
