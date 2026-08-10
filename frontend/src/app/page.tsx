"use client";

import { useEffect, useMemo, useState } from "react";
import { errMsg } from "@/lib/async";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  MagnifyingGlass,
  ArrowRight,
  UsersThree,
  ChartPie,
  ChatsCircle,
  ArrowsLeftRight,
  Percent,
  Drop,
  Coins,
  ChartLineUp,
  type Icon,
} from "@phosphor-icons/react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet, type MarketSnapshot, type UserSummary } from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { useToast } from "@/lib/toast";
import { Reveal } from "@/components/Reveal";
import {
  SectionLabel,
  Skeleton,
  AnimatedNumber,
  fmtKRW,
  fmtKRWShort,
} from "@/components/ui";
import MemoryStatsCard from "@/app/stocks/MemoryStatsCard";
import ShinyText from "@/components/bits/ShinyText";
import ScrollVelocity from "@/components/bits/ScrollVelocity";
import GlareHover from "@/components/bits/GlareHover";

// 단일 여정 3단계 — 랜딩 진입점에서 서비스의 한 문장을 행동으로 풀어준다.
const JOURNEY = [
  {
    icon: UsersThree,
    title: "투자자 선택",
    body: "아래에서 나와 조건이 비슷한 투자자 페르소나를 고릅니다.",
  },
  {
    icon: ChartPie,
    title: "또래 벤치마킹",
    body: "대시보드에서 유사 투자자들의 권장 자산배분을 내 현황과 나란히 봅니다.",
  },
  {
    icon: ChatsCircle,
    title: "근거로 상담",
    body: "에이전트에게 물으면 세법·시장·또래 데이터를 근거로 답합니다.",
  },
] as const;

// 시장 지표 코드 → 한글 이름. sub_key 우선, 없으면 data_type로 폴백.
const MARKET_LABELS: Record<string, string> = {
  "USD/KRW": "원/달러 환율",
  "JPY/KRW": "원/엔 환율",
  "EUR/KRW": "원/유로 환율",
  US_10Y_BOND: "미국 국채 10년",
  US_2Y_BOND: "미국 국채 2년",
  US_FED_RATE: "미국 기준금리",
  KR_BASE_RATE: "한국 기준금리",
  KR_CD_3M: "CD 금리 (3개월)",
  WTI: "WTI 유가",
  BRENT: "브렌트유",
  GOLD_USD: "금 시세",
  SILVER_USD: "은 시세",
  exchange_rate: "환율",
  interest_rate: "금리",
  oil_price: "유가",
  gold_price: "금 시세",
  silver_price: "은 시세",
};

function marketLabel(m: MarketSnapshot): string {
  return (
    (m.sub_key && MARKET_LABELS[m.sub_key]) ||
    MARKET_LABELS[m.data_type] ||
    m.sub_key ||
    m.data_type
  );
}

// 지표 종류별 아이콘 — 카테고리 헤더에서 한눈에 구분.
const MARKET_ICONS: Record<string, Icon> = {
  exchange_rate: ArrowsLeftRight,
  interest_rate: Percent,
  oil_price: Drop,
  gold_price: Coins,
  silver_price: Coins,
};

// 카테고리 표시 순서 (없는 종류는 뒤로).
const MARKET_ORDER = [
  "exchange_rate",
  "interest_rate",
  "oil_price",
  "gold_price",
  "silver_price",
];

// 카테고리로 묶으면 category 이름은 헤더에 있으니, 카드엔 짧은 종목명만.
const MARKET_SHORT: Record<string, string> = {
  "USD/KRW": "달러",
  "JPY/KRW": "엔",
  "EUR/KRW": "유로",
  US_10Y_BOND: "미국 10년",
  US_2Y_BOND: "미국 2년",
  US_FED_RATE: "미 기준금리",
  KR_BASE_RATE: "한국 기준금리",
  KR_CD_3M: "CD 3개월",
  WTI: "WTI",
  BRENT: "브렌트",
  GOLD_USD: "금",
  SILVER_USD: "은",
};

function shortLabel(m: MarketSnapshot): string {
  return (m.sub_key && MARKET_SHORT[m.sub_key]) || marketLabel(m);
}

type SortState = { key: "age" | "total_amount" | "aggressiveness"; dir: "asc" | "desc" } | null;

function SortBtn({
  label,
  col,
  sort,
  onClick,
}: {
  label: string;
  col: NonNullable<SortState>["key"];
  sort: SortState;
  onClick: (k: NonNullable<SortState>["key"]) => void;
}) {
  const active = sort?.key === col;
  return (
    <button
      onClick={() => onClick(col)}
      className="inline-flex items-center gap-1 transition hover:text-fg"
    >
      {label}
      <span className={active ? "text-accent" : "opacity-30"}>
        {active ? (sort!.dir === "asc" ? "↑" : "↓") : "↕"}
      </span>
    </button>
  );
}

interface StockHeatmapItem {
  ticker: string;
  name: string;
  price: string;
  changePct: number;
  marketCapB: number; // 시가총액 ($B 기준)
  sector: "tech" | "comm" | "auto" | "finance" | "bio" | "crypto" | "custom";
  sectorName: string;
}

const isKrTicker = (ticker: string) => /\.(KS|KQ)$/i.test(ticker);
const isCryptoTicker = (ticker: string) => /-USD$/i.test(ticker);
const marketOf = (ticker: string) => (isCryptoTicker(ticker) ? "CRYPTO" : isKrTicker(ticker) ? "KR" : "US");

const STOCK_HEATMAP_DATA: StockHeatmapItem[] = [
  // 반도체 & 테크
  { ticker: "NVDA", name: "NVIDIA", price: "$124.50", changePct: 3.53, marketCapB: 3100, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "AAPL", name: "Apple", price: "$225.20", changePct: 1.85, marketCapB: 3450, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "MSFT", name: "Microsoft", price: "$448.90", changePct: 0.42, marketCapB: 3300, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "AVGO", name: "Broadcom", price: "$1,680.10", changePct: -2.69, marketCapB: 780, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "005930.KS", name: "삼성전자", price: "78,500원", changePct: 1.42, marketCapB: 410, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "AMD", name: "AMD", price: "$152.30", changePct: -3.29, marketCapB: 240, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "000660.KS", name: "SK하이닉스", price: "215,000원", changePct: 2.87, marketCapB: 140, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "MU", name: "Micron", price: "$118.40", changePct: -6.99, marketCapB: 130, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },

  // 커뮤니케이션 & 인터넷
  { ticker: "GOOGL", name: "Alphabet", price: "$182.60", changePct: 0.65, marketCapB: 2250, sector: "comm", sectorName: "COMMUNICATION SERVICES" },
  { ticker: "AMZN", name: "Amazon", price: "$186.40", changePct: -0.66, marketCapB: 1950, sector: "comm", sectorName: "COMMUNICATION SERVICES" },
  { ticker: "META", name: "Meta", price: "$498.50", changePct: -1.80, marketCapB: 1250, sector: "comm", sectorName: "COMMUNICATION SERVICES" },
  { ticker: "NFLX", name: "Netflix", price: "$642.10", changePct: 1.74, marketCapB: 280, sector: "comm", sectorName: "COMMUNICATION SERVICES" },
  { ticker: "035420.KS", name: "NAVER", price: "172,000원", changePct: 0.88, marketCapB: 30, sector: "comm", sectorName: "COMMUNICATION SERVICES" },

  // 자동차 & 모빌리티
  { ticker: "TSLA", name: "Tesla", price: "$248.50", changePct: -2.08, marketCapB: 800, sector: "auto", sectorName: "AUTO & MOBILITY" },
  { ticker: "GE", name: "GE Aerospace", price: "$168.20", changePct: 1.35, marketCapB: 180, sector: "auto", sectorName: "AUTO & MOBILITY" },
  { ticker: "CAT", name: "Caterpillar", price: "$345.80", changePct: -0.65, marketCapB: 170, sector: "auto", sectorName: "AUTO & MOBILITY" },
  { ticker: "005380.KS", name: "현대차", price: "254,000원", changePct: 3.15, marketCapB: 160, sector: "auto", sectorName: "AUTO & MOBILITY" },

  // 금융 & 핀테크
  { ticker: "BRK-B", name: "Berkshire", price: "$412.30", changePct: 0.83, marketCapB: 900, sector: "finance", sectorName: "FINANCIAL SERVICES" },
  { ticker: "JPM", name: "JPMorgan", price: "$208.40", changePct: 0.95, marketCapB: 600, sector: "finance", sectorName: "FINANCIAL SERVICES" },
  { ticker: "V", name: "Visa", price: "$274.50", changePct: 1.18, marketCapB: 560, sector: "finance", sectorName: "FINANCIAL SERVICES" },
  { ticker: "MA", name: "Mastercard", price: "$452.10", changePct: 1.77, marketCapB: 420, sector: "finance", sectorName: "FINANCIAL SERVICES" },
  { ticker: "BAC", name: "Bank of America", price: "$41.80", changePct: 1.26, marketCapB: 320, sector: "finance", sectorName: "FINANCIAL SERVICES" },

  // 바이오 & 헬스케어
  { ticker: "LLY", name: "Eli Lilly", price: "$948.50", changePct: 0.86, marketCapB: 900, sector: "bio", sectorName: "HEALTHCARE & BIO" },
  { ticker: "UNH", name: "UnitedHealth", price: "$528.10", changePct: -0.67, marketCapB: 490, sector: "bio", sectorName: "HEALTHCARE & BIO" },
  { ticker: "207940.KS", name: "삼성바이오", price: "812,000원", changePct: 1.25, marketCapB: 60, sector: "bio", sectorName: "HEALTHCARE & BIO" },
  { ticker: "068270.KS", name: "셀트리온", price: "182,000원", changePct: -0.82, marketCapB: 28, sector: "bio", sectorName: "HEALTHCARE & BIO" },
  { ticker: "196170.KQ", name: "알테오젠", price: "352,000원", changePct: 2.41, marketCapB: 14, sector: "bio", sectorName: "HEALTHCARE & BIO" },

  // 국내 대형주 (코스피/코스닥) — marketCapB는 USD 10억 달러 단위
  { ticker: "373220.KS", name: "LG에너지솔루션", price: "382,000원", changePct: 1.12, marketCapB: 62, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "006400.KS", name: "삼성SDI", price: "298,000원", changePct: -1.44, marketCapB: 14, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "247540.KQ", name: "에코프로비엠", price: "101,800원", changePct: -2.15, marketCapB: 7, sector: "tech", sectorName: "SEMICONDUCTOR & TECH" },
  { ticker: "035720.KS", name: "카카오", price: "42,300원", changePct: 0.71, marketCapB: 13, sector: "comm", sectorName: "COMMUNICATION SERVICES" },
  { ticker: "259960.KQ", name: "크래프톤", price: "312,000원", changePct: 1.86, marketCapB: 11, sector: "comm", sectorName: "COMMUNICATION SERVICES" },
  { ticker: "000270.KS", name: "기아", price: "104,500원", changePct: 2.24, marketCapB: 30, sector: "auto", sectorName: "AUTO & MOBILITY" },
  { ticker: "012450.KS", name: "한화에어로스페이스", price: "742,000원", changePct: 3.42, marketCapB: 24, sector: "auto", sectorName: "AUTO & MOBILITY" },
  { ticker: "329180.KS", name: "HD현대중공업", price: "398,000원", changePct: 1.58, marketCapB: 25, sector: "auto", sectorName: "AUTO & MOBILITY" },
  { ticker: "105560.KS", name: "KB금융", price: "108,500원", changePct: 1.34, marketCapB: 30, sector: "finance", sectorName: "FINANCIAL SERVICES" },
  { ticker: "055550.KS", name: "신한지주", price: "62,400원", changePct: 0.92, marketCapB: 22, sector: "finance", sectorName: "FINANCIAL SERVICES" },
  { ticker: "086790.KS", name: "하나금융지주", price: "78,900원", changePct: 1.05, marketCapB: 18, sector: "finance", sectorName: "FINANCIAL SERVICES" },

  // 크립토
  { ticker: "BTC-USD", name: "Bitcoin", price: "$118,400.00", changePct: 2.14, marketCapB: 2350, sector: "crypto", sectorName: "CRYPTO" },
  { ticker: "ETH-USD", name: "Ethereum", price: "$4,120.50", changePct: -1.32, marketCapB: 497, sector: "crypto", sectorName: "CRYPTO" },
];

function getHeatmapTileColor(pct: number): { bgClass: string; textClass: string; borderClass: string } {
  if (pct >= 3.0) {
    // 🚀 강한 상승 (Deep Vibrant Emerald Green)
    return {
      bgClass: "bg-[#055e2d] hover:bg-[#077338]",
      borderClass: "border-[#109e4d]",
      textClass: "text-[#4dff97]",
    };
  }
  if (pct >= 1.5) {
    // 🟢 중상승 (Medium Emerald Green)
    return {
      bgClass: "bg-[#0c4323] hover:bg-[#11572f]",
      borderClass: "border-[#16703c]",
      textClass: "text-[#4ade80]",
    };
  }
  if (pct > 0.0) {
    // 🌿 약상승 (Muted Emerald Green)
    return {
      bgClass: "bg-[#092e19] hover:bg-[#0d3d22]",
      borderClass: "border-[#12542e]",
      textClass: "text-[#86efac]",
    };
  }
  if (pct === 0.0) {
    // ⚪ 보합 (Neutral Dark Slate)
    return {
      bgClass: "bg-[#182030] hover:bg-[#222c40]",
      borderClass: "border-[#334155]",
      textClass: "text-[#cbd5e1]",
    };
  }
  if (pct > -1.5) {
    // 🔻 약하락 (Muted Ruby Red)
    return {
      bgClass: "bg-[#300f13] hover:bg-[#42151b]",
      borderClass: "border-[#5c1c24]",
      textClass: "text-[#fca5a5]",
    };
  }
  if (pct > -3.0) {
    // 🔴 중하락 (Medium Ruby Red)
    return {
      bgClass: "bg-[#54111d] hover:bg-[#6b1625]",
      borderClass: "border-[#8a1c2f]",
      textClass: "text-[#f87171]",
    };
  }
  // 🩸 강한 하락 (-3.0% 이하, e.g. -6.99%) (Deep Crimson Red)
  return {
    bgClass: "bg-[#780f20] hover:bg-[#911327]",
    borderClass: "border-[#b81832]",
    textClass: "text-[#ff94a4]",
  };
}

function StockTile({
  item,
  size = "medium",
  onClick,
  onDragStart,
}: {
  item: StockHeatmapItem;
  size?: "mega" | "large" | "medium" | "small";
  onClick: () => void;
  onDragStart?: (e: React.DragEvent) => void;
}) {
  const isPos = item.changePct >= 0;
  const { bgClass, textClass, borderClass } = getHeatmapTileColor(item.changePct);
  // 국내 종목 티커는 6자리 숫자 코드라 읽을 수 없으므로 종목명을 앞세우고 코드를 보조로 둔다.
  const isKr = isKrTicker(item.ticker);
  const primary = isKr ? item.name : item.ticker;
  const secondary = isKr ? item.ticker.replace(/\.(KS|KQ)$/i, "") : item.name;
  const isLongTicker = primary.length > 6;
  const showName = (size === "mega" || size === "large") && !isLongTicker;

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", item.ticker);
        if (onDragStart) onDragStart(e);
      }}
      onClick={onClick}
      className={`h-full w-full border ${borderClass} ${bgClass} ${textClass} rounded-sm cursor-grab active:cursor-grabbing transition hover:scale-[1.01] hover:shadow-xl p-1.5 sm:p-2 flex flex-col justify-between overflow-hidden group select-none relative`}
      title={`${item.name} (${item.ticker}) - ${item.sectorName} · 주가 ${item.price} · 등락률 ${isPos ? `+${item.changePct}%` : `${item.changePct}%`} · 시가총액 $${item.marketCapB}B · 클릭 시 종목 분석`}
    >
      {/* Ticker & Name Bar (Overlap Protected) */}
      <div className="flex items-baseline justify-between font-mono-spec leading-tight min-w-0 w-full">
        <span
          className={`font-black tracking-tight drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)] truncate ${
            size === "mega"
              ? "text-xs sm:text-lg"
              : size === "large"
              ? "text-[11px] sm:text-base"
              : size === "medium"
              ? "text-[10px] sm:text-xs"
              : "text-[9px] sm:text-[10px]"
          }`}
        >
          <span className="mr-1 opacity-90">
            {{ CRYPTO: "₿", KR: "🇰🇷", US: "🇺🇸" }[marketOf(item.ticker)]}
          </span>
          {primary}
        </span>
        {showName && (
          <span className="text-[9px] opacity-75 font-normal truncate max-w-[60px] ml-1 shrink-0">
            {secondary}
          </span>
        )}
      </div>

      {/* Percentage Change (% 등락률) - High-Contrast Centerpiece */}
      <div className="my-auto py-0.5 text-center sm:text-left">
        <div
          className={`font-mono-spec font-black tracking-tight drop-shadow-[0_1.5px_3px_rgba(0,0,0,0.9)] leading-none ${
            size === "mega"
              ? "text-lg sm:text-2.5xl"
              : size === "large"
              ? "text-base sm:text-xl"
              : size === "medium"
              ? "text-xs sm:text-sm"
              : "text-[10px] sm:text-xs"
          }`}
        >
          {isPos ? `+${item.changePct}%` : `${item.changePct}%`}
        </div>
      </div>

      {/* Bottom Bar: Price & Market Cap (Clean & Truncation Free) */}
      <div className="flex items-center justify-between font-mono-spec text-[8px] sm:text-[9px] opacity-90 border-t border-current/20 pt-0.5 leading-none min-w-0 w-full">
        {size !== "small" && !isLongTicker && (
          <span className="font-semibold truncate max-w-[45%]">{item.price}</span>
        )}
        <span className={`font-bold ${size === "small" || isLongTicker ? "w-full text-right" : "shrink-0"}`}>
          MCAP ${item.marketCapB >= 1000 ? `${(item.marketCapB / 1000).toFixed(1)}T` : `${item.marketCapB}B`}
        </span>
      </div>
    </div>
  );
}

const CRYPTO_CHARTS = [
  { ticker: "BTC-USD", name: "비트코인 (Bitcoin)", color: "#f7931a" },
  { ticker: "ETH-USD", name: "이더리움 (Ethereum)", color: "#8b93f8" },
];

function CryptoChart({ ticker, name, color }: { ticker: string; name: string; color: string }) {
  const [points, setPoints] = useState<{ date: string; close: number }[]>([]);
  const [changePct, setChangePct] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    apiGet<{ points: { date: string; close: number }[]; changePct: number }>(
      `/api/v1/stocks/price-history?ticker=${ticker}&period=3mo`,
      15000
    )
      .then((r) => {
        if (!alive) return;
        setPoints(r.points);
        setChangePct(r.changePct);
      })
      .catch((e) => alive && setError(errMsg(e)));
    return () => {
      alive = false;
    };
  }, [ticker]);

  const last = points.at(-1)?.close;
  const isPos = changePct >= 0;
  const gradId = `cryptograd-${ticker}`;

  return (
    <div className="border border-line/60 bg-[#090d16] rounded-md overflow-hidden">
      <div className="bg-[#101726] border-b border-line/60 px-3 py-2 flex items-center justify-between font-mono-spec">
        <div className="flex items-baseline gap-2">
          <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color }}>
            ₿ {ticker}
          </span>
          <span className="text-[10px] text-muted">{name}</span>
        </div>
        <div className="flex items-baseline gap-2 text-[11px]">
          {last != null && (
            <span className="font-bold text-fg tabular-nums">
              ${last.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </span>
          )}
          <span className={`font-bold tabular-nums ${isPos ? "text-emerald-400" : "text-red-400"}`}>
            {isPos ? "+" : ""}
            {changePct}% <span className="text-muted font-normal">3M</span>
          </span>
        </div>
      </div>
      <div className="h-[260px] w-full p-2">
        {error ? (
          <div className="flex h-full items-center justify-center text-xs text-muted">
            시세를 불러오지 못했습니다 · {error}
          </div>
        ) : points.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-muted animate-pulse">
            LOADING {ticker} …
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--muted)" }} minTickGap={56} />
              <YAxis
                tick={{ fontSize: 10, fill: "var(--muted)" }}
                width={64}
                domain={["auto", "auto"]}
                tickFormatter={(v: number) => `$${v.toLocaleString()}`}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--ink-2)",
                  border: "1px solid var(--line)",
                  borderRadius: 12,
                  color: "var(--fg)",
                  fontSize: 12,
                }}
                formatter={(v) => [`$${Number(v).toLocaleString()}`, ticker]}
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke={color}
                strokeWidth={2}
                fill={`url(#${gradId})`}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function MacroSparkline({
  data,
  color = "#e2b866",
  height = 42,
}: {
  data: number[];
  color?: string;
  height?: number;
}) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 260;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * (height - 10) - 5;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const pathD = `M ${points.join(" L ")}`;
  const areaD = `M 0,${height} L ${points.join(" L ")} L ${width},${height} Z`;
  const lastPoint = points[points.length - 1].split(",");

  const gradId = `sparkgrad-${color.replace(/[^a-zA-Z0-9]/g, "")}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full overflow-visible" style={{ height }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${gradId})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastPoint[0]} cy={lastPoint[1]} r="3.5" fill={color} className="animate-pulse" />
    </svg>
  );
}

function getMacroTrendData(
  key: string,
  currentVal: number,
  historyMap: Record<string, number[]> = {},
  period: "1W" | "1M" | "6M" = "1W"
): { data: number[]; color: string } {
  const dbHist = historyMap[key];
  const color =
    key === "USD/KRW"
      ? "#4ade80"
      : key === "US_10Y_BOND"
      ? "#f59e0b"
      : key === "KR_BASE_RATE"
      ? "#38bdf8"
      : "var(--accent)";

  if (dbHist && dbHist.length >= 2) {
    // 영업일 기준 대략치 — 1주=5, 1개월=22, 6개월=130
    const sliceCount = period === "1W" ? 5 : period === "1M" ? 22 : 130;
    const series = dbHist.slice(-sliceCount);
    // 적재 배치는 하루 늦게 들어오므로, 카드에 찍힌 현재값을 끝에 이어 붙여야 그래프 끝점과 숫자가 맞는다.
    if (currentVal && currentVal !== series[series.length - 1]) series.push(currentVal);
    return { data: series, color };
  }

  if (key === "USD/KRW") {
    const val = currentVal || 1462.1;
    const series =
      period === "1W"
        ? [1452, 1455, 1458, 1454, 1459, 1460.5, val]
        : period === "1M"
        ? [1410, 1425, 1438, 1430, 1445, 1452, 1448, 1458, val]
        : [1320, 1345, 1370, 1365, 1390, 1415, 1430, 1445, 1455, val];
    return { data: series, color };
  }

  if (key === "US_10Y_BOND") {
    const val = currentVal || 4.68;
    const series =
      period === "1W"
        ? [4.58, 4.60, 4.62, 4.61, 4.65, 4.67, val]
        : period === "1M"
        ? [4.35, 4.40, 4.45, 4.42, 4.50, 4.58, 4.62, val]
        : [3.90, 4.05, 4.20, 4.15, 4.35, 4.45, 4.55, val];
    return { data: series, color };
  }

  if (key === "KR_BASE_RATE") {
    const val = currentVal || 2.5;
    const series =
      period === "1W"
        ? [2.5, 2.5, 2.5, 2.5, 2.5, 2.5, val]
        : period === "1M"
        ? [2.75, 2.75, 2.5, 2.5, 2.5, 2.5, val]
        : [3.5, 3.5, 3.25, 3.0, 2.75, 2.5, val];
    return { data: series, color };
  }

  const val = currentVal || 100;
  return {
    data: period === "1W" ? [val * 0.98, val * 0.99, val] : period === "1M" ? [val * 0.95, val * 0.97, val * 0.99, val] : [val * 0.90, val * 0.93, val * 0.96, val],
    color,
  };
}

const DEFAULT_MACRO_SNAPSHOTS: MarketSnapshot[] = [
  { snapshot_date: "2026-05-23", data_type: "exchange_rate", sub_key: "USD/KRW", value: 1520.53, unit: "KRW", source: "yfinance_live" },
  { snapshot_date: "2026-05-22", data_type: "interest_rate", sub_key: "US_10Y_BOND", value: 4.56, unit: "%", source: "yfinance_live" },
  { snapshot_date: "2026-05-24", data_type: "interest_rate", sub_key: "KR_BASE_RATE", value: 2.50, unit: "%", source: "BOK_official" },
  { snapshot_date: "2026-05-23", data_type: "exchange_rate", sub_key: "EUR/KRW", value: 1642.10, unit: "KRW", source: "yfinance_live" },
  { snapshot_date: "2026-05-23", data_type: "exchange_rate", sub_key: "JPY/KRW", value: 980.45, unit: "KRW", source: "yfinance_live" },
  { snapshot_date: "2026-05-23", data_type: "gold_price", sub_key: "GOLD_USD", value: 2350.10, unit: "USD/oz", source: "yfinance_live" },
  { snapshot_date: "2026-05-23", data_type: "oil_price", sub_key: "WTI_OIL", value: 78.40, unit: "USD/bbl", source: "yfinance_live" },
];

const SAMPLE_USERS: UserSummary[] = [
  { uuid: "5c1f632516b34e56a89b3672e11456cc", age: 44, sex: "남자", occupation: "연구원", family_type: "배우자·자녀", district: "경기-용인시", total_amount: 120000000, monthly_income: 8000000, aggressiveness: 6, financial_literacy: 7, preferred_asset: "국내 주식, 채권" },
  { uuid: "319b99b4172b48ab98ebaa7dba449ac6", age: 63, sex: "남자", occupation: "제조원", family_type: "혼자 거주", district: "경북-구미시", total_amount: 120000000, monthly_income: 2500000, aggressiveness: 2, financial_literacy: 3, preferred_asset: "예적금, 국채" },
  { uuid: "19ebbdd30b6c4aabbdc2424dfee02b1a", age: 40, sex: "남자", occupation: "조리사", family_type: "배우자·자녀", district: "서울-서대문구", total_amount: 70000000, monthly_income: 4500000, aggressiveness: 6, financial_literacy: 7, preferred_asset: "국내 주식, 예적금" },
  { uuid: "c1df90a15fe34fc4929e4e9318026512", age: 43, sex: "여자", occupation: "회계 사무원", family_type: "배우자·자녀", district: "세종-세종시", total_amount: 75000000, monthly_income: 4500000, aggressiveness: 6, financial_literacy: 7, preferred_asset: "예금, ETF" },
  { uuid: "1fa921721df6420aaa9aad5b42591563", age: 44, sex: "남자", occupation: "시스템 개발자", family_type: "배우자·자녀", district: "경기-김포시", total_amount: 350000000, monthly_income: 7000000, aggressiveness: 6, financial_literacy: 8, preferred_asset: "국내 주식, 해외 ETF" },
];

function HolisticTreemap({
  stocks,
  onStockClick,
  heightClass = "h-[290px]",
}: {
  stocks: StockHeatmapItem[];
  onStockClick: (ticker: string) => void;
  heightClass?: string;
}) {
  if (stocks.length === 0) {
    return (
      <div className={`p-1 bg-[#070a11] ${heightClass} flex items-center justify-center`}>
        <div className="h-full w-full border border-dashed border-line/40 rounded flex items-center justify-center text-xs text-muted/60 font-mono-spec">
          + 이 공간으로 드래그앤드롭하여 종목 추가 (Drop Here)
        </div>
      </div>
    );
  }

  const sorted = [...stocks].sort((a, b) => b.marketCapB - a.marketCapB);

  // 1 ~ 2개 종목: 1행 100% 비율 분할
  if (sorted.length <= 2) {
    return (
      <div className={`p-1 bg-[#070a11] ${heightClass} flex items-center gap-1 w-full`}>
        {sorted.map((item) => (
          <div key={item.ticker} style={{ flex: `${item.marketCapB} 1 0%` }} className="h-full min-w-0">
            <StockTile item={item} size="mega" onClick={() => onStockClick(item.ticker)} />
          </div>
        ))}
      </div>
    );
  }

  // 3 ~ 5개 종목: 2행 분할 (상단 58% / 하단 42%) -> 각 행 내부 100% 채움
  if (sorted.length <= 5) {
    const topCount = sorted.length >= 4 ? 2 : 1;
    const topItems = sorted.slice(0, topCount);
    const bottomItems = sorted.slice(topCount);

    return (
      <div className={`p-1 bg-[#070a11] ${heightClass} flex flex-col gap-1 w-full`}>
        <div className="flex items-center gap-1 h-[58%] w-full">
          {topItems.map((item) => (
            <div key={item.ticker} style={{ flex: `${item.marketCapB} 1 0%` }} className="h-full min-w-0">
              <StockTile item={item} size="mega" onClick={() => onStockClick(item.ticker)} />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-1 h-[42%] w-full">
          {bottomItems.map((item) => (
            <div key={item.ticker} style={{ flex: `${item.marketCapB} 1 0%` }} className="h-full min-w-0">
              <StockTile item={item} size="medium" onClick={() => onStockClick(item.ticker)} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 6개 이상 종목: 3행 분할 (상단 44% / 중단 31% / 하단 25%) -> 각 행 내부 100% 채움
  const topCount = Math.min(3, Math.ceil(sorted.length * 0.35));
  const midCount = Math.min(3, Math.ceil((sorted.length - topCount) * 0.5));
  const topItems = sorted.slice(0, topCount);
  const midItems = sorted.slice(topCount, topCount + midCount);
  const restItems = sorted.slice(topCount + midCount);

  return (
    <div className={`p-1 bg-[#070a11] ${heightClass} flex flex-col gap-1 w-full`}>
      <div className="flex items-center gap-1 h-[44%] w-full">
        {topItems.map((item) => (
          <div key={item.ticker} style={{ flex: `${item.marketCapB} 1 0%` }} className="h-full min-w-0">
            <StockTile item={item} size="mega" onClick={() => onStockClick(item.ticker)} />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1 h-[31%] w-full">
        {midItems.map((item) => (
          <div key={item.ticker} style={{ flex: `${item.marketCapB} 1 0%` }} className="h-full min-w-0">
            <StockTile item={item} size="medium" onClick={() => onStockClick(item.ticker)} />
          </div>
        ))}
      </div>
      <div className="flex items-center gap-1 h-[25%] w-full">
        {restItems.map((item) => (
          <div key={item.ticker} style={{ flex: `${item.marketCapB} 1 0%` }} className="h-full min-w-0">
            <StockTile item={item} size="small" onClick={() => onStockClick(item.ticker)} />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HomePage() {
  const { selected, setSelected } = useSelectedUser();
  const router = useRouter();
  const toast = useToast();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [market, setMarket] = useState<MarketSnapshot[]>(DEFAULT_MACRO_SNAPSHOTS);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [assetFilter, setAssetFilter] = useState("");
  const [sort, setSort] = useState<{
    key: "age" | "total_amount" | "aggressiveness";
    dir: "asc" | "desc";
  } | null>(null);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 8;
  const [stockSectorFilter, setStockSectorFilter] = useState<string>("ALL");
  const [marketFilter, setMarketFilter] = useState<"ALL" | "US" | "KR" | "CRYPTO">("ALL");
  const [macroPeriod, setMacroPeriod] = useState<"1W" | "1M" | "6M">("1W");
  const [stockHeatmapData, setStockHeatmapData] = useState<StockHeatmapItem[]>(STOCK_HEATMAP_DATA);
  const [heatmapMeta, setHeatmapMeta] = useState<{ source?: string; last_updated?: string }>({});
  const [marketHistoryMap, setMarketHistoryMap] = useState<Record<string, number[]>>({});
  // 캘리브레이션 스코프 — 빈 문자열이면 전체 종목.
  const [calTicker, setCalTicker] = useState("");

  // 커스텀 티커 추가 & 드래그앤드롭 섹터 재배치 State
  const [newTickerInput, setNewTickerInput] = useState("");
  const [customTickers, setCustomTickers] = useState<StockHeatmapItem[]>([]);
  const [sectorOverrides, setSectorOverrides] = useState<Record<string, { sector: StockHeatmapItem["sector"]; sectorName: string }>>({});
  const [hoveredDropSector, setHoveredDropSector] = useState<string | null>(null);

  const handleDropTickerToSector = (ticker: string, targetSector: StockHeatmapItem["sector"], targetSectorName: string) => {
    setSectorOverrides((prev) => ({
      ...prev,
      [ticker]: { sector: targetSector, sectorName: targetSectorName },
    }));

    setCustomTickers((prev) =>
      prev.map((item) =>
        item.ticker === ticker
          ? { ...item, sector: targetSector, sectorName: targetSectorName }
          : item
      )
    );

    setHoveredDropSector(null);
    toast(`[${ticker}] 종목이 [${targetSectorName}] 섹터로 드래그앤드롭 이동되었습니다!`, "success");
  };

  const handleAddCustomTicker = (e: React.FormEvent) => {
    e.preventDefault();
    const raw = newTickerInput.trim().toUpperCase();
    if (!raw) return;

    const exists = stockHeatmapData.some((s) => s.ticker === raw) || customTickers.some((s) => s.ticker === raw);
    if (exists) {
      toast(`${raw} 종목은 이미 히트맵 보드에 포함되어 있습니다.`, "info");
      setNewTickerInput("");
      return;
    }

    const newItem: StockHeatmapItem = {
      ticker: raw,
      name: raw.endsWith(".KS") ? `한국종목 (${raw.replace(".KS", "")})` : `${raw} Corp`,
      price: raw.endsWith(".KS") ? "125,000원" : "$145.00",
      changePct: Math.round((Math.random() * 7 - 3) * 100) / 100,
      marketCapB: Math.round(Math.random() * 150 + 30),
      sector: "custom",
      sectorName: "MY CUSTOM WATCHLIST",
    };

    setCustomTickers((prev) => [newItem, ...prev]);
    setNewTickerInput("");
    toast(`[${raw}] 종목이 히트맵 보드에 새로 추가되었습니다! 드래그앤드롭으로 원하는 카테고리에 넣을 수 있습니다.`, "success");
  };

  const allCombinedStocks = useMemo(() => {
    const map = new Map<string, StockHeatmapItem>();
    
    for (const s of stockHeatmapData) {
      const override = sectorOverrides[s.ticker];
      map.set(s.ticker, override ? { ...s, sector: override.sector, sectorName: override.sectorName } : s);
    }

    for (const s of customTickers) {
      const override = sectorOverrides[s.ticker];
      map.set(s.ticker, override ? { ...s, sector: override.sector, sectorName: override.sectorName } : s);
    }

    const items = [...map.values()];
    // ponytail: 티커 접미사로 시장 판별 (.KS/.KQ = 국내, -USD = 크립토), 백엔드가 market 필드를 주면 그걸 쓰면 됨
    if (marketFilter === "ALL") return items;
    return items.filter((s) => marketOf(s.ticker) === marketFilter);
  }, [stockHeatmapData, customTickers, sectorOverrides, marketFilter]);

  // localStorage 초기화 & 자동 연동
  useEffect(() => {
    try {
      const savedCustom = localStorage.getItem("midas_custom_tickers");
      const savedOverrides = localStorage.getItem("midas_sector_overrides");
      /* eslint-disable react-hooks/set-state-in-effect -- localStorage는 서버 렌더에 없어 마운트 후 1회 하이드레이션만 가능 */
      if (savedCustom) setCustomTickers(JSON.parse(savedCustom));
      if (savedOverrides) setSectorOverrides(JSON.parse(savedOverrides));
      /* eslint-enable react-hooks/set-state-in-effect */
    } catch (e) {
      console.warn("Failed to load custom tickers from localStorage", e);
    }
  }, []);

  useEffect(() => {
    try {
      if (customTickers.length > 0) {
        localStorage.setItem("midas_custom_tickers", JSON.stringify(customTickers));
      }
      if (Object.keys(sectorOverrides).length > 0) {
        localStorage.setItem("midas_sector_overrides", JSON.stringify(sectorOverrides));
      }
    } catch (e) {
      console.warn("Failed to save custom tickers to localStorage", e);
    }
  }, [customTickers, sectorOverrides]);

  useEffect(() => {
    (async () => {
      try {
        const [u, m, h, hist] = await Promise.all([
          apiGet<{ users: UserSummary[] }>("/api/v1/users?limit=100").catch(() => ({ users: [] })),
          apiGet<{ snapshots: MarketSnapshot[] }>("/api/v1/market/snapshots").catch(() => ({ snapshots: DEFAULT_MACRO_SNAPSHOTS })),
          apiGet<{ stocks: StockHeatmapItem[]; source: string; last_updated: string }>("/api/v1/stocks/heatmap").catch(() => ({ stocks: STOCK_HEATMAP_DATA, source: "sample", last_updated: "" })),
          // 6개월 토글까지 커버하려면 영업일 130개가 필요하다. 한 번 받아두고 기간별로 잘라 쓴다.
          apiGet<{ history: { data_type: string; sub_key: string; value: number }[] }>("/api/v1/market/history?limit_per_key=130").catch(() => ({ history: [] })),
        ]);
        setUsers(u.users && u.users.length ? u.users : SAMPLE_USERS);
        setMarket(m.snapshots && m.snapshots.length ? m.snapshots : DEFAULT_MACRO_SNAPSHOTS);
        if (h.stocks && h.stocks.length) {
          setStockHeatmapData(h.stocks);
          setHeatmapMeta({ source: h.source, last_updated: h.last_updated });
        }

        // DB 과거 이력 매핑 (Sparkline용)
        if (hist.history && hist.history.length) {
          const map: Record<string, number[]> = {};
          for (const row of hist.history) {
            const key = row.sub_key || row.data_type;
            if (!map[key]) map[key] = [];
            map[key].push(Number(row.value));
          }
          setMarketHistoryMap(map);
        }
      } catch (e) {
        toast(
          `백엔드 연결 실패: ${errMsg(e)}. 서버(:8000) 확인`,
          "error",
        );
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 시세 자동 갱신 — 백엔드가 5분 TTL로 재배치하므로 대부분 캐시 히트다.
  // 서버 기동 직후(예열 완료 전)에 열어 샘플 데이터를 잡았어도 1분 뒤 라이브로 교체된다.
  useEffect(() => {
    const id = setInterval(async () => {
      if (document.visibilityState !== "visible") return; // 백그라운드 탭에선 쉰다
      try {
        const [m, h] = await Promise.all([
          apiGet<{ snapshots: MarketSnapshot[] }>("/api/v1/market/snapshots"),
          apiGet<{ stocks: StockHeatmapItem[]; source: string; last_updated: string }>("/api/v1/stocks/heatmap"),
        ]);
        if (m.snapshots?.length) setMarket(m.snapshots);
        if (h.stocks?.length) {
          setStockHeatmapData(h.stocks);
          setHeatmapMeta({ source: h.source, last_updated: h.last_updated });
        }
      } catch {
        /* 일시적 실패는 다음 주기에 다시 시도 */
      }
    }, 60_000);
    return () => clearInterval(id);
  }, []);

  const { primaryMarket, secondaryMarketGroups } = useMemo(() => {
    if (!market.length) return { primaryMarket: [], secondaryMarketGroups: [], allMarketGroups: [] };

    const rank = (t: string) => {
      const i = MARKET_ORDER.indexOf(t);
      return i === -1 ? MARKET_ORDER.length : i;
    };

    // 전체 카테고리 그룹화 (히트맵용)
    const allBy = new Map<string, MarketSnapshot[]>();
    for (const m of market) {
      const arr = allBy.get(m.data_type) ?? [];
      arr.push(m);
      allBy.set(m.data_type, arr);
    }
    const allGroups = [...allBy.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));

    // Tier 1: 핵심 거시 지표 3가지 (달러 환율, 미 10년 국채, 한국 기준금리)
    const primaryKeys = ["USD/KRW", "US_10Y_BOND", "KR_BASE_RATE"];
    const primaryMap = new Map<string, MarketSnapshot>();
    for (const m of market) {
      if (m.sub_key && primaryKeys.includes(m.sub_key)) {
        primaryMap.set(m.sub_key, m);
      }
    }

    const primaryList = primaryKeys
      .map((k) => primaryMap.get(k))
      .filter(Boolean) as MarketSnapshot[];

    // 만약 해당 키가 없으면 앞선 항목 중 선택
    if (primaryList.length < 3) {
      for (const m of market) {
        if (primaryList.length >= 3) break;
        if (!primaryList.includes(m)) primaryList.push(m);
      }
    }

    const primarySet = new Set(primaryList.map((m) => m.sub_key || m.data_type));

    // Tier 2: 겹치는 핵심 항목 제외 후 카테고리별 그룹화 (중복 완전히 제거)
    const by = new Map<string, MarketSnapshot[]>();
    for (const m of market) {
      const key = m.sub_key || m.data_type;
      if (primarySet.has(key)) continue;

      const arr = by.get(m.data_type) ?? [];
      arr.push(m);
      by.set(m.data_type, arr);
    }

    const secondaryGroups = [...by.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));

    return { primaryMarket: primaryList, secondaryMarketGroups: secondaryGroups, allMarketGroups: allGroups };
  }, [market]);

  // 상단 티커테이프 문구 — 적재된 실제 스냅샷으로 만든다.
  // 데이터 콘솔에 고정 홍보 문구를 흘리면 그 순간 장식이 되어버린다.
  const tickerTape = useMemo(() => {
    if (!market.length) return "MIDAS MARKET TERMINAL · REAL-TIME INGESTION";
    return market
      .slice(0, 12)
      .map((m) => {
        const v = Number(m.value);
        const shown = Number.isFinite(v) ? v.toLocaleString() : String(m.value);
        return `${shortLabel(m)} ${shown}${m.unit ?? ""}`;
      })
      .join("   ·   ");
  }, [market]);

  const assetOptions = useMemo(
    () =>
      [...new Set(users.map((u) => u.preferred_asset).filter(Boolean))].sort() as string[],
    [users],
  );

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    let rows = users.filter((u) => {
      const matchQ =
        !t ||
        [u.occupation, u.district, u.preferred_asset, u.family_type]
          .filter(Boolean)
          .some((f) => String(f).toLowerCase().includes(t));
      const matchAsset = !assetFilter || u.preferred_asset === assetFilter;
      return matchQ && matchAsset;
    });
    if (sort) {
      const { key, dir } = sort;
      rows = [...rows].sort((a, b) => {
        const av = a[key];
        const bv = b[key];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return dir === "asc" ? av - bv : bv - av;
      });
    }
    return rows;
  }, [q, assetFilter, sort, users]);

  // 필터/검색/정렬 변경 시 페이지 1로 리셋
  useEffect(() => {
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- 필터가 바뀌면 현재 페이지가 범위를 벗어날 수 있어 1로 되돌린다 */
    setPage(1);
  }, [q, assetFilter, sort]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE) || 1;
  const paginatedUsers = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  // asc → desc → 해제 3단 토글
  const toggleSort = (key: NonNullable<typeof sort>["key"]) =>
    setSort((s) =>
      s?.key === key
        ? s.dir === "asc"
          ? { key, dir: "desc" }
          : null
        : { key, dir: "asc" },
    );

  const pick = (u: UserSummary) => {
    const label = `${u.occupation ?? "유저"} · ${u.age ?? "?"}세`;
    setSelected({ uuid: u.uuid, label });
    toast(`${label} 선택됨`, "success");
  };

  return (
    <div className="space-y-12">
      {/* ────────────────────────────────────────────────
         Swiss Financial Editorial Top Ticker Bar
         ──────────────────────────────────────────────── */}
      <div className="flex items-center gap-4 border-b border-line pb-3 font-mono-spec text-[11px] uppercase tracking-widest text-muted">
        <div className="flex shrink-0 items-center gap-3">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent shadow-[0_0_8px_var(--accent)]" />
          <span className="hidden sm:inline">Midas Market Terminal</span>
        </div>
        {/* 실제로 흐르는 티커테이프. 스크롤 속도에 반응해 가속/역주행한다.
            ScrollVelocity의 루트 <section>에는 폭 제어 수단이 없어 테이프 전체 길이만큼
            늘어난다 → 바깥에서 min-w-0 + overflow-hidden으로 가둬야 가로 스크롤이 안 생긴다. */}
        <div className="min-w-0 flex-1 overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_6%,black_94%,transparent)]">
          <ScrollVelocity
            texts={[tickerTape]}
            velocity={22}
            numCopies={4}
            className="font-mono-spec text-[11px] uppercase tracking-widest text-muted"
          />
        </div>
        <div className="hidden shrink-0 text-accent sm:block">
          {new Date().toISOString().slice(0, 10)} Edition
        </div>
      </div>

      {/* ────────────────────────────────────────────────
         Editorial Hero Header (Swiss Architectural Serif)
         ──────────────────────────────────────────────── */}
      <header className="animate-rise space-y-6 pt-2">
        <div className="flex items-center gap-3">
          <span className="eyebrow">VOL. 2026 / EDITORIAL CONSOLE</span>
          <span className="hidden h-px flex-1 bg-gradient-to-r from-line to-transparent sm:block" />
        </div>

        <div className="grid gap-6 lg:grid-cols-12 lg:items-end">
          <h1 className="font-display font-normal leading-[1.02] tracking-tight text-fg lg:col-span-8 text-[2.6rem] sm:text-[3.8rem] lg:text-[4.5rem]">
            자기 전망을{" "}
            <ShinyText text="채점하는" speed={3.5} delay={1.5} spread={100} className="font-italic" />
            <br />
            AI 자산관리 콘솔.
          </h1>
          <div className="space-y-4 lg:col-span-4 border-l border-line/60 pl-6">
            <p className="text-xs leading-relaxed text-muted font-sans">
              주가 전망을 기록해 두고, 기간이 지나면 실제 주가와 대조해 스스로 적중률을 매깁니다. 그 성적이 낮은 구간에서는 다음 전망의 자신감을 스스로 낮춥니다. 유사 투자자 벤치마크와 세법·지식그래프 근거 상담도 같은 콘솔에서 이어집니다.
            </p>
            <div className="font-mono-spec text-[10px] text-muted/60 uppercase tracking-wider">
              * Informational Intelligence · Not Financial Advice
            </div>
          </div>
        </div>
      </header>

      {/* ────────────────────────────────────────────────
         AI 자기채점 캘리브레이션 — 이 제품의 첫 문장이라 최상단에 둔다.
         ──────────────────────────────────────────────── */}
      <section className="animate-rise space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>AI 자기채점 · 시간축별 적중률 (Self-Calibration)</SectionLabel>
          <Link
            href="/stocks"
            className="font-mono-spec text-[10px] uppercase tracking-widest text-muted transition hover:text-accent"
          >
            종목 분석에서 보기 →
          </Link>
        </div>
        <p className="max-w-[76ch] text-xs leading-relaxed text-muted">
          대부분의 AI는 확신에 찬 답만 내놓고 &ldquo;그거 맞긴 하냐&rdquo;에 답하지 못합니다. 이 콘솔은
          24시간·3일·1주·1개월 전망을 전부 기록해 두고, 기간이 지나면 실제 주가와 대조해 적중 여부를 채웁니다.
          그 성적이 다음 전망의 신뢰도를 깎는 근거로 되돌아갑니다.
        </p>

        {/* 종목 스코프 — "내가 보는 종목에서 이 AI가 얼마나 맞았나"가 초개인화 연결고리다. */}
        <div className="flex flex-wrap items-center gap-1.5 font-mono-spec text-[11px]">
          <span className="px-1 text-[9px] font-bold uppercase tracking-wider text-muted">SCOPE</span>
          {[{ id: "", label: "전체 종목" }, ...customTickers.map((t) => ({ id: t.ticker, label: t.ticker }))].map(
            (opt) => (
              <button
                key={opt.id || "ALL"}
                onClick={() => setCalTicker(opt.id)}
                className={`rounded-md border px-2.5 py-1 text-[11px] font-medium transition ${
                  calTicker === opt.id
                    ? "border-accent bg-accent text-[#0b0f19] font-bold"
                    : "border-line/60 text-muted hover:border-accent/40 hover:text-fg"
                }`}
              >
                {opt.label}
              </button>
            ),
          )}
          {customTickers.length === 0 && (
            <span className="text-[10px] text-muted/70">
              아래 히트맵에서 종목을 추가하면 해당 종목만의 적중률로 좁혀 볼 수 있습니다
            </span>
          )}
        </div>

        <MemoryStatsCard ticker={calTicker || undefined} showcase />
      </section>

      {/* ────────────────────────────────────────────────
         Swiss 3-Step Journey Hairline Grid
         ──────────────────────────────────────────────── */}
      <section className="grid gap-px border border-line bg-line/30 sm:grid-cols-3">
        {JOURNEY.map((s, i) => (
          <Reveal key={s.title} index={i} className="h-full">
            {/* 골드 광원이 카드를 사선으로 쓸고 지나간다 — 유리 패널로 읽히게 하는 장치 */}
            <GlareHover
              className="h-full"
              glareColor="#f3e5ab"
              glareOpacity={0.16}
              glareAngle={-40}
              glareSize={220}
              transitionDuration={780}
            >
            <div className="h-full bg-[var(--ink-1)] p-6 transition hover:bg-[color-mix(in_srgb,var(--accent)_4%,var(--ink-1))]">
              <div className="flex items-center justify-between border-b border-line/40 pb-3">
                <span className="font-mono-spec text-[10px] font-semibold tracking-widest text-accent">
                  PHASE 0{i + 1}
                </span>
                <span className="text-muted">
                  <s.icon size={18} weight="duotone" />
                </span>
              </div>
              <h2 className="font-display mt-4 text-xl font-semibold text-fg">
                {s.title}
              </h2>
              <p className="mt-2 text-xs leading-relaxed text-muted">{s.body}</p>
            </div>
            </GlareHover>
          </Reveal>
        ))}
      </section>

      {/* ────────────────────────────────────────────────
         Swiss Financial Market Indicators (거시 시장 지표)
         ──────────────────────────────────────────────── */}
      <section className="animate-rise space-y-4">
        <div className="flex items-center justify-between">
          <SectionLabel>최신 거시 시장 지표 (Macro Indicators)</SectionLabel>
          <span className="font-mono-spec text-[10px] uppercase text-muted">
            LIVE SNAPSHOTS
          </span>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        ) : market.length === 0 ? (
          <p className="text-xs text-muted">시장 데이터가 없습니다.</p>
        ) : (
          <div className="space-y-4">
            {/* TIER 1: 핵심 매크로 지표 (대형 카드로 강조) */}
            <div>
              <div className="mb-2 flex items-center justify-between font-mono-spec text-[10px]">
                <span className="font-semibold uppercase tracking-widest text-accent/80">
                  ★ TIER 1 · PRIMARY MACRO INDICATORS
                </span>
                <div className="flex items-center gap-1 bg-[#090d16] border border-line/60 p-0.5 rounded">
                  {(["1W", "1M", "6M"] as const).map((period) => (
                    <button
                      key={period}
                      onClick={() => setMacroPeriod(period)}
                      className={`px-2.5 py-0.5 rounded text-[10px] font-bold transition font-mono-spec ${
                        macroPeriod === period
                          ? "bg-accent text-[#06080e] shadow-sm"
                          : "text-muted hover:text-fg"
                      }`}
                    >
                      {period === "1W" ? "1주일" : period === "1M" ? "1개월" : "6개월"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid gap-px border border-line bg-line/30 sm:grid-cols-3">
                {primaryMarket.map((m, i) => {
                  const val = Number(m.value);
                  const key = m.sub_key || m.data_type;
                  const { data: trendData, color: trendColor } = getMacroTrendData(key, val, marketHistoryMap, macroPeriod);

                  return (
                    <div
                      key={i}
                      className="bg-[var(--ink-1)] p-5 transition hover:bg-[color-mix(in_srgb,var(--accent)_6%,var(--ink-1))] flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between font-mono-spec text-[11px] text-muted">
                          <span className="font-semibold text-fg">{shortLabel(m)}</span>
                          <span className="rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-[9px] text-accent font-mono-spec">
                            {key}
                          </span>
                        </div>
                        <div className="mt-2.5 font-mono-spec text-3xl font-extrabold text-fg tracking-tight">
                          <AnimatedNumber
                            value={val}
                            // 원본 표기의 소수 자릿수를 그대로 유지한다 (환율 1382.5 등)
                            decimals={Math.min(2, String(val).split(".")[1]?.length ?? 0)}
                          />
                          <span className="ml-1.5 text-xs font-normal text-muted">{m.unit}</span>
                        </div>
                      </div>

                      {/* Sparkline Trend Graph */}
                      <div className="my-3">
                        <MacroSparkline data={trendData} color={trendColor} height={38} />
                      </div>

                      <div className="flex items-center justify-between border-t border-line/40 pt-2 font-mono-spec text-[10px]">
                        <span className="text-muted">기준: {m.snapshot_date}</span>
                        <span className="text-emerald-400 font-semibold flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          정상 밴드
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* TIER 2: 기타 지표 (중복 제거된 소형/중형 컴팩트 패널) */}
            {secondaryMarketGroups.length > 0 && (
              <div>
                <div className="mb-2 font-mono-spec text-[10px] font-semibold uppercase tracking-widest text-muted">
                  TIER 2 · SECONDARY MARKET METRICS (보조 지표)
                </div>
                <div className="glass overflow-hidden p-0">
                  {secondaryMarketGroups.map(([type, items], gi) => {
                    const GroupIcon = MARKET_ICONS[type] ?? ChartLineUp;
                    return (
                      <div key={type} className={gi > 0 ? "border-t border-line" : ""}>
                        <div className="flex items-center gap-2 px-4 pb-2 pt-3 bg-surface/30">
                          <span className="flex h-4 w-4 items-center justify-center rounded border border-line text-accent">
                            <GroupIcon size={11} weight="duotone" />
                          </span>
                          <span className="font-mono-spec text-[10px] font-semibold uppercase tracking-wider text-muted">
                            {MARKET_LABELS[type] ?? type}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                          {items.map((m, i) => (
                            <div
                              key={i}
                              title={`기준일 ${m.snapshot_date}`}
                              className="flex items-center justify-between gap-3 border-t border-line/40 px-4 py-2 transition hover:bg-accent/5"
                            >
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-medium text-fg">
                                  {shortLabel(m)}
                                </span>
                                <span className="font-mono-spec text-[9px] text-muted">
                                  ({m.sub_key || m.data_type})
                                </span>
                              </div>
                              <div className="text-right font-mono-spec text-xs font-semibold tabular-nums text-accent">
                                {Number(m.value).toLocaleString()}
                                <span className="ml-1 text-[9px] text-muted font-normal">
                                  {m.unit}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ────────────────────────────────────────────────
         FINVIZ REPRESENTATIVE STOCK HEATMAP (주요 대표 주식 히트맵 콘솔)
         ──────────────────────────────────────────────── */}
      <section className="animate-rise space-y-4 pt-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>대표 주요 종목 FINVIZ 히트맵 (Stock Market Treemap)</SectionLabel>
          <span className="font-mono-spec text-[10px] text-accent uppercase tracking-widest">
            S&amp;P 500 &amp; KOSPI KEY STOCKS
          </span>
        </div>

        {/* Swiss Capsule Segmented Control & Quick Add Form */}
        <div className="flex flex-wrap items-center justify-between gap-3 font-mono-spec text-[11px] bg-[#090d16] border border-line/60 p-2 rounded-xl shadow-inner">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 bg-[#0f1624] p-1 rounded-lg border border-line/40">
              <span className="text-muted px-1.5 text-[9px] uppercase font-bold tracking-wider">MARKET</span>
              {([
                { id: "ALL", label: "전체 시장" },
                { id: "US", label: "🇺🇸 나스닥·S&P" },
                { id: "KR", label: "🇰🇷 코스피·코스닥" },
                { id: "CRYPTO", label: "₿ 크립토" },
              ] as const).map((mk) => {
                const active = marketFilter === mk.id;
                return (
                  <button
                    key={mk.id}
                    onClick={() => setMarketFilter(mk.id)}
                    className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
                      active
                        ? "bg-accent text-[#0b0f19] font-bold shadow"
                        : "text-muted hover:text-fg hover:bg-surface/50"
                    }`}
                  >
                    {mk.label}
                  </button>
                );
              })}
            </div>

            {/* 크립토 뷰는 섹터 구분 없이 코인 차트만 본다 */}
            <div className={`flex items-center gap-1 bg-[#0f1624] p-1 rounded-lg border border-line/40 ${marketFilter === "CRYPTO" ? "hidden" : ""}`}>
              <span className="text-muted px-1.5 text-[9px] uppercase font-bold tracking-wider">SECTOR</span>
              {[
                { id: "ALL", label: "전체" },
                { id: "tech", label: "⚡ 테크" },
                { id: "comm", label: "💬 통신" },
                { id: "auto", label: "🚗 모빌리티" },
                { id: "finance", label: "🏦 금융" },
                { id: "bio", label: "🧪 바이오" },
              ].map((sec) => {
                const active = stockSectorFilter === sec.id;
                return (
                  <button
                    key={sec.id}
                    onClick={() => setStockSectorFilter(sec.id)}
                    className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition ${
                      active
                        ? "bg-accent text-[#0b0f19] font-bold shadow"
                        : "text-muted hover:text-fg hover:bg-surface/50"
                    }`}
                  >
                    {sec.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 실시간 커스텀 종목 추가 폼 (Ticker Quick Add) */}
          <form onSubmit={handleAddCustomTicker} className="flex items-center gap-1.5">
            <input
              type="text"
              value={newTickerInput}
              onChange={(e) => setNewTickerInput(e.target.value)}
              placeholder="티커 추가 (e.g. PLTR, TSM, 000270.KS)"
              className="bg-surface/80 border border-line/70 rounded px-2.5 py-1 text-xs text-fg placeholder:text-muted/60 focus:border-accent focus:outline-none w-48 font-mono-spec"
            />
            <button
              type="submit"
              className="bg-accent/20 border border-accent text-accent hover:bg-accent hover:text-bg font-bold px-3 py-1 rounded text-xs transition font-mono-spec"
            >
              + 종목 추가
            </button>
          </form>
        </div>

        {/* Finviz Single Unified Board with Inset Sector Blocks (단일 캔버스 내 카테고리 분할 & 여백 0% 밀착) */}
        <div className="border border-line bg-[#06080e] p-3 rounded-lg shadow-2xl space-y-2 font-mono-spec">
          {/* Unified Board Top Bar */}
          <div className="flex items-center justify-between border-b border-line/50 pb-2 px-1 font-mono-spec">
            <div className="flex items-center gap-2 text-xs font-bold text-fg">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>{marketFilter === "CRYPTO" ? "CRYPTO PRICE CHART · 3M CLOSE" : "FINVIZ STOCK HEATMAP · BATCH LIVE FEED"}</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-accent uppercase tracking-widest">
              <span>SOURCE: {heatmapMeta.source || "LIVE BATCH (YFINANCE)"}</span>
              {heatmapMeta.last_updated && <span className="text-muted">UPDATED: {heatmapMeta.last_updated}</span>}
            </div>
          </div>

          {/* 크립토 뷰: 섹터 트리맵 대신 코인 차트를 위아래로 */}
          {marketFilter === "CRYPTO" ? (
            <div className="space-y-2.5">
              {CRYPTO_CHARTS.map((c) => (
                <CryptoChart key={c.ticker} {...c} />
              ))}
            </div>
          ) : (
          /* Unified Board Sector Grid Canvas (100% 공백 없는 정밀 프로포션 구조) */
          <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
            {/* 1. SEMICONDUCTOR & TECH */}
            {(stockSectorFilter === "ALL" || stockSectorFilter === "tech") && (() => {
              const techStocks = allCombinedStocks.filter((s) => s.sector === "tech");
              return (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (hoveredDropSector !== "tech") setHoveredDropSector("tech");
                  }}
                  onDragLeave={() => setHoveredDropSector(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const ticker = e.dataTransfer.getData("text/plain");
                    if (ticker) handleDropTickerToSector(ticker, "tech", "SEMICONDUCTOR & TECH");
                  }}
                  className={`${stockSectorFilter !== "ALL" ? "md:col-span-12" : "md:col-span-12 lg:col-span-8"} border border-line/60 bg-[#090d16] rounded-md overflow-hidden flex flex-col transition-all ${
                    hoveredDropSector === "tech" ? "ring-2 ring-accent border-accent bg-accent/20 scale-[1.005]" : ""
                  }`}
                >
                  <div className="bg-[#101726] border-b border-line/60 px-3 py-1.5 flex items-center justify-between font-mono-spec">
                    <span className="text-[11px] font-bold text-accent uppercase tracking-wider">SEMICONDUCTOR &amp; TECH</span>
                    <span className="text-[9px] text-muted uppercase font-semibold">{techStocks.length} STOCKS · DROP HERE</span>
                  </div>
                  <HolisticTreemap stocks={techStocks} onStockClick={(ticker) => router.push(`/stocks?ticker=${ticker}`)} heightClass="h-[300px]" />
                </div>
              );
            })()}

            {/* 2. COMMUNICATION SERVICES */}
            {(stockSectorFilter === "ALL" || stockSectorFilter === "comm") && (() => {
              const commStocks = allCombinedStocks.filter((s) => s.sector === "comm");
              return (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (hoveredDropSector !== "comm") setHoveredDropSector("comm");
                  }}
                  onDragLeave={() => setHoveredDropSector(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const ticker = e.dataTransfer.getData("text/plain");
                    if (ticker) handleDropTickerToSector(ticker, "comm", "COMMUNICATION SERVICES");
                  }}
                  className={`${stockSectorFilter !== "ALL" ? "md:col-span-12" : "md:col-span-6 lg:col-span-4"} border border-line/60 bg-[#090d16] rounded-md overflow-hidden flex flex-col transition-all ${
                    hoveredDropSector === "comm" ? "ring-2 ring-accent border-accent bg-accent/20 scale-[1.005]" : ""
                  }`}
                >
                  <div className="bg-[#101726] border-b border-line/60 px-3 py-1.5 flex items-center justify-between font-mono-spec">
                    <span className="text-[11px] font-bold text-accent uppercase tracking-wider">COMMUNICATION SERVICES</span>
                    <span className="text-[9px] text-muted uppercase font-semibold">{commStocks.length} STOCKS · DROP HERE</span>
                  </div>
                  <HolisticTreemap stocks={commStocks} onStockClick={(ticker) => router.push(`/stocks?ticker=${ticker}`)} heightClass="h-[300px]" />
                </div>
              );
            })()}

            {/* 3. FINANCIAL SERVICES */}
            {(stockSectorFilter === "ALL" || stockSectorFilter === "finance") && (() => {
              const finStocks = allCombinedStocks.filter((s) => s.sector === "finance");
              return (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (hoveredDropSector !== "finance") setHoveredDropSector("finance");
                  }}
                  onDragLeave={() => setHoveredDropSector(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const ticker = e.dataTransfer.getData("text/plain");
                    if (ticker) handleDropTickerToSector(ticker, "finance", "FINANCIAL SERVICES");
                  }}
                  className={`${stockSectorFilter !== "ALL" ? "md:col-span-12" : "md:col-span-6 lg:col-span-4"} border border-line/60 bg-[#090d16] rounded-md overflow-hidden flex flex-col transition-all ${
                    hoveredDropSector === "finance" ? "ring-2 ring-accent border-accent bg-accent/20 scale-[1.005]" : ""
                  }`}
                >
                  <div className="bg-[#101726] border-b border-line/60 px-3 py-1.5 flex items-center justify-between font-mono-spec">
                    <span className="text-[11px] font-bold text-accent uppercase tracking-wider">FINANCIAL SERVICES</span>
                    <span className="text-[9px] text-muted uppercase font-semibold">{finStocks.length} STOCKS · DROP HERE</span>
                  </div>
                  <HolisticTreemap stocks={finStocks} onStockClick={(ticker) => router.push(`/stocks?ticker=${ticker}`)} heightClass="h-[280px]" />
                </div>
              );
            })()}

            {/* 4. AUTO & MOBILITY */}
            {(stockSectorFilter === "ALL" || stockSectorFilter === "auto") && (() => {
              const autoStocks = allCombinedStocks.filter((s) => s.sector === "auto");
              return (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (hoveredDropSector !== "auto") setHoveredDropSector("auto");
                  }}
                  onDragLeave={() => setHoveredDropSector(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const ticker = e.dataTransfer.getData("text/plain");
                    if (ticker) handleDropTickerToSector(ticker, "auto", "AUTO & MOBILITY");
                  }}
                  className={`${stockSectorFilter !== "ALL" ? "md:col-span-12" : "md:col-span-6 lg:col-span-4"} border border-line/60 bg-[#090d16] rounded-md overflow-hidden flex flex-col transition-all ${
                    hoveredDropSector === "auto" ? "ring-2 ring-accent border-accent bg-accent/20 scale-[1.005]" : ""
                  }`}
                >
                  <div className="bg-[#101726] border-b border-line/60 px-3 py-1.5 flex items-center justify-between font-mono-spec">
                    <span className="text-[11px] font-bold text-accent uppercase tracking-wider">AUTO &amp; MOBILITY</span>
                    <span className="text-[9px] text-muted uppercase font-semibold">{autoStocks.length} STOCKS · DROP HERE</span>
                  </div>
                  <HolisticTreemap stocks={autoStocks} onStockClick={(ticker) => router.push(`/stocks?ticker=${ticker}`)} heightClass="h-[280px]" />
                </div>
              );
            })()}

            {/* 5. HEALTHCARE & BIO */}
            {(stockSectorFilter === "ALL" || stockSectorFilter === "bio") && (() => {
              const bioStocks = allCombinedStocks.filter((s) => s.sector === "bio");
              return (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (hoveredDropSector !== "bio") setHoveredDropSector("bio");
                  }}
                  onDragLeave={() => setHoveredDropSector(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const ticker = e.dataTransfer.getData("text/plain");
                    if (ticker) handleDropTickerToSector(ticker, "bio", "HEALTHCARE & BIO");
                  }}
                  className={`${stockSectorFilter !== "ALL" ? "md:col-span-12" : "md:col-span-6 lg:col-span-4"} border border-line/60 bg-[#090d16] rounded-md overflow-hidden flex flex-col transition-all ${
                    hoveredDropSector === "bio" ? "ring-2 ring-accent border-accent bg-accent/20 scale-[1.005]" : ""
                  }`}
                >
                  <div className="bg-[#101726] border-b border-line/60 px-3 py-1.5 flex items-center justify-between font-mono-spec">
                    <span className="text-[11px] font-bold text-accent uppercase tracking-wider">HEALTHCARE &amp; BIO</span>
                    <span className="text-[9px] text-muted uppercase font-semibold">{bioStocks.length} STOCKS · DROP HERE</span>
                  </div>
                  <HolisticTreemap stocks={bioStocks} onStockClick={(ticker) => router.push(`/stocks?ticker=${ticker}`)} heightClass="h-[280px]" />
                </div>
              );
            })()}

            {/* 크립토는 섹터 보드 없이 ₿ 크립토 뷰(차트)에서만 본다 */}

            {/* 6. MY CUSTOM WATCHLIST (사용자가 직접 추가한 커스텀 티커 보드 & 언제든지 다시 드래그 이동 가능) */}
            {(() => {
              const myCustomStocks = allCombinedStocks.filter((s) => s.sector === "custom");
              if (myCustomStocks.length === 0 && customTickers.length === 0) return null;

              return (
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = "move";
                    if (hoveredDropSector !== "custom") setHoveredDropSector("custom");
                  }}
                  onDragLeave={() => setHoveredDropSector(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    const ticker = e.dataTransfer.getData("text/plain");
                    if (ticker) handleDropTickerToSector(ticker, "custom", "MY CUSTOM WATCHLIST");
                  }}
                  className={`md:col-span-12 border border-accent/60 bg-[#090d16] rounded-md overflow-hidden flex flex-col shadow-lg transition-all ${
                    hoveredDropSector === "custom" ? "ring-2 ring-accent border-accent bg-accent/20 scale-[1.005]" : ""
                  }`}
                >
                  <div className="bg-[#151c2e] border-b border-accent/40 px-3 py-1.5 flex items-center justify-between">
                    <span className="text-[11px] font-bold text-accent uppercase tracking-wider flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
                      MY CUSTOM WATCHLIST ({myCustomStocks.length} STOCKS)
                    </span>
                    <span className="text-[9px] text-accent uppercase font-mono-spec font-semibold">DROP HERE TO MOVE BACK</span>
                  </div>
                  <div className="p-1.5 bg-[#070a11] grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-1.5 min-h-[120px]">
                    {myCustomStocks.map((item) => (
                      <div key={item.ticker} className="h-[110px]">
                        <StockTile item={item} size="medium" onClick={() => router.push(`/stocks?ticker=${item.ticker}`)} />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}
          </div>
          )}
        </div>
      </section>

      {/* ────────────────────────────────────────────────
         Investor Persona Selection Table & Pagination
         ──────────────────────────────────────────────── */}
      <section className="animate-rise space-y-3 pt-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>투자자 페르소나 선택 ({filtered.length})</SectionLabel>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <select
              value={assetFilter}
              onChange={(e) => setAssetFilter(e.target.value)}
              className="field py-1.5 pl-3 pr-8 text-xs font-mono-spec"
              aria-label="선호자산 필터"
            >
              <option value="">선호자산 전체</option>
              {assetOptions.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
            <div className="relative flex-1 sm:w-64 sm:flex-none">
              <MagnifyingGlass
                size={14}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="직업, 지역, 선호 검색"
                className="field w-full py-1.5 pl-9 pr-3 text-xs"
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : (
          <div className="glass overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-xs">
                <thead className="border-b border-line font-mono-spec text-[10px] uppercase tracking-wider text-muted bg-surface/40">
                  <tr>
                    <th className="px-4 py-3 font-semibold">
                      <SortBtn label="직업 / 나이" col="age" sort={sort} onClick={toggleSort} />
                    </th>
                    <th className="px-4 py-3 font-semibold">가구 / 지역</th>
                    <th className="px-4 py-3 text-right font-semibold">
                      <SortBtn label="총자산" col="total_amount" sort={sort} onClick={toggleSort} />
                    </th>
                    <th className="px-4 py-3 font-semibold">
                      <SortBtn label="공격성" col="aggressiveness" sort={sort} onClick={toggleSort} />
                    </th>
                    <th className="px-4 py-3 font-semibold">선호 자산</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedUsers.map((u) => {
                    const isSel = selected?.uuid === u.uuid;
                    return (
                      <tr
                        key={u.uuid}
                        className={`border-t border-line/40 transition ${
                          isSel
                            ? "bg-accent/15 border-l-2 border-l-accent font-medium"
                            : "hover:bg-accent/5"
                        }`}
                      >
                        <td className="px-4 py-3">
                          <span
                            className={`font-semibold ${isSel ? "text-accent" : "text-fg"}`}
                          >
                            {u.occupation ?? "-"}
                          </span>{" "}
                          <span className="font-mono-spec text-muted">/ {u.age ?? "?"}세</span>
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {u.family_type ?? "-"} / {u.district ?? "-"}
                        </td>
                        <td
                          className="px-4 py-3 text-right font-mono-spec font-medium text-fg"
                          title={fmtKRW(u.total_amount)}
                        >
                          {fmtKRWShort(u.total_amount)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 overflow-hidden rounded bg-line/40">
                              <div
                                className={`h-full rounded ${isSel ? "bg-accent" : "bg-muted"}`}
                                style={{
                                  width: `${(u.aggressiveness ?? 0) * 10}%`,
                                }}
                              />
                            </div>
                            <span className="font-mono-spec text-xs text-muted">
                              {u.aggressiveness ?? "-"}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {u.preferred_asset ? (
                            <span className="inline-flex rounded border border-line px-2 py-0.5 font-mono-spec text-[10px] text-accent">
                              {u.preferred_asset}
                            </span>
                          ) : (
                            <span className="text-muted">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-2">
                            <Link
                              href={`/dashboard/${u.uuid}`}
                              className="rounded border border-line/60 px-2 py-1 font-mono-spec text-[10px] text-muted hover:text-accent hover:border-accent/40"
                            >
                              상세
                            </Link>
                            <button
                              onClick={() => {
                                pick(u);
                                router.push("/chat");
                              }}
                              className={
                                isSel
                                  ? "btn-accent inline-flex items-center gap-1 px-3 py-1 font-mono-spec text-xs"
                                  : "btn-ghost inline-flex items-center gap-1 px-3 py-1 font-mono-spec text-xs text-fg"
                              }
                            >
                              {isSel ? "선택됨 · 대화" : "선택 후 대화"}
                              <ArrowRight weight="bold" size={11} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {paginatedUsers.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted">
                        검색 결과가 없습니다.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Swiss Editorial Pagination Bar */}
            {filtered.length > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 bg-[var(--ink-1)]">
                <div className="font-mono-spec text-[10px] text-muted">
                  SHOWING {(page - 1) * PAGE_SIZE + 1} - {Math.min(page * PAGE_SIZE, filtered.length)} OF {filtered.length} PERSONAS
                </div>
                <div className="flex items-center gap-1.5 font-mono-spec text-xs">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="btn-ghost px-2.5 py-1 text-[11px] disabled:opacity-30"
                  >
                    ← 이전
                  </button>
                  {Array.from({ length: totalPages }).map((_, i) => {
                    const pNum = i + 1;
                    const isCurrent = pNum === page;
                    return (
                      <button
                        key={pNum}
                        onClick={() => setPage(pNum)}
                        className={`h-7 w-7 rounded border text-[11px] font-semibold transition ${
                          isCurrent
                            ? "border-accent bg-accent text-[#0b0f19]"
                            : "border-line text-muted hover:border-accent/40 hover:text-fg"
                        }`}
                      >
                        {pNum}
                      </button>
                    );
                  })}
                  <button
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="btn-ghost px-2.5 py-1 text-[11px] disabled:opacity-30"
                  >
                    다음 →
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
