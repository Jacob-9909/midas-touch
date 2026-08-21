/** "내 정보" 단일 저장소 — 청약 심사 기준에 맞춰 사용자가 직접 입력한 값.
 *
 * 예전엔 합성 페르소나(500명) 중 하나를 고르게 했는데, 남의 프로필을 뒤집어쓰는 구조라
 * 자기 청약 자격을 볼 수 없었다. 이 파일이 그걸 대체한다 — 가점 계산, 1순위 자격 안내,
 * 챗봇 프로필 주입, 시뮬레이터 초기값이 전부 여기 하나를 읽는다.
 *
 * 서버로 보내지 않는다(챗봇 질의 시 프로필 요약만 동봉). localStorage 에만 남는다.
 */

import { depositRequirement, type AreaTier, type Region } from "./simulate";
import {
  dependentsScore,
  homelessPeriodScore,
  subscriptionPeriodScore,
} from "./cheongyak-score";

// ─────────────────────────────────────────────────────────────
// 거주지역
// ─────────────────────────────────────────────────────────────

/** 시/도 → 예치금 표의 지역 구분. 「주택공급에 관한 규칙」 제28조 기준
 * (특별시·부산 / 그 밖의 광역시 / 특별시·광역시 외). 세종·제주 등 특별자치는 '그 외'로 본다. */
export const SIDO = [
  "서울", "부산", "인천", "대구", "광주", "대전", "울산", "세종",
  "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
] as const;
export type Sido = (typeof SIDO)[number];

const METRO: Sido[] = ["인천", "대구", "광주", "대전", "울산"];
/** 수도권 = 서울·인천·경기. 1순위 통장 가입기간 요건이 여기서 갈린다. */
const CAPITAL_AREA: Sido[] = ["서울", "인천", "경기"];

export function regionOf(sido: Sido): Region {
  if (sido === "서울" || sido === "부산") return "seoul_busan";
  if (METRO.includes(sido)) return "other_metro";
  return "other";
}

export function isCapitalArea(sido: Sido): boolean {
  return CAPITAL_AREA.includes(sido);
}

// ─────────────────────────────────────────────────────────────
// 프로필
// ─────────────────────────────────────────────────────────────

export interface MyProfile {
  // [가점 3요소] 「주택공급에 관한 규칙」 별표1
  homelessYears: number;
  dependents: number;
  subscriptionYears: number;
  /** 만 30세 미만이면서 미혼 → 무주택기간 카운트가 시작 안 해서 0점 */
  under30Unmarried: boolean;

  // [1순위 자격]
  sido: Sido;
  /** 해당 지역 거주기간(년). 규제지역은 2년 이상 요건이 있다. */
  residenceYears: number;
  /** 규제지역(투기과열지구·청약과열지역) 해당 여부.
   * 지정은 정부 고시로 수시 변경되므로 앱이 판단하지 않고 사용자가 공고문 보고 표시한다. */
  regulatedArea: boolean;
  isHouseholder: boolean;
  /** 세대구성원 전원 무주택 여부 */
  noHouseOwnership: boolean;
  /** 세대구성원 중 최근 5년 내 당첨 이력 있음 */
  wonLotteryIn5Years: boolean;
  /** 청약통장 납입 총액(원) — 민영주택은 납입횟수가 아니라 예치금 총액이 기준 */
  subscriptionDeposit: number;
  /** 청약하려는 전용면적 구간 — 예치금 기준금액이 여기서 갈린다 */
  targetArea: AreaTier;

  // [자금] 시뮬레이터 초기값
  currentAssets: number;
  monthlySaving: number;
  annualIncome: number;
}

export const DEFAULT_PROFILE: MyProfile = {
  homelessYears: 3,
  dependents: 0,
  subscriptionYears: 5,
  under30Unmarried: false,

  sido: "서울",
  residenceYears: 2,
  regulatedArea: false,
  isHouseholder: false,
  noHouseOwnership: true,
  wonLotteryIn5Years: false,
  subscriptionDeposit: 3_000_000,
  targetArea: "85",

  currentAssets: 20_000_000,
  monthlySaving: 600_000,
  annualIncome: 40_000_000,
};

const STORAGE_KEY = "midas.myProfile.v1";
/** 예전 가점 카드가 쓰던 키. 값이 있으면 한 번 흡수해서 사용자가 다시 입력하지 않게 한다. */
const LEGACY_SCORE_KEY = "midas.cheongyak.myScore.v1";

export function loadProfile(): MyProfile {
  if (typeof window === "undefined") return DEFAULT_PROFILE;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_PROFILE, ...JSON.parse(raw) };
    const legacy = localStorage.getItem(LEGACY_SCORE_KEY);
    if (legacy) return { ...DEFAULT_PROFILE, ...JSON.parse(legacy) };
  } catch {
    /* 손상된 값이면 기본값으로 */
  }
  return DEFAULT_PROFILE;
}

export function saveProfile(p: MyProfile): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
}

const CLIENT_ID_KEY = "midas.clientId";

/** 이 브라우저의 익명 식별자. 대화 세션·관심종목을 묶는 키로만 쓴다.
 *
 * 로그인이 없으니 서버는 "누구"인지 알 필요가 없고, 알아서도 안 된다. 예전엔 페르소나
 * uuid 가 이 역할을 겸했는데(= 남의 신원으로 내 세션이 묶임) 그걸 끊어낸 것이다.
 * 개인 식별정보를 담지 않는 난수이고 브라우저 저장소를 비우면 사라진다. */
export function clientId(): string {
  if (typeof window === "undefined") return "anon";
  let id = localStorage.getItem(CLIENT_ID_KEY);
  if (!id) {
    id = crypto.randomUUID().replace(/-/g, "");
    localStorage.setItem(CLIENT_ID_KEY, id);
  }
  return id;
}

// ─────────────────────────────────────────────────────────────
// 1순위 자격 (민영주택 일반공급)
// ─────────────────────────────────────────────────────────────

/** 민영주택 1순위 통장 가입기간 요건(개월).
 *
 * 근거: 「주택공급에 관한 규칙」 제28조 — 투기과열지구·청약과열지역 24개월,
 * 수도권 12개월, 수도권 외 6개월. 시·도지사가 연장할 수 있어(수도권 24개월,
 * 그 외 12개월까지) 공고문 확인이 필요하다.
 *
 * 주의: '납입횟수'(투기과열 24회 등)는 국민주택 요건이다. 민영주택은 횟수가 아니라
 * 예치금 총액을 본다 — 두 기준을 섞어 놓은 자료가 흔해서 여기 명시해 둔다. */
export function requiredSubscriptionMonths(sido: Sido, regulated: boolean): number {
  if (regulated) return 24;
  return isCapitalArea(sido) ? 12 : 6;
}

export const FIRST_PRIORITY_SOURCE_NOTE =
  "출처: 「주택공급에 관한 규칙」 제28조(민영주택 일반공급 1순위) — 청약Home·KB 안내 대조(2026-08-21 확인). " +
  "규제지역 지정과 시·도지사 연장 여부는 수시로 바뀌므로 실제 신청 전 입주자모집공고문을 반드시 확인하세요.";

export interface Check {
  label: string;
  ok: boolean;
  /** 왜 충족/미충족인지 사실만 적는다 */
  detail: string;
  /** 규제지역에서만 적용되는 항목 */
  regulatedOnly?: boolean;
}

/** 민영주택 일반공급 1순위 요건을 항목별로 판정한다.
 * 예측이 아니라 입력값과 법령 기준의 대조 결과만 돌려준다. */
export function firstPriorityChecks(p: MyProfile): Check[] {
  const needMonths = requiredSubscriptionMonths(p.sido, p.regulatedArea);
  const haveMonths = Math.floor(p.subscriptionYears * 12);
  const needDeposit = depositRequirement(regionOf(p.sido), p.targetArea);

  const checks: Check[] = [
    {
      label: "청약통장 가입기간",
      ok: haveMonths >= needMonths,
      detail: `기준 ${needMonths}개월 이상` +
        (p.regulatedArea ? "(규제지역)" : isCapitalArea(p.sido) ? "(수도권)" : "(수도권 외)") +
        `, 내 보유 ${haveMonths}개월`,
    },
    {
      label: "예치금",
      ok: p.subscriptionDeposit >= needDeposit,
      detail: `기준 ${needDeposit.toLocaleString("ko-KR")}원 이상` +
        `(${p.sido}·${AREA_TEXT[p.targetArea]}), 내 납입액 ${p.subscriptionDeposit.toLocaleString("ko-KR")}원`,
    },
    {
      label: "무주택 여부",
      ok: p.noHouseOwnership,
      detail: p.noHouseOwnership
        ? "세대구성원 전원 무주택"
        : "세대에 주택 소유자가 있음 — 가점제 일반공급 대상이 아닐 수 있음",
    },
  ];

  if (p.regulatedArea) {
    checks.push(
      {
        label: "세대주 여부",
        ok: p.isHouseholder,
        detail: p.isHouseholder ? "세대주" : "세대원 — 규제지역은 세대주여야 함",
        regulatedOnly: true,
      },
      {
        label: "해당 지역 거주기간",
        ok: p.residenceYears >= 2,
        detail: `기준 2년 이상, 내 거주기간 ${p.sido} ${p.residenceYears}년`,
        regulatedOnly: true,
      },
      {
        label: "최근 5년 당첨 이력",
        ok: !p.wonLotteryIn5Years,
        detail: p.wonLotteryIn5Years
          ? "세대구성원 중 5년 내 당첨 이력 있음 — 1순위 제한"
          : "5년 내 당첨 이력 없음",
        regulatedOnly: true,
      },
    );
  }

  return checks;
}

const AREA_TEXT: Record<AreaTier, string> = {
  "85": "전용 85㎡ 이하",
  "102": "전용 102㎡ 이하",
  "135": "전용 135㎡ 이하",
  all: "모든 면적",
};

/** 챗봇 첫 턴에 주입할 프로필 요약. 서버는 이 문자열만 받는다(원시 입력값 전송 없음).
 *
 * 총점만 주면 모델이 그 숫자를 맞추려고 없는 항목을 지어낸다 — 실제로 "청년 가점 5점",
 * "기타 가산점 2점" 같은 존재하지 않는 항목을 만들어 12점을 채우는 걸 확인했다.
 * 그래서 항목별 점수와 1순위 판정 근거를 전부 계산해서 넘기고, 재계산·창작을 금지한다
 * ("계산과 판정은 코드, 설명과 종합은 AI"라는 이 서비스의 원칙이 여기서도 그대로 적용된다). */
export function profileSummary(p: MyProfile, score: number): string {
  const homeless = p.under30Unmarried ? 0 : homelessPeriodScore(p.homelessYears);
  const dep = dependentsScore(p.dependents);
  const sub = subscriptionPeriodScore(p.subscriptionYears);
  const checks = firstPriorityChecks(p);

  return [
    "[의뢰인 정보 — 본인이 직접 입력한 값. 이 조건에 맞춰 답하십시오]",
    `- 거주: ${p.sido} ${p.residenceYears}년 / ${p.isHouseholder ? "세대주" : "세대원"} / ` +
      `${p.noHouseOwnership ? "무주택" : "세대 내 주택 소유"}${p.regulatedArea ? " / 규제지역" : ""}`,
    `- 청약통장 납입액: ${p.subscriptionDeposit.toLocaleString("ko-KR")}원, 관심 면적: ${AREA_TEXT[p.targetArea]}`,
    `- 자금: 현재 자산 ${p.currentAssets.toLocaleString("ko-KR")}원 / ` +
      `월 저축 가능 ${p.monthlySaving.toLocaleString("ko-KR")}원 / 연소득 ${p.annualIncome.toLocaleString("ko-KR")}원`,
    "",
    `[청약가점 — 앱이 「주택공급에 관한 규칙」 별표1로 계산 완료. 합계 ${score}점/84점]`,
    `- 무주택기간: ${homeless}점/32점 ` +
      (p.under30Unmarried
        ? "(만 30세 미만이면서 미혼이라 무주택기간 산정이 시작되지 않아 0점)"
        : `(${p.homelessYears}년)`),
    `- 부양가족수: ${dep}점/35점 (${p.dependents}명, 본인 제외)`,
    `- 청약통장 가입기간: ${sub}점/17점 (${p.subscriptionYears}년)`,
    "",
    "[민영주택 일반공급 1순위 — 앱이 항목별로 대조 완료]",
    ...checks.map((c) => `- ${c.label}: ${c.ok ? "충족" : "미충족"} (${c.detail})`),
    "",
    "[위 계산 결과를 다룰 때 지켜야 할 것]",
    "- 가점 항목은 무주택기간·부양가족수·청약통장 가입기간 3가지가 전부다. " +
      "'청년 가점', '생애최초 가산점' 같은 항목은 가점제에 존재하지 않으므로 만들어내지 말 것.",
    "- 위 점수와 충족 여부는 이미 계산된 값이다. 다시 계산하거나 다른 숫자로 바꾸지 말고 그대로 인용할 것.",
    "- 위에 없는 요건(특별공급 자격, 소득 기준 등)은 이 앱이 판정하지 않았다. " +
      "단정하지 말고 입주자모집공고문 확인이 필요하다고 안내할 것.",
  ].join("\n");
}
