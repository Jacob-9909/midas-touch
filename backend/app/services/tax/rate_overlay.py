"""세율 오버레이 저장소 — 승인된 제안을 레지스트리 위에 얹는 계층.

하드코딩 기본 세트(`rates.RATE_REGISTRY`)는 소스코드라 함부로 못 바꾼다. 개정안에서 추출·검증·
**승인**된 세율은 여기(JSON 파일)에 기록되고, `get_rates(year)`가 기본 세트 위에 병합해 돌려준다.
즉 승인 전에는 계산에 전혀 영향이 없고, 승인 순간부터 그 귀속연도 계산이 새 세율을 쓴다.

데모는 새 귀속연도(예 2026)만 오버레이하므로 기존 2025 계산·테스트에는 영향이 없다.
파일이 없거나 해당 연도 항목이 없으면 병합할 것이 없어 기본 동작으로 남는다.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from .rate_extraction import ProposedRateSet
from .rates import DEFAULT_YEAR, RATE_REGISTRY, Rate, TaxRateSet


def _overlay_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path or os.environ.get("TAX_RATE_OVERLAY_PATH", "data/tax_rate_overlays.json"))


def _load_all(path: str | os.PathLike[str] | None = None) -> dict:
    p = _overlay_path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def apply_overlay(
    proposed: ProposedRateSet,
    *,
    source: str = "업로드 개정안(승인)",
    path: str | os.PathLike[str] | None = None,
) -> None:
    """승인된 제안을 오버레이 파일에 기록한다(해당 귀속연도 항목을 덮어쓴다)."""
    overlays = _load_all(path)
    effective_from = f"{proposed.year}-01-01"
    overlays[proposed.year] = {
        "source": source,
        "effective_from": effective_from,
        "rates": {
            field: {"value": pr.value, "basis": pr.basis}
            for field, pr in proposed.changed_fields().items()
        },
    }
    p = _overlay_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(overlays, ensure_ascii=False, indent=2), encoding="utf-8")


def build_overlaid_set(
    year: str, path: str | os.PathLike[str] | None = None
) -> TaxRateSet | None:
    """오버레이가 있는 귀속연도면 기본 세트 위에 병합한 TaxRateSet을, 없으면 None을 돌려준다."""
    entry = _load_all(path).get(year)
    if not entry:
        return None
    base = RATE_REGISTRY[DEFAULT_YEAR]
    source = entry.get("source", "오버레이")
    effective_from = entry.get("effective_from", f"{year}-01-01")
    overrides: dict[str, Rate] = {}
    for field, payload in entry.get("rates", {}).items():
        if not hasattr(base, field):
            continue
        overrides[field] = Rate(
            value=payload["value"],
            basis=payload.get("basis", "오버레이"),
            source=source,
            effective_from=effective_from,
        )
    return dataclasses.replace(base, year=year, **overrides)
