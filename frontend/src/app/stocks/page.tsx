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
  getStrategies,
  getQuickAnalysis,
  getPriceHistory,
  runBacktest,
  runGridSearch,
  runStockAnalysis,
  type StockStrategy,
  type BacktestResult,
  type BacktestMetrics,
  type BacktestPeriod,
  type GridSearchResult,
  type QuickAnalysis,
  type PriceHistory,
  type OutlookHorizon,
} from "@/lib/api";
import { clientId } from "@/lib/my-profile";
import { seedChat } from "@/lib/chat-seed";
import MiniSparkline from "@/components/bits/MiniSparkline";
import SpecularMetricCard from "@/components/bits/SpecularMetricCard";
import {
  Card,
  PageTitle,
  SectionLabel,
  Spinner,
  LoadingBlock,
  AnimatedNumber,
} from "@/components/ui";
import SegmentedTabs from "@/components/SegmentedTabs";
import GuideTour, { type TourStep } from "@/components/GuideTour";
import { Compass } from "@phosphor-icons/react";
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
  stop_loss: "text-negative",
  trailing_stop: "text-warning",
  take_profit: "text-positive",
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
      <label className="flex w-24 shrink-0 items-center gap-2 text-xs cursor-pointer">
        {togglable && (
          <input
            type="checkbox"
            checked={on}
            onChange={(e) => onToggle?.(e.target.checked)}
            className="h-3.5 w-3.5 accent-[var(--accent)] cursor-pointer"
          />
        )}
        <span className={on ? "text-fg font-medium" : "text-muted line-through"}>{label}</span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={!on}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 flex-1 cursor-pointer accent-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-30 rounded-lg"
      />
      <span className={`w-16 text-center font-mono-spec text-xs font-bold px-2 py-0.5 rounded border transition ${
        on ? "bg-accent/15 border-accent/40 text-accent" : "bg-surface/50 border-line/40 text-muted"
      }`}>
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
    tone === "up" ? "text-positive" : tone === "down" ? "text-negative" : "text-fg";
  const toneBg =
    tone === "up" ? "bg-positive" : tone === "down" ? "bg-negative" : "bg-accent";

  // 호출부는 "12.34%", "-1,203원" 같은 완성된 문자열을 넘긴다.
  // 여기서 앞쪽 수치만 떼어 카운트업하고 단위는 그대로 붙인다 →
  // 호출부를 하나도 건드리지 않고 모든 타일이 이득을 본다.
  // "∞", "-" 처럼 수치가 아닌 값은 매칭되지 않아 원문 그대로 나간다.
  const numeric = /^(-?[\d,]+(?:\.\d+)?)(.*)$/.exec(value);

  return (
    <div className="rounded-2xl border border-line bg-[var(--ink-2)]/40 px-4 py-3 relative overflow-hidden group hover:border-accent/40 transition">
      <div className={`absolute top-0 left-0 h-1 w-full ${toneBg}`} />
      <div className="text-xs uppercase tracking-wider text-muted font-mono-spec">{label}</div>
      <div className={`mt-1 font-display text-xl font-extrabold ${color}`}>
        {numeric ? (
          <>
            <AnimatedNumber
              value={Number(numeric[1].replace(/,/g, ""))}
              decimals={numeric[1].split(".")[1]?.length ?? 0}
              duration={1.1}
            />
            {numeric[2]}
          </>
        ) : (
          value
        )}
      </div>
      {sub && <div className="mt-0.5 text-[11px] text-muted font-mono-spec">{sub}</div>}
    </div>
  );
}

// ── Quick Analysis sub-components ─────────────────────────────────────────────

function RsiGauge({ value, signal }: { value: number; signal: string }) {
  const color =
    signal === "oversold"
      ? "text-positive"
      : signal === "overbought"
        ? "text-negative"
        : "text-fg";
  const label =
    signal === "oversold" ? "과매도" : signal === "overbought" ? "과매수" : "중립";
  const barPct = Math.min(100, Math.max(0, value));
  const barColor =
    barPct < 30 ? "var(--positive)" : barPct > 70 ? "var(--negative)" : "var(--accent)";
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
    tone === "up" ? "text-positive" : tone === "down" ? "text-negative" : "text-fg";
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
    trend === "BUY" ? "text-positive" : trend === "SELL" ? "text-negative" : "text-muted";
  const bg =
    trend === "BUY"
      ? "border-positive/30 bg-positive/5"
      : trend === "SELL"
        ? "border-negative/30 bg-negative/5"
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

/** 처음 온 사람에게 주식 분석 화면의 구조와 지표 읽는 법을 순서대로 짚어준다.
 * 화면 구조가 바뀌면 target(data-tour)도 같이 고쳐야 한다. */
const TOUR: TourStep[] = [
  {
    target: "setup",
    title: "티커를 검색하고 실행하세요",
    body: "AAPL·TSLA처럼 미국 주식 티커를 검색해 선택하면, 아래 빠른 분석·백테스트가 모두 이 종목 기준으로 실행됩니다.",
  },
  {
    target: "watchlist",
    title: "자주 보는 종목은 관심종목에",
    body: "저장해 둔 관심종목을 클릭하면 입력창에 바로 불러와집니다. 종목을 매번 검색하지 않아도 됩니다.",
  },
  {
    target: "tabs",
    title: "두 가지 모드가 있습니다",
    body: "빠른 분석은 지금 이 순간의 기술적 지표 스냅샷 + AI 전망입니다. 백테스트는 과거 데이터로 전략의 수익률을 검증합니다. '지금 어떻게 되고 있나'는 빠른 분석, '이 전략이 통했을까'는 백테스트에서 봅니다.",
  },
  {
    target: "indicators",
    title: "기술적 지표는 방향과 위치로 읽습니다",
    body: "RSI 70 이상은 과매수·30 이하는 과매도, MACD와 MA 추세는 방향, 볼린저 %B는 밴드 내 위치(0~100%), 지지선·저항선은 매매 참고 가격대입니다. 한 지표만 믿지 말고 방향+위치를 함께 보세요.",
  },
  {
    target: "outlook",
    title: "AI 전망은 결정·신뢰도·보정으로 읽습니다",
    body: "매수/매도/보유 결정과 24시간~1개월 네 구간 목표가가 표시됩니다. 신뢰도 보정은 AI 자신감을 과거 적중률로 깎아내린 실측치라, 이 숫자가 낮으면 전망을 크게 참고하지 않는 게 좋습니다. '이 분석으로 상담받기'로 챗봇에 바로 물어볼 수도 있습니다.",
  },
];

export default function StocksPage() {
  const toast = useToast();
  const router = useRouter();
  // 로그인이 없으므로 관심종목은 이 브라우저의 익명 id 로 묶는다.
  const [uid, setUid] = useState<string | undefined>(undefined);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 브라우저 식별자 복원
    setUid(clientId());
  }, []);

  // Shared state
  const [ticker, setTicker] = useState("AAPL");
  const [activeTab, setActiveTab] = useState<"quick" | "backtest">("quick");
  // 가이드 재실행용. undefined 면 GuideTour 가 첫 방문 여부로 스스로 판단한다.
  const [tourOpen, setTourOpen] = useState<boolean | undefined>(undefined);

  // Quick analysis state
  const [qa, setQa] = useState<QuickAnalysis | null>(null);
  /** 가격 헤더 스파크라인용 실제 종가 시계열(최근 1개월, yfinance). */
  const [series, setSeries] = useState<number[]>([]);
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
      // 가격 헤더의 스파크라인용 실제 종가 시계열(최근 1개월). 실패해도 분석 자체는 유효하므로 조용히 무시.
      getPriceHistory(symbol, "1mo")
        .then((h: PriceHistory) => setSeries(h.points.map((p) => p.close)))
        .catch(() => setSeries([]));
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
    <main className="mx-auto max-w-[1200px] px-6 py-[72px]">
      <GuideTour
        steps={TOUR}
        storageKey="midas.tour.stocks.v1"
        open={tourOpen}
        onClose={() => setTourOpen(undefined)}
      />
      <div className="flex items-start justify-between gap-4">
        <PageTitle
          eyebrow="TRADING LAB"
          title="주식 분석"
          subtitle="기술적 지표 스냅샷과 AI 다중 시간축 전망, 전략 백테스트로 글로벌 종목을 분석하세요."
        />
        <button
          type="button"
          onClick={() => setTourOpen(true)}
          className="inline-flex shrink-0 items-center gap-2 rounded-[var(--r-pill)] border border-accent/50 bg-accent/12 px-4 py-2 text-xs font-semibold text-accent transition-colors duration-150 hover:border-accent hover:bg-accent/20"
        >
          <Compass size={15} weight="bold" />
          사용 가이드
        </button>
      </div>

      {/* ── 공통 입력 ──────────────────────────────────────────────── */}
      <Card className="mb-6" data-tour="setup">
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
            {qaBusy || busy ? <Spinner className="h-4 w-4" /> : <Play weight="fill" size={16} />}
            {qaBusy || busy ? "분석 중…" : activeTab === "quick" ? "빠른 분석" : "백테스트 실행"}
          </button>
        </div>

        {/* 페르소나 "보유 종목 퀵픽"은 제거했다 — 남의 포트폴리오였다.
            직접 담는 관심종목(아래 WatchlistCard)이 그 자리를 대신한다. */}
      </Card>

      <div data-tour="watchlist" className="mb-6">
        <WatchlistCard
          userUuid={uid}
          currentTicker={ticker}
          onPick={(t) => (activeTab === "quick" ? runQuick(t) : run(t, strategy))}
        />
      </div>

      {/* ── 탭 선택 ─────────────────────────────────────────────────────── */}
      <div data-tour="tabs">
        <SegmentedTabs
          className="mb-6"
          tabs={[
            { id: "quick", label: "빠른 분석", icon: <Lightning size={15} /> },
            { id: "backtest", label: "백테스트", icon: <ChartLineUp size={15} /> },
          ]}
          active={activeTab}
          onChange={setActiveTab}
        />
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
          {qaBusy && (
            <Card>
              <LoadingBlock label="기술적 지표와 AI 전망을 분석 중입니다…" />
            </Card>
          )}

          {qa && (
            <>
              {/* Price header */}
              <SpecularMetricCard glowColor={qa.change_pct >= 0 ? "emerald" : "rose"}>
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono-spec text-xs font-bold uppercase tracking-wider text-accent">{qa.ticker}</span>
                      {/* 실시간 표시는 과장이므로 빼고, 데이터 출처·분석 시점을 정직하게 남긴다 */}
                      <span className="rounded-full border border-line px-2 py-0.5 font-mono-spec text-[10px] text-muted">
                        yfinance · {new Date().toLocaleDateString("ko-KR")}
                      </span>
                    </div>
                    <p className="font-display text-3xl font-bold tracking-tight text-fg">{price(qa.current_price)}</p>
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-semibold ${qa.change_pct >= 0 ? "text-positive" : "text-negative"}`}>
                        {qa.change_pct >= 0 ? "▲ +" : "▼ "}
                        {pct(qa.change_pct)} 전일 대비
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {/* 최근 1개월 종가 스파크라인 (yfinance 실데이터).
                        색은 오늘 등락이 아니라 이 시계열 자체의 추세를 따른다 — 그래프가
                        그리는 대상과 색의 근거가 달라지면 읽는 사람이 혼란스럽다. */}
                    {series.length > 2 && (
                      <div className="hidden flex-col items-end sm:flex">
                        <MiniSparkline
                          data={series}
                          color={series[series.length - 1] >= series[0] ? "positive" : "negative"}
                          width={110}
                          height={36}
                        />
                        <span className="mt-0.5 font-mono-spec text-[10px] text-muted">
                          최근 1개월 종가
                        </span>
                      </div>
                    )}
                    <button
                      onClick={consultQuick}
                      className="rounded-full border border-accent/40 bg-accent/15 px-3.5 py-1.5 text-xs font-mono-spec text-accent hover:bg-accent/25 transition flex items-center gap-1.5"
                    >
                      <ChatCircleText size={14} /> 이 분석으로 상담받기
                    </button>
                  </div>
                </div>
              </SpecularMetricCard>

              {/* Technical indicators */}
              <Card data-tour="indicators">
                <SectionLabel>기술적 지표</SectionLabel>
                <p className="mb-3 text-xs leading-relaxed text-muted">
                  <span className="font-semibold text-fg/80">읽는 법</span> · RSI 70 이상 과매수 / 30
                  이하 과매도 · MACD·MA 추세는 방향 · 볼린저 %B는 밴드 내 위치(0~100%) · 지지선·저항선은
                  반등/저항을 기대해 볼 가격대. 한 지표보다 방향+위치를 함께 보세요.
                </p>
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
                <Card data-tour="outlook">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <SectionLabel>
                        <span className="inline-flex items-center gap-1.5">
                          <Sparkle size={14} /> AI 다중 시간축 전망
                        </span>
                      </SectionLabel>
                      <p className="mt-1 text-sm text-fg/80">{qa.outlook.summary}</p>
                      <p className="mt-1 text-xs leading-relaxed text-muted">
                        네 구간(24시간~1개월)의 목표가와 신뢰도입니다. 신뢰도 보정은 AI 자신감을 과거
                        적중률로 깎아내린 실측치 — 낮게 나오면 이 전망을 크게 참고하지 않는 게 좋습니다.
                      </p>
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
                            ? "text-positive"
                            : "text-negative"
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
                          <p className="mb-1.5 text-xs font-medium text-positive">핵심 근거</p>
                          <ul className="space-y-1 text-xs text-fg/80">
                            {qa.outlook.key_reasons.map((r, i) => (
                              <li key={i} className="flex gap-1.5">
                                <span className="mt-0.5 text-positive">•</span>
                                {r}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {qa.outlook.risks?.length > 0 && (
                        <div>
                          <p className="mb-1.5 text-xs font-medium text-negative">리스크 요인</p>
                          <ul className="space-y-1 text-xs text-fg/80">
                            {qa.outlook.risks.map((r, i) => (
                              <li key={i} className="flex gap-1.5">
                                <span className="mt-0.5 text-negative">•</span>
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
                          ? "text-positive"
                          : p.decision === "SELL"
                            ? "text-negative"
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
                                      ? "bg-positive/10 text-positive"
                                      : "bg-negative/10 text-negative"
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
            <p className="mb-3 text-xs leading-relaxed text-muted">
              <span className="font-semibold text-fg/80">백테스트란?</span> 선택한 전략(예: 골든크로스,
              RSI 역추세)을 과거 가격 데이터에 그대로 적용해, 실제로 얼마나 수익이 났을지 검증하는
              시뮬레이션입니다. 수익률과 함께 최대낙폭(MDD)·승률을 꼭 함께 보세요.
            </p>
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
                    {gridBusy ? <Spinner className="h-3.5 w-3.5" /> : <Target size={14} />}
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
                        className={`font-semibold ${gridResult.best_return >= 0 ? "text-positive" : "text-negative"}`}
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

          {busy && (
            <Card>
              <LoadingBlock label="백테스트를 실행 중입니다…" />
            </Card>
          )}

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
                        stroke="var(--accent)"
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
                                className={`py-1.5 pr-4 text-right font-mono font-medium ${t.pnl_pct >= 0 ? "text-positive" : "text-negative"}`}
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
                    {reportBusy ? <Spinner className="h-3.5 w-3.5" /> : <Sparkle size={14} />}
                    {reportBusy ? "생성 중…" : report ? "다시 생성" : "리포트 생성"}
                  </button>
                </div>
                {reportBusy && <LoadingBlock label="AI 투자 리포트를 작성 중입니다…" className="py-8" />}
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
