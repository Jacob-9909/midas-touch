"""세율·정책수치 레지스트리 — 계산 로직과 분리된 '버전 관리되는 세율 데이터'.

절충안 설계의 핵심: 세율·공제액·구간표 같은 **곱하거나 빼는 수치**를 계산 코드에서 떼어내
귀속연도별 레지스트리로 관리한다. 세법이 개정되면 `calculator.py`의 로직은 건드리지 않고
여기 데이터(RATE_REGISTRY)만 새 귀속연도로 추가·교체한다.

각 수치는 값만이 아니라 **법령 근거(조문)·출처·시행일**을 함께 들고 다닌다(Rate). 산술 자체는
여전히 `calculator.py`(순수 코드)가 하므로 "LLM이 세액을 계산하지 않는다"는 불변식은 유지된다.
레지스트리는 계산기가 어떤 수치를 어느 근거로 썼는지 감사(audit)할 수 있게 하는 계층이다.
"""

from __future__ import annotations

from dataclasses import dataclass

# 2025~2026 귀속 세트의 공통 출처·시행일. 개정 세트를 추가할 때 새 상수로 분리한다.
SOURCE_2025 = "국세청 2025~2026 귀속 세법 기준"
EFFECTIVE_2025 = "2025-01-01"


@dataclass(frozen=True)
class Rate:
    """단일 세율·공제액·기준금액 한 개 — 값과 그 법령 근거를 함께 보관한다."""

    value: float | int
    basis: str  # 법령 근거 조문 (예: "소득세법 §155①")
    source: str = SOURCE_2025
    effective_from: str = EFFECTIVE_2025


@dataclass(frozen=True)
class Bracket:
    """소득세 누진세율표의 한 구간 (상한원, 세율, 누진공제액). upper=None은 무제한."""

    upper: int | None
    rate: float
    credit: int


@dataclass(frozen=True)
class TaxRateSet:
    """한 귀속연도에 적용되는 세율·정책수치 전체 묶음."""

    year: str
    # ── 국내 주택 양도소득세 ─────────────────────────────────────────
    housing_exempt_min_hold_years: Rate
    adjusted_area_exempt_price_limit: Rate
    general_area_exempt_price_limit: Rate
    lbts_yearly_rate: Rate
    lbts_sole_home_max_rate: Rate
    lbts_general_max_rate: Rate
    lbts_min_hold_years: Rate
    capital_gain_basic_deduction_per_year: Rate
    income_tax_brackets: tuple[Bracket, ...]
    income_tax_brackets_basis: str
    housing_local_education_tax_rate: Rate
    # ── 해외주식 양도소득세 ─────────────────────────────────────────
    foreign_stock_national_rate: Rate
    local_income_tax_ratio: Rate
    foreign_stock_basic_deduction: Rate
    # ── 이자·배당 분리과세 ─────────────────────────────────────────
    interest_dividend_withholding_rate: Rate
    financial_income_total_tax_threshold: Rate

    @property
    def provenance(self) -> str:
        """이 세트의 출처·시행일 요약 — 계산 결과에 근거로 표기한다."""
        return f"{self.year} 귀속 · {SOURCE_2025}"


# ---------------------------------------------------------------------------
# 2025~2026 귀속 세트 (값·근거는 기존 calculator.py 주석에서 그대로 이관)
# ---------------------------------------------------------------------------
_RATES_2025 = TaxRateSet(
    year="2025",
    # 1세대 1주택 비과세 최소 보유기간 2년 — 소득세법 §97①2호
    housing_exempt_min_hold_years=Rate(2.0, "소득세법 §97①2호"),
    # 1세대 1주택 비과세 양도가액 한도: 조정대상지역 9억 / 그 밖 12억 — 소득세법 §97④·시행령 §126
    adjusted_area_exempt_price_limit=Rate(900_000_000, "소득세법 §97④·시행령 §126"),
    general_area_exempt_price_limit=Rate(1_200_000_000, "소득세법 §97④·시행령 §126"),
    # 장기보유특별공제: 보유연수별 연 8%p, 최대 80%(1주택)/40%(일반), 3년 이상부터 — 소득세법 §100의5
    lbts_yearly_rate=Rate(0.08, "소득세법 §100의5"),
    lbts_sole_home_max_rate=Rate(0.80, "소득세법 §100의5"),
    lbts_general_max_rate=Rate(0.40, "소득세법 §100의5"),
    lbts_min_hold_years=Rate(3.0, "소득세법 §100의5"),
    # 양도소득 기본공제: 보유·경과연수 × 연 250만원 — 소득세법 §99
    capital_gain_basic_deduction_per_year=Rate(2_500_000, "소득세법 §99"),
    # 양도소득세 과세표준 세율표(누진공제 방식) — 소득세법 §55① (2025 귀속 개정: 5억 초과 45%)
    income_tax_brackets=(
        Bracket(12_000_000, 0.06, 0),
        Bracket(46_000_000, 0.15, 1_080_000),
        Bracket(88_000_000, 0.24, 5_220_000),
        Bracket(150_000_000, 0.35, 13_400_000),
        Bracket(300_000_000, 0.38, 17_900_000),
        Bracket(500_000_000, 0.40, 23_900_000),
        Bracket(None, 0.45, 48_900_000),
    ),
    income_tax_brackets_basis="소득세법 §55① 세율표",
    # 주택 양도소득세 지방교육세: 본세의 10% — 지방교육세법 §21·시행령 §31
    housing_local_education_tax_rate=Rate(0.10, "지방교육세법 §21·시행령 §31"),
    # 국외주권 등 양도소득 기본세율 20% — 소득세법 §155①
    foreign_stock_national_rate=Rate(0.20, "소득세법 §155①"),
    # 지방소득세: 소득세액의 10% — 지방소득세법 §17①·§104①
    local_income_tax_ratio=Rate(0.10, "지방소득세법 §17①·§104①"),
    # 양도소득 기본공제 연 250만원 — 소득세법 §98①
    foreign_stock_basic_deduction=Rate(2_500_000, "소득세법 §98①"),
    # 이자·배당 분리과세율 15.4%(소득세 14% + 지방소득세 1.4%) — 소득세법 §174·지방소득세법 §17
    interest_dividend_withholding_rate=Rate(0.154, "소득세법 §174·지방소득세법 §17"),
    # 금융소득종합과세 기준: 연간 금융소득 2,000만원 초과 — 소득세법 §46①
    financial_income_total_tax_threshold=Rate(20_000_000, "소득세법 §46①"),
)


# 귀속연도 → 세트. 세법 개정 시 새 연도 키를 추가한다(로직 수정 없이 데이터만 확장).
RATE_REGISTRY: dict[str, TaxRateSet] = {
    "2025": _RATES_2025,
}

DEFAULT_YEAR = "2025"


def latest_year() -> str:
    """등록된(하드코딩 + 승인 오버레이) 귀속연도 중 가장 최신.

    규정은 기본적으로 최신 연도로 적용한다 — 계산 노드가 발화에 과거 연도가 없을 때 이 값을 쓴다.
    """
    from .rate_overlay import overlay_years

    years = set(RATE_REGISTRY) | set(overlay_years())
    return max(years, key=int)


def get_rates(year: str = DEFAULT_YEAR) -> TaxRateSet:
    """귀속연도에 해당하는 세율 세트를 돌려준다.

    우선순위: 승인된 오버레이(rate_overlay) > 하드코딩 기본 세트 > DEFAULT_YEAR 폴백.
    오버레이는 승인된 개정안만 반영되므로, 승인 전에는 기본 세트 동작이 유지된다.
    """
    from .rate_overlay import build_overlaid_set  # 지연 import — 순환 참조 회피

    overlaid = build_overlaid_set(year)
    if overlaid is not None:
        return overlaid
    return RATE_REGISTRY.get(year, RATE_REGISTRY[DEFAULT_YEAR])
