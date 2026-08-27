"""추출된 세율 제안 검증 — 승인 전에 통과해야 하는 결정론 게이트.

LLM/휴리스틱 추출은 틀릴 수 있으므로, 레지스트리에 반영하기 전 코드가 sanity 규칙으로 걸러낸다.
세율은 0~1 소수여야 하고, 금액 공제는 음수가 아니어야 하는 등 자명한 불변식만 확인한다.
검증 실패 항목이 하나라도 있으면 승인(apply)을 막는다.
"""

from __future__ import annotations

from .rate_extraction import ProposedRateSet

# 세율(소수)로 취급하는 필드 — [0, 1] 범위여야 한다.
_RATE_FIELDS = {
    "foreign_stock_national_rate",
    "interest_dividend_withholding_rate",
    "local_income_tax_ratio",
    "housing_local_education_tax_rate",
    "lbts_yearly_rate",
}
# 금액(원)으로 취급하는 필드 — 음수가 아니어야 한다.
_AMOUNT_FIELDS = {
    "capital_gain_basic_deduction_per_year",
    "financial_income_total_tax_threshold",
}

# 세율 상한 sanity: 개별 세목 세율이 60%를 넘으면 추출 오류로 본다(경고).
_RATE_SANITY_CEILING = 0.60


def validate_proposed(proposed: ProposedRateSet) -> list[str]:
    """검증 이슈 목록을 돌려준다. 비어 있으면 통과."""
    issues: list[str] = []

    if not proposed.year.isdigit() or len(proposed.year) != 4:
        issues.append(f"귀속연도 '{proposed.year}'가 4자리 연도 형식이 아닙니다.")

    changed = proposed.changed_fields()
    if not changed:
        issues.append("추출된 세율이 하나도 없습니다. 문서를 확인하세요.")

    for field, rate in changed.items():
        v = rate.value
        if field in _RATE_FIELDS:
            if not (0 <= v <= 1):
                issues.append(f"{field}: 세율 {v}는 0~1 소수 범위를 벗어납니다.")
            elif v > _RATE_SANITY_CEILING:
                issues.append(f"{field}: 세율 {v:.1%}가 비정상적으로 높습니다(추출 오류 의심).")
        elif field in _AMOUNT_FIELDS and v < 0:
            issues.append(f"{field}: 금액 {v}는 음수일 수 없습니다.")

    return issues
