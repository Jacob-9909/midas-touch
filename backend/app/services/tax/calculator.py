"""결정론적 한국 세금 계산기 — LLM이 계산하지 않고 코드가 계산한다.

2025~2026 귀속 기준의 대표 세목(주택 양도소득세·해외주식 양도소득세·이자배당 분리과세)만
단순화해 계산한다. 각 상수에 법령 근거를 주석으로 남긴다. 감면·특례(일시적 2주택, 필요경비
인정 범위, 장기보유특별공제 세부 제한 등)는 반영하지 않은 '실제 세액과 다를 수 있는 단순
계산기'이며, 모든 결과에 DISCLAIMER가 함께 간다.

금액 반올림은 원단위 round()로 단순화한다(실무 신고 시의 절삭/반올림 규칙과 다를 수 있음).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 공통 면책 문구 (모든 계산 결과에 필수로 붙인다)
# ---------------------------------------------------------------------------
DISCLAIMER = (
    "⚠️ 본 결과는 2025~2026 귀속 세법 기준을 단순화한 '실제 세액과 다를 수 있는 단순 계산기' "
    "출력입니다. 감면·특례·필요경비 인정 범위 등을 반영하지 않았으므로 실제 신고 전에는 "
    "반드시 세무 전문가 확인이 필요합니다."
)


# ---------------------------------------------------------------------------
# 국내 주택 양도소득세 상수 (2025~2026 귀속)
# ---------------------------------------------------------------------------
# 1세대 1주택 비과세 최소 보유기간 2년 — 소득세법 §97①2호
HOUSING_EXEMPT_MIN_HOLD_YEARS = 2.0
# 1세대 1주택 비과세 양도가액 한도: 조정대상지역 9억 / 그 밖 12억 —
# 소득세법 §97④·동법 시행령 §126조(2020.7.10 이후 취득분). 초과 시 초과분에 해당하는
# 양도차익만 비례 과세한다(단순판단).
ADJUSTED_AREA_EXEMPT_PRICE_LIMIT = 900_000_000
GENERAL_AREA_EXEMPT_PRICE_LIMIT = 1_200_000_000
# 장기보유특별공제: 보유연수별 연 8%p, 3년 이상부터 적용 — 소득세법 §100의5.
# 1세대 1주택(비과세 한도 초과분 포함) 최대 80%, 그 외 일반 주택 최대 40%.
LBTS_YEARLY_RATE = 0.08
LBTS_SOLE_HOME_MAX_RATE = 0.80
LBTS_GENERAL_MAX_RATE = 0.40
LBTS_MIN_HOLD_YEARS = 3.0
# 양도소득 기본공제: 보유·경과연수 × 연 250만원 — 소득세법 §99조
CAPITAL_GAIN_BASIC_DEDUCTION_PER_YEAR = 2_500_000
# 양도소득세 과세표준 세율표(상한원, 세율, 누진공제액). 상한 None은 무제한.
# 소득세법 §55① — 2025 귀속연도 개정 구간(5억 초과 45% 단일화).
INCOME_TAX_BRACKETS: tuple[tuple[int | None, float, int], ...] = (
    (12_000_000, 0.06, 0),
    (46_000_000, 0.15, 1_080_000),
    (88_000_000, 0.24, 5_220_000),
    (150_000_000, 0.35, 13_400_000),
    (300_000_000, 0.38, 17_900_000),
    (500_000_000, 0.40, 23_900_000),
    (None, 0.45, 48_900_000),
)
# 주택 양도소득세 지방교육세: 본세의 10% — 지방교육세법 §21①③·동법 시행령 §31①②
HOUSING_LOCAL_EDUCATION_TAX_RATE = 0.10


# ---------------------------------------------------------------------------
# 해외주식 양도소득세 상수 (2025~2026 귀속)
# ---------------------------------------------------------------------------
# 국외주권 등의 양도소득 기본세율 20% — 소득세법 §155①
FOREIGN_STOCK_NATIONAL_RATE = 0.20
# 지방소득세: 소득세법상 세액의 10% — 지방소득세법 §17①·§104① → 합계 22%
LOCAL_INCOME_TAX_RATIO = 0.10
# 양도소득 기본공제 연 250만원 — 소득세법 §98①
FOREIGN_STOCK_BASIC_DEDUCTION = 2_500_000


# ---------------------------------------------------------------------------
# 이자·배당소득 분리과세 상수 (2025~2026 귀속)
# ---------------------------------------------------------------------------
# 이자·배당소득 분리과세율 15.4%(소득세 14% + 지방소득세 1.4%) —
# 소득세법 §174①·동법 §174조 관련 과세특례, 지방소득세법 §17①
INTEREST_DIVIDEND_WITHHOLDING_RATE = 0.154
# 금융소득종합과세 기준: 연간 금융소득 2,000만원 초과 — 소득세법 §46①
FINANCIAL_INCOME_TOTAL_TAX_THRESHOLD = 20_000_000


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


def _progressive_tax(base: int) -> int:
    """소득세법 §55① 세율표(누진공제 방식)."""
    for upper, rate, credit in INCOME_TAX_BRACKETS:
        if upper is None or base <= upper:
            return max(_round_won(base * rate) - credit, 0)
    return 0  # 도달하지 않음(마지막 구간이 None 처리됨)


# ---------------------------------------------------------------------------
# a) 국내 주택 양도소득세 (1세대 1주택 중심 단순판단)
# ---------------------------------------------------------------------------
def calc_housing_sale(p: HousingSaleInput) -> TaxCalcResult:
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
    limit = ADJUSTED_AREA_EXEMPT_PRICE_LIMIT if p.adjusted_area else GENERAL_AREA_EXEMPT_PRICE_LIMIT

    if p.is_sole_home and p.holding_years >= HOUSING_EXEMPT_MIN_HOLD_YEARS and p.sale_price <= limit:
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
                    f"1세대 1주택 보유 {p.holding_years:g}년 + 양도가액 {limit:,}원 이하 "
                    "(소득세법 §97)",
                ),
            ],
            notes=[
                "장기보유특별공제·기본공제는 비과세 적용 시 계산에 들어가지 않습니다.",
                "※ 실제 비과세는 2년 이내 일시적 2주택·증여받은 주택 합산 등 요건 확인이 필요합니다.",
            ],
        )

    if p.is_sole_home and p.holding_years >= HOUSING_EXEMPT_MIN_HOLD_YEARS and p.sale_price > limit:
        # 한도 초과분만 비례 과세(단순판단): 과세차익 = 차익 × (양도가액 − 한도)/양도가액
        # — 소득세법 §97④·동법 시행령 §126조의 비과세대상금액 방식 단순화
        ratio = (p.sale_price - limit) / p.sale_price
        taxable_gain = _round_won(gain * ratio)
        lines.append(CalcLine("양도차익", gain))
        lines.append(
            CalcLine(
                f"비과세 한도({limit:,}원) 초과분 과세대상 차익", taxable_gain,
                "소득세법 §97④ (한도 초과분 비례 과세)",
            )
        )
    else:
        reason = (
            f"보유 {p.holding_years:g}년(<2년)"
            if not p.is_sole_home or p.holding_years < HOUSING_EXEMPT_MIN_HOLD_YEARS
            else ""
        )
        lines.append(CalcLine("양도차익", gain))
        if reason:
            notes.append(f"1세대 1주택 비과세 미적용({reason}).")

    # 장기보유특별공제 — 소득세법 §100의5 (보유연수별 연 8%p, 최대 80%/40%)
    lbts_rate = 0.0
    if p.holding_years >= LBTS_MIN_HOLD_YEARS:
        cap = LBTS_SOLE_HOME_MAX_RATE if p.is_sole_home else LBTS_GENERAL_MAX_RATE
        lbts_rate = min((int(p.holding_years) - 2) * LBTS_YEARLY_RATE, cap)
    lbts_amount = _round_won(taxable_gain * lbts_rate)
    after_lbts = taxable_gain - lbts_amount
    if lbts_amount > 0:
        lines.append(
            CalcLine(
                f"장기보유특별공제({lbts_rate:.0%})", -lbts_amount, "소득세법 §100의5"
            )
        )

    # 양도소득 기본공제 — 소득세법 §99 (보유·경과연수 × 연 250만원)
    basic_deduction = int(p.holding_years) * CAPITAL_GAIN_BASIC_DEDUCTION_PER_YEAR
    base = max(after_lbts - basic_deduction, 0)
    if basic_deduction > 0:
        lines.append(
            CalcLine(
                f"기본공제({int(p.holding_years)}년 × 연 250만원)", -basic_deduction,
                "소득세법 §99",
            )
        )

    national = _progressive_tax(base)
    education = _round_won(national * HOUSING_LOCAL_EDUCATION_TAX_RATE)
    total = national + education

    lines.append(CalcLine("과세표준", base))
    lines.append(CalcLine("양도소득세 본세(국세)", national, "소득세법 §55 세율표"))
    lines.append(
        CalcLine(
            "지방교육세(10%)", education,
            "지방교육세법 §21·동법 시행령 §31",
        )
    )

    if p.sale_price > GENERAL_AREA_EXEMPT_PRICE_LIMIT:
        notes.append("12억 초과 1주택은 고가주택 추가 재산세·종부세 이슈가 별도로 있을 수 있습니다.")
    return TaxCalcResult(title="주택 양도소득세", total_tax=total, lines=lines, notes=notes)


# ---------------------------------------------------------------------------
# b) 해외주식 양도소득세
# ---------------------------------------------------------------------------
def calc_foreign_stock_sale(p: ForeignStockSaleInput) -> TaxCalcResult:
    gain = p.sale_price - p.acquisition_cost
    taxable_base = max(gain - FOREIGN_STOCK_BASIC_DEDUCTION, 0)
    national = _round_won(taxable_base * FOREIGN_STOCK_NATIONAL_RATE)
    local = _round_won(national * LOCAL_INCOME_TAX_RATIO)
    total = national + local

    lines = [
        CalcLine("양도차익", gain),
        CalcLine(
            f"기본공제(연 {FOREIGN_STOCK_BASIC_DEDUCTION:,}원)",
            -min(gain, FOREIGN_STOCK_BASIC_DEDUCTION),
            "소득세법 §98",
        ),
        CalcLine("과세표준", taxable_base),
        CalcLine(
            "양도소득세(20%)", national, "소득세법 §155 (국외주권 등 양도소득)"
        ),
        CalcLine(
            "지방소득세(본세의 10%)", local, "지방소득세법 §17·§104"
        ),
    ]
    notes: list[str] = []
    if gain < FOREIGN_STOCK_BASIC_DEDUCTION:
        notes.append("양도차익이 기본공제 250만원 이하라면 납부할 세액이 없습니다.")
    notes.append("해외주식 손실은 같은 해 해외주식 양도차익과만 통산됩니다(국내주식과 불가).")
    return TaxCalcResult(
        title="해외주식 양도소득세", total_tax=total, lines=lines, notes=notes
    )


# ---------------------------------------------------------------------------
# c) 이자·배당소득 분리과세
# ---------------------------------------------------------------------------
def calc_interest_dividend(p: InterestDividendInput) -> TaxCalcResult:
    tax = _round_won(p.annual_income * INTEREST_DIVIDEND_WITHHOLDING_RATE)
    lines = [
        CalcLine("연간 이자·배당소득", p.annual_income),
        CalcLine(
            f"분리과세 세액({INTEREST_DIVIDEND_WITHHOLDING_RATE:.1%})",
            tax,
            "소득세 14% + 지방소득세 1.4% — 소득세법 §174, 지방소득세법 §17",
        ),
    ]
    notes: list[str] = []
    if p.annual_income > FINANCIAL_INCOME_TOTAL_TAX_THRESHOLD:
        notes.append(
            f"연간 금융소득이 {FINANCIAL_INCOME_TOTAL_TAX_THRESHOLD:,}원을 초과하므로 "
            "분리과세가 아니라 **금융소득종합과세** 대상입니다: 타 소득과 합산해 종합소득세 "
            "신고·납부가 필요합니다(소득세법 §46)."
        )
    else:
        notes.append("연 2,000만원 이하 금융소득은 원천징수(분리과세)로 신고 의무가 없습니다.")
    return TaxCalcResult(
        title="이자·배당소득 세액 (분리과세)", total_tax=tax, lines=lines, notes=notes
    )
