"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { apiGet, type UserDetail } from "@/lib/api";
import { Card, PageTitle, Skeleton, fmtKRW } from "@/components/ui";

const COLORS = ["#d4af37", "#5fd0a0", "#60a5fa", "#e8c873", "#a78bfa", "#fb923c"];
const TOOLTIP_STYLE = {
  background: "var(--ink-2)",
  border: "1px solid var(--line)",
  borderRadius: 10,
  color: "var(--fg)",
  fontSize: 12,
} as const;

export default function DashboardPage() {
  const params = useParams<{ uuid: string }>();
  const uuid = params.uuid;
  const [detail, setDetail] = useState<UserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setDetail(await apiGet<UserDetail>(`/api/v1/users/${uuid}`));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [uuid]);

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
        title={`${p.occupation ?? "유저"} · ${p.age ?? "?"}세 대시보드`}
        subtitle={String(uuid)}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* 프로필 */}
        <Card>
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

        {/* 자산 배분 */}
        <Card>
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
      </div>

      {/* 권장 포트폴리오 */}
      {activePf && (
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
                  </tr>
                </thead>
                <tbody>
                  {activePf.items.map((it, i) => (
                    <tr key={i} className="border-t border-line/60">
                      <td className="py-1.5">{it.name ?? it.ticker ?? "-"}</td>
                      <td className="py-1.5 text-muted">{it.asset_type}</td>
                      <td className="py-1.5 font-mono text-gold">
                        {Number(it.allocation_pct)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
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
