"""네이버 검색 API (webkr)."""

from __future__ import annotations

import html as html_lib
import logging
import os
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)


def strip_html_bold(s: str) -> str:
    t = html_lib.unescape(s or "")
    return re.sub(r"<[^>]+>", "", t)


def require_naver_search_keys() -> None:
    cid = (os.environ.get("NAVER_CLIENT_ID") or "").strip()
    csec = (os.environ.get("NAVER_CLIENT_SECRET") or "").strip()
    if not cid or not csec:
        raise ValueError(
            "네이버 검색 API 키가 필요합니다. .env 에 NAVER_CLIENT_ID 와 "
            "NAVER_CLIENT_SECRET 을 설정하세요."
        )


def naver_query_suffix(profile: dict[str, Any]) -> str: # 목표 기간(개월) 또는 월 여유금액(원 단위 정수)
    parts: list[str] = []
    horizon = profile.get("horizon_months")
    if horizon is not None:
        parts.append(f"{horizon}개월")
    surplus = profile.get("monthly_surplus_krw")
    if surplus is not None:
        try:
            n = int(surplus)
        except (TypeError, ValueError):
            n = 0
        if n > 0 and n % 10_000 == 0:
            parts.append(f"월{n // 10_000}만원")
        elif n > 0:
            parts.append(f"월{n}원")
    return " ".join(parts)


def naver_web_search_once(query: str, max_results: int = 4) -> str:
    cid = (os.environ.get("NAVER_CLIENT_ID") or "").strip()
    csec = (os.environ.get("NAVER_CLIENT_SECRET") or "").strip()
    display = min(max(1, max_results), 20)
    log_body_cap = 12_000

    def _log_result(
        body: str,
        *,
        api_total: Any = None,
        item_count: int | None = None,
    ) -> None:
        shown = (
            body
            if len(body) <= log_body_cap
            else body[:log_body_cap] + "\n... [로그 길이 제한으로 잘림]"
        )
        extra = ""
        if item_count is not None:
            extra += f" items={item_count}"
        if api_total is not None:
            extra += f" api_total={api_total}"
        logger.info("Naver webkr query=%r display=%d%s\n%s", query, display, extra, shown)

    try:
        r = requests.get(
            "https://openapi.naver.com/v1/search/webkr.json",
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
            params={"query": query, "display": display, "sort": "sim"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        api_err = data.get("errorMessage")
        if api_err:
            code = data.get("errorCode") or ""
            out = f"(네이버 API 오류 {code}: {api_err})"
            _log_result(out)
            return out
        items = data.get("items") or []
        lines: list[str] = []
        for it in items:
            title = strip_html_bold(it.get("title") or "")
            desc = strip_html_bold((it.get("description") or ""))[:300]
            lines.append(f"- {title}: {desc}")
        out = "\n".join(lines) if lines else "(결과 없음)"
        _log_result(out, api_total=data.get("total"), item_count=len(items))
        return out
    except Exception as exc:  # noqa: BLE001
        out = f"(네이버 검색 오류: {exc})"
        _log_result(out)
        return out


def naver_web_snippets(
    query: str,
    max_results: int = 4,
    *,
    fallback_query: str | None = None,
) -> str:
    out = naver_web_search_once(query, max_results)
    if out != "(결과 없음)" or not fallback_query:
        return out
    logger.info("Naver webkr 1차 결과 없음 → fallback 검색")
    return naver_web_search_once(fallback_query, max_results)
