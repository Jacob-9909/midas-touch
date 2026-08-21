/** my-profile 자체검증. 프레임워크 없이 돌린다:
 *     cd frontend && npx tsx src/lib/my-profile.check.ts
 * 1순위 요건은 법령 수치라 조용히 틀어지면 알아채기 어렵다 — 경계값을 박아 둔다. */
import assert from "node:assert";
import {
  DEFAULT_PROFILE, firstPriorityChecks, requiredSubscriptionMonths,
  regionOf, isCapitalArea, profileSummary, areaTierOf, parseExclusiveArea,
  type MyProfile, type ListingContext,
} from "./my-profile";

const P = (o: Partial<MyProfile>): MyProfile => ({ ...DEFAULT_PROFILE, ...o });
const ok = (p: MyProfile, label: string) => firstPriorityChecks(p).find(c => c.label === label)!.ok;

// 지역 매핑
assert.equal(regionOf("서울"), "seoul_busan");
assert.equal(regionOf("부산"), "seoul_busan");
assert.equal(regionOf("인천"), "other_metro");
assert.equal(regionOf("경기"), "other");
assert.equal(isCapitalArea("경기"), true);
assert.equal(isCapitalArea("부산"), false);   // 부산은 광역시지만 수도권 아님

// 가입기간 요건: 규제 24 / 수도권 12 / 그 외 6
assert.equal(requiredSubscriptionMonths("서울", true), 24);
assert.equal(requiredSubscriptionMonths("서울", false), 12);
assert.equal(requiredSubscriptionMonths("부산", false), 6);
assert.equal(requiredSubscriptionMonths("경기", false), 12);

// 통장 기간 경계: 수도권 비규제 12개월
assert.equal(ok(P({ sido: "서울", subscriptionYears: 1 }), "청약통장 가입기간"), true);
assert.equal(ok(P({ sido: "서울", subscriptionYears: 0.9 }), "청약통장 가입기간"), false); // 10개월
// 규제지역은 24개월
assert.equal(ok(P({ sido: "서울", regulatedArea: true, subscriptionYears: 2 }), "청약통장 가입기간"), true);
assert.equal(ok(P({ sido: "서울", regulatedArea: true, subscriptionYears: 1.5 }), "청약통장 가입기간"), false);

// 예치금: 서울 85㎡ 이하 = 300만
assert.equal(ok(P({ sido: "서울", targetArea: "85", subscriptionDeposit: 3_000_000 }), "예치금"), true);
assert.equal(ok(P({ sido: "서울", targetArea: "85", subscriptionDeposit: 2_999_999 }), "예치금"), false);
// 같은 돈이라도 면적 올리면 미달 (서울 102㎡ = 600만)
assert.equal(ok(P({ sido: "서울", targetArea: "102", subscriptionDeposit: 3_000_000 }), "예치금"), false);
// 기타지역은 기준이 낮아 통과 (경기 85㎡ = 200만)
assert.equal(ok(P({ sido: "경기", targetArea: "85", subscriptionDeposit: 2_000_000 }), "예치금"), true);

// 규제지역에서만 3개 항목이 추가된다
assert.equal(firstPriorityChecks(P({ regulatedArea: false })).length, 3);
assert.equal(firstPriorityChecks(P({ regulatedArea: true })).length, 6);

// 규제지역 세부 요건
assert.equal(ok(P({ regulatedArea: true, isHouseholder: false }), "세대주 여부"), false);
assert.equal(ok(P({ regulatedArea: true, residenceYears: 2 }), "해당 지역 거주기간"), true);
assert.equal(ok(P({ regulatedArea: true, residenceYears: 1.9 }), "해당 지역 거주기간"), false);
assert.equal(ok(P({ regulatedArea: true, wonLotteryIn5Years: true }), "최근 5년 당첨 이력"), false);

// 무주택
assert.equal(ok(P({ noHouseOwnership: false }), "무주택 여부"), false);

// 요약 문자열: 항목별 미충족이 드러나야 함
const s = profileSummary(P({ sido: "서울", subscriptionYears: 0.5, subscriptionDeposit: 0 }), 20);
assert.ok(s.includes("청약통장 가입기간: 미충족"), s);
assert.ok(s.includes("기준 12개월 이상(수도권), 내 보유 6개월"), s);
assert.ok(s.includes("예치금: 미충족"), s);
const s2 = profileSummary(DEFAULT_PROFILE, 20);
assert.ok(s2.includes("청약통장 가입기간: 충족"), s2);

// 항목별 점수를 계산해서 넘겨야 한다(총점만 주면 모델이 없는 항목을 지어낸다).
// 기본값 = 무주택 3년 8점 + 부양 0명 5점 + 통장 5년 7점 = 20점
assert.ok(s2.includes("무주택기간: 8점/32점"), s2);
assert.ok(s2.includes("부양가족수: 5점/35점"), s2);
assert.ok(s2.includes("청약통장 가입기간: 7점/17점"), s2);
assert.ok(s2.includes("합계 20점/84점"), s2);
// 30세 미만·미혼이면 무주택 0점으로 넘어가야 함
const s3 = profileSummary(P({ under30Unmarried: true }), 12);
assert.ok(s3.includes("무주택기간: 0점/32점"), s3);
assert.ok(s3.includes("산정이 시작되지 않아"), s3);
// 창작 금지 지시가 빠지면 안 된다
assert.ok(s2.includes("청년 가점"), s2);
assert.ok(s2.includes("만들어내지 말 것"), s2);

// ── 공고 기준 재판정 ──
// 공공데이터 주택형 코드 → 전용면적
assert.equal(parseExclusiveArea("084.9800A"), 84.98);
assert.equal(parseExclusiveArea("059.9700"), 59.97);
assert.equal(parseExclusiveArea(""), null);

// 전용면적 → 예치금 면적구간 (경계 포함)
assert.equal(areaTierOf(84.98), "85");
assert.equal(areaTierOf(85), "85");
assert.equal(areaTierOf(85.01), "102");
assert.equal(areaTierOf(102), "102");
assert.equal(areaTierOf(135), "135");
assert.equal(areaTierOf(135.01), "all");

// 핵심: 같은 프로필이라도 보고 있는 공고가 다르면 판정이 달라져야 한다.
// (이 분기가 없으면 A공고를 보든 B공고를 보든 같은 답이 나온다 = 원래 있던 버그)
const me = P({ sido: "서울", targetArea: "85", subscriptionDeposit: 3_000_000, subscriptionYears: 1 });
const okOf = (p: MyProfile, label: string, ctx?: ListingContext) =>
  firstPriorityChecks(p, ctx).find((c) => c.label === label)!.ok;

// 내 프로필 기준(서울 85㎡)은 300만원이면 충족
assert.equal(okOf(me, "예치금"), true);
// 같은 사람이 서울 102㎡ 공고를 보면 600만원 기준이라 미달
assert.equal(okOf(me, "예치금", { sido: "서울", area: "102" }), false);
// 경기 85㎡ 공고는 200만원 기준이라 충족
assert.equal(okOf(me, "예치금", { sido: "경기", area: "85" }), true);
// 통장 기간도 공고 지역을 따른다: 서울(수도권 12개월)은 12개월이면 충족,
// 같은 사람이 부산(수도권 외 6개월) 공고를 보면 역시 충족
assert.equal(okOf(me, "청약통장 가입기간", { sido: "서울", area: "85" }), true);
assert.equal(okOf(me, "청약통장 가입기간", { sido: "부산", area: "85" }), true);
// 6개월만 보유했다면 수도권 공고는 미달, 수도권 외 공고는 충족
const half = P({ subscriptionYears: 0.5 });
assert.equal(okOf(half, "청약통장 가입기간", { sido: "서울", area: "85" }), false);
assert.equal(okOf(half, "청약통장 가입기간", { sido: "부산", area: "85" }), true);

console.log("✅ 1순위 판정 로직 전 케이스 통과");
console.log("\n--- 기본 프로필 요약 샘플 ---\n" + s2);
