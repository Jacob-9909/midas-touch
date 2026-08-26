"use client";

/**
 * 디자인 프리뷰용 목데이터 폴백 — 백엔드 미기동(DB/API 연결 실패)일 때만
 * 잠깐 보여주는 용도다. 실데이터가 오면 절대 섞이지 않게 withMock이
 * 성공 응답을 우선하고, 폴백 시 콘솔에 [mock] 배지를 남긴다.
 */

import type { CheongyakSummary } from "@/lib/api";
import type { QuickAnalysis } from "@/lib/api";
import type { PriceHistory } from "@/lib/api";
import type { GraphSnapshot } from "@/lib/api";

export async function withMock<T>(
  real: Promise<T>,
  mock: T | (() => T),
  label = "api",
): Promise<T> {
  try {
    return await real;
  } catch {
    console.info(`[mock] ${label} 폴백 — 백엔드 미기동, 디자인 프리뷰용 데이터 표시`);
    return typeof mock === "function" ? (mock as () => T)() : mock;
  }
}

// ── 청약 공고 ────────────────────────────────────────────────

const d = (s: string) => s; // 가독성용 아이덴티티

export const MOCK_CHEONGYAK: CheongyakSummary[] = [
  {
    house_manage_no: "2026000123",
    pblanc_no: "2026000123",
    house_nm: "래미안 강서 루체하임",
    house_secd_nm: "아파트",
    house_dtl_secd_nm: "민영",
    rent_secd_nm: "분양",
    region: "서울",
    address: "서울특별시 강서구 공항동",
    total_supply: 1584,
    announcement_date: d("2026-09-01"),
    reception_start: d("2026-09-14"),
    reception_end: d("2026-09-16"),
    special_start: d("2026-09-11"),
    special_end: d("2026-09-11"),
    winner_date: d("2026-09-24"),
    contract_start: d("2026-10-12"),
    contract_end: d("2026-10-16"),
    homepage: "https://www.ramian.co.kr",
    pblanc_url: "https://www.ramian.co.kr",
    constructor: "(주)포스코이앤씨",
    phone: "02-2600-8800",
    move_in_month: "2029년 04월",
    status: "예정",
  },
  {
    house_manage_no: "2026000456",
    pblanc_no: "2026000456",
    house_nm: "자이 송도 클라우드시티",
    house_secd_nm: "아파트",
    house_dtl_secd_nm: "민영",
    rent_secd_nm: "분양",
    region: "인천",
    address: "인천광역시 연수구 송도동",
    total_supply: 2872,
    announcement_date: d("2026-08-28"),
    reception_start: d("2026-09-10"),
    reception_end: d("2026-09-12"),
    special_start: d("2026-09-07"),
    special_end: d("2026-09-08"),
    winner_date: d("2026-09-22"),
    contract_start: d("2026-10-05"),
    contract_end: d("2026-10-09"),
    homepage: "https://www.jai.co.kr",
    pblanc_url: "https://www.jai.co.kr",
    constructor: "재단법인 대한장학재단",
    phone: "032-720-1100",
    move_in_month: "2029년 02월",
    status: "접수예정",
  },
  {
    house_manage_no: "2026000789",
    pblanc_no: "2026000789",
    house_nm: "e편한세상 동탄 센트럴파크",
    house_secd_nm: "아파트",
    house_dtl_secd_nm: "민영",
    rent_secd_nm: "분양",
    region: "경기",
    address: "경기도 화성시 반송동",
    total_supply: 1964,
    announcement_date: d("2026-08-21"),
    reception_start: d("2026-09-03"),
    reception_end: d("2026-09-04"),
    special_start: d("2026-08-31"),
    special_end: d("2026-09-01"),
    winner_date: d("2026-09-15"),
    contract_start: d("2026-09-28"),
    contract_end: d("2026-10-02"),
    homepage: "https://www.ehyundai.com",
    pblanc_url: "https://www.ehyundai.com",
    constructor: "현대엔지니어링(주)",
    phone: "031-373-7000",
    move_in_month: "2028년 12월",
    status: "접수예정",
  },
  {
    house_manage_no: "2026000321",
    pblanc_no: "2026000321",
    house_nm: "호반써밋 부산 센텀파크",
    house_secd_nm: "아파트",
    house_dtl_secd_nm: "민영",
    rent_secd_nm: "분양",
    region: "부산",
    address: "부산광역시 해운대구 반송동",
    total_supply: 1128,
    announcement_date: d("2026-08-18"),
    reception_start: d("2026-08-27"),
    reception_end: d("2026-08-28"),
    special_start: d("2026-08-24"),
    special_end: d("2026-08-25"),
    winner_date: d("2026-09-08"),
    contract_start: d("2026-09-21"),
    contract_end: d("2026-09-25"),
    homepage: "https://www.hoban.co.kr",
    pblanc_url: "https://www.hoban.co.kr",
    constructor: "(주)호반건설",
    phone: "051-790-8800",
    move_in_month: "2028년 10월",
    status: "접수중",
  },
];

// ── 주식 퀵분석/가격 ─────────────────────────────────────────

/** 결정론적 워크 — 같은 티커면 항상 같은 그래프(프리뷰 흔들림 방지). */
function walk(seed: number, n: number, start: number): number[] {
  const out: number[] = [];
  let x = seed;
  let v = start;
  for (let i = 0; i < n; i++) {
    x = (x * 1103515245 + 12345) % 2147483648;
    const r = (x / 2147483648 - 0.48) * 0.024;
    v = Math.max(1, v * (1 + r));
    out.push(Math.round(v * 100) / 100);
  }
  return out;
}

const seedOf = (t: string) => [...t].reduce((a, c) => a + c.charCodeAt(0), 0);

export function mockPriceHistory(ticker: string, period = "1mo"): PriceHistory {
  const n = period === "1y" ? 252 : period === "3mo" ? 63 : 22;
  const closes = walk(seedOf(ticker), n, ticker.startsWith("005930") || ticker === "AAPL" ? 100 : 240);
  const today = new Date();
  const points = closes.map((close, i) => {
    const dt = new Date(today);
    dt.setDate(dt.getDate() - (n - 1 - i));
    return { date: dt.toISOString().slice(0, 10), close };
  });
  const changePct = ((closes[n - 1] - closes[0]) / closes[0]) * 100;
  return { ticker, period, points, changePct: Math.round(changePct * 100) / 100 };
}

export function mockQuickAnalysis(ticker: string): QuickAnalysis {
  const hist = mockPriceHistory(ticker);
  const price = hist.points.at(-1)?.close ?? 100;
  const rsiVal = 42 + (seedOf(ticker) % 30);
  return {
    ticker,
    current_price: price,
    change_pct: hist.changePct,
    rsi: { value: rsiVal, signal: rsiVal < 35 ? "oversold" : rsiVal > 68 ? "overbought" : "neutral" },
    macd: { line: price * 0.0012, signal_line: price * 0.0008, histogram: price * 0.0004, signal: "bullish" },
    kdj: { k: 61, d: 54, j: 75 },
    moving_averages: {
      sma20: Math.round(price * 0.982 * 100) / 100,
      sma50: Math.round(price * 0.961 * 100) / 100,
      sma200: null,
      trend: "bullish",
    },
    bollinger: {
      upper: Math.round(price * 1.06 * 100) / 100,
      mid: Math.round(price * 100) / 100,
      lower: Math.round(price * 0.94 * 100) / 100,
      pct_b: 0.58,
    },
    atr: { value: price * 0.021, pct: 2.1, volatility: "medium" },
    levels: { support: Math.round(price * 0.955 * 100) / 100, resistance: Math.round(price * 1.072 * 100) / 100 },
    outlook: {
      decision: "HOLD",
      confidence: "medium",
      summary:
        "[디자인 프리뷰용 예시 답변] 단기 이평선 위에서 완만한 상승 추세다. 거래량 동반 여부를 확인한 뒤 방향을 판단하는 것이 좋겠다.",
      outlook: {
        "24h": { trend: "HOLD", strength: "moderate", note: "전일 흐름 유지 예상" },
        "3d": { trend: "BUY", strength: "weak", note: "단기 반등 시도 가능" },
        "1w": { trend: "HOLD", strength: "moderate", note: "박스권 상단 테스트" },
        "1m": { trend: "HOLD", strength: "weak", note: "추세 확인 필요" },
      },
      key_reasons: ["20·50일 이동평균 정배열", "RSI 중립권(50±)", "거래량 감소 — 추세 신뢰도 제한"],
      risks: ["박스권 상단 이탈 실패 시 눌림 목", "외부 시장 변동성 확대", "프리뷰 데이터라 실제 판단 근거 아님"],
    },
    similar_patterns: [],
  };
}

// ── 지식그래프 ───────────────────────────────────────────────

export const MOCK_GRAPH: GraphSnapshot = {
  nodes: [
    { id: "소득세법", group: "law", props: { name: "소득세법" } },
    { id: "조세특례제한법", group: "law", props: { name: "조세특례제한법" } },
    { id: "주택에 관한 특별법 요약", group: "doc", props: { name: "주택 청약 가점 안내문" } },
    { id: "제94조(양도소득세)", group: "article", props: { name: "소득세법 제94조" } },
    { id: "제33조(장기보유특별공제)", group: "article", props: { name: "조특법 제33조" } },
    { id: "1세대 1주택 비과세", group: "concept" },
    { id: "비과세 12억 기준", group: "concept" },
    { id: "청약가점 84점", group: "concept" },
    { id: "무주택기간", group: "factor" },
    { id: "부양가족수", group: "factor" },
    { id: "청년특별공급", group: "concept" },
  ],
  links: [
    { source: "소득세법", target: "제94조(양도소득세)", rel: "포함" },
    { source: "조세특례제한법", target: "제33조(장기보유특별공제)", rel: "포함" },
    { source: "제94조(양도소득세)", target: "1세대 1주택 비과세", rel: "규정" },
    { source: "1세대 1주택 비과세", target: "비과세 12억 기준", rel: "요건" },
    { source: "제33조(장기보유특별공제)", target: "비과세 12억 기준", rel: "적용" },
    { source: "주택에 관한 특별법 요약", target: "청약가점 84점", rel: "설명" },
    { source: "무주택기간", target: "청약가점 84점", rel: "가점" },
    { source: "부양가족수", target: "청약가점 84점", rel: "가점" },
    { source: "청약가점 84점", target: "청년특별공급", rel: "자격" },
  ],
};
