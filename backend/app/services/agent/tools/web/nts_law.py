"""국가법령정보 국세청 법령해석 목록 API (ntsCgmExpc, XML).

목록 응답에는 메타·법령해석 상세링크만 있다. 상세 본문은 링크 페이지에 있으며,
taxlaw.nts.go.kr 은 JS로 본문을 채우므로 설정 시 Playwright로 렌더 후 텍스트를
추출한다(선택 의존성 `nts-law-detail`). GET만 하면 툴바 문구만 잡히는 경우가 많다.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import requests

from ._config import (
    NTS_LAW_DETAIL_TEXT_MAX_CHARS,
    NTS_LAW_DETAIL_TOP_N,
    NTS_LAW_FALLBACK_API_QUERIES,
    NTS_LAW_FETCH_DETAIL_PAGE_TEXT,
    NTS_LAW_MAX_API_QUERIES,
    NTS_LAW_PLAYWRIGHT_TIMEOUT_MS,
    NTS_LAW_USE_PLAYWRIGHT_DETAIL,
)

logger = logging.getLogger(__name__)

NTS_LAW_SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"

_ALLOWED_DETAIL_HOSTS = frozenset(
    {
        "taxlaw.nts.go.kr",
        "www.law.go.kr",
        "law.go.kr",
    }
)

_DETAIL_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Langgraph-user-asset-example/1.0; "
        "+https://github.com/) AppleWebKit/537.36 (KHTML, like Gecko)"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
}


def _is_allowed_detail_url(url: str) -> bool:
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return False
        host = (p.hostname or "").lower()
        return host in _ALLOWED_DETAIL_HOSTS
    except Exception:
        return False


def html_to_plain_excerpt(html: str, max_chars: int) -> str:
    """HTML을 거친 플레인 텍스트로(스크립트·태그 제거)."""

    s = html_lib.unescape(html or "")
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_chars:
        s = s[:max_chars].rstrip() + " …"
    return s


def _is_taxlaw_nts_host(url: str) -> bool:
    try:
        return (urlparse(url.strip()).hostname or "").lower() == "taxlaw.nts.go.kr"
    except Exception:
        return False


def _fetch_nts_law_detail_http(
    url: str,
    *,
    timeout: int = 25,
    max_chars: int | None = None,
) -> str:
    """상세 URL 단순 GET 후 HTML→플레인(초기 응답만; taxlaw 는 본문 없을 수 있음)."""

    cap = max_chars if max_chars is not None else NTS_LAW_DETAIL_TEXT_MAX_CHARS
    u = (url or "").strip()
    if not u:
        return "(상세 URL 없음)"
    if not _is_allowed_detail_url(u):
        logger.warning("허용되지 않은 상세 URL 무시: %r", u[:120])
        return "(상세 URL 허용 목록에 없음)"

    try:
        r = requests.get(
            u,
            timeout=timeout,
            headers=_DETAIL_HTTP_HEADERS,
            allow_redirects=True,
        )
        r.raise_for_status()
        final = (r.url or u).strip()
        if not _is_allowed_detail_url(final):
            return "(리다이렉트 도메인이 허용 목록에 없음)"
        ct = (r.headers.get("Content-Type") or "").lower()
        if "html" not in ct and "text" not in ct and ct:
            return f"(상세 응답이 HTML 아님: {ct})"
        plain = html_to_plain_excerpt(r.text, cap)
        if not plain:
            return "(상세 페이지에서 텍스트 추출 실패)"
        return plain
    except Exception as exc:  # noqa: BLE001
        logger.info("상세 페이지 GET 실패 url=%r err=%s", u[:100], exc)
        return f"(상세 페이지 요청 실패: {exc})"


def _playwright_batch_taxlaw(urls: list[str], max_chars: int) -> list[str]:
    """taxlaw.nts.go.kr 상세 N건을 한 브라우저에서 순차 로드·본문 추출."""

    if not urls:
        return []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        msg = (
            "(Playwright 미설치: 프로젝트 루트에서 "
            "`uv sync --extra nts-law-detail` 후 `playwright install chromium`)"
        )
        return [msg] * len(urls)

    timeout = max(5_000, NTS_LAW_PLAYWRIGHT_TIMEOUT_MS)
    out: list[str] = []

    def _extract_body(page: Any) -> str:
        from playwright.sync_api import TimeoutError as PwTimeout

        try:
            page.wait_for_function(
                """() => {
                    const el = document.querySelector(
                        "[data-center-type='body_content']"
                    );
                    return el && el.innerText && el.innerText.trim().length > 40;
                }""",
                timeout=timeout,
            )
        except PwTimeout:
            logger.info("NTS body_content 로딩 대기 타임아웃(폴백 시도)")

        text = ""
        body_loc = page.locator("[data-center-type='body_content']")
        if body_loc.count() > 0:
            text = (body_loc.first.inner_text() or "").strip()
        if len(text) < 40:
            box = page.locator("#dcmDetailBox")
            if box.count() > 0:
                text = (box.first.inner_text() or "").strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + " …"
        return text if text else "(본문 영역을 찾지 못함)"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_default_timeout(timeout)
            for u in urls:
                u = (u or "").strip()
                if not u:
                    out.append("(상세 URL 없음)")
                    continue
                if not _is_allowed_detail_url(u):
                    out.append("(상세 URL 허용 목록에 없음)")
                    continue
                if not _is_taxlaw_nts_host(u):
                    out.append(_fetch_nts_law_detail_http(u, max_chars=max_chars))
                    continue
                try:
                    page.goto(
                        u,
                        wait_until="domcontentloaded",
                        timeout=timeout,
                    )
                    out.append(_extract_body(page))
                except Exception as exc:  # noqa: BLE001
                    logger.info(
                        "Playwright 상세 실패 url=%r err=%s", u[:100], exc
                    )
                    out.append(f"(상세 페이지 Playwright 실패: {exc})")
        finally:
            browser.close()
    return out


def fetch_nts_law_detail_plain_text(
    url: str,
    *,
    timeout: int = 25,
    max_chars: int | None = None,
) -> str:
    """목록 API가 준 상세 URL에서 본문 발췌. taxlaw 는 Playwright 우선(SSRF 방지)."""

    cap = max_chars if max_chars is not None else NTS_LAW_DETAIL_TEXT_MAX_CHARS
    u = (url or "").strip()
    if not u:
        return "(상세 URL 없음)"
    if not _is_allowed_detail_url(u):
        logger.warning("허용되지 않은 상세 URL 무시: %r", u[:120])
        return "(상세 URL 허용 목록에 없음)"

    if NTS_LAW_USE_PLAYWRIGHT_DETAIL and _is_taxlaw_nts_host(u):
        return _playwright_batch_taxlaw([u], cap)[0]
    return _fetch_nts_law_detail_http(u, timeout=timeout, max_chars=cap)


def require_law_go_kr_oc() -> None:
    """국세청 법령해석 목록(ntsCgmExpc) live 호출에 필요."""

    oc = (os.environ.get("LAW_GO_KR_OC") or "").strip()
    if not oc:
        raise ValueError(
            "LAW_GO_KR_OC 가 필요합니다. .env 에 국가법령정보 Open API 발급 OC 를 설정하세요. "
            "(https://open.law.go.kr)"
        )


def nts_xml_local_tag(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_cgm_expc_xml(
    xml_text: str,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    raw = (xml_text or "").strip()
    if not raw:
        return [], "빈 응답", None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [], f"XML 파싱 오류: {exc}", None

    root_name = nts_xml_local_tag(root.tag)
    if root_name.lower() != "cgmexpc":
        return [], f"루트 태그가 CgmExpc 가 아님: {root_name!r}", None

    result_code = (root.findtext("resultCode") or "").strip()
    result_msg = (root.findtext("resultMsg") or "").strip()
    if result_code and result_code != "00":
        return [], f"API resultCode={result_code} {result_msg}".strip(), None

    total_cnt = root.findtext("totalCnt")
    records: list[dict[str, Any]] = []
    for child in root:
        if nts_xml_local_tag(child.tag).lower() != "cgmexpc":
            continue
        rec: dict[str, Any] = {}
        cid = child.attrib.get("id")
        if cid is not None:
            rec["id"] = cid
        for sub in child:
            key = nts_xml_local_tag(sub.tag)
            rec[key] = (sub.text or "").strip()
        if rec:
            records.append(rec)

    return records, None, (total_cnt.strip() if total_cnt else None) or None


def rec_detail_link(rec: dict[str, Any]) -> str:
    explicit = (
        rec.get("법령해석상세링크")
        or rec.get("법령해석 상세링크")
        or rec.get("lsEfLink")
    )
    if explicit:
        return str(explicit).strip()
    for k, v in rec.items():
        if not isinstance(k, str) or v is None:
            continue
        collapsed = k.replace(" ", "")
        if "상세링크" in collapsed or (
            "상세" in collapsed and "링크" in collapsed
        ):
            return str(v).strip()
    return ""


def law_record_to_line(
    rec: dict[str, Any],
    idx: int,
    *,
    detail_excerpt: str | None = None,
) -> str:
    """제목·번호·일·링크 + 선택적으로 상세 페이지 발췌."""

    title = (rec.get("안건명") or rec.get("lawItmNm") or "").strip()
    no = (rec.get("안건번호") or "").strip()
    ymd = (rec.get("해석일자") or "").strip()
    link = rec_detail_link(rec)
    meta = " · ".join(p for p in (no, ymd) if p)
    block = f"{idx}. {title}" if title else f"{idx}. (제목 없음)"
    if meta:
        block += f"\n   {meta}"
    if link:
        block += f"\n   {link}"
    if detail_excerpt and not detail_excerpt.startswith("(상세"):
        ex = detail_excerpt.strip()
        if ex:
            block += f"\n   [상세 페이지 발췌]\n   {ex}"
    elif detail_excerpt and detail_excerpt.startswith("("):
        block += f"\n   {detail_excerpt}"
    return block


def law_records_to_text(
    records: list[dict[str, Any]],
    *,
    header: str,
    detail_by_index: dict[int, str] | None = None,
) -> str:
    if not records:
        return "(검색 결과 없음)"
    max_items = 8
    d = detail_by_index or {}
    body = "\n".join(
        law_record_to_line(
            r,
            i + 1,
            detail_excerpt=d.get(i + 1),
        )
        for i, r in enumerate(records[:max_items])
    )
    return f"{header}\n{body}".strip()


def nts_cgm_search_once(query: str, *, display: int = 8) -> str:
    oc = (os.environ.get("LAW_GO_KR_OC") or "").strip()
    if not oc:
        return (
            "(국세청 법령해석 API: LAW_GO_KR_OC 미설정 — tax_research 시작 전 "
            "require_law_go_kr_oc() 를 호출하세요.)"
        )
    params = {
        "OC": oc,
        "target": "ntsCgmExpc",
        "type": "XML",
        "search": 1,
        "query": query,
        "display": min(max(1, display), 100),
        "page": 1,
    }
    try:
        r = requests.get(NTS_LAW_SEARCH_URL, params=params, timeout=25)
        r.raise_for_status()
        body = r.text.strip()
    except Exception as exc:  # noqa: BLE001
        return f"(국세청 법령해석 API 요청 실패: {exc})"

    if body.startswith("{"):
        try:
            err_obj = json.loads(body)
            if isinstance(err_obj, dict) and (
                err_obj.get("msg") or err_obj.get("result")
            ):
                return (
                    "(국세청 법령해석 API: "
                    f"{err_obj.get('msg') or err_obj.get('result')})"
                )
        except json.JSONDecodeError:
            pass

    recs, err, total_cnt = parse_cgm_expc_xml(body)
    if err:
        return f"(국세청 법령해석 XML: {err})"
    n = len(recs)
    tc = total_cnt or "?"
    fetch = NTS_LAW_FETCH_DETAIL_PAGE_TEXT
    top = min(NTS_LAW_DETAIL_TOP_N, n, 8)
    detail_by_index: dict[int, str] = {}
    cap = NTS_LAW_DETAIL_TEXT_MAX_CHARS
    if fetch and top > 0:
        pending_pw: list[tuple[int, str]] = []
        for i in range(top):
            link = rec_detail_link(recs[i])
            idx = i + 1
            if not link:
                detail_by_index[idx] = "(상세 URL 없음)"
                continue
            if not _is_allowed_detail_url(link):
                detail_by_index[idx] = "(상세 URL 허용 목록에 없음)"
                continue
            if NTS_LAW_USE_PLAYWRIGHT_DETAIL and _is_taxlaw_nts_host(link):
                pending_pw.append((idx, link))
            else:
                excerpt = _fetch_nts_law_detail_http(link, max_chars=cap)
                detail_by_index[idx] = excerpt
                logger.info(
                    "NTS 법령해석 상세 발췌(GET) query=%r idx=%d chars=%d",
                    query,
                    idx,
                    len(excerpt),
                )

        if pending_pw:
            urls = [u for _, u in pending_pw]
            excerpts = _playwright_batch_taxlaw(urls, cap)
            for (idx, _), ex in zip(pending_pw, excerpts, strict=True):
                detail_by_index[idx] = ex
                logger.info(
                    "NTS 법령해석 상세 발췌(Playwright) query=%r idx=%d chars=%d",
                    query,
                    idx,
                    len(ex),
                )

    any_pw = bool(
        fetch
        and top > 0
        and NTS_LAW_USE_PLAYWRIGHT_DETAIL
        and any(
            _is_taxlaw_nts_host(rec_detail_link(recs[i]) or "")
            for i in range(top)
        )
    )
    head = (
        f"[법령해석] 검색={query!r} 전체≈{tc}건·항목 {n}건"
        + (
            (
                f" · 상위 {top}건 상세 본문(Playwright)"
                if any_pw
                else f" · 상위 {top}건 상세 발췌(GET)"
            )
            if fetch and top > 0
            else " · 목록 메타만(상세 발췌 끔)"
        )
    )
    logger.info(
        "NTS 법령해석 live query=%r records=%d totalCnt=%s",
        query,
        len(recs),
        total_cnt,
    )
    return law_records_to_text(recs, header=head, detail_by_index=detail_by_index)


def resolve_nts_law_search_specs(profile: dict[str, Any]) -> list[tuple[str, str]]:
    """프로필의 `nts_law_api_queries`(Open API용 정리 키워드) → (라벨, 검색어). 비면 폴백."""

    raw = profile.get("nts_law_api_queries")
    seen: set[str] = set()
    queries: list[str] = []
    if isinstance(raw, list):
        for x in raw:
            q = str(x).strip()
            if not q or len(q) > 48:
                continue
            key = q.casefold()
            if key in seen:
                continue
            seen.add(key)
            queries.append(q)
            if len(queries) >= NTS_LAW_MAX_API_QUERIES:
                break
    if not queries:
        queries = list(NTS_LAW_FALLBACK_API_QUERIES)
    return [(f"검색{i + 1}", q) for i, q in enumerate(queries)]
