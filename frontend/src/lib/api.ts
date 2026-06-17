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
