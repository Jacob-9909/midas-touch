"""fraud_check 도구 — 사기 메시지 휴리스틱 스코어러 + 선택적 웹 검색 보강.

URL 패턴(짧은링크·IP·오타 도메인), 고수익 보장 문구, 개인 SNS·오픈채팅 유도, 선입금 요구,
정부기관 사칭 카테고리별 점수를 합산해 위험/주의/확인필요 3단으로 판정한다. 오프라인
휴리스틱만으로 완결되며, TAVILY_API_KEY가 있을 때만 최신 피싱 정보를 1~2건 덧붙인다.

절대 단정 금지 원칙: 판정은 어디까지나 패턴 기반 참고 정보이며, 어떤 결과에도 신고 안내
(경찰청 112, 금융감독원 1332) 문구를 반드시 붙인다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# 점수 설계 (카테고리별 가중치와 상한)
# ---------------------------------------------------------------------------
SCORE_URL_SHORTENER = 15   # 짧은 링크
SCORE_URL_IP_HOST = 30     # IP 주소 직접 연결
SCORE_URL_TYPOSQUAT = 30   # 브랜드 도메인 사칭(훼칭)
SCORE_URL_SUSPICIOUS_TLD = 15  # 의심 TLD(.xyz/.top 등)
HIGH_RETURN_HIT_SCORE = 25     # 고수익 보장 문구 1건당, 상한
SNS_LURE_HIT_SCORE = 10        # SNS 유도 1건당, 상한
ADVANCE_PAYMENT_HIT_SCORE = 25  # 선입금 요구 1건당, 상한
IMPERSONATION_MENTION_SCORE = 15   # 기관명 언급만
IMPERSONATION_COERCION_SCORE = 20  # 압박·위협 맥락 결합
IMPERSONATION_EXPLICIT_SCORE = 30  # "사칭" 직접 언급
_HIGH_RETURN_CAP = 50
_SNS_LURE_CAP = 20
_ADVANCE_PAYMENT_CAP = 50

VERDICT_DANGER_MIN = 60  # >= 이면 위험
VERDICT_CAUTION_MIN = 30  # >= 이면 주의, 미만이면 확인필요

DISCLAIMER_NOTE = (
    "본 판정은 패턴 기반 휴리스틱 참고 정보입니다. 사기 여부를 절대 단정하지 않으며, "
    "정상 통신도 걸릴 수 있고 교묘한 사기는 미탐지될 수 있습니다."
)
REPORT_GUIDE_NOTE = (
    "의심되는 경우 거래·이체를 즉시 중단하고 경찰청 112 또는 금융감독원 1332로 "
    "신고·상담하십시오."
)

# ---------------------------------------------------------------------------
# 탐지 패턴 정의
# ---------------------------------------------------------------------------
_SHORTENER_DOMAINS = (
    "bit.ly", "t.ly", "tinyurl.com", "goo.gl", "ow.ly", "is.gd",
    "cutt.ly", "url.kr", "me2.kr", "bit.do", "rebrand.ly", "shorturl.at",
)
_SUSPICIOUS_TLDS = ("xyz", "top", "icu", "club", "online", "site", "shop", "buzz", "click")

_HTTP_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_BARE_DOMAIN_RE = re.compile(
    r"\b(?:[\w-]+\.)+(?:co\.kr|or\.kr|pe\.kr|re\.kr|com|net|org|kr|xyz|top|icu|club|online|site|shop|buzz)\b",
    re.IGNORECASE,
)
_IP_HOST_RE = re.compile(r"https?://(\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?", re.IGNORECASE)

# 브랜드 → 공식 도메인. 호스트에 브랜드가 들어 있는데 공식 도메인으로 끝나지 않으면 훼칭 의심.
_BRAND_OFFICIAL_DOMAINS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("naver", ("naver.com",)),
    ("kakao", ("kakao.com", "kakaobank.com", "kakaopay.com")),
    ("kbank", ("kbank.co.kr",)),
    ("shinhan", ("shinhan.com",)),
    ("woori", ("wooribank.com",)),
    ("kbstar", ("kbstar.com",)),
    ("toss", ("tossbank.com", "toss.im")),
    ("hana", ("hanabank.com",)),
    ("samsung", ("samsung.com", "samsungsec.com")),
    ("nts", ("nts.go.kr",)),
    ("fss", ("fss.or.kr",)),
)

_HIGH_RETURN_PHRASES = (
    "절대 손실 없", "손실 없음", "수익률 보장", "원금 보장", "확정 수익", "무손실",
    "보장된 수익", "보장 이율", "리스크 없", "단타 확정", "두배", "두 배", "10배", "100배",
)
_MONTHLY_PROMISE_RE = re.compile(r"월\s*\d+\s*(?:%|퍼센트)")
_ANNUAL_PROMISE_RE = re.compile(r"연\s*\d{2,}\s*(?:%|퍼센트)")

_SNS_LURE_PHRASES = (
    "오픈채팅", "오픈 프로필", "카톡", "카카오톡", "텔레그램", "텔레그램채널", "라인",
    "whatsapp", "디스코드", "discord", "dm", "쪽지", "1:1 상담", "채널 추가", "채널추가",
)

_ADVANCE_PAYMENT_PHRASES = (
    "선입금", "먼저 입금", "먼저 송금", "선 송금", "보증금", "예치금", "검증금",
    "수수료 입금", "수수료를 입금", "입금 후 이용", "이체 후 시작", "계좌로 입금",
)

_IMPERSONATION_INSTITUTIONS = (
    "검찰", "검사", "경찰", "국세청", "금융감독원", "금감원", "법원",
    "한국은행", "금융위", "과학수사대",
)
_IMPERSONATION_COERCION = (
    "수사", "혐의", "압류", "압수", "환수", "동결", "해지", "체납",
    "벌금", "강제", "즉시 이체", "즉시 입금", "신원 확인 차",
)


# ---------------------------------------------------------------------------
# 휴리스틱 스코어러 (순수 함수 — 네트워크 불필요, 오프라인 완결)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FraudSignal:
    category: str
    detail: str
    score: int


@dataclass(frozen=True)
class FraudReport:
    signals: list[FraudSignal] = field(default_factory=list)
    total_score: int = 0

    @property
    def verdict(self) -> str:
        if self.total_score >= VERDICT_DANGER_MIN:
            return "위험"
        if self.total_score >= VERDICT_CAUTION_MIN:
            return "주의"
        return "확인필요"


def _capped_signal(category: str, hits: list[str], per_hit: int, cap: int) -> FraudSignal | None:
    """같은 카테고리의 다중 적중은 상한(cap)까지만 인정한다."""
    if not hits:
        return None
    return FraudSignal(
        category=category,
        detail="; ".join(dict.fromkeys(hits)),
        score=min(len(hits) * per_hit, cap),
    )


def _extract_hosts(text: str) -> list[str]:
    hosts: list[str] = []
    for url in _HTTP_URL_RE.findall(text):
        host = urlparse(url).netloc.lower().rstrip(".")
        if host:
            hosts.append(host)
    for m in _BARE_DOMAIN_RE.finditer(text):
        hosts.append(m.group(0).lower().rstrip("."))
    return list(dict.fromkeys(hosts))


def scan_message(text: str) -> FraudReport:
    """발화/문자 본문을 카테고리별로 스캔해 점수 합계와 근거를 돌려준다."""
    lowered = text.lower()
    signals: list[FraudSignal] = []

    # 1) URL 패턴
    shorteners = [h for h in _extract_hosts(text) for d in _SHORTENER_DOMAINS if h == d or h.endswith("." + d)]
    if ip_match := _IP_HOST_RE.search(text):
        signals.append(
            FraudSignal("URL 위험", f"IP 주소 직접 연결({ip_match.group(1)})", SCORE_URL_IP_HOST)
        )
    typosquats: list[str] = []
    typo_hosts: set[str] = set()
    suspicious_tlds: list[str] = []
    for host in _extract_hosts(text):
        for brand, officials in _BRAND_OFFICIAL_DOMAINS:
            if brand in host and not any(host == off or host.endswith("." + off) for off in officials):
                typosquats.append(f"{host} ({brand} 사칭 의심)")
                typo_hosts.add(host)
                break
        tld = host.rsplit(".", 1)[-1]
        if tld in _SUSPICIOUS_TLDS and host not in typo_hosts:
            suspicious_tlds.append(host)
    if shorteners:
        signals.append(FraudSignal("URL 위험", f"짧은 링크 사용({', '.join(shorteners)})", SCORE_URL_SHORTENER))
    if typosquat := _capped_signal("URL 위험", typosquats, SCORE_URL_TYPOSQUAT, SCORE_URL_TYPOSQUAT):
        signals.append(typosquat)
    if suspicious_tlds:
        signals.append(
            FraudSignal("URL 위험", f"의심 TLD 사용({', '.join(suspicious_tlds)})", SCORE_URL_SUSPICIOUS_TLD)
        )

    # 2) 고수익 보장 문구
    high_return_hits = [p for p in _HIGH_RETURN_PHRASES if p in text]
    high_return_hits += [m.group(0) for m in _MONTHLY_PROMISE_RE.finditer(text)]
    high_return_hits += [m.group(0) for m in _ANNUAL_PROMISE_RE.finditer(text)]
    if sig := _capped_signal("고수익 보장", high_return_hits, HIGH_RETURN_HIT_SCORE, _HIGH_RETURN_CAP):
        signals.append(sig)

    # 3) 개인 SNS·오픈채팅 유도
    sns_hits = [p for p in _SNS_LURE_PHRASES if p in lowered]
    if sig := _capped_signal("SNS·오픈채팅 유도", sns_hits, SNS_LURE_HIT_SCORE, _SNS_LURE_CAP):
        signals.append(sig)

    # 4) 선입금 요구
    advance_hits = [p for p in _ADVANCE_PAYMENT_PHRASES if p in text]
    if sig := _capped_signal("선입금 요구", advance_hits, ADVANCE_PAYMENT_HIT_SCORE, _ADVANCE_PAYMENT_CAP):
        signals.append(sig)

    # 5) 정부기관 사칭 (기관 언급 + 압박 맥락 결합 시 강하게 가산)
    institutions = [w for w in _IMPERSONATION_INSTITUTIONS if w in text]
    coercions = [w for w in _IMPERSONATION_COERCION if w in text]
    impersonation_score = 0
    impersonation_detail: list[str] = []
    if institutions:
        impersonation_score += IMPERSONATION_MENTION_SCORE
        impersonation_detail.append(f"기관명 언급({', '.join(institutions)})")
    if institutions and coercions:
        impersonation_score += IMPERSONATION_COERCION_SCORE
        impersonation_detail.append(f"압박 맥락({', '.join(coercions)})")
    if "사칭" in text:
        impersonation_score += IMPERSONATION_EXPLICIT_SCORE
        impersonation_detail.append('"사칭" 직접 언급')
    if impersonation_detail:
        signals.append(
            FraudSignal("정부기관 사칭 의심", "; ".join(impersonation_detail), impersonation_score)
        )

    return FraudReport(signals=signals, total_score=sum(s.score for s in signals))


def format_report(report: FraudReport) -> str:
    lines = [f"### 판정: {report.verdict} (휴리스틱 점수 {report.total_score})", "발견된 근거:"]
    if report.signals:
        lines += [f"- [{s.category}] {s.detail} (+{s.score})" for s in report.signals]
    else:
        lines.append("- 탐지된 위험 신호 없음")
    lines.append("")
    lines.append(f"※ {DISCLAIMER_NOTE}")
    if report.verdict != "위험":
        lines.append("※ 탐지된 위험 신호가 없거나 낮아도 안전을 보장하지 않습니다.")
    lines.append(f"※ {REPORT_GUIDE_NOTE}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 웹 검색 보강 (TAVILY_API_KEY 있을 때만; 없으면 우아하게 생략)
# ---------------------------------------------------------------------------
def web_enrichment(text: str) -> str:
    """URL·문구 관련 최신 피싱 정보를 1~2건 조회한다. 키 부재/오류는 안내 문구로 흡수한다."""
    try:
        from .web import require_tavily_api_key

        require_tavily_api_key()
    except ValueError:
        return "(웹 검색 보강 생략: TAVILY_API_KEY 미설정 — 오프라인 휴리스틱만으로 판정했습니다.)"
    except Exception as exc:
        return f"(웹 검색 보강 생략: {exc})"

    try:
        from langchain_tavily import TavilySearch

        from .web import tavily_search_body

        tool = TavilySearch(max_results=2, search_depth="basic", include_answer=False)

        queries = ["최신 보이스피싱 스미싱 투자사기 문자 유형"]
        hosts = _extract_hosts(text)
        if hosts:
            queries.insert(0, f"{hosts[0]} 사이트 사기 피싱 여부")
        sections = [f"- 질의 '{q}':\n{tavily_search_body(tool, q)}" for q in queries[:2]]
        return "\n".join(sections)[:4000]
    except Exception as exc:
        return f"(웹 검색 보강 실패 — 오프라인 휴리스틱 판정은 유효합니다: {exc})"


# ---------------------------------------------------------------------------
# @tool 얇은 래퍼 (노드에서 invoke된다)
# ---------------------------------------------------------------------------
@tool
def fraud_check(message_text: str) -> str:
    """받은 문자·메신저 내용·링크(URL)가 사기성인지 휴리스틱으로 검증한다.
    투자 권유·고수익 보장·선입금 요구·정부기관 사칭·수상한 링크가 의심될 때 사용하라.
    판정은 '실제 사기 여부를 단정하지 않는' 참고 정보이며, 신고 안내를 함께 돌려준다.

    Args:
        message_text: 사용자가 받은 문자·알림·메시지 원문(링크가 포함되면 함께 넣는다).
    """
    report = scan_message(message_text)
    body = format_report(report)
    disabled = os.environ.get("FRAUD_CHECK_DISABLE_WEB", "").strip().lower() in ("1", "true")
    enrichment = "(생략됨)" if disabled else web_enrichment(message_text)
    body += "\n\n### 최신 피싱·사기 정보 (웹 검색 보강)\n" + enrichment
    return body
