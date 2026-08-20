/** 청약가점제 점수 계산 (국토부 고시 기준, 84점 만점) — 순수 계산, 공식 표 그대로라
 * 판단/자문이 아니라 정보 제공. 무주택자를 전제로 한 계산이다(유주택자는 가점제 적용 자체가
 * 다르게 갈리므로 이 계산기 범위 밖).
 */

export const MAX_SCORE = 84;

/** 무주택기간(년) → 0~32점. 1년 미만 2점, 이후 1년마다 2점씩 가산, 15년 이상 만점. */
export function homelessPeriodScore(years: number): number {
  if (years < 0) return 0;
  return Math.min(32, 2 * (Math.floor(years) + 1));
}

/** 부양가족수(본인 제외) → 5~35점. 0명 5점부터 1명당 5점씩 가산, 6명 이상 만점. */
export function dependentsScore(dependents: number): number {
  return Math.min(35, 5 + 5 * Math.max(0, Math.floor(dependents)));
}

/** 청약통장 가입기간(년) → 1~17점. 6개월 미만 1점, 6개월~1년 2점, 이후 1년마다 1점씩 가산, 15년 이상 만점. */
export function subscriptionPeriodScore(years: number): number {
  if (years < 0.5) return 1;
  if (years < 1) return 2;
  return Math.min(17, Math.floor(years) + 2);
}

export interface ScoreInput {
  homelessYears: number;
  dependents: number;
  subscriptionYears: number;
}

export function totalCheongyakScore({ homelessYears, dependents, subscriptionYears }: ScoreInput): number {
  return (
    homelessPeriodScore(homelessYears) +
    dependentsScore(dependents) +
    subscriptionPeriodScore(subscriptionYears)
  );
}
