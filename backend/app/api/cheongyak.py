"""청약 정보 라우터 (wealth_advisor 이식).

공공데이터포털 청약홈 API를 노출한다. wealth_advisor의 JWT 인증(get_current_user)은 제거하고
midas 컨벤션(인증 없는 공개 조회)으로 맞췄다. 동기 클라이언트는 asyncio.to_thread로 오프로드한다.
CHEONGYAK_API_KEY 미설정 시 RuntimeError → 500(명확한 안내 detail).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Query

from backend.app.services.cheongyak import (
    fetch_apt_competition,
    fetch_apt_housing_types,
    fetch_apt_scores,
    fetch_apt_special_supply,
    fetch_officetel,
    fetch_officetel_competition,
    fetch_opt_competition,
    fetch_opt_supply,
    fetch_public_rent,
    fetch_public_rent_competition,
    fetch_recent_apt,
    fetch_remaining_apt,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cheongyak", tags=["cheongyak"])


async def _run_list(fn: Callable[[int, int], list[dict]], days_back: int, days_forward: int) -> list[dict]:
    """목록 조회를 스레드로 오프로드하고 키/외부 오류를 HTTP로 변환한다."""
    try:
        return await asyncio.to_thread(fn, days_back, days_forward)
    except RuntimeError as exc:  # 키 미설정
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("청약 공공데이터 목록 조회 실패")
        raise HTTPException(status_code=502, detail="공공데이터 API 호출에 실패했습니다.") from exc


async def _run_detail(fn: Callable[[str, str], list[dict]], house_manage_no: str, pblanc_no: str) -> list[dict]:
    try:
        return await asyncio.to_thread(fn, house_manage_no, pblanc_no)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("청약 공공데이터 상세 조회 실패")
        raise HTTPException(status_code=502, detail="공공데이터 API 호출에 실패했습니다.") from exc


# ── 목록 ────────────────────────────────────────────────
_LIST_FETCHERS: dict[str, Callable[[int, int], list[dict]]] = {
    "apt": fetch_recent_apt,
    "officetel": fetch_officetel,
    "remaining": fetch_remaining_apt,
    "opt": fetch_opt_supply,
    "public-rent": fetch_public_rent,
}


@router.get("/list/{kind}")
async def list_cheongyak(
    kind: str,
    days_back: int = Query(60, ge=1, le=365),
    days_forward: int = Query(60, ge=1, le=365),
) -> list[dict]:
    """분양 공고 목록. kind: apt | officetel | remaining | opt | public-rent."""
    fetcher = _LIST_FETCHERS.get(kind)
    if not fetcher:
        raise HTTPException(status_code=404, detail=f"알 수 없는 종류: {kind}")
    return await _run_list(fetcher, days_back, days_forward)


# ── 상세 ────────────────────────────────────────────────
@router.get("/detail/{house_manage_no}/{pblanc_no}/housing-types")
async def apt_housing_types(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """APT 주택형별 상세."""
    return await _run_detail(fetch_apt_housing_types, house_manage_no, pblanc_no)


@router.get("/detail/{house_manage_no}/{pblanc_no}/competition")
async def apt_competition(
    house_manage_no: str,
    pblanc_no: str,
    kind: str = Query("apt", description="apt | officetel | public-rent | opt"),
) -> list[dict]:
    """경쟁률 조회(종류별)."""
    fetchers = {
        "apt": fetch_apt_competition,
        "officetel": fetch_officetel_competition,
        "public-rent": fetch_public_rent_competition,
        "opt": fetch_opt_competition,
    }
    fetcher = fetchers.get(kind)
    if not fetcher:
        raise HTTPException(status_code=404, detail=f"알 수 없는 종류: {kind}")
    return await _run_detail(fetcher, house_manage_no, pblanc_no)


@router.get("/detail/{house_manage_no}/{pblanc_no}/scores")
async def apt_scores(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """APT 당첨 가점(최저/최고/평균)."""
    return await _run_detail(fetch_apt_scores, house_manage_no, pblanc_no)


@router.get("/detail/{house_manage_no}/{pblanc_no}/special-supply")
async def apt_special_supply(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """APT 특별공급 신청현황."""
    return await _run_detail(fetch_apt_special_supply, house_manage_no, pblanc_no)
