// 백엔드(FastAPI) 호출 헬퍼. NEXT_PUBLIC_API_BASE 환경변수로 베이스 URL 지정.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// ngrok 무료 터널의 브라우저 경고 페이지(ERR_NGROK_6024)를 건너뛴다.
// 로컬/다른 환경에선 백엔드가 무시하는 무해한 헤더라 항상 붙여도 됨.
const DEFAULT_HEADERS = { "ngrok-skip-browser-warning": "true" };

// ── 인증 토큰 (localStorage) ──────────────────────────────────
// SPA가 별도 백엔드(FastAPI)를 직접 호출하므로 JWT를 클라이언트에 보관하고 Bearer로 붙인다.
// ponytail: localStorage는 XSS에 노출된다는 한계가 있다. 더 단단히 하려면 백엔드가 httpOnly 쿠키를
//           SameSite/secure로 내려주고 CORS credentials를 켜야 하는데, 그건 교차출처 설정이 붙는 별개 작업.
const TOKEN_KEY = "midas.token";

export function getToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string): void {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken(): void {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const t = getToken();
  return { ...DEFAULT_HEADERS, ...(extra ?? {}), ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  user_uuid: string;
}
export async function apiLogin(email: string, password: string): Promise<LoginResult> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...DEFAULT_HEADERS },
    body: JSON.stringify({ email, password }),
  });
  const data = await handle<LoginResult>(res);
  setToken(data.access_token);
  return data;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string, timeoutMs: number = 4000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      headers: authHeaders(),
      signal: controller.signal,
    });
    return await handle<T>(res);
  } finally {
    clearTimeout(timer);
  }
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  return handle<T>(res);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  return handle<T>(res);
}

/** /api/v1/chat/stream SSE를 읽어 토큰을 onToken으로 흘린다. */
export async function streamChat(
  body: { session_id: string; user_uuid: string; message: string; profile?: string },
  onToken: (t: string) => void,
  onStatus?: (msg: string) => void, // 도구 수집 등 대기 구간 진행상태(status 이벤트)
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    await handle(res); // 에러 메시지 추출 후 throw
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const evt = JSON.parse(line.slice(5).trim());
      if (evt.type === "token") onToken(evt.content as string);
      else if (evt.type === "status") onStatus?.(evt.message as string);
      else if (evt.type === "error") throw new Error(evt.detail);
    }
    // 브라우저가 청크를 버퍼링해 read()가 즉시 반환되면 setState들이 마이크로태스크로 뭉쳐
    // React가 한 번에 페인트한다("확 나와"). 매 청크 후 매크로태스크로 양보해 점진 렌더를 강제한다.
    if (parts.length) await new Promise((r) => setTimeout(r, 0));
  }
}

export interface ChatSessionMeta {
  session_id: string;
  user_uuid: string | null;
  title: string;
  message_count: number;
  updated_at: string | null;
}

// ---- 타입 ----
export interface UserSummary {
  uuid: string;
  age: number | null;
  sex: string | null;
  occupation: string | null;
  family_type: string | null;
  district: string | null;
  total_amount: number | null;
  monthly_income: number | null;
  aggressiveness: number | null;
  financial_literacy: number | null;
  preferred_asset: string | null;
}

export interface UserDetail {
  profile: Record<string, unknown>;
  portfolios: Portfolio[];
}

export interface Portfolio {
  id: string;
  name: string | null;
  strategy_name: string | null;
  stock_ratio: number;
  bond_ratio: number;
  deposit_ratio: number;
  real_estate_ratio: number;
  gold_ratio: number;
  cash_ratio: number;
  is_active: boolean;
  items: PortfolioItem[];
}

export interface PortfolioItem {
  asset_type: string;
  ticker: string | null;
  name: string | null;
  allocation_pct: number;
  currency: string;
  note: string | null;
}

export interface MarketSnapshot {
  snapshot_date: string;
  data_type: string;
  sub_key: string | null;
  value: number;
  unit: string | null;
  source: string;
}

export interface JobState {
  job_id: string;
  kind: string;
  status: "running" | "succeeded" | "failed";
  progress: number;
  logs: string[];
  result: unknown;
  error: string | null;
}

export interface QueryResponse {
  query: string;
  response: string;
  subgraph_triplets: string[];
  source_texts: string[];
}

export interface GraphNode {
  id: string;
  group: string;
  props?: Record<string, string | number | boolean>;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  links: { source: string; target: string; rel: string }[];
}

// ---- 주식 백테스트/분석 ----
export interface StockStrategy {
  name: string;
  label: string;
  default_params: Record<string, number>;
  grid_supported: boolean;
}

export interface GridSearchResult {
  ticker: string;
  strategy: string;
  default_params: Record<string, number>;
  best_params: Record<string, number>;
  best_return: number;
  results_count: number;
}

export interface MemoryStats {
  total: number;
  validated: number;
  accuracy_pct: number;
  avg_return_pct: number;
}

export interface MemoryValidateResult {
  validated: number;
  correct: number;
  incorrect: number;
  errors: number;
}

export interface BacktestMetrics {
  total_return: number;
  buy_hold_return: number;
  annual_return: number;
  max_drawdown: number;
  total_trades: number;
  final_value: number;
  win_rate: number;
  sharpe_ratio: number;
  profit_factor: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  /** 보유 바 비율(시장 노출도). */
  exposure_pct?: number;
  /** 청산 사유별 횟수 (signal·stop_loss·take_profit·trailing_stop). */
  exit_reasons?: Record<string, number>;
}

/** 리스크·비용 오버레이 설정(백테스트에 적용된 값). null = 미적용. */
export interface RiskConfig {
  stop_loss_pct: number | null;
  take_profit_pct: number | null;
  trailing_stop_pct: number | null;
  fee_bps: number | null;
}

export type ExitReason = "signal" | "stop_loss" | "take_profit" | "trailing_stop";

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
  exit_reason?: ExitReason;
}

/** 차트 1행. date 외 컬럼은 전략별로 가변. */
export type BacktestChartRow = {
  date: string;
} & Record<string, number | string | null>;

export interface BacktestResult {
  metrics: BacktestMetrics;
  trades: BacktestTrade[];
  chart_data: BacktestChartRow[];
  strategy: string;
  ticker: string;
  params_used: Record<string, number>;
  risk_used?: RiskConfig;
}

export type BacktestPeriod = "1mo" | "3mo" | "6mo" | "1y" | "2y";

export interface BacktestRequest {
  ticker: string;
  strategy: string;
  period?: BacktestPeriod;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  /** 전략 파라미터 override. {전략명: {파라미터}} 또는 {risk: {...}} 형태. null = 해당 규칙 미적용. */
  params?: Record<string, Record<string, number | null>>;
}

export interface TickerSearchItem {
  symbol: string;
  name: string;
  exchange: string;
  type: string;
}

// ---- 빠른 분석 (QuantDinger fast-analysis 스타일) ----
export interface OutlookHorizon {
  trend: "BUY" | "SELL" | "HOLD";
  strength: "strong" | "moderate" | "weak";
  note: string;
}

export interface CalibrationInfo {
  level: "high" | "medium" | "low";
  raw_pct: number;
  calibrated_pct: number;
  sample_size: number;
  scope: "ticker" | "global";
}

export interface QuickOutlook {
  decision: "BUY" | "SELL" | "HOLD";
  confidence: "high" | "medium" | "low";
  summary: string;
  outlook: {
    "24h": OutlookHorizon;
    "3d": OutlookHorizon;
    "1w": OutlookHorizon;
    "1m": OutlookHorizon;
  };
  key_reasons: string[];
  risks: string[];
  calibration?: CalibrationInfo;
  // 캘리브레이션으로 confidence가 보정된 경우, 보정 전 원본 자신감.
  raw_confidence?: "high" | "medium" | "low";
  error?: string;
}

export interface SimilarPattern {
  id: number;
  decision: "BUY" | "SELL" | "HOLD";
  confidence: string;
  price: number | null;
  summary: string;
  created_at: string | null;
  was_correct: boolean | null;
  actual_return_pct: number | null;
  // 교차종목 검색 시 해당 사례의 종목(현재 분석 종목과 다를 수 있음).
  ticker?: string;
  similarity: number;
}

export interface HorizonStat {
  n: number;
  accuracy_pct: number;
  avg_return_pct: number;
}

export interface HorizonStats {
  horizons: Partial<Record<"24h" | "3d" | "1w" | "1m", HorizonStat>>;
}

export interface QuickAnalysis {
  ticker: string;
  current_price: number;
  change_pct: number;
  rsi: { value: number; signal: "oversold" | "neutral" | "overbought" };
  macd: { line: number; signal_line: number; histogram: number; signal: "bullish" | "bearish" };
  kdj: { k: number; d: number; j: number };
  moving_averages: {
    sma20: number | null;
    sma50: number | null;
    sma200: number | null;
    trend: "bullish" | "bearish" | "mixed";
  };
  bollinger: { upper: number; mid: number; lower: number; pct_b: number };
  atr: { value: number; pct: number; volatility: "high" | "medium" | "low" };
  levels: { support: number; resistance: number };
  outlook: QuickOutlook;
  similar_patterns: SimilarPattern[];
}

export function getStrategies(): Promise<{ strategies: StockStrategy[] }> {
  return apiGet("/api/v1/stocks/strategies");
}

export function searchTickers(q: string): Promise<TickerSearchItem[]> {
  return apiGet(`/api/v1/stocks/ticker-search?q=${encodeURIComponent(q)}`);
}

export function getQuickAnalysis(ticker: string): Promise<QuickAnalysis> {
  // 이 GET은 yfinance 조회 + NIM LLM 다중 시간축 생성을 동기로 수행해 통상 ~10s 걸린다.
  // 기본 4s 타임아웃(가벼운 메타 GET 기준)이면 항상 abort 되므로 넉넉히 준다.
  return apiGet(`/api/v1/stocks/quick-analysis?ticker=${encodeURIComponent(ticker)}`, 60000);
}

export interface PriceHistory {
  ticker: string;
  period: string;
  points: { date: string; close: number }[];
  changePct: number;
}

/** 종가 시계열 (yfinance 실데이터). 스파크라인 등 미니 차트용. */
export function getPriceHistory(ticker: string, period = "1mo"): Promise<PriceHistory> {
  return apiGet(
    `/api/v1/stocks/price-history?ticker=${encodeURIComponent(ticker)}&period=${period}`,
    15000,
  );
}

export function runBacktest(body: BacktestRequest): Promise<BacktestResult> {
  return apiPost("/api/v1/stocks/backtest", body);
}

export function runGridSearch(body: {
  ticker: string;
  strategy: string;
  period?: BacktestPeriod;
}): Promise<GridSearchResult> {
  return apiPost("/api/v1/stocks/grid-search", body);
}

export function getMemoryStats(ticker?: string): Promise<MemoryStats> {
  const q = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";
  return apiGet(`/api/v1/stocks/memory/stats${q}`);
}

export function getHorizonStats(ticker?: string): Promise<HorizonStats> {
  const q = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";
  return apiGet(`/api/v1/stocks/memory/horizon-stats${q}`);
}

export function validateMemory(): Promise<MemoryValidateResult> {
  return apiPost("/api/v1/stocks/memory/validate", {});
}

// ---- 관심종목 (watchlist) ----  모든 함수가 갱신된 티커 목록을 반환
export function getWatchlist(userUuid: string): Promise<string[]> {
  return apiGet(`/api/v1/stocks/watchlist?user_uuid=${encodeURIComponent(userUuid)}`);
}

export function addWatchlist(userUuid: string, ticker: string): Promise<string[]> {
  return apiPost("/api/v1/stocks/watchlist", { user_uuid: userUuid, ticker });
}

export function removeWatchlist(userUuid: string, ticker: string): Promise<string[]> {
  return apiDelete(
    `/api/v1/stocks/watchlist?user_uuid=${encodeURIComponent(userUuid)}&ticker=${encodeURIComponent(ticker)}`,
  );
}

export function runStockAnalysis(body: {
  ticker: string;
  strategy: string;
  metrics: BacktestMetrics;
}): Promise<{ ticker: string; strategy: string; report: string }> {
  return apiPost("/api/v1/stocks/analysis", body);
}

// ---- 청약 (wealth_advisor 이식) ----
export type CheongyakKind = "apt" | "officetel" | "remaining" | "opt" | "public-rent";

export interface CheongyakSummary {
  house_manage_no: string;
  pblanc_no: string;
  house_nm: string;
  house_secd_nm: string;
  house_dtl_secd_nm: string;
  rent_secd_nm: string;
  region: string;
  address: string;
  total_supply: number;
  announcement_date: string;
  reception_start: string;
  reception_end: string;
  special_start: string;
  special_end: string;
  winner_date: string;
  contract_start: string;
  contract_end: string;
  homepage: string;
  constructor: string;
  phone: string;
  move_in_month: string;
  status: string;
  pblanc_url: string;
}

export function listCheongyak(
  kind: CheongyakKind,
  daysBack = 60,
  daysForward = 60,
): Promise<CheongyakSummary[]> {
  return apiGet(
    `/api/v1/cheongyak/list/${kind}?days_back=${daysBack}&days_forward=${daysForward}`,
  );
}

// ---- 청약 상세 ----
export interface CheongyakHousingType {
  house_ty: string;
  supply_area: string;
  supply_count: number;
  special_count: number;
  general_count: number;
  lttot_top_amount: string;
}

export interface CheongyakCompetition {
  house_ty: string;
  supply_count: number;
  rank?: string;
  region_name?: string;
  applicants: string;
  competition_rate: string;
}

export interface CheongyakScore {
  house_ty: string;
  supply_count: number;
  region_name: string;
  min_score: string;
  max_score: string;
  avg_score: string;
}

export interface CheongyakSpecialSupply {
  house_ty: string;
  special_total: number;
  multi_child: number;
  newlywed: number;
  first_life: number;
  elderly_parent: number;
  institution: number;
  result: string;
}

/** 경쟁률 조회 시 종류별 엔드포인트 분기(apt 외엔 competition?kind= 사용). */
type CompetitionKind = "apt" | "officetel" | "public-rent" | "opt";

const _COMPETITION_KIND: Record<CheongyakKind, CompetitionKind> = {
  apt: "apt",
  officetel: "officetel",
  remaining: "apt",
  opt: "opt",
  "public-rent": "public-rent",
};

export function getCheongyakHousingTypes(
  houseManageNo: string,
  pblancNo: string,
): Promise<CheongyakHousingType[]> {
  return apiGet(`/api/v1/cheongyak/detail/${houseManageNo}/${pblancNo}/housing-types`);
}

export function getCheongyakCompetition(
  houseManageNo: string,
  pblancNo: string,
  kind: CheongyakKind = "apt",
): Promise<CheongyakCompetition[]> {
  const ck = _COMPETITION_KIND[kind];
  return apiGet(
    `/api/v1/cheongyak/detail/${houseManageNo}/${pblancNo}/competition?kind=${ck}`,
  );
}

export function getCheongyakScores(
  houseManageNo: string,
  pblancNo: string,
): Promise<CheongyakScore[]> {
  return apiGet(`/api/v1/cheongyak/detail/${houseManageNo}/${pblancNo}/scores`);
}

export function getCheongyakSpecialSupply(
  houseManageNo: string,
  pblancNo: string,
): Promise<CheongyakSpecialSupply[]> {
  return apiGet(`/api/v1/cheongyak/detail/${houseManageNo}/${pblancNo}/special-supply`);
}

// ---- 라이브 시장 리서치 (대시보드 브리핑) ----
export interface RateBriefing {
  available: boolean;
  message: string;
  sections: { label: string; body: string }[];
}

export function getRateBriefing(): Promise<RateBriefing> {
  return apiGet("/api/v1/research/rate-briefing");
}

// ---- RAG 지식베이스 (챗봇 좌측 패널) ----
export interface RagDocument {
  source: string;
  passages: number;
}

export function listRagDocuments(): Promise<{ documents: RagDocument[] }> {
  return apiGet("/api/v1/graph/documents");
}

export function deleteRagDocument(source: string): Promise<{ source: string; deleted_passages: number }> {
  return apiDelete(`/api/v1/graph/documents/${encodeURIComponent(source)}`);
}

export function ingestDocument(filename: string): Promise<{ job_id: string }> {
  return apiPost("/api/v1/graph/ingest/jobs", { filename });
}

export function buildGraph(limit = -1): Promise<{ job_id: string }> {
  return apiPost("/api/v1/graph/build/jobs", { limit });
}

// ---- 세율 개정안 인입 (rate ingestion) ----
// 개정안 텍스트 → 추출 → 현행 대비 diff → 승인 시 오버레이 반영. 계산 산술은 승인 뒤에도 코드가 한다.
export interface ProposedRate {
  value: number;
  basis: string;
}

export interface ProposedRateSet {
  year: string;
  foreign_stock_national_rate: ProposedRate | null;
  interest_dividend_withholding_rate: ProposedRate | null;
  local_income_tax_ratio: ProposedRate | null;
  housing_local_education_tax_rate: ProposedRate | null;
  lbts_yearly_rate: ProposedRate | null;
  capital_gain_basic_deduction_per_year: ProposedRate | null;
  financial_income_total_tax_threshold: ProposedRate | null;
}

export interface RateDiffRow {
  field: string;
  label: string;
  kind: "rate" | "amount";
  old_value: number;
  new_value: number;
  old_basis: string;
  new_basis: string;
  changed: boolean;
}

export interface RateExtractResult {
  proposed: ProposedRateSet;
  diff: RateDiffRow[];
  issues: string[];
  validation_passed: boolean;
}

export interface RateCurrent {
  year: string;
  provenance: string;
  rates: Record<string, { value: number; basis: string }>;
}

export function getCurrentRates(year = "2026"): Promise<RateCurrent> {
  return apiGet(`/api/v1/tax-rates/current?year=${encodeURIComponent(year)}`);
}

/** 개정안 파일(PDF·TXT·MD)을 업로드해 추출한다. PDF는 서버가 파서로 텍스트를 뽑아 동일 파이프라인을 탄다. */
export async function extractRatesUpload(
  file: File,
  year = "2026",
  useLlm = false,
): Promise<RateExtractResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("year", year);
  form.append("use_llm", String(useLlm));
  const res = await fetch(`${API_BASE}/api/v1/tax-rates/extract/upload`, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  return handle<RateExtractResult>(res);
}
