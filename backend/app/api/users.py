"""유저/대시보드 조회 라우터 (read-only).

웹 콘솔이 챗봇 대상 유저를 고르고, 프로필·포트폴리오·시장지표·세율을
시각화하는 데 쓰는 조회 전용 엔드포인트 모음.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shared.database.connector import (
    get_all_tax_rules,
    get_latest_market_snapshots,
    get_portfolios_by_user_uuid,
    get_user_by_uuid,
    list_users,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/users")
def get_users(limit: int = 50, offset: int = 0) -> dict:
    """유저 선택용 요약 목록."""
    rows = list_users(limit=limit, offset=offset)
    return {"users": rows, "count": len(rows)}


@router.get("/users/{uuid}")
def get_user_detail(uuid: str) -> dict:
    """단일 유저 프로필 + 포트폴리오(+종목)."""
    profile = get_user_by_uuid(uuid)
    if not profile:
        raise HTTPException(status_code=404, detail=f"사용자를 찾을 수 없습니다: {uuid}")
    portfolios = get_portfolios_by_user_uuid(uuid)
    return {"profile": profile, "portfolios": portfolios}


@router.get("/market/snapshots")
def get_market_snapshots() -> dict:
    """data_type/sub_key별 최신 시장 지표."""
    return {"snapshots": get_latest_market_snapshots()}


@router.get("/tax-rules")
def get_tax_rules() -> dict:
    """현행 세법 기준 세율/공제 한도."""
    return {"tax_rules": get_all_tax_rules()}
