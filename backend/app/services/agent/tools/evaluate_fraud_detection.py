"""fraud_check 휴리스틱 스코어러 소규모 평가 스크립트 (인하우스 라벨셋 회귀 점검).

⚠️ 방법론 고지 — 이 평가는 범용 벤치마크가 아니며, 아래 한계를 전제로 읽어야 한다.
  1. 표본: 인하우스 라벨셋 n=32(사기 16 / 정상 16). 실전 메시지 분포를 대표하지 않는
     소규모 편향 표본이므로, 수치는 '참고 실측치'로만 인용한다.
  2. 용도: (a) fraud_check 룰 변경(카테고리 확대·가중치 조정) 전후 성능 저하를 잡아내는
     내부 회귀 지표, (b) 공모전 기획서·Q&A에 인용할 Before/After 실측 근거 확보.
  3. 라벨: 작성자가 직접 라벨링했으므로 주관이 개입된다. 외부 공개 데이터셋과의 비교는 무의미.
  4. 판정 기준: positive = total_score >= 60(verdict=="위험"). 참고로 score >= 30(주의 이상)
     기준 재현율을 함께 출력한다 — "일단 의심 건은 걸러내자"는 1차 트리아지 관점의 지표.
  5. fraud_check.py는 동시에 수정 중일 수 있다: 이 스크립트의 출력은 항상 '실행 시점' 룰
     기준이며, 커밋 간 비교는 같은 리비전에서 재실행한 결과로만 유효하다.

사용 예:
    PYTHONPATH=. uv run python scripts/evaluate_fraud_detection.py          # 사람 읽기용 표
    PYTHONPATH=. uv run python scripts/evaluate_fraud_detection.py --json   # 기획서 삽입용 JSON
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field

from backend.app.services.agent.tools.fraud_check import FraudReport, scan_message

# ---------------------------------------------------------------------------
# 평가 설정
# ---------------------------------------------------------------------------
POSITIVE_THRESHOLD = 60  # verdict=="위험" — 본 평가의 positive 판정 기준
CAUTION_THRESHOLD = 30  # verdict=="주의" 이상 — 1차 트리아지 관점 참고 지표

# (유형 라벨, 본문) 쌍. 라벨은 룰 개선 포인트 분석을 위한 유형 태그일 뿐, 스코어러에는 주입되지 않는다.
Sample = tuple[str, str]

# ---------------------------------------------------------------------------
# 라벨셋 — 사기 16건 (실제 뉴스에 보도되는 문체: 짧은 문자체, [기관] 접두사, 금액·링크 포함)
# ---------------------------------------------------------------------------
SCAMS: list[Sample] = [
    # --- 가족·지인 사칭 3 ---
    (
        "가족·지인 사칭",
        (
            "엄마 나 폰 액정 깨져서 친구 폰으로 문자한다. 오늘 오후까지 수술비 200만원이 급하게 "
            "필요해. 기존 번호는 연결이 안 되니 일단 계좌로 입금해주면 저녁에 전화할게. "
            "http://bit.ly/mom-help"
        ),
    ),
    (
        "가족·지인 사칭",
        (
            "[아들] 휴대폰 분실로 임시번호 사용 중. 회사 보증보험 해지 처리에 150만원 선입금이 "
            "필요하다고 한다. 내일까지 꼭 보내줘. 자세한 건 카톡으로 설명할게."
        ),
    ),
    (
        "가족·지인 사칭",
        (
            "저번에 밥 산 거 기억하지? 급하게 80만원만 빌려줘, 카드값 때문에 오늘까지만 필요해. "
            "번호 바꿨어. 먼저 송금해주면 이번 주 안에 정확히 갚을게."
        ),
    ),
    # --- 대출빙자 3 ---
    (
        "대출빙자",
        (
            "[대출승인] 무직·연체자 3,000만원 한도 승인 완료되었습니다. 실행 수수료 선입금 후 "
            "즉시 지급되며 상담은 https://loan-ok7.xyz 에서 받으실 수 있습니다."
        ),
    ),
    (
        "대출빙자",
        (
            "[당일대출] 서류 없이 신청 즉시 500만원 입금. 신용등록·연체 이력 전부 가능. 조건 확인 "
            "후 수수료 먼저 입금해 주세요. 상담 http://t.ly/xYz9"
        ),
    ),
    (
        "대출빙자",
        (
            "[모바일대출] 재직·건강보험 없이 가능. 처리비 예치금 99,000원을 먼저 입금하시면 "
            "30분 내 한도 지급됩니다. 신청 http://kd-fast.top"
        ),
    ),
    # --- 가상자산 리딩방 3 ---
    (
        "가상자산 리딩방",
        (
            "리딩방 12기 특별모집 마감 임박. 코인 시드 2배 보장, 매달 월 30% 수익률 확정으로 "
            "알려드립니다. 참여 희망자는 오픈채팅으로."
        ),
    ),
    (
        "가상자산 리딩방",
        (
            "[단타클럽] 비트코인 자동매매 시스템, 원금 보장·연 120% 수익 실증. 무료 체험은 "
            "텔레그램 채널 추가 후 받아가세요."
        ),
    ),
    (
        "가상자산 리딩방",
        (
            "오늘 밤 9시 프리미엄 리딩방 하루 무료 공개. 이번 주 타깃 코인 단타 확정, 지난주 "
            "실적 +38%로 증명합니다. 선착순 5명, 카톡 1:1 상담만 받아요."
        ),
    ),
    # --- 환급·지원금 사칭 3 ---
    (
        "환급·지원금 사칭",
        (
            "[국세청] 근로소득 미환급금 248,600원 수령 대상입니다. 접수 마감이 내일까지이므로 "
            "서둘러 신청하세요. http://bit.ly/nts-refund26"
        ),
    ),
    (
        "환급·지원금 사칭",
        (
            "[정부24] 2026년 1차 정부지원금 87만원 대상 조회 완료. 금일 발급 마감이며 지급 "
            "수수료 19,000원을 먼저 입금하시면 등록 계좌로 즉시 지급됩니다. http://cutt.ly/kw26a"
        ),
    ),
    (
        "환급·지원금 사칭",
        (
            "[국민연금공단] 미지급 연금 320만원 확인 결과 안내. 금일 17시까지 본인 계좌로 입금 "
            "신청하실 수 있으며 등록 수수료 9,900원은 선입금입니다. http://bit.ly/nps-pay"
        ),
    ),
    # --- 알바·부업 보증금 2 ---
    (
        "알바·부업 보증금",
        (
            "[재택부업] 하루 2시간 문자 답장 알바, 일당 8만원 당일 지급. 활동 보증금 3만원 "
            "선입금 후 바로 시작 가능. 문의는 카톡 주세요."
        ),
    ),
    (
        "알바·부업 보증금",
        (
            "간편 노래방 도우미 알바 모집. 주 3회, 시급 15,000원. 채용 확정 시 통신비 예치금 "
            "20만원을 먼저 입금해 주시면 당일 배치됩니다."
        ),
    ),
    # --- 기관 사칭·수사조작 2 ---
    (
        "기관 사칭·수사조작",
        (
            "[검찰] 귀하는 명의도용 사건 피의자로 지정되었습니다. 전화 불응 시 체포영장이 "
            "발부됩니다. 수사 협조를 위해 보유 현금을 검찰 지정 계좌로 입금하여 정화 조치하십시오. "
            "http://bit.ly/pros-112"
        ),
    ),
    (
        "기관 사칭·수사조작",
        (
            "[경찰청 사이버수사과] 귀하 명의 불법 통장 적발로 자금 환수 절차가 진행 중입니다. "
            "금융감독원 지정 안전계좌로 즉시 입금하지 않으면 계좌 동결 및 압류됩니다."
        ),
    ),
]

# ---------------------------------------------------------------------------
# 라벨셋 — 정상 16건 (세금·환급·링크·은행 단어가 나와도 문맥상 정상인 오탐 저항 케이스 포함)
# ---------------------------------------------------------------------------
NORMALS: list[Sample] = [
    ("가족 대화", "엄마 오늘 저녁에 김치찌개 끓였어. 퇴근하고 일찍 들어와서 같이 먹자."),
    ("가족 대화", "아들 생일이라 삼겹살 사 놨으니 바로 집에 와. 케이크는 엄마가 예약해 뒀다."),
    (
        "직장 연락",
        (
            "[인사팀] 김하늘님, 내일 오전 10시 연봉 면담은 3층 회의실로 장소가 변경되었습니다. "
            "준비 자료는 메일함을 확인해 주세요."
        ),
    ),
    (
        "직장 연락",
        (
            "회식은 내일 저녁 7시, 강남역 역전돼지국밥 2층으로 예약했어요. 못 오시는 분은 "
            "오늘까지 알려주세요."
        ),
    ),
    (
        "배달·택배",
        (
            "[배달의민족] 주문하신 마라탕이 곧 도착합니다. 예상 도착 시간은 18:40입니다. "
            "맛있게 드세요!"
        ),
    ),
    (
        "배달·택배",
        (
            "[CJ대한통운] 기사님이 상품을 문 앞에 보관했습니다. 파손·반품 문의는 판매처로 "
            "연락해 주세요."
        ),
    ),
    (
        "은행 공식 알림",
        (
            "[카카오뱅크] 입출금통장에 100,000원이 입금되었습니다. 잔액 1,250,000원 "
            "(08/26 14:32)"
        ),
    ),
    (
        "은행 공식 알림",
        (
            "[토스뱅크] 8월 이자 1,240원이 지급되었습니다. 이번 달 거래내역 요약은 앱에서 "
            "확인하실 수 있습니다."
        ),
    ),
    (
        "학교·학원",
        (
            "[○○고등학교] 내일 진로 체험학습 대상자는 오전 8시 교문 앞 집합입니다. 개인 "
            "휴대폰은 출발 전 담임 선생님께 제출하세요."
        ),
    ),
    (
        "학교·학원",
        (
            "[한빛학원] 8월 학원비 납부 안내입니다. 8월 31일까지 등록하신 계좌로 자동이체됩니다. "
            "감사합니다."
        ),
    ),
    (
        "모임 일정",
        (
            "산악회 정기 모임은 다음 주 토요일 아침 7시, 지하철 3호선 춘천행 승강장에서 "
            "만납니다. 참석 여부 투표 부탁드려요!"
        ),
    ),
    (
        "공식 도메인 안내",
        (
            "[네이버] 새로운 기기에서 로그인했습니다. 본인이 아닌 경우 내계정 > 보안설정에서 "
            "확인하세요. https://nid.naver.com/user/help"
        ),
    ),
    (
        "공식 도메인 안내",
        (
            "[카카오] 2차 인증 코드는 482913입니다. 타인에게 알려주지 마세요. 자세한 문의는 "
            "help.kakao.com"
        ),
    ),
    (
        "세금 안내",
        (
            "[국세청] 연말정산 간소화 서비스가 1월 15일 개시됩니다. 귀하의 소득·세액공제 자료를 "
            "미리 확인해 보세요. www.nts.go.kr"
        ),
    ),
    (
        "세금 안내",
        (
            "경리팀입니다. 연말정산 환급금이 지급 계좌로 지급될 예정입니다. 계좌가 동일하시면 "
            "별도 회신은 받지 않겠습니다."
        ),
    ),
    (
        "공식 도메인 안내",
        (
            "[KB국민은행] 스마트뱅킹 앱 9.4.1 버전이 출시되었습니다. 앱스토어에서 업데이트해 "
            "주세요. 공지: kbstar.com/notice"
        ),
    ),
]


# ---------------------------------------------------------------------------
# 평가 로직
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CaseResult:
    """샘플 1건의 스코어러 판정 결과."""

    label: str
    text: str
    score: int
    verdict: str
    is_scam: bool


@dataclass(frozen=True)
class EvalReport:
    """위험 기준(>=60) 혼동 행렬 + 주의 기준(>=30) 트리아지 재현율."""

    results: list[CaseResult] = field(default_factory=list)
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    triage_caught: int = 0  # 사기 중 score >= 30 에 걸린 건수
    triage_total: int = 0  # 사기 전체 건수
    triage_normal_flagged: int = 0  # 정상 중 score >= 30 오탐 건수

    @property
    def precision(self) -> float:
        return _safe_div(self.tp, self.tp + self.fp)

    @property
    def recall(self) -> float:
        return _safe_div(self.tp, self.tp + self.fn)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return _safe_div(2 * p * r, p + r)

    @property
    def triage_recall(self) -> float:
        return _safe_div(self.triage_caught, self.triage_total)

    def to_dict(self) -> dict[str, object]:
        """기획서 삽입용 JSON 직렬화."""
        return {
            "meta": {
                "dataset_size": len(SCAMS) + len(NORMALS),
                "scams": len(SCAMS),
                "normals": len(NORMALS),
                "positive_threshold": POSITIVE_THRESHOLD,
                "caution_threshold": CAUTION_THRESHOLD,
                "note": "인하우스 소규모 라벨셋(n=32) 기반 내부 회귀 지표. 범용 벤치마크가 아님.",
            },
            "danger_ge_60": {
                "tp": self.tp,
                "fp": self.fp,
                "tn": self.tn,
                "fn": self.fn,
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1": round(self.f1, 4),
            },
            "caution_ge_30_triage": {
                "scam_recall": round(self.triage_recall, 4),
                "caught": self.triage_caught,
                "total": self.triage_total,
                "normal_flagged": self.triage_normal_flagged,
            },
            "false_negatives": [
                {"label": c.label, "score": c.score, "verdict": c.verdict, "text": c.text}
                for c in self.results
                if c.is_scam and c.score < POSITIVE_THRESHOLD
            ],
            "false_positives": [
                {"label": c.label, "score": c.score, "verdict": c.verdict, "text": c.text}
                for c in self.results
                if not c.is_scam and c.score >= POSITIVE_THRESHOLD
            ],
        }


def _safe_div(num: float, den: float) -> float:
    """0으로 나눌 때 0 처리."""
    return num / den if den else 0.0


def _classify(text: str, label: str, is_scam: bool) -> CaseResult:
    report: FraudReport = scan_message(text)
    return CaseResult(
        label=label,
        text=text,
        score=report.total_score,
        verdict=report.verdict,
        is_scam=is_scam,
    )


def evaluate() -> EvalReport:
    """라벨셋 전체를 스캔해 혼동 행렬과 트리아지 지표를 집계한다."""
    results = [_classify(text, label, True) for label, text in SCAMS]
    results += [_classify(text, label, False) for label, text in NORMALS]
    tp = sum(r.is_scam and r.score >= POSITIVE_THRESHOLD for r in results)
    fp = sum(not r.is_scam and r.score >= POSITIVE_THRESHOLD for r in results)
    fn = sum(r.is_scam and r.score < POSITIVE_THRESHOLD for r in results)
    tn = sum(not r.is_scam and r.score < POSITIVE_THRESHOLD for r in results)
    return EvalReport(
        results=results,
        tp=int(tp),
        fp=int(fp),
        tn=int(tn),
        fn=int(fn),
        triage_caught=sum(r.is_scam and r.score >= CAUTION_THRESHOLD for r in results),
        triage_total=len(SCAMS),
        triage_normal_flagged=sum(
            not r.is_scam and r.score >= CAUTION_THRESHOLD for r in results
        ),
    )


# ---------------------------------------------------------------------------
# 사람 읽기용 출력
# ---------------------------------------------------------------------------
def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _shorten(text: str, width: int = 44) -> str:
    return text if len(text) <= width else text[:width] + "…"


def render_human(report: EvalReport) -> str:
    """사람 읽기용 요약 표. FN/FP는 룰 개선 포인트 도출을 위해 문장 전체를 출력한다."""
    n_scam, n_norm = len(SCAMS), len(NORMALS)
    lines = [
        f"== fraud_check 휴리스틱 평가 (n={n_scam + n_norm}: 사기 {n_scam} / 정상 {n_norm}) ==",
        "",
        f"[혼동 행렬 · 위험 기준(total_score >= {POSITIVE_THRESHOLD})]",
        "                 예측: 위험   예측: 미만",
        f"  실제: 사기({n_scam})       TP {report.tp:>2}         FN {report.fn:>2}",
        f"  실제: 정상({n_norm})       FP {report.fp:>2}         TN {report.tn:>2}",
        "",
        (f"precision {report.precision:.3f}   recall {report.recall:.3f}   "
         f"F1 {report.f1:.3f}"),
        "",
        f"[1차 트리아지 관점 · 주의 기준(score >= {CAUTION_THRESHOLD})]",
        (f"사기 재현율: {report.triage_caught}/{report.triage_total} = {_pct(report.triage_recall)}"
         f"  (같은 기준 정상 오탐: {report.triage_normal_flagged}/{n_norm}건)"),
        "",
    ]

    fn_cases = [c for c in report.results if c.is_scam and c.score < POSITIVE_THRESHOLD]
    fp_cases = [c for c in report.results if not c.is_scam and c.score >= POSITIVE_THRESHOLD]

    lines.append(f"[미탐지(FN) {len(fn_cases)}건 — 룰 개선 포인트 후보]")
    if fn_cases:
        for i, c in enumerate(fn_cases, start=1):
            lines.append(f"  {i}. ({c.label}, 점수 {c.score}, 판정 {c.verdict}) {c.text}")
    else:
        lines.append("  (없음)")
    lines.append("")
    lines.append(f"[오탐(FP) {len(fp_cases)}건 — 위험 기준에서 정상을 놓친 케이스]")
    if fp_cases:
        for i, c in enumerate(fp_cases, start=1):
            lines.append(f"  {i}. ({c.label}, 점수 {c.score}, 판정 {c.verdict}) {c.text}")
    else:
        lines.append("  (없음)")

    lines += ["", "[샘플별 점수]"]
    scam_rows = [c for c in report.results if c.is_scam]
    norm_rows = [c for c in report.results if not c.is_scam]
    for tag, rows in (("사기", scam_rows), ("정상", norm_rows)):
        for c in rows:
            lines.append(
                f"  {tag} | {c.label:<12} {c.score:>4} {c.verdict:<6} {_shorten(c.text)}"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="fraud_check 휴리스틱 스코어러를 인하우스 라벨셋(n=32)으로 평가한다."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="사람 읽기용 표 대신 기획서 삽입용 JSON을 출력한다.",
    )
    args = parser.parse_args()

    report = evaluate()
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_human(report))


if __name__ == "__main__":
    main()
