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
import { apiGet, type MarketSnapshot, type UserSummary } from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { useToast } from "@/lib/toast";
import { Reveal } from "@/components/Reveal";
import {
  Card,
  SectionLabel,
  Skeleton,
  fmtKRW,
  fmtKRWShort,
} from "@/components/ui";

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

export default function HomePage() {
  const { selected, setSelected } = useSelectedUser();
  const router = useRouter();
  const toast = useToast();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [market, setMarket] = useState<MarketSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [assetFilter, setAssetFilter] = useState("");
  const [sort, setSort] = useState<{
    key: "age" | "total_amount" | "aggressiveness";
    dir: "asc" | "desc";
  } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [u, m] = await Promise.all([
          apiGet<{ users: UserSummary[] }>("/api/v1/users?limit=100"),
          apiGet<{ snapshots: MarketSnapshot[] }>("/api/v1/market/snapshots"),
        ]);
        setUsers(u.users);
        setMarket(m.snapshots);
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

  const marketGroups = useMemo(() => {
    const by = new Map<string, MarketSnapshot[]>();
    for (const m of market) {
      const arr = by.get(m.data_type) ?? [];
      arr.push(m);
      by.set(m.data_type, arr);
    }
    const rank = (t: string) => {
      const i = MARKET_ORDER.indexOf(t);
      return i === -1 ? MARKET_ORDER.length : i;
    };
    return [...by.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));
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
        if (av == null) return 1; // null은 항상 뒤로
        if (bv == null) return -1;
        return dir === "asc" ? av - bv : bv - av;
      });
    }
    return rows;
  }, [q, assetFilter, sort, users]);

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
    <div className="space-y-10">
      {/* 히어로 — 편집형 명제. 골드로 물든 한 구절 + 얇은 gilt 규칙이 시그니처. */}
      <header className="animate-rise">
        <span className="eyebrow mb-5">Midas Touch</span>
        <h1 className="font-display max-w-[22ch] break-keep text-[2.15rem] font-medium leading-[1.14] tracking-tight text-fg sm:text-[3rem]">
          나와 <span className="text-gilt">비슷한 투자자</span>는 어떻게 하고 있을까
        </h1>
        <p className="mt-5 max-w-[54ch] break-keep text-sm leading-relaxed text-muted">
          유사 투자자의 자산배분을 벤치마크로 보여주고, 세법·시장 근거로 상담하는
          자산관리 어시스턴트.{" "}
          <span className="text-muted/60">
            정보 제공 목적이며 투자자문이 아닙니다.
          </span>
        </p>
        <div
          aria-hidden
          className="mt-7 h-px w-full max-w-xs bg-gradient-to-r from-gilt/70 to-transparent"
        />
      </header>

      {/* 단일 여정 안내 — 진입점에서 "무엇을 하고 가는지" 한눈에 */}
      <section className="grid gap-3 sm:grid-cols-3">
        {JOURNEY.map((s, i) => (
          <Reveal key={s.title} index={i}>
            <Card className="lift h-full p-5">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[color-mix(in_srgb,var(--fg)_6%,transparent)] text-fg">
                  <s.icon size={20} weight="duotone" />
                </span>
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.18em] text-gilt">
                    STEP {i + 1}
                  </div>
                  <div className="mt-0.5 text-sm font-semibold text-fg">
                    {s.title}
                  </div>
                </div>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-muted">{s.body}</p>
            </Card>
          </Reveal>
        ))}
      </section>

      {/* 시장 지표 */}
      <section className="animate-rise">
        <SectionLabel>최신 시장 지표</SectionLabel>
        {loading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : market.length === 0 ? (
          <p className="text-sm text-muted">시장 데이터가 없습니다.</p>
        ) : (
          // 스탯 타일을 개별 박스로 흩뿌리지 않고, 하나의 패널에 카테고리별
          // 섹션 + 우측 정렬 tabular 값 열로 묶는다 (금융 대시보드 정석).
          <div className="glass overflow-hidden p-0">
            {marketGroups.map(([type, items], gi) => {
              const GroupIcon = MARKET_ICONS[type] ?? ChartLineUp;
              return (
                <div key={type} className={gi > 0 ? "border-t border-line" : ""}>
                  <div className="flex items-center gap-2 px-4 pb-1.5 pt-3">
                    <span className="flex h-5 w-5 items-center justify-center rounded-md border border-line text-muted">
                      <GroupIcon size={12} weight="duotone" />
                    </span>
                    <span className="text-[11px] font-semibold tracking-wide text-muted">
                      {MARKET_LABELS[type] ?? type}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
                    {items.map((m, i) => (
                      <div
                        key={i}
                        title={`기준일 ${m.snapshot_date}`}
                        className="flex items-baseline justify-between gap-3 border-t border-line/40 px-4 py-2.5 transition hover:bg-[color-mix(in_srgb,var(--fg)_4%,transparent)]"
                      >
                        <span className="truncate text-sm text-muted">
                          {shortLabel(m)}
                        </span>
                        <span className="whitespace-nowrap text-sm font-semibold tabular-nums text-fg">
                          {Number(m.value).toLocaleString()}
                          <span className="ml-1 text-[10px] font-medium text-muted">
                            {m.unit}
                          </span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 유저 목록 */}
      <section className="animate-rise">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>유저 선택 ({filtered.length})</SectionLabel>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <select
              value={assetFilter}
              onChange={(e) => setAssetFilter(e.target.value)}
              className="field py-1.5 pl-3 pr-8 text-sm"
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
                size={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="직업, 지역, 선호 검색"
                className="field w-full py-1.5 pl-9 pr-3 text-sm"
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
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
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
                    <th className="px-4 py-3 font-semibold">선호</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => {
                    const isSel = selected?.uuid === u.uuid;
                    return (
                      <tr
                        key={u.uuid}
                        className={`border-t border-line/60 transition ${
                          isSel
                            ? "bg-[color-mix(in_srgb,var(--gilt)_10%,transparent)] shadow-[inset_2px_0_0_0_var(--gilt)]"
                            : "hover:bg-[color-mix(in_srgb,var(--fg)_4%,transparent)]"
                        }`}
                      >
                        <td className="px-4 py-3">
                          <span
                            className={`font-medium ${isSel ? "text-gilt" : "text-fg"}`}
                          >
                            {u.occupation ?? "-"}
                          </span>{" "}
                          <span className="text-muted">/ {u.age ?? "?"}</span>
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {u.family_type ?? "-"} / {u.district ?? "-"}
                        </td>
                        <td
                          className="px-4 py-3 text-right font-medium tabular-nums text-fg"
                          title={fmtKRW(u.total_amount)}
                        >
                          {fmtKRWShort(u.total_amount)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--fg)_14%,transparent)]">
                              <div
                                className={`h-full rounded-full ${isSel ? "bg-gilt" : "bg-[color-mix(in_srgb,var(--fg)_55%,transparent)]"}`}
                                style={{
                                  width: `${(u.aggressiveness ?? 0) * 10}%`,
                                }}
                              />
                            </div>
                            <span className="tabular-nums text-xs text-muted">
                              {u.aggressiveness ?? "-"}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {u.preferred_asset ? (
                            <span className="inline-flex rounded-full border border-line px-2 py-0.5 text-xs text-muted">
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
                              className="rounded-md px-2 py-1 text-xs text-muted hover:text-gilt"
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
                                  ? "btn-gilt inline-flex items-center gap-1 px-3 py-1 text-xs"
                                  : "btn-ghost inline-flex items-center gap-1 px-3 py-1 text-xs text-fg"
                              }
                            >
                              {isSel ? "선택됨 · 대화" : "선택 후 대화"}
                              <ArrowRight weight="bold" size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted">
                        검색 결과가 없습니다.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
