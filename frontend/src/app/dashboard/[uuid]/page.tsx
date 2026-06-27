"use client";

import { useEffect, useState } from "react";
import { errMsg } from "@/lib/async";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { ChartLineUp, Buildings, TrendUp } from "@phosphor-icons/react";
import {
  apiGet,
  getRateBriefing,
  type RateBriefing,
  type UserDetail,
} from "@/lib/api";
import { Reveal } from "@/components/Reveal";
import { Card, PageTitle, SectionLabel, Skeleton, fmtKRW } from "@/components/ui";

// 사파이어 블루 정체성에 맞춘 분할 팔레트(은행권 무드).
// 블루 계열 + 쿨 중립 + 시맨틱 그린 1포인트.
const COLORS = ["#4f8df9", "#88b6ff", "#1f5fd0", "#2a3a5c", "#9aa3b5", "#58c8a0"];
const TOOLTIP_STYLE = {
  background: "var(--ink-2)",
  border: "1px solid var(--line)",
  borderRadius: 14,
  color: "var(--fg)",
  fontSize: 12,
  boxShadow: "var(--shadow-float)",
} as const;

export default function DashboardPage() {
  const params = useParams<{ uuid: string }>();
  const uuid = params.uuid;
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [briefing, setBriefing] = useState<RateBriefing | null>(null);
  const [briefingBusy, setBriefingBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setDetail(await apiGet<UserDetail>(`/api/v1/users/${uuid}`));
      } catch (e) {
        setError(errMsg(e));
      }
    })();
  }, [uuid]);

  const loadBriefing = async () => {
    setBriefingBusy(true);
    try {
      setBriefing(await getRateBriefing());
    } catch {
      setBriefing({ available: false, message: "브리핑을 불러오지 못했습니다.", sections: [] });
    } finally {
      setBriefingBusy(false);
    }
  };

  if (error) return <p className="text-sm text-negative">오류: {error}</p>;
  if (!detail)
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );

  const p = detail.profile as Record<string, number | string | null>;

  // 유저 자산 배분 (보유 금액 기준)
  const assetData = [
    { name: "주식", value: Number(p.stock_amount) || 0 },
    { name: "채권", value: Number(p.bond_amount) || 0 },
    { name: "예적금", value: Number(p.deposit_amount) || 0 },
    { name: "부동산", value: Number(p.real_estate_amount) || 0 },
  ].filter((d) => d.value > 0);

  const activePf = detail.portfolios.find((pf) => pf.is_active) ?? detail.portfolios[0];

  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Dashboard"
        title={`${p.occupation ?? "유저"} · ${p.age ?? "?"}세 대시보드`}
        subtitle={String(uuid)}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 프로필 */}
        <Reveal index={0} className="h-full">
        <Card className="h-full">
          <h2 className="mb-3 text-sm font-medium text-fg">프로필</h2>
          <dl className="grid grid-cols-2 gap-y-2 text-sm">
            <Field label="성별" value={p.sex} />
            <Field label="가구 형태" value={p.family_type} />
            <Field label="주거" value={`${p.housing_type ?? "-"} (${p.district ?? "-"})`} />
            <Field label="총자산" value={fmtKRW(Number(p.total_amount))} />
            <Field label="월 소득" value={fmtKRW(Number(p.monthly_income))} />
            <Field label="월 가용액" value={fmtKRW(Number(p.monthly_investable))} />
            <Field label="공격성" value={`${p.aggressiveness ?? "-"}/10`} />
            <Field label="금융이해도" value={`${p.financial_literacy ?? "-"}/10`} />
            <Field label="선호 자산" value={p.preferred_asset} />
            <Field label="목표 수익률" value={`${p.target_return_percent ?? "-"}%`} />
          </dl>
        </Card>
        </Reveal>

        {/* 자산 배분 */}
        <Reveal index={1} className="h-full">
        <Card className="h-full">
          <h2 className="mb-3 text-sm font-medium text-fg">현재 자산 배분</h2>
          {assetData.length === 0 ? (
            <p className="text-sm text-muted">자산 데이터가 없습니다.</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={assetData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  innerRadius={50}
                  paddingAngle={2}
                >
                  {assetData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) => fmtKRW(Number(v))}
                  contentStyle={TOOLTIP_STYLE}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
        </Reveal>
      </div>

      {/* 시장 리서치 + 빠른 작업 (이식 기능 연결) */}
      <Reveal index={2}>
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="flex h-full flex-col">
            <div className="flex items-center justify-between">
              <SectionLabel>
                <span className="inline-flex items-center gap-1.5">
                  <TrendUp size={14} /> 라이브 금리 브리핑
                </span>
              </SectionLabel>
              <button
                onClick={loadBriefing}
                disabled={briefingBusy}
                className="btn-ghost px-3 py-1.5 text-xs disabled:opacity-50"
              >
                {briefingBusy ? "조회 중…" : briefing ? "새로고침" : "브리핑 보기"}
              </button>
            </div>
            {!briefing && !briefingBusy && (
              <p className="mt-2 text-sm text-muted">
                미·일·한 기준금리 동향을 라이브로 요약합니다. (TAVILY_API_KEY 필요)
              </p>
            )}
            {briefing && !briefing.available && (
              <p className="mt-2 text-sm text-muted">{briefing.message}</p>
            )}
            {briefing && briefing.available && (
              <div className="mt-2 space-y-3">
                {briefing.sections.map((s) => (
                  <div key={s.label}>
                    <div className="text-xs font-medium text-accent">{s.label}</div>
                    <p className="mt-0.5 line-clamp-4 text-xs leading-relaxed text-muted">{s.body}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="flex h-full flex-col">
            <SectionLabel>빠른 작업</SectionLabel>
            <div className="mt-2 flex flex-col gap-2">
              <Link
                href="/cheongyak"
                className="flex items-center justify-between rounded-xl border border-line px-4 py-3 text-sm transition hover:border-accent hover:text-accent"
              >
                <span className="inline-flex items-center gap-2">
                  <Buildings size={16} /> 맞춤 청약 보기
                </span>
                <span className="text-muted">→</span>
              </Link>
              <Link
                href="/stocks"
                className="flex items-center justify-between rounded-xl border border-line px-4 py-3 text-sm transition hover:border-accent hover:text-accent"
              >
                <span className="inline-flex items-center gap-2">
                  <ChartLineUp size={16} /> 보유 종목 백테스트
                </span>
                <span className="text-muted">→</span>
              </Link>
            </div>
          </Card>
        </div>
      </Reveal>

      {/* 권장 포트폴리오 */}
      {activePf && (
        <Reveal index={3}>
        <Card>
          <h2 className="mb-3 text-sm font-medium text-fg">
            포트폴리오: {activePf.name ?? activePf.strategy_name ?? "전략"}
          </h2>
          <div className="grid gap-6 lg:grid-cols-2">
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={ratioData(activePf)}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={85}
                  label={(e: { name?: string; value?: number }) =>
                    `${e.name} ${e.value}%`
                  }
                >
                  {ratioData(activePf).map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="scroll-thin max-h-60 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-muted">
                  <tr>
                    <th className="py-1 font-medium">종목</th>
                    <th className="py-1 font-medium">유형</th>
                    <th className="py-1 font-medium">비중</th>
                    <th className="py-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {activePf.items.map((it, i) => (
                    <tr key={i} className="border-t border-line/60">
                      <td className="py-1.5">{it.name ?? it.ticker ?? "-"}</td>
                      <td className="py-1.5 text-muted">{it.asset_type}</td>
                      <td className="py-1.5 font-mono text-accent">
                        {Number(it.allocation_pct)}%
                      </td>
                      <td className="py-1.5 text-right">
                        {it.ticker && (
                          <Link
                            href={`/stocks?ticker=${encodeURIComponent(it.ticker)}`}
                            className="inline-flex items-center gap-1 text-[11px] text-muted transition hover:text-accent"
                            title={`${it.ticker} 백테스트`}
                          >
                            <ChartLineUp size={12} /> 백테스트
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
        </Reveal>
      )}
    </div>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  return (
    <>
      <dt className="text-muted">{label}</dt>
      <dd className="text-fg">{value ?? "-"}</dd>
    </>
  );
}

function ratioData(pf: {
  stock_ratio: number;
  bond_ratio: number;
  deposit_ratio: number;
  real_estate_ratio: number;
  gold_ratio: number;
  cash_ratio: number;
}) {
  return [
    { name: "주식", value: Number(pf.stock_ratio) },
    { name: "채권", value: Number(pf.bond_ratio) },
    { name: "예적금", value: Number(pf.deposit_ratio) },
    { name: "부동산", value: Number(pf.real_estate_ratio) },
    { name: "금", value: Number(pf.gold_ratio) },
    { name: "현금", value: Number(pf.cash_ratio) },
  ].filter((d) => d.value > 0);
}
