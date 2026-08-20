/** 청약가점제 점수 계산 (84점 만점).
 *
 * 근거: 「주택공급에 관한 규칙」 별표1(가점제 산정기준표). 법령 자체는 개정이 있어야만 바뀌는
 * 고정 수치라 실시간 조회 없이 하드코딩함 — 시세·금리처럼 매일 변하는 값이 아님.
 *
 * 확인 방법·일자(2026-08-20): 청약Home 공식 계산기(applyhome.co.kr/ap/apg/selectAddpntCalculatorView.do)
 * 와 주택도시보증공사 안내(khug.or.kr/khmb/m/hg/lg/hglg000020.jsp)를 웹서치로 대조해 브라켓 재검증함.
 * 법령 원문(law.go.kr)은 JS 렌더링이라 직접 파싱은 못 했고, 위 두 2차 출처 교차확인으로 대체.
 *
 * 순수 계산이라 판단/자문이 아니라 정보 제공. 무주택자를 전제로 한 계산이다(유주택자는 가점제
 * 적용 자체가 다르게 갈리므로 이 계산기 범위 밖).
 */

export const MAX_SCORE = 84;
export const SCORE_SOURCE_NOTE =
  "출처: 「주택공급에 관한 규칙」 별표1 — 청약Home 공식 계산기·주택도시보증공사 안내 대조(2026-08-20 확인)";

/** 무주택기간(년, 이미 카운트가 시작된 경우) → 2~32점. 1년 미만 2점, 이후 1년마다 2점씩
 * 가산, 15년 이상 만점. 카운트 시작 여부 자체(만 30세 미만·미혼이면 0점)는 별도 처리 —
 * totalCheongyakScore의 under30Unmarried 참고. */
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
  /** 무주택기간은 만 30세부터 계산한다(30세 이전 혼인 시 혼인신고일부터 — 그 경우는 이 플래그를
   * false로 두고 혼인신고일 기준 연차를 homelessYears에 넣으면 됨). 30세 미만이면서 미혼이면
   * 카운트가 아직 시작 안 해서 연차와 무관하게 0점 — 청약Home 공식 계산기로 확인한 규칙. */
  under30Unmarried: boolean;
}

export function totalCheongyakScore({
  homelessYears,
  dependents,
  subscriptionYears,
  under30Unmarried,
}: ScoreInput): number {
  return (
    (under30Unmarried ? 0 : homelessPeriodScore(homelessYears)) +
    dependentsScore(dependents) +
    subscriptionPeriodScore(subscriptionYears)
  );
}
