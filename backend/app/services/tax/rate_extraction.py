"""세법 개정안 문서 → 구조화 세율 추출 (업로드 시점 · 오프라인).

이 모듈은 **런타임 계산 경로가 아니다.** 개정안 PDF/텍스트를 업로드할 때 1회 돌아, 문서에서
세율·공제액을 뽑아 `ProposedRateSet`(검토 대기 제안)으로 만든다. 이 제안은 검증(rate_validation)
·기존값 대비 비교(rate_diff)를 거쳐 **사람이 승인할 때만** 레지스트리 오버레이에 반영된다.
계산 자체는 승인 뒤에도 여전히 코드가 하므로 "LLM이 세액을 계산하지 않는다"는 불변식은 유지된다.

추출은 LLM(structured output)을 우선 시도하고, 키 부재·네트워크 실패 시 정규식 휴리스틱으로
우아하게 저하한다(오프라인 데모·테스트 보장). 어느 경로든 결과는 사람이 검수하는 '제안'일 뿐이다.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from backend.app.services.agent.nodes.tax_calculator import parse_amounts

logger = logging.getLogger("tax.rate_extraction")

# 추출된 값에 붙는 기본 근거 라벨 — 실제 조문은 사람이 검수 시 교정한다.
_EXTRACTED_BASIS = "업로드 문서 추출(검수 필요)"

# 필드별 (키워드, 종류). 문서에서 키워드 근처의 퍼센트/금액을 그 필드 값으로 읽는다.
# 종류 'rate'는 퍼센트(→소수), 'amount'는 원화 금액.
_FIELD_KEYWORDS: dict[str, tuple[tuple[str, ...], str]] = {
    "foreign_stock_national_rate": (("해외주식", "국외주식", "해외 주식", "국외주권"), "rate"),
    "interest_dividend_withholding_rate": (("이자·배당", "이자배당", "배당소득", "분리과세"), "rate"),
    "local_income_tax_ratio": (("지방소득세",), "rate"),
    "housing_local_education_tax_rate": (("지방교육세",), "rate"),
    "lbts_yearly_rate": (("장기보유특별공제", "장특공"), "rate"),
    "capital_gain_basic_deduction_per_year": (("양도소득 기본공제", "양도소득기본공제"), "amount"),
    "financial_income_total_tax_threshold": (("금융소득종합과세", "종합과세 기준"), "amount"),
}

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_WINDOW_CHARS = 40


class ProposedRate(BaseModel):
    """문서에서 추출된 세율·금액 한 개(검토 대기)."""

    value: float = Field(description="세율(소수, 예 0.22) 또는 금액(원)")
    basis: str = Field(default=_EXTRACTED_BASIS, description="근거 라벨")


class ProposedRateSet(BaseModel):
    """개정안에서 추출된 세율 제안. 문서에 없던 필드는 None(=기존값 유지)."""

    year: str = Field(description="적용 귀속연도, 예 '2026'")
    foreign_stock_national_rate: ProposedRate | None = None
    interest_dividend_withholding_rate: ProposedRate | None = None
    local_income_tax_ratio: ProposedRate | None = None
    housing_local_education_tax_rate: ProposedRate | None = None
    lbts_yearly_rate: ProposedRate | None = None
    capital_gain_basic_deduction_per_year: ProposedRate | None = None
    financial_income_total_tax_threshold: ProposedRate | None = None

    def changed_fields(self) -> dict[str, ProposedRate]:
        """실제 추출된(=None 아닌) 필드만 {필드명: ProposedRate}로 돌려준다."""
        return {
            name: value
            for name, value in self.__dict__.items()
            if isinstance(value, ProposedRate)
        }


def _extract_near_keyword(text: str, keywords: tuple[str, ...], kind: str) -> float | None:
    """키워드 첫 등장 위치 ±window 안에서 퍼센트(rate)나 금액(amount)을 하나 뽑는다."""
    for kw in keywords:
        idx = text.find(kw)
        if idx == -1:
            continue
        start = max(0, idx - _WINDOW_CHARS)
        window = text[start : idx + len(kw) + _WINDOW_CHARS]
        # "20%에서 22%로 상향" 같은 표기에서 마지막 값을 '개정 후' 값으로 본다(단일 값이면 그 값).
        if kind == "rate":
            matches = _PERCENT_RE.findall(window)
            if matches:
                return round(float(matches[-1]) / 100, 6)
        else:  # amount
            amounts = parse_amounts(window)
            if amounts:
                return float(amounts[-1])
    return None


def heuristic_extract(text: str, year: str) -> ProposedRateSet:
    """정규식 휴리스틱 추출 — LLM 없이 오프라인으로 완결된다(폴백·테스트 경로)."""
    found: dict[str, ProposedRate] = {}
    for field, (keywords, kind) in _FIELD_KEYWORDS.items():
        value = _extract_near_keyword(text, keywords, kind)
        if value is not None:
            found[field] = ProposedRate(value=value)
    return ProposedRateSet(year=year, **found)


def llm_extract(text: str, year: str) -> ProposedRateSet:
    """LLM structured output 추출. 실패 시 예외를 올려 호출부가 휴리스틱으로 폴백한다."""
    from backend.app.services.agent.llm import build_chat_model

    model = build_chat_model(temperature=0.0).with_structured_output(ProposedRateSet)
    prompt = (
        f"다음은 한국 세법 개정안 문서다. {year} 귀속연도에 적용되는 세율·공제액을 추출하라.\n"
        "각 값은 문서에 명시된 것만 채우고, 없으면 반드시 null로 남겨라(추측 금지). "
        "세율은 소수로(22% → 0.22), 금액은 원 단위 정수로 변환하라.\n\n"
        f"[문서]\n{text}"
    )
    result = model.invoke(prompt)
    if isinstance(result, ProposedRateSet):
        result.year = year
        return result
    return ProposedRateSet.model_validate({**dict(result), "year": year})


def extract_rate_set(text: str, year: str = "2026", use_llm: bool = True) -> ProposedRateSet:
    """개정안 텍스트에서 세율 제안을 추출한다. LLM 우선, 실패 시 휴리스틱 폴백."""
    if use_llm:
        try:
            proposed = llm_extract(text, year)
            if proposed.changed_fields():
                return proposed
            logger.info("[rate_extraction] LLM 추출 결과가 비어 휴리스틱으로 보강합니다.")
        except Exception as exc:  # 키 부재·네트워크·파싱 실패 모두 폴백 대상
            logger.warning("[rate_extraction] LLM 추출 실패(%s) → 휴리스틱 폴백.", type(exc).__name__)
    return heuristic_extract(text, year)
