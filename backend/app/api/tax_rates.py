"""세율 개정안 인입 라우터 — 추출 → 검증 → 현행 대비 비교 (읽기 전용 미리보기).

데모 흐름: 개정안 파일(PDF/TXT/MD) 업로드 → `/extract/upload`가 세율 제안·현행 대비 diff·검증 이슈를 돌려준다.
반영(승인) 단계는 두지 않는다 — 세율은 코드 상수(rates.RATE_REGISTRY)로만 결정되는 결정론
불변식을 지키기 위해 런타임 오버레이 변경 경로를 제거했다. 추출·비교는 근거 확인용 미리보기다.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.api.uploads import read_upload_capped
from backend.app.services.tax.rate_diff import diff_against_current
from backend.app.services.tax.rate_extraction import (
    ProposedRateSet,
    extract_rate_set,
)
from backend.app.services.tax.rate_validation import validate_proposed
from backend.app.services.tax.rates import get_rates

router = APIRouter(prefix="/api/v1/tax-rates", tags=["tax-rates"])

_SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}
_MAX_TEXT_CHARS = 20_000


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
        "validation_passed": not issues,
    }


def _pdf_to_text(raw: bytes) -> str:
    """업로드된 PDF 바이트를 텍스트로 추출한다(RAG용 DocumentParser 재사용 — 표까지 마크다운으로).

    임시 파일에 써서 pymupdf(+pypdf 폴백) 파서를 태운다. 실패는 400으로 흡수한다.
    """
    import tempfile

    from pipelines.embedding.document_parser import DocumentParser

    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(raw)
        tmp.flush()
        try:
            return DocumentParser()._parse_pdf(Path(tmp.name))
        except Exception as exc:  # 파서 라이브러리 부재·손상 PDF 등
            raise HTTPException(
                status_code=400,
                detail=f"PDF에서 텍스트를 추출하지 못했습니다: {exc}",
            ) from exc


@router.post("/extract/upload")
async def extract_upload(
    file: UploadFile = File(...),
    year: str = Form("2026"),
    use_llm: bool = Form(True),
) -> dict:
    """개정안 파일(.pdf/.txt/.md)을 업로드해 추출한다. PDF는 파서로 텍스트를 뽑아 동일 파이프라인을 탄다."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다: {suffix} (지원: {sorted(_SUPPORTED_SUFFIXES)})",
        )
    raw = await read_upload_capped(file)
    if suffix == ".pdf":
        text = _pdf_to_text(raw)
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="텍스트로 읽을 수 없는 파일입니다. .pdf/.txt/.md 개정안을 올리거나 텍스트로 붙여넣으세요.",
            ) from None
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="파일에서 읽은 텍스트가 비어 있습니다.")
    proposed = extract_rate_set(text[:_MAX_TEXT_CHARS], year=year, use_llm=use_llm)
    return _diff_payload(proposed)


@router.get("/current")
def current(year: str = "2026") -> dict:
    """해당 귀속연도의 현행 세율(코드 상수)을 돌려준다."""
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
