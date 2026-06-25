// 백엔드(FastAPI) 호출 헬퍼. NEXT_PUBLIC_API_BASE 환경변수로 베이스 URL 지정.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  return handle<T>(res);
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<T>(res);
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  return handle<T>(res);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  return handle<T>(res);
}

/** /api/v1/chat/stream SSE를 읽어 토큰을 onToken으로 흘린다. */
export async function streamChat(
  body: { session_id: string; user_uuid: string; message: string },
  onToken: (t: string) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
      else if (evt.type === "error") throw new Error(evt.detail);
    }
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

export interface GraphSnapshot {
  nodes: { id: string; group: string }[];
  links: { source: string; target: string; rel: string }[];
}

// ---- 주식 백테스트/분석 ----
export interface StockStrategy {
  name: string;
  label: string;
  default_params: Record<string, number>;
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
}

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
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
}

export type BacktestPeriod = "1mo" | "3mo" | "6mo" | "1y" | "2y";

export interface BacktestRequest {
  ticker: string;
  strategy: string;
  period?: BacktestPeriod;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
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
  error?: string;
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
}

export function getStrategies(): Promise<{ strategies: StockStrategy[] }> {
  return apiGet("/api/v1/stocks/strategies");
}

export function searchTickers(q: string): Promise<TickerSearchItem[]> {
  return apiGet(`/api/v1/stocks/ticker-search?q=${encodeURIComponent(q)}`);
}

export function getQuickAnalysis(ticker: string): Promise<QuickAnalysis> {
  return apiGet(`/api/v1/stocks/quick-analysis?ticker=${encodeURIComponent(ticker)}`);
}

export function runBacktest(body: BacktestRequest): Promise<BacktestResult> {
  return apiPost("/api/v1/stocks/backtest", body);
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

// ---- 라이브 시장 리서치 (대시보드 브리핑) ----
export interface RateBriefing {
  available: boolean;
  message: string;
  sections: { label: string; body: string }[];
}

export function getRateBriefing(): Promise<RateBriefing> {
  return apiGet("/api/v1/research/rate-briefing");
}
