"""추출 제안 ↔ 현행 세율 비교 — 승인 전에 '무엇이 바뀌는가'를 보여준다.

제안(ProposedRateSet)의 각 필드를 현행 기본 세트(get_rates)와 대조해, 사람이 승인 판단을
내릴 수 있게 (필드, 라벨, 기존값, 제안값, 변화율)을 구조화한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rate_extraction import ProposedRateSet
from .rates import DEFAULT_YEAR, get_rates

# 필드 → (사람이 읽는 라벨, 종류). 종류 'rate'는 퍼센트로, 'amount'는 원화로 렌더한다.
FIELD_META: dict[str, tuple[str, str]] = {
    "foreign_stock_national_rate": ("해외주식 양도소득세율", "rate"),
    "interest_dividend_withholding_rate": ("이자·배당 분리과세율", "rate"),
    "local_income_tax_ratio": ("지방소득세 비율", "rate"),
    "housing_local_education_tax_rate": ("지방교육세율", "rate"),
    "lbts_yearly_rate": ("장기보유특별공제 연율", "rate"),
    "capital_gain_basic_deduction_per_year": ("양도소득 기본공제(연)", "amount"),
    "financial_income_total_tax_threshold": ("금융소득종합과세 기준", "amount"),
}


@dataclass(frozen=True)
class RateDiff:
    """한 세율 항목의 현행 → 제안 비교."""

    field: str
    label: str
    kind: str
    old_value: float
    new_value: float
    old_basis: str
    new_basis: str

    @property
    def changed(self) -> bool:
        return self.old_value != self.new_value


def diff_against_current(proposed: ProposedRateSet) -> list[RateDiff]:
    """제안의 추출 필드들을 현행 기본 세트와 비교한 목록을 돌려준다."""
    current = get_rates(DEFAULT_YEAR)
    diffs: list[RateDiff] = []
    for field, pr in proposed.changed_fields().items():
        meta = FIELD_META.get(field)
        if meta is None:
            continue
        label, kind = meta
        current_rate = getattr(current, field)
        diffs.append(
            RateDiff(
                field=field,
                label=label,
                kind=kind,
                old_value=float(current_rate.value),
                new_value=float(pr.value),
                old_basis=current_rate.basis,
                new_basis=pr.basis,
            )
        )
    return diffs
