"""청약홈 분양정보 조회 서비스 — 공공데이터 API 클라이언트."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests

from shared.utils.timez import KST, today_kst

_BASE_DETAIL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
_BASE_CMPET = "https://api.odcloud.kr/api/ApplyhomeInfoCmpetRtSvc/v1"

# ── Cache (TTL 1 hour) ──────────────────────────────────
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 3600
_MAX_CACHE_ENTRIES = 500


def _prune_cache(now: float) -> None:
    """만료된 캐시 항목을 정리하고 최대 개수 초과 시 가장 오래된 항목을 삭제한다."""
    expired = [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL]
    for k in expired:
        _cache.pop(k, None)
    if len(_cache) > _MAX_CACHE_ENTRIES:
        oldest_keys = sorted(_cache.keys(), key=lambda k: _cache[k][0])[: len(_cache) - _MAX_CACHE_ENTRIES]
        for k in oldest_keys:
            _cache.pop(k, None)


def _get_key() -> str:
    # midas는 CHEONGYAK_API_KEY 를 표준으로 쓴다(wealth_advisor의 DATA_GO_KR_API_KEY도 호환).
    key = (
        os.environ.get("CHEONGYAK_API_KEY")
        or os.environ.get("DATA_GO_KR_API_KEY")
        or ""
    ).strip()
    if not key:
        raise RuntimeError(
            "CHEONGYAK_API_KEY 가 설정되지 않았습니다. .env 에 공공데이터포털 청약홈 API 키를 설정하세요."
        )
    return key


def _call(endpoint: str, params: dict[str, Any], *, base: str = _BASE_DETAIL) -> dict:
    """Call data.go.kr API with caching and cache eviction."""
    cache_key = f"{base}/{endpoint}:{sorted(params.items())}"
    now = time.time()
    _prune_cache(now)
    if cache_key in _cache:
        ts, data = _cache[cache_key]
        if now - ts < _CACHE_TTL:
            return data

    url = f"{base}/{endpoint}"
    params["serviceKey"] = _get_key()
    params.setdefault("page", 1)
    params.setdefault("perPage", 100)

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _cache[cache_key] = (now, data)
    return data


# ── Public helpers ───────────────────────────────────────


@dataclass(frozen=True)
class CheongyakSummary:
    """Flattened summary of a single 분양 공고."""

    house_manage_no: str
    pblanc_no: str
    house_nm: str
    house_secd_nm: str
    house_dtl_secd_nm: str
    rent_secd_nm: str
    region: str
    address: str
    total_supply: int
    announcement_date: str  # 모집공고일
    reception_start: str  # 접수 시작
    reception_end: str  # 접수 종료
    special_start: str
    special_end: str
    winner_date: str  # 당첨자 발표일
    contract_start: str
    contract_end: str
    homepage: str
    constructor: str
    phone: str
    move_in_month: str
    status: str = ""  # 접수중 / 접수예정 / 마감


def _status_for(row: dict) -> str:
    """Derive human-readable status from dates."""
    today = today_kst().isoformat()
    rcept_start = row.get("RCEPT_BGNDE", "") or ""
    rcept_end = row.get("RCEPT_ENDDE", "") or ""
    special_end = row.get("SPSPLY_RCEPT_ENDDE", "") or ""
    gnrl_end = row.get("GNRL_RNK1_CRSPAREA_ENDDE", "") or row.get("GNRL_RNK2_CRSPAREA_ENDDE", "") or ""

    last_end = max(filter(None, [rcept_end, special_end, gnrl_end]), default="")

    if not rcept_start:
        return "일정미정"
    if today < rcept_start:
        return "접수예정"
    if last_end and today > last_end:
        return "마감"
    return "접수중"


def _row_to_summary(row: dict) -> dict:
    """Convert raw API row to frontend-friendly dict."""
    status = _status_for(row)
    return {
        "house_manage_no": row.get("HOUSE_MANAGE_NO", ""),
        "pblanc_no": row.get("PBLANC_NO", ""),
        "house_nm": row.get("HOUSE_NM", ""),
        "house_secd_nm": row.get("HOUSE_SECD_NM", ""),
        "house_dtl_secd_nm": row.get("HOUSE_DTL_SECD_NM", ""),
        "rent_secd_nm": row.get("RENT_SECD_NM", ""),
        "region": row.get("SUBSCRPT_AREA_CODE_NM", ""),
        "address": row.get("HSSPLY_ADRES", ""),
        "total_supply": row.get("TOT_SUPLY_HSHLDCO", 0) or 0,
        "announcement_date": row.get("RCRIT_PBLANC_DE", ""),
        "reception_start": row.get("RCEPT_BGNDE", ""),
        "reception_end": row.get("RCEPT_ENDDE", ""),
        "special_start": row.get("SPSPLY_RCEPT_BGNDE", ""),
        "special_end": row.get("SPSPLY_RCEPT_ENDDE", ""),
        "winner_date": row.get("PRZWNER_PRESNATN_DE", ""),
        "contract_start": row.get("CNTRCT_CNCLS_BGNDE", ""),
        "contract_end": row.get("CNTRCT_CNCLS_ENDDE", ""),
        "homepage": row.get("HMPG_ADRES", ""),
        "constructor": row.get("CNSTRCT_ENTRPS_NM", ""),
        "phone": row.get("MDHS_TELNO", ""),
        "move_in_month": row.get("MVN_PREARNGE_YM", ""),
        "status": status,
        "pblanc_url": row.get("PBLANC_URL", ""),
    }


def _announcement_ts(date_str: str | None) -> float:
    """공고일 정렬용 timestamp. YYYYMMDD·YYYY-MM-DD 모두 허용, 빈값/파싱 실패는 -inf(가장 오래된 취급)."""
    s = (date_str or "").strip().replace("-", "")
    try:
        return datetime.strptime(s, "%Y%m%d").replace(tzinfo=KST).timestamp()
    except ValueError:
        return float("-inf")


_STATUS_ORDER = {"접수중": 0, "접수예정": 1, "일정미정": 2, "마감": 3}
# ponytail: 한 조회의 상한. ±120일 창 실측이 APT 108건이라 5배 여유. 더 필요해지면 올린다.
_MAX_ROWS = 500


def _fetch_list(endpoint: str, days_back: int, days_forward: int) -> list[dict]:
    """공고 목록 공통 경로 — 기간 조건으로 전 페이지를 모아 상태·공고일 순으로 정렬한다.

    perPage=100 단일 호출은 조회 창을 넓히면 조용히 잘렸다(프론트가 쓰는 ±120일 창에서
    matchCount 108건 중 100건만 돌아와 8건이 사라지고 "100건"이라는 틀린 수를 표시했다).
    matchCount 를 다 채울 때까지 page 를 넘긴다.
    """
    today = today_kst()
    params = {
        "cond[RCRIT_PBLANC_DE::GTE]": (today - timedelta(days=days_back)).isoformat(),
        "cond[RCRIT_PBLANC_DE::LTE]": (today + timedelta(days=days_forward)).isoformat(),
        "perPage": 100,
    }

    rows: list[dict] = []
    page = 1
    while True:
        data = _call(endpoint, {**params, "page": page})
        batch = data.get("data") or []
        rows.extend(batch)
        if not batch or len(rows) >= int(data.get("matchCount") or 0) or len(rows) >= _MAX_ROWS:
            break
        page += 1

    results = [_row_to_summary(r) for r in rows[:_MAX_ROWS]]
    # 접수중 → 접수예정 → 일정미정 → 마감 순, 같은 그룹 안에서는 공고일 내림차순(최신 먼저).
    results.sort(key=lambda r: (_STATUS_ORDER.get(r["status"], 9), -_announcement_ts(r.get("announcement_date"))))
    return results


def fetch_recent_apt(days_back: int = 60, days_forward: int = 60) -> list[dict]:
    """Fetch APT 분양정보 for recent + upcoming announcements."""
    return _fetch_list("getAPTLttotPblancDetail", days_back, days_forward)


def fetch_officetel(days_back: int = 60, days_forward: int = 60) -> list[dict]:
    """Fetch 오피스텔/도시형/민간임대 분양정보."""
    return _fetch_list("getUrbtyOfctlLttotPblancDetail", days_back, days_forward)


def fetch_remaining_apt(days_back: int = 60, days_forward: int = 60) -> list[dict]:
    """Fetch APT 무순위/잔여세대 분양정보."""
    return _fetch_list("getRemndrLttotPblancDetail", days_back, days_forward)


def fetch_opt_supply(days_back: int = 60, days_forward: int = 60) -> list[dict]:
    """Fetch 임의공급 분양정보."""
    return _fetch_list("getOPTLttotPblancDetail", days_back, days_forward)


def fetch_public_rent(days_back: int = 60, days_forward: int = 60) -> list[dict]:
    """Fetch 공공지원 민간임대 분양정보."""
    return _fetch_list("getPblPvtRentLttotPblancDetail", days_back, days_forward)


def fetch_apt_housing_types(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """Fetch 주택형별 상세 for a specific 공고."""
    data = _call(
        "getAPTLttotPblancMdl",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
        },
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "supply_area": r.get("SUPLY_AR", ""),
            "supply_count": r.get("SUPLY_HSHLDCO", 0) or 0,
            "special_count": r.get("SPSPLY_HSHLDCO", 0) or 0,
            "general_count": r.get("GNRL_HSHLDCO", 0) or 0,
            "lttot_top_amount": r.get("LTTOT_TOP_AMOUNT", ""),
        }
        for r in rows
    ]


# ── 경쟁률 / 당첨 가점 API (ApplyhomeInfoCmpetRtSvc) ────


def fetch_apt_competition(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """APT 경쟁률 조회 — 주택형별·지역별 경쟁률."""
    data = _call(
        "getAPTLttotPblancCmpet",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
            "perPage": 200,
        },
        base=_BASE_CMPET,
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "supply_count": r.get("SUPLY_HSHLDCO", 0) or 0,
            "rank": r.get("SUBSCRPT_RANK_CODE", ""),
            "region_code": r.get("RESIDE_SECD", ""),
            "region_name": r.get("RESIDE_SENM", ""),
            "applicants": r.get("REQ_CNT", "0"),
            "competition_rate": r.get("CMPET_RATE", "0"),
        }
        for r in rows
    ]


def fetch_officetel_competition(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """오피스텔/도시형/민간임대 경쟁률 조회."""
    data = _call(
        "getUrbtyOfctlLttotPblancCmpet",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
            "perPage": 200,
        },
        base=_BASE_CMPET,
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "supply_count": r.get("SUPLY_HSHLDCO", 0) or 0,
            "resident_prior": r.get("RESIDNT_PRIOR_SENM", ""),
            "applicants": r.get("REQ_CNT", "0"),
            "competition_rate": r.get("CMPET_RATE", "0"),
        }
        for r in rows
    ]


def fetch_public_rent_competition(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """공공지원 민간임대 경쟁률 조회."""
    data = _call(
        "getPblPvtRentLttotPblancCmpet",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
            "perPage": 200,
        },
        base=_BASE_CMPET,
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "supply_count": r.get("SUPLY_HSHLDCO", 0) or 0,
            "supply_type": r.get("SPSPLY_KND_NM", ""),
            "supply_type_count": r.get("SPSPLY_KND_HSHLDCO", 0) or 0,
            "applicants": r.get("REQ_CNT", "0"),
            "competition_rate": r.get("CMPET_RATE", "0"),
        }
        for r in rows
    ]


def fetch_opt_competition(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """임의공급 경쟁률 조회."""
    data = _call(
        "getOPTLttotPblancCmpet",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
            "perPage": 200,
        },
        base=_BASE_CMPET,
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "supply_count": r.get("SUPLY_HSHLDCO", 0) or 0,
            "applicants": r.get("REQ_CNT", "0"),
            "competition_rate": r.get("CMPET_RATE", "0"),
        }
        for r in rows
    ]


def fetch_apt_scores(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """APT 당첨 가점 정보 조회."""
    data = _call(
        "getAptLttotPblancScore",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
            "perPage": 200,
        },
        base=_BASE_CMPET,
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "supply_count": r.get("SUPLY_HSHLDCO", 0) or 0,
            "region_name": r.get("RESIDE_SENM", ""),
            "min_score": r.get("LWET_SCORE", ""),
            "max_score": r.get("TOP_SCORE", ""),
            "avg_score": r.get("AVRG_SCORE", ""),
        }
        for r in rows
    ]


def fetch_apt_special_supply(house_manage_no: str, pblanc_no: str) -> list[dict]:
    """APT 특별공급 신청현황 조회."""
    data = _call(
        "getAPTSpsplyReqstStus",
        {
            "cond[HOUSE_MANAGE_NO::EQ]": house_manage_no,
            "cond[PBLANC_NO::EQ]": pblanc_no,
            "perPage": 200,
        },
        base=_BASE_CMPET,
    )
    rows = data.get("data", [])
    return [
        {
            "house_ty": r.get("HOUSE_TY", ""),
            "special_total": r.get("SPSPLY_HSHLDCO", 0) or 0,
            "multi_child": r.get("MNYCH_HSHLDCO", 0) or 0,
            "newlywed": r.get("NWWDS_NMTW_HSHLDCO", 0) or 0,
            "first_life": r.get("LFE_FRST_HSHLDCO", 0) or 0,
            "elderly_parent": r.get("OLD_PARNTS_SUPORT_HSHLDCO", 0) or 0,
            "institution": r.get("INSTT_RECOMEND_HSHLDCO", 0) or 0,
            "result": r.get("SUBSCRPT_RESULT_NM", ""),
        }
        for r in rows
    ]
