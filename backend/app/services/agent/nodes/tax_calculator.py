"""tax_calculator 도구 노드 — 발화에서 금액·보유기간을 추출해 결정론적 계산기를 실행한다.

계산은 절대 LLM에게 맡기지 않는다. 이 노드가 간단한 정규식으로 금액(억/만/천만 단위)과
보유기간을 뽑고, 부족하면 필요 항목을 되물어 달라는 안내 문자열을 tool_context에 넣는다.
추출·계산 실패는 모두 안내/실패 문구로 흡수해 그래프를 보호한다.

정규식 파서의 한계: "2억 5000만" 같은 복합 표기는 2개의 독립 금액으로 읽힌다. 애매하면
안내 문자열로 사용자에게 재확인을 요청한다.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Literal

from pydantic import BaseModel, Field

from ..state import AgentState
from ..tools import tax_calculator
from ._common import latest_user_text

logger = logging.getLogger("agent.tax_calculator")

# 계산 종류 감지 토큰. 이자·배당 → 해외주식 → 주택 순으로 판정한다.
_FINANCIAL_INCOME_TOKENS = ("이자", "배당", "금융소득")
_FOREIGN_STOCK_TOKENS = (
    "해외주식", "해외 주식", "미국주식", "미국 주식", "나스닥", "다우",
    "애플", "테슬라", "엔비디아", "아마존", "구글", "마이크로소프트",
)
_HOUSING_TOKENS = ("주택", "아파트", "오피스텔", "집을 팔", "집 팔", "내 집", "내집")

# 금액: 숫자 + (억|천만|백만|십만|만) [+원]
_AMOUNT_RE = re.compile(r"(\d[\d,]*)\s*(억|천만|백만|십만|만)\s*원?")
_UNIT_VALUE = {
    "억": 100_000_000,
    "천만": 10_000_000,
    "백만": 1_000_000,
    "십만": 100_000,
    "만": 10_000,
}
# 단위 없는 큰 원화 수치(쉼표 구분 포함). 예: 1200000000 / 1,200,000,000
_BARE_WON_RE = re.compile(r"(?<![\d,.])(\d{1,3}(?:,\d{3})+|\d{6,})(?![\d])")
# 보유기간: N년 / N.N년 (2025년 같은 연도 표기 제외용 상한 필터), N개월
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*년")
_MONTHS_RE = re.compile(r"(\d{1,3})\s*개월")
# 귀속연도 명시: "2025년 기준", "2024년에 팔았는데" 등. 없으면 최신 규정을 적용한다.
_TAX_YEAR_RE = re.compile(r"(20\d{2})\s*년")

# 양도/취득 구분 힌트: 금액 직후 짧은 창(window)에서 매수·매도 동사를 찾는다.
_ACQ_VERB_RE = re.compile(r"(샀|사서|구입|취득|들였|에\s*산)")
_SALE_VERB_RE = re.compile(r"(팔|매도)")
_HINT_WINDOW_CHARS = 16

_MAX_PLAUSIBLE_HOLDING_YEARS = 50

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "housing_sale": ("양도가액(팔 때 가격)", "취득가액·필요경비 합계(산 가격 + 경비)", "보유기간"),
    "foreign_stock_sale": ("양도가액 합계(팔 때 총액)", "취득가액·필요경비 합계"),
    "interest_dividend": ("연간 이자·배당소득 합계",),
}

_TYPE_LABELS: dict[str, str] = {
    "housing_sale": "주택 양도소득세",
    "foreign_stock_sale": "해외주식 양도소득세",
    "interest_dividend": "이자·배당 분리과세",
}


def _detect_calc_type(text: str) -> str | None:
    if any(tok in text for tok in _FINANCIAL_INCOME_TOKENS):
        return "interest_dividend"
    if any(tok in text for tok in _FOREIGN_STOCK_TOKENS):
        return "foreign_stock_sale"
    if any(tok in text for tok in _HOUSING_TOKENS):
        return "housing_sale"
    return None


def _detect_year(text: str) -> str | None:
    """발화에 명시된 귀속연도(예 '2024년')를 뽑는다. 없으면 None(툴이 최신 규정 적용)."""
    m = _TAX_YEAR_RE.search(text)
    return m.group(1) if m else None


def _amount_spans(text: str) -> list[tuple[int, int]]:
    """(시작 위치, 금액) 목록. 단위 표기 우선, 단위 없는 원화 수치는 겹치지 않을 때만 보조."""
    spans: list[tuple[int, int]] = []
    consumed: list[tuple[int, int]] = []

    for m in _AMOUNT_RE.finditer(text):
        value = int(m.group(1).replace(",", "")) * _UNIT_VALUE[m.group(2)]
        spans.append((m.start(), value))
        consumed.append(m.span())

    def _consumed(start: int) -> bool:
        return any(s <= start < e for s, e in consumed)

    for m in _BARE_WON_RE.finditer(text):
        if not _consumed(m.start(1)):
            spans.append((m.start(), int(m.group(1).replace(",", ""))))
    return spans


def parse_amounts(text: str) -> list[int]:
    """발화에서 금액 후보를 출현 순서대로 추출한다(단위 표기 우선, 단위 없는 원화 수치 보조)."""
    return [value for _, value in _amount_spans(text)]


def split_sale_and_acquisition(text: str, amounts: list[int]) -> tuple[int | None, int | None]:
    """금액 순서를 (양도가액, 취득가액)으로 추정한다.

    매수·매도 동사 근접성("3억에 샀는데 5억에 팔았어")을 힌트로 쓰고, 힌트가 부족하면
    첫 금액을 양도가액으로 보는 위치 기반 폴백으로 돌아간다.
    """
    sale = acq = None
    for start, value in _amount_spans(text):
        window = text[start : start + _HINT_WINDOW_CHARS]
        if _ACQ_VERB_RE.search(window):
            acq = value
        elif _SALE_VERB_RE.search(window):
            sale = value
        if sale is not None and acq is not None:
            return sale, acq
    if len(amounts) >= 2:
        return amounts[0], amounts[1]
    # 동사 힌트로 특정된 금액이 있으면 위치 폴백보다 힌트를 우선한다.
    # (예: "5억에 산 집을 팔면?" → 취득가 5억 확정, 양도가액만 되묻기)
    if sale is not None or acq is not None:
        return sale, acq
    if amounts:
        return amounts[0], None
    return None, None


def parse_holding_years(text: str) -> float | None:
    """발화에서 보유기간(년)을 추출한다. 연도 표기(예: 2025년)와 형태소 내 'N년'(예: 5년)을
    구분하기 위해 상한 필터를 둔다."""
    for m in _YEARS_RE.finditer(text):
        value = float(m.group(1))
        if 0 < value < _MAX_PLAUSIBLE_HOLDING_YEARS:
            return value
    for m in _MONTHS_RE.finditer(text):
        months = int(m.group(1))
        if 0 < months < _MAX_PLAUSIBLE_HOLDING_YEARS * 12:
            return months / 12
    return None


def _guidance(calc_type: str | None) -> str:
    if calc_type is None:
        supported = ", ".join(f"{label}({_TYPE_LABELS[label]})" for label in _REQUIRED_FIELDS)
        return (
            "[tax_calculator] 어떤 세금을 계산할지 특정하지 못했습니다. 지원 대상은 "
            f"{supported}입니다. 해당하는 질문으로 다시 물어봐 주십시오."
            "\n※ 실제 세액과 다를 수 있는 단순 계산기임을 참고하십시오."
        )
    fields = "\n".join(f"- {f}" for f in _REQUIRED_FIELDS[calc_type])
    return (
        f"[tax_calculator] {_TYPE_LABELS[calc_type]} 계산에 필요한 정보가 부족합니다. "
        "아래 항목을 알려주시면 바로 코드로 계산합니다:\n"
        f"{fields}"
        "\n※ 실제 세액과 다를 수 있는 단순 계산기임을 참고하십시오."
    )


# ---------------------------------------------------------------------------
# LLM 슬롯필링 — 자연어에서 계산 입력을 구조화 추출한다(계산은 여전히 코드 몫).
# ---------------------------------------------------------------------------
# LLM은 '입력 추출'만 하고 세액은 계산하지 않는다("2억5천" 오독 위험은 regex 폴백 + 결과 내역
# 에코로 완화). 환경변수 TAX_SLOT_LLM=0 이면 완전히 끄고 regex만 쓴다(오프라인/테스트).
class TaxSlots(BaseModel):
    """발화에서 뽑은 세금 계산 입력 슬롯. 확실한 값만 채우고 나머지는 None으로 둔다."""

    calc_type: Literal["housing_sale", "foreign_stock_sale", "interest_dividend"] | None = (
        Field(default=None, description="세금 종류. 특정 불가 시 null")
    )
    sale_price: int | None = Field(default=None, description="양도가액/매도가(원)")
    acquisition_cost: int | None = Field(default=None, description="취득가액+필요경비/매수가(원)")
    net_profit: int | None = Field(
        default=None,
        description="순수익/양도차익(원). '2천만원 벌었다', '수익 2000만'처럼 매도가/매수가가 따로 없이 순이익만 명시된 경우 채움",
    )
    holding_years: float | None = Field(default=None, description="보유연수(년)")
    is_sole_home: bool | None = Field(default=None, description="1세대 1주택 여부")
    adjusted_area: bool | None = Field(default=None, description="조정대상지역·투기과열지구 여부")
    annual_financial_income: int | None = Field(default=None, description="연간 이자·배당소득(원)")
    year: str | None = Field(default=None, description="명시된 귀속연도(예 '2024'). 없으면 null")


def _llm_slots(user_text: str, *args, **kwargs) -> TaxSlots | None:
    """LLM structured output으로 슬롯을 추출한다. 비활성/실패 시 None(→ regex 폴백)."""
    context = args[0] if args else kwargs.get("context", "")
    if os.environ.get("TAX_SLOT_LLM", "1") == "0":
        return None
    try:
        from ..llm import build_chat_model

        model = build_chat_model(temperature=0.0).with_structured_output(TaxSlots)
        prompt = (
            "다음 사용자 발화 및 이전 대화 맥락에서 세금 계산에 필요한 입력만 구조화해 추출하라. "
            "세액을 직접 계산하지 말고, 발화 및 맥락에 명확히 있는 값만 채우고 없으면 null로 두라. "
            "금액은 원 단위 정수로 환산하라('3억'=300000000, '2000만원'=20000000, '2억5천만'=250000000). "
            "해외주식/미국주식의 경우 '2,000만원 벌었다'처럼 순이익만 언급된 경우 net_profit에 20000000을 채우라.\n\n"
            f"[대화 맥락]\n{context}\n\n[현재 발화]\n{user_text}"
        )
        result = model.invoke(prompt)
        return result if isinstance(result, TaxSlots) else None
    except Exception as exc:  # 키 부재·네트워크·파싱 실패 모두 regex 폴백 대상
        logger.warning("[tax_slots] LLM 슬롯필링 실패(%s) → regex 폴백.", type(exc).__name__)
        return None


def _kwargs_from_slots(slots: TaxSlots) -> dict[str, object] | None:
    """슬롯이 계산에 충분하면 tax_calculator 호출 kwargs로, 부족하면 None을 돌려준다."""
    ct = slots.calc_type
    if ct == "interest_dividend":
        if slots.annual_financial_income is None:
            return None
        kw: dict[str, object] = {"calc_type": ct, "annual_financial_income": slots.annual_financial_income}
    elif ct == "foreign_stock_sale":
        if slots.sale_price is not None and slots.acquisition_cost is not None:
            kw = {
                "calc_type": ct,
                "sale_price": slots.sale_price,
                "acquisition_cost": slots.acquisition_cost,
            }
        elif slots.net_profit is not None:
            kw = {
                "calc_type": ct,
                "sale_price": slots.net_profit,
                "acquisition_cost": 0,
            }
        elif slots.sale_price is not None and slots.acquisition_cost is None:
            kw = {
                "calc_type": ct,
                "sale_price": slots.sale_price,
                "acquisition_cost": 0,
            }
        else:
            return None
    elif ct == "housing_sale":
        if slots.sale_price is None or slots.acquisition_cost is None:
            return None
        if slots.holding_years is None:
            return None
        kw = {
            "calc_type": ct,
            "sale_price": slots.sale_price,
            "acquisition_cost": slots.acquisition_cost,
            "holding_years": slots.holding_years,
        }
        if slots.is_sole_home is not None:
            kw["is_sole_home"] = slots.is_sole_home
        if slots.adjusted_area is not None:
            kw["adjusted_area"] = slots.adjusted_area
    else:
        return None
    if slots.year:
        kw["year"] = slots.year
    return kw


def _regex_kwargs(user_text: str, *args, **kwargs) -> tuple[dict[str, object] | None, str]:
    """정규식 폴백. (kwargs, "") on 성공, (None, 안내문구) on 정보 부족."""
    context = args[0] if args else kwargs.get("context", "")
    calc_type = _detect_calc_type(user_text) or _detect_calc_type(context)
    if calc_type is None:
        return None, _guidance(None)

    amounts = parse_amounts(user_text)
    year = _detect_year(user_text) or _detect_year(context)

    if calc_type == "interest_dividend":
        if not amounts:
            return None, _guidance("interest_dividend")
        kw: dict[str, object] = {"calc_type": calc_type, "annual_financial_income": amounts[0]}
    elif calc_type == "foreign_stock_sale":
        if any(w in user_text for w in ("벌었", "수익", "차익", "이익")) and len(amounts) == 1:
            kw = {
                "calc_type": calc_type,
                "sale_price": amounts[0],
                "acquisition_cost": 0,
            }
        else:
            sale_price, acquisition_cost = split_sale_and_acquisition(user_text, amounts)
            if sale_price is None or acquisition_cost is None:
                return None, _guidance(calc_type)
            kw = {
                "calc_type": calc_type,
                "sale_price": sale_price,
                "acquisition_cost": acquisition_cost,
            }
    else:
        years = parse_holding_years(user_text) or parse_holding_years(context)
        sale_price, acquisition_cost = split_sale_and_acquisition(user_text, amounts)
        if sale_price is None or acquisition_cost is None or years is None:
            return None, _guidance(calc_type)
        kw = {
            "calc_type": calc_type,
            "sale_price": sale_price,
            "acquisition_cost": acquisition_cost,
            "holding_years": years,
            "adjusted_area": any(t in user_text or t in context for t in ("조정대상지역", "투기과열지구")),
        }
    if year:
        kw["year"] = year
    return kw, ""


def tax_calculator_node(state: AgentState) -> dict:
    try:
        user_text = latest_user_text(state)

        # 멀티턴 대화 맥락 추출
        raw_msgs = state.get("messages") or []
        history_snippets: list[str] = []
        for m in raw_msgs[-4:]:
            role = getattr(m, "type", "user")
            c = getattr(m, "content", "")
            if c:
                prefix = "사용자" if role in ("human", "user") else "AI"
                history_snippets.append(f"{prefix}: {c[:200]}")
        context_text = "\n".join(history_snippets) if history_snippets else user_text

        # 1) LLM 슬롯필링 우선(자연어 강건성) — 입력만 추출, 계산은 코드.
        try:
            slots = _llm_slots(user_text, context_text)
        except TypeError:
            slots = _llm_slots(user_text)
        kwargs = _kwargs_from_slots(slots) if slots else None

        # 2) 실패/불충분 시 regex 폴백. 폴백도 부족하면 되묻기 안내.
        if kwargs is None:
            try:
                kwargs, guidance = _regex_kwargs(user_text, context_text)
            except TypeError:
                kwargs, guidance = _regex_kwargs(user_text)
            if kwargs is None:
                return {"tool_context": [guidance]}

        result = tax_calculator.invoke(kwargs)
        return {"tool_context": [f"[tax_calculator 결과]\n{result}"]}
    except Exception as exc:
        return {"tool_context": [f"[tax_calculator 계산 실패] {exc}"]}
