/** 자금마련 타임라인 시뮬레이터 — 순수 계산 유틸. 서버 왕복 없이 브라우저에서 계산한다
 * (개인 자산 숫자가 밖으로 안 나감 + 정적 표라 백엔드 필요 없음).
 *
 * ponytail: 적금 이자는 실제로는 상품마다 계산식이 다르다(단리/월복리/선이자 등).
 * 여기서는 월복리로 단순화한 시뮬레이션이며, 실제 세후 수령액은 상품 약관을 따라야 한다.
 * 화면에도 "시뮬레이션이며 실제 상품과 다를 수 있음" 문구가 같이 나가야 함.
 */

export type Region = "seoul_busan" | "other_metro" | "other";
export type AreaTier = "85" | "102" | "135" | "all";

/** 민영주택 청약예치금 기준표(지역 x 전용면적).
 *
 * 근거: 「주택공급에 관한 규칙」 제28조 예치금 기준. 법령 개정이 있어야만 바뀌는 고정 수치라
 * 실시간 조회 없이 하드코딩함.
 *
 * 확인 방법·일자(2026-08-20): 웹서치로 셀 단위 교차확인 — 한국경제
 * (hankyung.com/article/2021051683831: 서울·부산 85㎡ 300만/102㎡ 600만/135㎡ 1,000만/전체 1,500만),
 * 우리집변호사(mylawstory.com/5017: 경기 등 기타지역 85㎡ 200만) 등. 목표금액 기본축으로 이 표를
 * 쓰는 이유는 "직접 입력(분양가 등)"도 옵션으로 병행 제공하기 때문 — 예치금이 유일한 축은 아님.
 */
const DEPOSIT_TABLE: Record<Region, Record<AreaTier, number>> = {
  seoul_busan: { "85": 3_000_000, "102": 6_000_000, "135": 10_000_000, all: 15_000_000 },
  other_metro: { "85": 2_500_000, "102": 4_000_000, "135": 7_000_000, all: 10_000_000 },
  other: { "85": 2_000_000, "102": 3_000_000, "135": 4_000_000, all: 5_000_000 },
};

export const DEPOSIT_SOURCE_NOTE =
  "출처: 「주택공급에 관한 규칙」 제28조 예치금 기준 — 언론·법률 자료 교차확인(2026-08-20 확인)";

export const REGION_LABELS: Record<Region, string> = {
  seoul_busan: "서울·부산",
  other_metro: "기타 광역시",
  other: "특별시·광역시 외",
};

export const AREA_LABELS: Record<AreaTier, string> = {
  "85": "전용 85㎡ 이하",
  "102": "전용 102㎡ 이하",
  "135": "전용 135㎡ 이하",
  all: "모든 면적",
};

export function depositRequirement(region: Region, area: AreaTier): number {
  return DEPOSIT_TABLE[region][area];
}

export interface TimelinePoint {
  month: number;
  balance: number;
}

export interface TimelineResult {
  points: TimelinePoint[];
  /** target에 처음 도달하는 달. capMonths 안에 못 미치면 null. */
  reachMonth: number | null;
}

/** 월복리 적립 시뮬레이션. points는 항상 capMonths+1개(0..capMonths)로, 여러 시나리오를 같은
 * x축에 겹쳐 그리기 쉽게 고정 길이로 반환한다. */
export function simulateTimeline(
  targetAmount: number,
  currentAssets: number,
  monthlySaving: number,
  annualRatePercent: number,
  capMonths = 240,
): TimelineResult {
  const monthlyRate = annualRatePercent / 100 / 12;
  const points: TimelinePoint[] = [{ month: 0, balance: currentAssets }];
  let balance = currentAssets;
  let reachMonth: number | null = balance >= targetAmount ? 0 : null;

  for (let m = 1; m <= capMonths; m++) {
    balance = balance * (1 + monthlyRate) + monthlySaving;
    points.push({ month: m, balance });
    if (reachMonth === null && balance >= targetAmount) reachMonth = m;
  }

  return { points, reachMonth };
}
