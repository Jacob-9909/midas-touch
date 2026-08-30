"""fraud_check 도구 — 사기 메시지 휴리스틱 스코어러 + 선택적 웹 검색 보강.

URL 패턴(짧은링크·IP·오타 도메인), 고수익 보장 문구, 개인 SNS·오픈채팅 유도, 선입금 요구,
정부기관 사칭에 더해 가족·지인 사칭, 대출 빙자, 가상자산 리딩방, 환급·지원금 사칭,
알바·부업 보증금 사기를 카테고리별 점수로 합산해 위험/주의/확인필요 3단으로 판정한다.
브랜드 공식 도메인만 감지되면 오탐 감쇠(URL 안심)를 적용하고, 발견된 카테고리에 대응하는
결정론 행동 요령(LLM 개입 없음)을 보고서 말미에 자동 첨부한다. 오프라인 휴리스틱만으로
완결되며, TAVILY_API_KEY가 있을 때만 최신 피싱 정보를 1~2건 덧붙인다.

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
IMPERSONATION_SAFE_ACCOUNT_SCORE = 15  # "안전계좌"+입금 결합(수사기관은 '안전계좌 이체'를 요구하지 않음)
_HIGH_RETURN_CAP = 50
_SNS_LURE_CAP = 20
_ADVANCE_PAYMENT_CAP = 50

# 신규 5카테고리 (2026 금융 AI Challenge 실측 미탐지 갭 해소)
FAMILY_KINSHIP_URGENT_SCORE = 30  # 지인 호칭 + 긴급 상황 결합(기본)
FAMILY_EMERGENCY_BORROW_SCORE = 30  # 급전 요구 동사 + 연락 수단 변경 결합(호칭 없는 지인 사칭)
FAMILY_TRANSFER_SCORE = 25        # 송금 요구 동사 결합
FAMILY_SECRECY_SCORE = 20         # 은폐 지시 결합
_FAMILY_CAP = 75

LOAN_TARGET_SCORE = 30            # 저신용·무직 등 취약 조건 타깃 언급
LOAN_INSTANT_APPROVAL_SCORE = 20  # 즉시 대출·승인 문구
_LOAN_CAP = 50                    # 선입금 요구와 자연스럽게 합산되도록 상한을 낮게 둔다

CRYPTO_KEYWORD_HIT_SCORE = 15     # 리딩방·거래소 키워드 1건당, 상한
CRYPTO_DEPOSIT_SCORE = 25         # 입금 유도 결합
_CRYPTO_KEYWORD_CAP = 30

REFUND_MENTION_SCORE = 20         # 환급·지원금 언급
REFUND_PRESSURE_LURE_SCORE = 25   # 마감 압박 또는 계좌·링크 유도 결합
_REFUND_CAP = 45

PARTTIME_RECRUIT_SCORE = 25       # 수익성 알바·부업 모집
PARTTIME_UPFRONT_COST_SCORE = 25  # 시작 전 비용 요구 결합(보증금 등은 선입금과 중복 가산 허용)
_PARTTIME_CAP = 50                # 모집 25 + 비용 결합 25: 선입금 요구(25)와 합산해야 실측
                                  # 보증금 사기 샘플이 위험 역치(60)에 도달한다.

SCORE_URL_RELIEF = -10            # 공식 도메인만 감지된 경우 오탐 감쇠(총점 하한 0)

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
    "수수료 입금", "수수료를 입금", "입금 후 이용", "이체 후 시작", "계좌로 입금", "즉시 입금",
)

_IMPERSONATION_INSTITUTIONS = (
    "검찰", "검사", "경찰", "국세청", "금융감독원", "금감원", "법원",
    "한국은행", "금융위", "과학수사대",
)
_IMPERSONATION_COERCION = (
    "수사", "혐의", "압류", "압수", "환수", "동결", "해지", "체납",
    "벌금", "강제", "즉시 이체", "즉시 입금", "신원 확인 차", "안전계좌",
)

# 가족·지인 사칭: 지인 호칭 + 긴급 상황이 겹치는 것이 전제이고, 송금 요구·은폐 지시가
# 덧붙일수록 위험도를 높인다(보이스피싱 상위 유형 — 가족 사칭 문자).
# 호칭이 빠진 문자라도 급전 요구 동사와 연락 수단 변경(번호 바뀜·두절)이 겹치면 지인 사칭으로 본다.
_FAMILY_KINSHIP_TERMS = (
    "아들", "딸", "엄마", "아빠", "할머니", "할아버지", "형", "누나", "언니", "오빠",
)
_FAMILY_URGENT_TERMS = (
    "사고", "병원", "경찰서", "교통사고", "긴급",
    "수술비", "입원비", "폰 액정", "휴대폰 분실", "임시번호", "번호 바꿨", "연결이 안 되",
)
_FAMILY_TRANSFER_TERMS = (
    "보내줘", "이체해줘", "송금해줘", "입금해줘", "빌려줘",
    "입금해주면", "송금해주면", "만원만", "원만 보내",
)
_FAMILY_SECRECY_TERMS = ("전화하지 마", "비밀", "말하지 마", "연락 금지")
_FAMILY_MONEY_ASK_TERMS = ("빌려줘", "급하게 빌려", "돈 빌려")
_FAMILY_CONTACT_CHANGE_TERMS = ("번호 바꿨", "번호가 바뀌", "임시번호", "연결이 안 되", "전화가 안 되")

# 대출 빙자 사기: 저신용·무직 등 취약 조건을 노린 뒤 즉시 승인 미끼를 제시한다.
_LOAN_TARGET_TERMS = ("저신용", "무직", "신용등급", "신용점수", "연체자", "대출 거절")
_LOAN_INSTANT_TERMS = (
    "즉시 대출", "즉시대출", "당일대출", "당일 대출", "대출 승인", "바로 대출",
    "서류 없이", "신청 즉시", "당일 입금",
)

# 가상자산 리딩방: 리딩방·거래소 키워드에 입금 유도가 결합하면 전형적인 리딩방 사기.
_CRYPTO_KEYWORDS = (
    "리딩방", "코인", "비트코인", "가상자산", "USDT", "선물 계좌", "선물계좌",
    "업비트", "바이낸스",
)
_CRYPTO_DEPOSIT_PHRASES = ("USDT 입금", "코인 입금", "입금 후 매수", "예치 후")

# 환급·지원금 사칭: 환급·지원금 미끼에 마감 압박이나 계좌·링크 유도가 붙는다.
_REFUND_MENTION_TERMS = ("환급금", "환급", "미환급", "지원금", "보조금", "상생금")
_REFUND_PRESSURE_TERMS = ("오늘까지", "마감", "기한 내")
_REFUND_LURE_TERMS = ("계좌를 입력", "링크에서", "클릭하여 신청", "https://")

# 알바·부업 보증금 사기: 쉬운 수익 모집 뒤 시작 전 비용을 요구한다. 보증금 등 일부 비용
# 토큰은 선입금 요구 카테고리와 겹치지만, 카테고리별 독립 가산을 허용한다.
_PARTTIME_RECRUIT_TERMS = (
    "재택", "부업", "알바", "특수 알바", "일당", "작업 수익", "좋아요 작업", "수익 인증",
)
_PARTTIME_COST_TERMS = ("보증금", "가입비", "키트비", "예치 후 시작")


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


def _is_official_host(host: str) -> bool:
    """호스트가 브랜드 공식 도메인과 정확히 일치하는지 검사한다(www. 접두어는 제거 후 비교,
    그 외 서브도메인은 제외 — 오탐 감쇠는 정확 일치에만 부여한다)."""
    bare = host.removeprefix("www.")
    return any(
        bare == official
        for _, officials in _BRAND_OFFICIAL_DOMAINS
        for official in officials
    )


def scan_message(text: str) -> FraudReport:
    """발화/문자 본문을 카테고리별로 스캔해 점수 합계와 근거를 돌려준다."""
    lowered = text.lower()
    signals: list[FraudSignal] = []

    # 1) URL 패턴 (공식 도메인과 정확히 일치하는 호스트는 짧은링크·훼칭·의심TLD 플래그 제외)
    hosts = _extract_hosts(text)
    official_hosts = {h for h in hosts if _is_official_host(h)}
    shorteners = [
        h
        for h in hosts
        if h not in official_hosts
        for d in _SHORTENER_DOMAINS
        if h == d or h.endswith("." + d)
    ]
    if ip_match := _IP_HOST_RE.search(text):
        signals.append(
            FraudSignal("URL 위험", f"IP 주소 직접 연결({ip_match.group(1)})", SCORE_URL_IP_HOST)
        )
    typosquats: list[str] = []
    typo_hosts: set[str] = set()
    suspicious_tlds: list[str] = []
    for host in hosts:
        if host in official_hosts:
            continue
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
    if hosts and len(official_hosts) == len(hosts):
        # 모든 호스트가 공식 도메인이면 감쇠 신호를 1회 부여한다(총점 하한 0).
        signals.append(
            FraudSignal("URL 안심", f"공식 도메인 확인({', '.join(hosts)})", SCORE_URL_RELIEF)
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
    if "안전계좌" in text and "입금" in text:
        # 수사기관은 '안전계좌 이체'를 요구하지 않는다 — 안전계좌+입금 결합은 압박 맥락과 별개로 가산.
        impersonation_score += IMPERSONATION_SAFE_ACCOUNT_SCORE
        impersonation_detail.append('"안전계좌"+입금 결합')
    if "사칭" in text:
        impersonation_score += IMPERSONATION_EXPLICIT_SCORE
        impersonation_detail.append('"사칭" 직접 언급')
    if impersonation_detail:
        signals.append(
            FraudSignal("정부기관 사칭 의심", "; ".join(impersonation_detail), impersonation_score)
        )

    # 6) 가족·지인 사칭 (지인 호칭 + 긴급 상황 결합이 전제, 송금 요구·은폐 지시가 가산).
    #    호칭이 없어도 급전 요구 동사와 연락 수단 변경이 겹치면 지인 사칭으로 본다.
    kinship = [w for w in _FAMILY_KINSHIP_TERMS if w in text]
    urgent = [w for w in _FAMILY_URGENT_TERMS if w in text]
    money_asks = [w for w in _FAMILY_MONEY_ASK_TERMS if w in text]
    contact_changes = [w for w in _FAMILY_CONTACT_CHANGE_TERMS if w in text]
    if (kinship and urgent) or (money_asks and contact_changes):
        family_score = (
            FAMILY_KINSHIP_URGENT_SCORE if kinship and urgent else FAMILY_EMERGENCY_BORROW_SCORE
        )
        family_detail = []
        if kinship:
            family_detail.append(f"지인 호칭({', '.join(kinship)})")
        if urgent:
            family_detail.append(f"긴급 상황({', '.join(urgent)})")
        if money_asks and contact_changes:
            family_detail.append(
                f"급전 요구·연락처 변경({', '.join(money_asks)} / {', '.join(contact_changes)})"
            )
        transfers = [w for w in _FAMILY_TRANSFER_TERMS if w in text]
        secrecy = [w for w in _FAMILY_SECRECY_TERMS if w in text]
        if transfers:
            family_score += FAMILY_TRANSFER_SCORE
            family_detail.append(f"송금 요구({', '.join(transfers)})")
        if secrecy:
            family_score += FAMILY_SECRECY_SCORE
            family_detail.append(f"은폐 지시({', '.join(secrecy)})")
        signals.append(
            FraudSignal("가족·지인 사칭", "; ".join(family_detail), min(family_score, _FAMILY_CAP))
        )

    # 7) 대출 빙자 사기 (취약 조건 타깃 + 즉시 승인 문구; 선입금 요구와 합산된다)
    loan_targets = [w for w in _LOAN_TARGET_TERMS if w in text]
    loan_instants = [w for w in _LOAN_INSTANT_TERMS if w in text]
    loan_score = (LOAN_TARGET_SCORE if loan_targets else 0) + (LOAN_INSTANT_APPROVAL_SCORE if loan_instants else 0)
    if loan_score:
        loan_detail = []
        if loan_targets:
            loan_detail.append(f"타깃 조건({', '.join(loan_targets)})")
        if loan_instants:
            loan_detail.append(f"즉시 승인 문구({', '.join(loan_instants)})")
        signals.append(FraudSignal("대출 빙자 사기", "; ".join(loan_detail), min(loan_score, _LOAN_CAP)))

    # 8) 가상자산 리딩방 (키워드 1건당 가산하되 상한, 입금 유도 결합 시 추가 가산)
    crypto_keywords = [w for w in _CRYPTO_KEYWORDS if w in text or w.lower() in lowered]
    crypto_deposits = [w for w in _CRYPTO_DEPOSIT_PHRASES if w in text or w.lower() in lowered]
    if sig := _capped_signal("가상자산 리딩방", crypto_keywords, CRYPTO_KEYWORD_HIT_SCORE, _CRYPTO_KEYWORD_CAP):
        signals.append(sig)
    if crypto_keywords and crypto_deposits:
        signals.append(
            FraudSignal("가상자산 리딩방", f"입금 유도({', '.join(crypto_deposits)})", CRYPTO_DEPOSIT_SCORE)
        )

    # 9) 환급·지원금 사칭 (언급 + 마감 압박 또는 계좌·링크 유도 결합)
    refund_mentions = [w for w in _REFUND_MENTION_TERMS if w in text]
    refund_combos = [w for w in (*_REFUND_PRESSURE_TERMS, *_REFUND_LURE_TERMS) if w in text]
    if refund_mentions:
        refund_score = REFUND_MENTION_SCORE + (REFUND_PRESSURE_LURE_SCORE if refund_combos else 0)
        refund_detail = [f"환급·지원금 언급({', '.join(refund_mentions)})"]
        if refund_combos:
            refund_detail.append(f"마감 압박·유도({', '.join(refund_combos)})")
        signals.append(
            FraudSignal("환급·지원금 사칭", "; ".join(refund_detail), min(refund_score, _REFUND_CAP))
        )

    # 10) 알바·부업 보증금 사기 (모집 + 시작 전 비용 결합; 비용 토큰은 선입금과 중복 가산 허용)
    parttime_recruits = [w for w in _PARTTIME_RECRUIT_TERMS if w in text]
    parttime_costs = [w for w in _PARTTIME_COST_TERMS if w in text]
    if parttime_recruits:
        parttime_score = PARTTIME_RECRUIT_SCORE + (PARTTIME_UPFRONT_COST_SCORE if parttime_costs else 0)
        parttime_detail = [f"수익성 알바 모집({', '.join(parttime_recruits)})"]
        if parttime_costs:
            parttime_detail.append(f"시작 전 비용 요구({', '.join(parttime_costs)})")
        signals.append(
            FraudSignal(
                "알바·부업 보증금 사기", "; ".join(parttime_detail), min(parttime_score, _PARTTIME_CAP)
            )
        )

    # 총점 하한 0: 공식 도메인 감쇠 신호로 음수가 되는 일이 없게 한다.
    return FraudReport(signals=signals, total_score=max(0, sum(s.score for s in signals)))


# 카테고리별 결정론 행동 요령 (LLM 개입 없음). 발견된 카테고리에 대응하는 항목만 출력한다.
_ACTION_GUIDES_BY_CATEGORY: tuple[tuple[str, str], ...] = (
    (
        "가족·지인 사칭",
        (
            "- 문자에 적힌 번호로 걸지 마세요 — 원래 저장돼 있던 가족 번호로 직접 확인하세요\n"
            "- 연결이 안 되면 다른 가족·지인의 휴대폰으로 다시 걸어 보세요"
            "(악성앱이 깔리면 발신이 사기범에게 가로채질 수 있습니다)\n"
            "- 이체 전 반드시 중단 — 112 즉시 신고\n"
            "- 피해 후엔 곧바로 은행 지급정지(1332) 요청"
        ),
    ),
    (
        "대출 빙자 사기",
        (
            "- 정식 대출은 선입금을 요구하지 않습니다\n"
            "- 금융감독원 1332 대출사기 상담"
        ),
    ),
    (
        "가상자산 리딩방",
        (
            "- 리딩방 수익 보장은 전부 사기입니다\n"
            "- 가상자산 불법 거래 업체 확인: 금융위원회 등록 조회"
        ),
    ),
    (
        "환급·지원금 사칭",
        (
            "- 국세청은 링크로 계좌를 요구하지 않습니다(홈택스/손택스 직접 확인)\n"
            "- 126 국세청 민원 신고"
        ),
    ),
    (
        "정부기관 사칭 의심",
        (
            "- 수사기관은 전화로 계좌·비밀번호를 요구하지 않습니다\n"
            "- 112 즉시 신고 후 통화 종료"
        ),
    ),
    (
        "알바·부업 보증금 사기",
        (
            "- 취업 전 예치금·보증금 요구는 전부 사기입니다\n"
            "- 112 신고 및 플랫폼 공식 고객센터 확인"
        ),
    ),
    (
        "URL 위험",
        "- 링크를 열지 말고, 공식 앱/대표번호로 직접 확인하세요",
    ),
)


def _action_guides(report: FraudReport) -> list[str]:
    """발견된 카테고리에 대응하는 행동 요령을 중복 없이 병합해 돌려준다."""
    categories = {s.category for s in report.signals}
    return [guide for category, guide in _ACTION_GUIDES_BY_CATEGORY if category in categories]


def format_report(report: FraudReport) -> str:
    lines = [f"### 판정: {report.verdict} (휴리스틱 점수 {report.total_score})", "발견된 근거:"]
    if report.signals:
        lines += [f"- [{s.category}] {s.detail} ({s.score:+d})" for s in report.signals]
    else:
        lines.append("- 탐지된 위험 신호 없음")
    lines.append("")
    lines.append(f"※ {DISCLAIMER_NOTE}")
    if report.verdict != "위험":
        lines.append("※ 탐지된 위험 신호가 없거나 낮아도 안전을 보장하지 않습니다.")
    lines.append(f"※ {REPORT_GUIDE_NOTE}")
    if guides := _action_guides(report):
        lines += ["", "### 권장 행동 요령", *guides]
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
    투자 권유·고수익 보장·선입금 요구·정부기관 사칭·가족·지인 사칭·대출 빙자·
    가상자산 리딩방·환급·지원금 사칭·알바·부업 보증금 요구·수상한 링크가 의심될 때 사용하라.
    판정은 '실제 사기 여부를 단정하지 않는' 참고 정보이며, 신고 안내와 행동 요령을 함께 돌려준다.

    Args:
        message_text: 사용자가 받은 문자·알림·메시지 원문(링크가 포함되면 함께 넣는다).
    """
    report = scan_message(message_text)
    body = format_report(report)
    disabled = os.environ.get("FRAUD_CHECK_DISABLE_WEB", "").strip().lower() in ("1", "true")
    enrichment = "(생략됨)" if disabled else web_enrichment(message_text)
    body += "\n\n### 최신 피싱·사기 정보 (웹 검색 보강)\n" + enrichment
    return body
