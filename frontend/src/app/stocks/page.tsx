"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { errMsg } from "@/lib/async";
import { useRouter } from "next/navigation";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import {
  ChartLineUp,
  Sparkle,
  Play,
  ChatCircleText,
  Lightning,
  CaretDown,
  CaretUp,
  ArrowUp,
  ArrowDown,
  Minus,
  ClockCounterClockwise,
  Target,
  CheckCircle,
  ChartBar,
  ArrowRight,
  ShieldCheck,
} from "@phosphor-icons/react";
import {
  apiGet,
  getStrategies,
  getQuickAnalysis,
  runBacktest,
  runGridSearch,
  runStockAnalysis,
  type StockStrategy,
  type BacktestResult,
  type BacktestMetrics,
  type BacktestPeriod,
  type GridSearchResult,
  type QuickAnalysis,
  type OutlookHorizon,
  type UserDetail,
} from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { seedChat } from "@/lib/chat-seed";
import { Card, PageTitle, SectionLabel, Skeleton } from "@/components/ui";
import { useToast } from "@/lib/toast";
import TickerAutocomplete from "./TickerAutocomplete";
import MemoryStatsCard from "./MemoryStatsCard";
import WatchlistCard from "./WatchlistCard";

const TOOLTIP_STYLE = {
  background: "var(--ink-2)",
  border: "1px solid var(--line)",
  borderRadius: 14,
  color: "var(--fg)",
  fontSize: 12,
  boxShadow: "var(--shadow-float)",
} as const;

const PERIODS: { value: BacktestPeriod; label: string }[] = [
  { value: "1mo", label: "1개월" },
  { value: "3mo", label: "3개월" },
  { value: "6mo", label: "6개월" },
  { value: "1y", label: "1년" },
  { value: "2y", label: "2년" },
];

const pct = (n: number): string => `${(n * 100).toFixed(2)}%`;
const price = (n: number): string =>
  n >= 1000 ? n.toLocaleString("ko-KR", { maximumFractionDigits: 2 }) : n.toFixed(4);

// 청산 사유 라벨/색 — 신호 청산 vs 리스크 청산(손절·추격손절·익절)을 구분해 보여준다.
const EXIT_LABEL: Record<string, string> = {
  signal: "신호",
  stop_loss: "손절",
  take_profit: "익절",
  trailing_stop: "추격손절",
};
const EXIT_TONE: Record<string, string> = {
  signal: "text-muted",
  stop_loss: "text-[#e2607b]",
  trailing_stop: "text-[#e2a15a]",
  take_profit: "text-[#58c8a0]",
};

// 백테스트에 적용된 리스크 오버레이를 사람이 읽는 한 줄로 (null=미적용은 생략).
function riskSummary(r: import("@/lib/api").RiskConfig): string {
  const parts: string[] = [];
  if (r.stop_loss_pct != null) parts.push(`손절 -${(r.stop_loss_pct * 100).toFixed(0)}%`);
  if (r.trailing_stop_pct != null) parts.push(`추격 -${(r.trailing_stop_pct * 100).toFixed(0)}%`);
  if (r.take_profit_pct != null) parts.push(`익절 +${(r.take_profit_pct * 100).toFixed(0)}%`);
  if (r.fee_bps != null) parts.push(`수수료 ${(r.fee_bps / 100).toFixed(2)}%`);
  return parts.length ? parts.join(" · ") : "미적용";
}

// 백테스트 리스크·비용 상태 (퍼센트/bp 단위의 UI 값; run에서 소수/bp로 변환해 params.risk로 전송).
type RiskState = {
  slOn: boolean; sl: number;
  tsOn: boolean; ts: number;
  tpOn: boolean; tp: number;
  fee: number;
};
const DEFAULT_RISK: RiskState = { slOn: true, sl: 8, tsOn: true, ts: 12, tpOn: false, tp: 20, fee: 5 };

// UI 값(% / bp) → 백엔드 params.risk (소수 / bp, 꺼진 규칙은 null).
function toRiskParams(r: RiskState): Record<string, number | null> {
  return {
    stop_loss_pct: r.slOn ? r.sl / 100 : null,
    take_profit_pct: r.tpOn ? r.tp / 100 : null,
    trailing_stop_pct: r.tsOn ? r.ts / 100 : null,
    fee_bps: r.fee,
  };
}

function RiskRow({
  label, on, onToggle, value, min, max, step, onChange, fmt, togglable = true,
}: {
  label: string;
  on: boolean;
  onToggle?: (v: boolean) => void;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  fmt: (v: number) => string;
  togglable?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <label className="flex w-24 shrink-0 items-center gap-2 text-xs">
        {togglable && (
          <input
            type="checkbox"
            checked={on}
            onChange={(e) => onToggle?.(e.target.checked)}
            className="h-3.5 w-3.5 accent-[var(--accent)]"
          />
        )}
        <span className={on ? "text-fg" : "text-muted line-through"}>{label}</span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={!on}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 flex-1 cursor-pointer accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-40"
      />
      <span className={`w-14 text-right font-mono text-xs ${on ? "text-accent" : "text-muted"}`}>
        {on ? fmt(value) : "끄기"}
      </span>
    </div>
  );
}

function MetricTile({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "neutral";
  sub?: string;
}) {
  const color =
    tone === "up" ? "text-[#58c8a0]" : tone === "down" ? "text-[#e2607b]" : "text-fg";
  return (
    <div className="rounded-2xl border border-line bg-[var(--ink-2)]/40 px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 font-display text-lg font-semibold ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

function portfolioTickers(detail: UserDetail | null): { ticker: string; name: string }[] {
  if (!detail) return [];
  const seen = new Set<string>();
  const out: { ticker: string; name: string }[] = [];
  for (const pf of detail.portfolios) {
    for (const it of pf.items) {
      const t = (it.ticker || "").trim();
      if (!t || seen.has(t.toUpperCase())) continue;
      seen.add(t.toUpperCase());
      out.push({ ticker: t, name: it.name || t });
    }
  }
  return out;
}

// ── Quick Analysis sub-components ─────────────────────────────────────────────

function RsiGauge({ value, signal }: { value: number; signal: string }) {
  const color =
    signal === "oversold"
      ? "text-[#58c8a0]"
      : signal === "overbought"
        ? "text-[#e2607b]"
        : "text-fg";
  const label =
    signal === "oversold" ? "과매도" : signal === "overbought" ? "과매수" : "중립";
  const barPct = Math.min(100, Math.max(0, value));
  const barColor =
    barPct < 30 ? "#58c8a0" : barPct > 70 ? "#e2607b" : "var(--accent)";
  return (
    <div className="rounded-2xl border border-line bg-[var(--ink-2)]/40 p-4">
      <div className="mb-2 text-xs uppercase tracking-wider text-muted">RSI (14)</div>
      <div className={`font-display text-2xl font-bold ${color}`}>{value}</div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--ink-3)]">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${barPct}%`, background: barColor }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-muted">
        <span>0 과매도</span>
        <span className={`font-medium ${color}`}>{label}</span>
        <span>100 과매수</span>
      </div>
    </div>
  );
}

function IndicatorCard({
  title,
  value,
  signal,
  detail,
  tone,
}: {
  title: string;
  value: string;
  signal: string;
  detail?: string;
  tone?: "up" | "down" | "neutral";
}) {
  const color =
    tone === "up" ? "text-[#58c8a0]" : tone === "down" ? "text-[#e2607b]" : "text-fg";
  return (
    <div className="rounded-2xl border border-line bg-[var(--ink-2)]/40 p-4">
      <div className="mb-2 text-xs uppercase tracking-wider text-muted">{title}</div>
      <div className={`font-display text-xl font-bold ${color}`}>{value}</div>
      <div className={`mt-1 text-sm font-medium ${color}`}>{signal}</div>
      {detail && <div className="mt-1 text-xs text-muted">{detail}</div>}
    </div>
  );
}

function OutlookCard({
  label,
  horizon,
}: {
  label: string;
  horizon: OutlookHorizon | undefined;
}) {
  if (!horizon) return null;
  const { trend, strength, note } = horizon;
  const Icon =
    trend === "BUY" ? ArrowUp : trend === "SELL" ? ArrowDown : Minus;
  const color =
    trend === "BUY" ? "text-[#58c8a0]" : trend === "SELL" ? "text-[#e2607b]" : "text-muted";
  const bg =
    trend === "BUY"
      ? "border-[#58c8a0]/30 bg-[#58c8a0]/5"
      : trend === "SELL"
        ? "border-[#e2607b]/30 bg-[#e2607b]/5"
        : "border-line bg-[var(--ink-2)]/30";
  const trendKo = trend === "BUY" ? "매수" : trend === "SELL" ? "매도" : "보유";
  const strengthKo = strength === "strong" ? "강함" : strength === "moderate" ? "보통" : "약함";
  return (
    <div className={`rounded-2xl border p-4 ${bg}`}>
      <div className="mb-2 text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className={`flex items-center gap-1.5 font-display text-lg font-bold ${color}`}>
        <Icon weight="bold" size={18} />
        {trendKo}
      </div>
      <div className="mt-1 text-xs text-muted">{strengthKo} · {note}</div>
    </div>
  );
}

export default function StocksPage() {
  const toast = useToast();
  const router = useRouter();
  const { selected } = useSelectedUser();

  // Shared state
  const [ticker, setTicker] = useState("AAPL");
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [activeTab, setActiveTab] = useState<"quick" | "backtest">("quick");

  // Quick analysis state
  const [qa, setQa] = useState<QuickAnalysis | null>(null);
  const [qaBusy, setQaBusy] = useState(false);
  const [tradesOpen, setTradesOpen] = useState(false);

  // Backtest state
  const [strategies, setStrategies] = useState<StockStrategy[]>([]);
  const [strategy, setStrategy] = useState("sma_crossover");
  const [period, setPeriod] = useState<BacktestPeriod>("1y");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [risk, setRisk] = useState<RiskState>(DEFAULT_RISK);
  const [gridResult, setGridResult] = useState<GridSearchResult | null>(null);
  const [gridShownKey, setGridShownKey] = useState("");
  const [gridBusy, setGridBusy] = useState(false);

  useEffect(() => {
    getStrategies()
      .then((r) => setStrategies(r.strategies))
      .catch((e) => toast(`전략 목록 로드 실패: ${errMsg(e)}`, "error"));
  }, [toast]);

  useEffect(() => {
    // 유저 미선택 시 보유종목 블록이 selected로 가드되므로 stale detail은 렌더되지 않음 → 동기 리셋 불필요.
    if (!selected) return;
    let alive = true;
    apiGet<UserDetail>(`/api/v1/users/${selected.uuid}`)
      .then((d) => alive && setDetail(d))
      .catch(() => alive && setDetail(null));
    return () => { alive = false; };
  }, [selected]);

  const tickers = useMemo(() => portfolioTickers(detail), [detail]);
  const currentStrategy = useMemo(
    () => strategies.find((s) => s.name === strategy),
    [strategies, strategy],
  );

  // ── Quick analysis ──────────────────────────────────────────────────────────
  const runQuick = useCallback(async (tk?: string) => {
    const symbol = (tk ?? ticker).trim().toUpperCase();
    if (!symbol) return;
    setTicker(symbol);
    setQaBusy(true);
    setQa(null);
    try {
      const res = await getQuickAnalysis(symbol);
      setQa(res);
    } catch (e) {
      toast(`빠른 분석 실패: ${errMsg(e)}`, "error");
    } finally {
      setQaBusy(false);
    }
  }, [ticker, toast]);

  const consultQuick = () => {
    if (!qa) return;
    const o = qa.outlook;
    const dec = o.decision === "BUY" ? "매수" : o.decision === "SELL" ? "매도" : "보유";
    const text =
      `[주식 빠른 분석] ${qa.ticker}\n` +
      `현재가: ${price(qa.current_price)} (${pct(qa.change_pct)})\n` +
      `RSI ${qa.rsi.value}(${qa.rsi.signal}) · MACD ${qa.macd.signal} · KDJ K=${qa.kdj.k}\n` +
      `AI 판단: ${dec} (${o.confidence} 신뢰도)\n요약: ${o.summary}\n\n` +
      `이 분석을 내 포트폴리오 및 위험성향 관점에서 평가하고 구체적 조언을 해줘.`;
    if (!selected) toast("홈에서 유저를 선택하면 맞춤 상담이 됩니다.", "info");
    seedChat(router, text);
  };

  // ── Backtest ────────────────────────────────────────────────────────────────
  const run = useCallback(
    async (tk?: string, strat?: string, params?: Record<string, Record<string, number | null>>) => {
      const symbol = (tk ?? ticker).trim().toUpperCase();
      const stratName = strat ?? strategy;
      if (!symbol) return;
      setTicker(symbol);
      setBusy(true);
      setReport(null);
      setTradesOpen(false);
      try {
        // 현재 리스크 슬라이더 값을 항상 실어 보낸다(그리드 최적 파라미터 등 다른 override와 병합).
        const merged = { ...(params ?? {}), risk: toRiskParams(risk) };
        const res = await runBacktest({ ticker: symbol, strategy: stratName, period, params: merged });
        setResult(res);
        toast(`${res.ticker} 백테스트 완료`, "success");
      } catch (e) {
        toast(`백테스트 실패: ${errMsg(e)}`, "error");
      } finally {
        setBusy(false);
      }
    },
    [ticker, strategy, period, toast, risk],
  );

  // 전략·기간·티커가 바뀌면 직전 그리드 결과는 무효 — 렌더 중 키 비교로 리셋(effect 불필요).
  const gridKey = `${strategy}|${period}|${ticker}`;
  if (gridShownKey !== gridKey) {
    setGridShownKey(gridKey);
    if (gridResult !== null) setGridResult(null);
  }

  const optimize = async () => {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;
    setGridBusy(true);
    setGridResult(null);
    try {
      const res = await runGridSearch({ ticker: symbol, strategy, period });
      setGridResult(res);
      toast(`${res.results_count}개 조합 탐색 완료`, "success");
    } catch (e) {
      toast(`그리드 서치 실패: ${errMsg(e)}`, "error");
    } finally {
      setGridBusy(false);
    }
  };

  const applyGrid = () => {
    if (!gridResult) return;
    void run(gridResult.ticker, gridResult.strategy, {
      [gridResult.strategy]: gridResult.best_params,
    });
  };

  const analyze = async (metrics: BacktestMetrics) => {
    if (!result) return;
    setReportBusy(true);
    try {
      const res = await runStockAnalysis({ ticker: result.ticker, strategy: result.strategy, metrics });
      setReport(res.report);
    } catch (e) {
      toast(`리포트 생성 실패: ${errMsg(e)}`, "error");
    } finally {
      setReportBusy(false);
    }
  };

  const consult = () => {
    if (!result) return;
    const m = result.metrics;
    const label = strategies.find((s) => s.name === result.strategy)?.label ?? result.strategy;
    const text =
      `[주식 백테스트] ${result.ticker} / ${label}\n` +
      `전략 수익률 ${pct(m.total_return)} · 매수후보유 ${pct(m.buy_hold_return)} · ` +
      `최대낙폭 ${pct(m.max_drawdown)} · 승률 ${pct(m.win_rate)} · 거래 ${result.trades.length}회.\n` +
      `이 결과를 내 포트폴리오와 위험성향 관점에서 평가하고, 조정안을 제안해줘.`;
    if (!selected) toast("먼저 홈에서 유저를 선택하면 맞춤 상담이 됩니다.", "info");
    seedChat(router, text);
  };

  // ?ticker= deeplink — 마운트 1회 URL 읽기(클라이언트 전용). lazy init은 SSR 하이드레이션
  // 불일치를 유발해 effect가 정답: 1회성 외부값 init이라 cascading-render 우려는 해당 없음.
  useEffect(() => {
    const tk = new URLSearchParams(window.location.search).get("ticker");
    if (tk) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveTab("backtest");
      void run(tk.toUpperCase(), "sma_crossover");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const m = result?.metrics;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <PageTitle
        eyebrow="TRADING LAB"
        title="주식 분석"
        subtitle="기술적 지표 스냅샷과 AI 다중 시간축 전망, 전략 백테스트로 글로벌 종목을 분석하세요."
      />

      {/* ── 공통 입력 ──────────────────────────────────────────────── */}
      <Card className="mb-6">
        <SectionLabel>종목 설정</SectionLabel>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <TickerAutocomplete
            value={ticker}
            onChange={setTicker}
            onSubmit={(sym) => (activeTab === "quick" ? runQuick(sym) : run(sym))}
          />
          <button
            onClick={() => (activeTab === "quick" ? runQuick() : run())}
            disabled={qaBusy || busy}
            className="btn-accent flex h-10 items-center justify-center gap-2 px-5 text-sm disabled:opacity-50"
          >
            <Play weight="fill" size={16} />
            {qaBusy || busy ? "분석 중…" : activeTab === "quick" ? "빠른 분석" : "백테스트 실행"}
          </button>
        </div>

        {/* 보유 종목 퀵픽 */}
        {selected && tickers.length > 0 && (
          <div className="mt-4">
            <span className="text-xs text-muted">{selected.label}님 보유 종목</span>
            <div className="mt-2 flex flex-wrap gap-2">
              {tickers.map((t) => (
                <button
                  key={t.ticker}
                  onClick={() =>
                    activeTab === "quick" ? runQuick(t.ticker) : run(t.ticker, strategy)
                  }
                  className="rounded-full border border-line px-3 py-1 text-xs text-muted transition hover:border-accent hover:text-accent"
                >
                  {t.name}{" "}
                  <span className="font-mono text-[10px] opacity-70">{t.ticker}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {!selected && (
          <p className="mt-3 text-xs text-muted">
            홈에서 유저를 선택하면 보유 종목이 퀵픽으로 표시되고, 분석 결과를 맞춤 상담으로 연결할 수 있습니다.
          </p>
        )}
      </Card>

      <WatchlistCard
        userUuid={selected?.uuid}
        currentTicker={ticker}
        onPick={(t) => (activeTab === "quick" ? runQuick(t) : run(t, strategy))}
      />

      {/* ── 탭 선택 ──────────────────────────────────────────────────────── */}
      <div className="mb-6 flex gap-1 rounded-2xl border border-line bg-[var(--ink-2)]/30 p-1">
        <button
          onClick={() => setActiveTab("quick")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-xl py-2 text-sm font-medium transition-colors ${
            activeTab === "quick"
              ? "bg-[color-mix(in_srgb,var(--accent)_13%,transparent)] text-accent"
              : "text-muted hover:text-fg"
          }`}
        >
          <Lightning size={15} />
          빠른 분석
        </button>
        <button
          onClick={() => setActiveTab("backtest")}
          className={`flex flex-1 items-center justify-center gap-2 rounded-xl py-2 text-sm font-medium transition-colors ${
            activeTab === "backtest"
              ? "bg-[color-mix(in_srgb,var(--accent)_13%,transparent)] text-accent"
              : "text-muted hover:text-fg"
          }`}
        >
          <ChartLineUp size={15} />
          백테스트
        </button>
      </div>

      {/* ── 빠른 분석 탭 ─────────────────────────────────────────────────── */}
      {activeTab === "quick" && (
        <div className="flex flex-col gap-6">
          {!qa && !qaBusy && (
            <Card>
              <p className="text-sm text-muted">
                티커를 입력하고 <strong>빠른 분석</strong>을 실행하면 RSI·MACD·KDJ·볼린저 밴드 등
                기술적 지표와 AI 다중 시간축 전망(24h/3d/1w/1m)을 확인할 수 있습니다.
              </p>
            </Card>
          )}
          {qaBusy && <Skeleton className="h-80 w-full rounded-2xl" />}

          {qa && (
            <>
              {/* Price header */}
              <div className="flex items-end justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted">{qa.ticker}</p>
                  <p className="font-display text-3xl font-bold">{price(qa.current_price)}</p>
                  <p
                    className={`text-sm font-medium ${qa.change_pct >= 0 ? "text-[#58c8a0]" : "text-[#e2607b]"}`}
                  >
                    {qa.change_pct >= 0 ? "+" : ""}
                    {pct(qa.change_pct)} 전일 대비
                  </p>
                </div>
                <button
                  onClick={consultQuick}
                  className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-sm"
                >
                  <ChatCircleText size={14} /> 이 분석으로 상담받기
                </button>
              </div>

              {/* Technical indicators */}
              <Card>
                <SectionLabel>기술적 지표</SectionLabel>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <RsiGauge value={qa.rsi.value} signal={qa.rsi.signal} />
                  <IndicatorCard
                    title="MACD (12,26,9)"
                    value={qa.macd.histogram.toFixed(4)}
                    signal={qa.macd.signal === "bullish" ? "상승 추세" : "하락 추세"}
                    detail={`MACD ${qa.macd.line.toFixed(4)}`}
                    tone={qa.macd.signal === "bullish" ? "up" : "down"}
                  />
                  <IndicatorCard
                    title="KDJ (9,3,3)"
                    value={`K ${qa.kdj.k}`}
                    signal={`D ${qa.kdj.d} · J ${qa.kdj.j}`}
                    tone={qa.kdj.k > qa.kdj.d ? "up" : "down"}
                  />
                  <IndicatorCard
                    title="MA 추세"
                    value={
                      qa.moving_averages.trend === "bullish"
                        ? "상승"
                        : qa.moving_averages.trend === "bearish"
                          ? "하락"
                          : "혼조"
                    }
                    signal={`SMA20 ${qa.moving_averages.sma20 ?? "-"}`}
                    detail={`SMA200 ${qa.moving_averages.sma200 ?? "데이터 부족"}`}
                    tone={
                      qa.moving_averages.trend === "bullish"
                        ? "up"
                        : qa.moving_averages.trend === "bearish"
                          ? "down"
                          : "neutral"
                    }
                  />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MetricTile
                    label="볼린저 %B"
                    value={`${(qa.bollinger.pct_b * 100).toFixed(1)}%`}
                    tone={qa.bollinger.pct_b > 0.8 ? "down" : qa.bollinger.pct_b < 0.2 ? "up" : "neutral"}
                    sub={`상단 ${price(qa.bollinger.upper)} / 하단 ${price(qa.bollinger.lower)}`}
                  />
                  <MetricTile
                    label="ATR 변동성"
                    value={
                      qa.atr.volatility === "high"
                        ? "높음"
                        : qa.atr.volatility === "low"
                          ? "낮음"
                          : "보통"
                    }
                    sub={`${(qa.atr.pct * 100).toFixed(2)}% / 일`}
                  />
                  <MetricTile
                    label="지지선"
                    value={price(qa.levels.support)}
                    tone="up"
                    sub="최근 20봉 저점"
                  />
                  <MetricTile
                    label="저항선"
                    value={price(qa.levels.resistance)}
                    tone="down"
                    sub="최근 20봉 고점"
                  />
                </div>
              </Card>

              {/* AI Outlook */}
              {qa.outlook && !qa.outlook.error && (
                <Card>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <SectionLabel>
                        <span className="inline-flex items-center gap-1.5">
                          <Sparkle size={14} /> AI 다중 시간축 전망
                        </span>
                      </SectionLabel>
                      <p className="mt-1 text-sm text-fg/80">{qa.outlook.summary}</p>
                    </div>
                    <div className="shrink-0 rounded-full border border-line px-3 py-1 text-xs font-medium">
                      {qa.outlook.decision === "BUY"
                        ? "✅ 매수"
                        : qa.outlook.decision === "SELL"
                          ? "🔻 매도"
                          : "⏸ 보유"}{" "}
                      <span className="text-muted">
                        {qa.outlook.confidence === "high"
                          ? "신뢰도 높음"
                          : qa.outlook.confidence === "medium"
                            ? "신뢰도 보통"
                            : "신뢰도 낮음"}
                      </span>
                    </div>
                  </div>

                  {/* 신뢰도 캘리브레이션 — 과거 적중률로 보정된 자신감 */}
                  {qa.outlook.calibration && (
                    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-[var(--ink-2)]/40 px-3 py-2 text-xs">
                      <ChartBar size={14} className="text-accent" />
                      <span className="text-muted">신뢰도 보정:</span>
                      <span className="text-fg/70">AI 자신감 {qa.outlook.calibration.raw_pct}%</span>
                      <ArrowRight size={12} className="text-muted" />
                      <span
                        className={`font-semibold ${
                          qa.outlook.calibration.calibrated_pct >= qa.outlook.calibration.raw_pct
                            ? "text-[#58c8a0]"
                            : "text-[#e2607b]"
                        }`}
                      >
                        실측 {qa.outlook.calibration.calibrated_pct}%
                      </span>
                      <span className="text-muted">
                        ({qa.outlook.calibration.scope === "ticker" ? qa.ticker : "전체"} 과거{" "}
                        {qa.outlook.calibration.sample_size}건 기준)
                      </span>
                    </div>
                  )}

                  {qa.outlook.outlook && (
                    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                      <OutlookCard label="24시간" horizon={qa.outlook.outlook["24h"]} />
                      <OutlookCard label="3일" horizon={qa.outlook.outlook["3d"]} />
                      <OutlookCard label="1주" horizon={qa.outlook.outlook["1w"]} />
                      <OutlookCard label="1개월" horizon={qa.outlook.outlook["1m"]} />
                    </div>
                  )}

                  {(qa.outlook.key_reasons?.length > 0 || qa.outlook.risks?.length > 0) && (
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      {qa.outlook.key_reasons?.length > 0 && (
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-[#58c8a0]">핵심 근거</p>
                          <ul className="space-y-1 text-xs text-fg/80">
                            {qa.outlook.key_reasons.map((r, i) => (
                              <li key={i} className="flex gap-1.5">
                                <span className="mt-0.5 text-[#58c8a0]">•</span>
                                {r}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {qa.outlook.risks?.length > 0 && (
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-[#e2607b]">리스크 요인</p>
                          <ul className="space-y-1 text-xs text-fg/80">
                            {qa.outlook.risks.map((r, i) => (
                              <li key={i} className="flex gap-1.5">
                                <span className="mt-0.5 text-[#e2607b]">•</span>
                                {r}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              )}

              {/* 과거 유사 패턴 (분석 메모리) */}
              {qa.similar_patterns?.length > 0 && (
                <Card>
                  <SectionLabel>
                    <span className="inline-flex items-center gap-1.5">
                      <ClockCounterClockwise size={14} /> 과거 유사 패턴
                    </span>
                  </SectionLabel>
                  <p className="mt-1 text-xs text-muted">
                    현재와 비슷한 지표 조건이었던 과거 분석입니다. AI 전망에 컨텍스트로 반영됩니다.
                  </p>
                  <div className="mt-3 flex flex-col gap-2">
                    {qa.similar_patterns.map((p) => {
                      const decColor =
                        p.decision === "BUY"
                          ? "text-[#58c8a0]"
                          : p.decision === "SELL"
                            ? "text-[#e2607b]"
                            : "text-muted";
                      const decKo = p.decision === "BUY" ? "매수" : p.decision === "SELL" ? "매도" : "보유";
                      return (
                        <div
                          key={p.id}
                          className="rounded-xl border border-line bg-[var(--ink-2)]/40 px-3 py-2"
                        >
                          <div className="flex items-center justify-between gap-2 text-xs">
                            <span className="text-muted">{(p.created_at ?? "").slice(0, 10)}</span>
                            <div className="flex items-center gap-2">
                              <span className={`font-medium ${decColor}`}>{decKo}</span>
                              <span className="text-muted">유사도 {(p.similarity * 100).toFixed(0)}%</span>
                              {p.was_correct !== null && (
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                                    p.was_correct
                                      ? "bg-[#58c8a0]/10 text-[#58c8a0]"
                                      : "bg-[#e2607b]/10 text-[#e2607b]"
                                  }`}
                                >
                                  {p.was_correct ? "적중" : "빗나감"}
                                  {p.actual_return_pct !== null
                                    ? ` ${p.actual_return_pct >= 0 ? "+" : ""}${p.actual_return_pct.toFixed(1)}%`
                                    : ""}
                                </span>
                              )}
                            </div>
                          </div>
                          {p.summary && (
                            <p className="mt-1 line-clamp-2 text-xs text-fg/70">{p.summary}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </Card>
              )}
            </>
          )}

          {/* 분석 메모리 누적 현황(데이터 있을 때만 표시) */}
          <MemoryStatsCard ticker={qa?.ticker} />
        </div>
      )}

      {/* ── 백테스트 탭 ──────────────────────────────────────────────────── */}
      {activeTab === "backtest" && (
        <div className="flex flex-col gap-6">
          {/* Strategy + period controls */}
          <Card>
            <SectionLabel>백테스트 설정</SectionLabel>
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col gap-1.5 sm:w-56">
                <span className="text-xs text-muted">전략</span>
                <select
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value)}
                  className="rounded-xl border border-line bg-[var(--ink-2)]/50 px-3 py-2 text-sm text-fg outline-none focus:border-accent"
                >
                  {strategies.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted">기간</span>
                <div className="flex gap-1">
                  {PERIODS.map((p) => (
                    <button
                      key={p.value}
                      onClick={() => setPeriod(p.value)}
                      className={`rounded-xl border px-3 py-2 text-sm transition-colors ${
                        period === p.value
                          ? "border-accent bg-[color-mix(in_srgb,var(--accent)_13%,transparent)] text-accent"
                          : "border-line text-muted hover:text-fg"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 리스크·비용 설정 — params.risk로 백테스트에 반영 */}
            <div className="mt-4 rounded-2xl border border-line bg-[var(--ink-2)]/30 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="flex items-center gap-1.5 text-sm font-medium text-fg">
                  <ShieldCheck size={15} /> 리스크·비용 설정
                </p>
                <button
                  onClick={() => setRisk(DEFAULT_RISK)}
                  className="text-xs text-muted transition-colors hover:text-accent"
                >
                  기본값
                </button>
              </div>
              <p className="mb-3 mt-0.5 text-xs text-muted">
                조정 후 백테스트를 다시 실행하면 반영됩니다. 리스크 청산이 신호 청산보다 우선합니다.
              </p>
              <div className="max-w-md space-y-2.5">
                <RiskRow
                  label="손절" on={risk.slOn}
                  onToggle={(v) => setRisk((r) => ({ ...r, slOn: v }))}
                  value={risk.sl} min={1} max={30} step={1}
                  onChange={(v) => setRisk((r) => ({ ...r, sl: v }))}
                  fmt={(v) => `-${v}%`}
                />
                <RiskRow
                  label="추격손절" on={risk.tsOn}
                  onToggle={(v) => setRisk((r) => ({ ...r, tsOn: v }))}
                  value={risk.ts} min={1} max={30} step={1}
                  onChange={(v) => setRisk((r) => ({ ...r, ts: v }))}
                  fmt={(v) => `-${v}%`}
                />
                <RiskRow
                  label="익절" on={risk.tpOn}
                  onToggle={(v) => setRisk((r) => ({ ...r, tpOn: v }))}
                  value={risk.tp} min={5} max={100} step={5}
                  onChange={(v) => setRisk((r) => ({ ...r, tp: v }))}
                  fmt={(v) => `+${v}%`}
                />
                <RiskRow
                  label="거래비용" togglable={false} on
                  value={risk.fee} min={0} max={50} step={1}
                  onChange={(v) => setRisk((r) => ({ ...r, fee: v }))}
                  fmt={(v) => `${(v / 100).toFixed(2)}%`}
                />
              </div>
            </div>

            {/* 그리드 서치 — 지원 전략만 */}
            {currentStrategy?.grid_supported && (
              <div className="mt-4 rounded-2xl border border-line bg-[var(--ink-2)]/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="flex items-center gap-1.5 text-sm font-medium text-fg">
                      <Target size={15} /> 파라미터 최적화 (그리드 서치)
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      {currentStrategy.label} 전략의 파라미터 조합을 전수 탐색해 최고 수익 조합을 찾습니다.
                    </p>
                  </div>
                  <button
                    onClick={optimize}
                    disabled={gridBusy}
                    className="btn-ghost flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
                  >
                    <Target size={14} className={gridBusy ? "animate-pulse" : ""} />
                    {gridBusy ? "탐색 중…" : "최적 파라미터 탐색"}
                  </button>
                </div>

                {gridResult && (
                  <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-muted">최적:</span>
                      {Object.entries(gridResult.best_params).map(([k, v]) => (
                        <span
                          key={k}
                          className="rounded-full border border-accent/40 bg-[color-mix(in_srgb,var(--accent)_10%,transparent)] px-2.5 py-0.5 font-mono text-xs text-accent"
                        >
                          {k}={v}
                        </span>
                      ))}
                    </div>
                    <span className="text-xs">
                      수익률{" "}
                      <span
                        className={`font-semibold ${gridResult.best_return >= 0 ? "text-[#58c8a0]" : "text-[#e2607b]"}`}
                      >
                        {pct(gridResult.best_return)}
                      </span>{" "}
                      <span className="text-muted">({gridResult.results_count}개 조합)</span>
                    </span>
                    <button
                      onClick={applyGrid}
                      className="btn-accent ml-auto flex items-center gap-1.5 px-3 py-1.5 text-sm"
                    >
                      <CheckCircle size={14} /> 이 파라미터로 백테스트
                    </button>
                  </div>
                )}
              </div>
            )}
          </Card>

          {busy && <Skeleton className="h-80 w-full rounded-2xl" />}

          {result && m && (
            <>
              {/* Enhanced metrics grid */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <MetricTile
                  label="전략 수익률"
                  value={pct(m.total_return)}
                  tone={m.total_return >= 0 ? "up" : "down"}
                />
                <MetricTile
                  label="매수후보유"
                  value={pct(m.buy_hold_return)}
                  tone={m.buy_hold_return >= 0 ? "up" : "down"}
                />
                <MetricTile
                  label="연간 수익률"
                  value={pct(m.annual_return)}
                  tone={m.annual_return >= 0 ? "up" : "down"}
                />
                <MetricTile label="최대 낙폭" value={pct(m.max_drawdown)} tone="down" />
                <MetricTile label="승률" value={pct(m.win_rate)} sub={`${result.trades.length}회 거래`} />
                <MetricTile
                  label="샤프 비율"
                  value={m.sharpe_ratio.toFixed(2)}
                  tone={m.sharpe_ratio >= 1 ? "up" : m.sharpe_ratio >= 0 ? "neutral" : "down"}
                  sub={`수익인수 ${m.profit_factor >= 99 ? "∞" : m.profit_factor.toFixed(2)}`}
                />
              </div>

              {/* 리스크 오버레이 요약 — 손절/추격/수수료 적용값 + 시장노출 + 청산사유 분포 */}
              {result.risk_used && (
                <p className="-mt-1 text-xs text-muted">
                  <span className="text-fg">리스크 오버레이</span> {riskSummary(result.risk_used)}
                  {typeof m.exposure_pct === "number" && ` · 시장노출 ${pct(m.exposure_pct)}`}
                  {m.exit_reasons && Object.keys(m.exit_reasons).length > 0 &&
                    ` · 청산 ${Object.entries(m.exit_reasons)
                      .map(([k, v]) => `${EXIT_LABEL[k] ?? k} ${v}`)
                      .join(" / ")}`}
                </p>
              )}

              {/* Chart */}
              <Card>
                <div className="flex items-center justify-between">
                  <SectionLabel>
                    <span className="inline-flex items-center gap-1.5">
                      <ChartLineUp size={14} /> 누적 수익률 — 전략 vs 매수후보유
                    </span>
                  </SectionLabel>
                  <button
                    onClick={consult}
                    className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-sm"
                  >
                    <ChatCircleText size={14} /> 이 결과로 상담받기
                  </button>
                </div>
                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={result.chart_data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                      <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted)" }} minTickGap={48} />
                      <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} width={48} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Line
                        type="monotone"
                        dataKey="strategy_cumulative"
                        name="전략"
                        stroke="#4f8df9"
                        dot={false}
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="cumulative_returns"
                        name="매수후보유"
                        stroke="#9aa3b5"
                        dot={false}
                        strokeWidth={1.5}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </Card>

              {/* Trade list */}
              {result.trades.length > 0 && (
                <Card>
                  <button
                    onClick={() => setTradesOpen((o) => !o)}
                    className="flex w-full items-center justify-between text-left"
                  >
                    <SectionLabel>거래 내역 ({result.trades.length}회)</SectionLabel>
                    {tradesOpen ? <CaretUp size={14} /> : <CaretDown size={14} />}
                  </button>
                  {tradesOpen && (
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-line text-muted">
                            <th className="py-2 pr-4 text-left font-medium">#</th>
                            <th className="py-2 pr-4 text-left font-medium">진입일</th>
                            <th className="py-2 pr-4 text-left font-medium">청산일</th>
                            <th className="py-2 pr-4 text-right font-medium">진입가</th>
                            <th className="py-2 pr-4 text-right font-medium">청산가</th>
                            <th className="py-2 pr-4 text-right font-medium">수익률</th>
                            <th className="py-2 text-right font-medium">청산사유</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.trades.map((t, i) => (
                            <tr key={i} className="border-b border-line/50">
                              <td className="py-1.5 pr-4 text-muted">{i + 1}</td>
                              <td className="py-1.5 pr-4">{t.entry_date}</td>
                              <td className="py-1.5 pr-4">{t.exit_date}</td>
                              <td className="py-1.5 pr-4 text-right font-mono">{price(t.entry_price)}</td>
                              <td className="py-1.5 pr-4 text-right font-mono">{price(t.exit_price)}</td>
                              <td
                                className={`py-1.5 pr-4 text-right font-mono font-medium ${t.pnl_pct >= 0 ? "text-[#58c8a0]" : "text-[#e2607b]"}`}
                              >
                                {t.pnl_pct >= 0 ? "+" : ""}
                                {pct(t.pnl_pct)}
                              </td>
                              <td className={`py-1.5 text-right ${EXIT_TONE[t.exit_reason ?? "signal"] ?? "text-muted"}`}>
                                {EXIT_LABEL[t.exit_reason ?? "signal"] ?? t.exit_reason}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Card>
              )}

              {/* AI Report */}
              <Card>
                <div className="flex items-center justify-between">
                  <SectionLabel>
                    <span className="inline-flex items-center gap-1.5">
                      <Sparkle size={14} /> AI 투자 리포트
                    </span>
                  </SectionLabel>
                  <button
                    onClick={() => analyze(m)}
                    disabled={reportBusy}
                    className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-sm disabled:opacity-50"
                  >
                    <Sparkle size={14} />
                    {reportBusy ? "생성 중…" : report ? "다시 생성" : "리포트 생성"}
                  </button>
                </div>
                {reportBusy && <Skeleton className="mt-3 h-40 w-full rounded-xl" />}
                {report && (
                  <article className="prose-invert mt-3 whitespace-pre-wrap text-sm leading-relaxed text-fg/90">
                    {report}
                  </article>
                )}
                {!report && !reportBusy && (
                  <p className="mt-3 text-sm text-muted">
                    공포탐욕지수·VIX·기업 프로필을 반영한 한국어 투자 리포트를 NIM LLM이 작성합니다.
                  </p>
                )}
              </Card>
            </>
          )}
        </div>
      )}
    </main>
  );
}
