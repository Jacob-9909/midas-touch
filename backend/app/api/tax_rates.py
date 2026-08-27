"""세율 개정안 인입 라우터 — 추출 → 검증 → 비교 → (승인 시) 반영.

데모 흐름: 개정안 텍스트/파일 업로드 → `/extract`가 세율 제안·현행 대비 diff·검증 이슈를 돌려줌
→ 사람이 확인 후 `/apply`로 승인 → 오버레이에 반영되어 그 귀속연도 계산이 새 세율을 쓴다.
계산 산술은 승인 뒤에도 코드가 하므로 결정론 불변식은 유지된다(추출/승인만 사람+LLM 개입).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.services.tax.rate_diff import diff_against_current
from backend.app.services.tax.rate_extraction import (
    ProposedRateSet,
    extract_rate_set,
)
from backend.app.services.tax.rate_overlay import apply_overlay
from backend.app.services.tax.rate_validation import validate_proposed
from backend.app.services.tax.rates import get_rates

router = APIRouter(prefix="/api/v1/tax-rates", tags=["tax-rates"])

_SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
_MAX_TEXT_CHARS = 20_000


class ExtractRequest(BaseModel):
    text: str
    year: str = "2026"
    use_llm: bool = True


class ApplyRequest(BaseModel):
    proposed: ProposedRateSet


def _diff_payload(proposed: ProposedRateSet) -> dict:
    diffs = diff_against_current(proposed)
    issues = validate_proposed(proposed)
    return {
        "proposed": proposed.model_dump(),
        "diff": [
            {
                "field": d.field,
                "label": d.label,
                "kind": d.kind,
                "old_value": d.old_value,
                "new_value": d.new_value,
                "old_basis": d.old_basis,
                "new_basis": d.new_basis,
                "changed": d.changed,
            }
            for d in diffs
        ],
        "issues": issues,
        "can_apply": not issues,
    }


@router.post("/extract")
def extract(req: ExtractRequest) -> dict:
    """개정안 텍스트에서 세율을 추출하고 현행 대비 diff·검증 결과를 돌려준다(승인 전)."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="개정안 텍스트가 비어 있습니다.")
    proposed = extract_rate_set(text[:_MAX_TEXT_CHARS], year=req.year, use_llm=req.use_llm)
    return _diff_payload(proposed)


@router.post("/extract/upload")
async def extract_upload(
    file: UploadFile = File(...),
    year: str = Form("2026"),
    use_llm: bool = Form(True),
) -> dict:
    """개정안 파일(.txt/.md)을 업로드해 추출한다. (.pdf는 텍스트 추출 파이프라인 연계 — 데모는 텍스트 우선)"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다: {suffix} (지원: {sorted(_SUPPORTED_SUFFIXES)})",
        )
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="텍스트로 읽을 수 없는 파일입니다. .txt/.md 개정안을 올리거나 텍스트로 붙여넣으세요.",
        ) from None
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="파일에서 읽은 텍스트가 비어 있습니다.")
    proposed = extract_rate_set(text[:_MAX_TEXT_CHARS], year=year, use_llm=use_llm)
    return _diff_payload(proposed)


@router.post("/apply")
def apply(req: ApplyRequest) -> dict:
    """검증을 통과한 제안을 승인해 오버레이에 반영한다. 검증 실패 시 400으로 거부."""
    proposed = req.proposed
    issues = validate_proposed(proposed)
    if issues:
        raise HTTPException(status_code=400, detail={"message": "검증 실패로 반영을 거부했습니다.", "issues": issues})
    apply_overlay(proposed)
    return {"applied": True, "year": proposed.year, "active": _current_payload(proposed.year)}


@router.get("/current")
def current(year: str = "2026") -> dict:
    """해당 귀속연도의 현재 유효 세율(오버레이 반영 후)을 돌려준다."""
    return _current_payload(year)


def _current_payload(year: str) -> dict:
    r = get_rates(year)
    return {
        "year": r.year,
        "provenance": r.provenance,
        "rates": {
            field: {"value": getattr(r, field).value, "basis": getattr(r, field).basis}
            for field, _ in _CURRENT_FIELDS
        },
    }


_CURRENT_FIELDS = (
    ("foreign_stock_national_rate", "해외주식 양도소득세율"),
    ("interest_dividend_withholding_rate", "이자·배당 분리과세율"),
    ("local_income_tax_ratio", "지방소득세 비율"),
    ("housing_local_education_tax_rate", "지방교육세율"),
    ("lbts_yearly_rate", "장기보유특별공제 연율"),
    ("capital_gain_basic_deduction_per_year", "양도소득 기본공제(연)"),
    ("financial_income_total_tax_threshold", "금융소득종합과세 기준"),
)
