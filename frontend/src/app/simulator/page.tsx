"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import { Card, PageTitle, SectionLabel, fmtKRW, fmtKRWShort } from "@/components/ui";
import { MoneyInput } from "@/components/MoneyInput";
import { loadProfile } from "@/lib/my-profile";
import {
  AREA_LABELS,
  DEPOSIT_SOURCE_NOTE,
  REGION_LABELS,
  depositRequirement,
  simulateTimeline,
  type AreaTier,
  type Region,
} from "@/lib/simulate";

const inputClass =
  "rounded-xl border border-line bg-[var(--ink-2)]/50 px-3 py-2 text-sm text-fg outline-none focus:border-accent";
const labelClass = "flex flex-col gap-1.5";
const labelTextClass = "text-xs text-muted";
const TOOLTIP_STYLE = {
  background: "var(--ink-2)",
  border: "1px solid var(--line)",
  borderRadius: 14,
  color: "var(--fg)",
};

export default function SimulatorPage() {
  // 기본값은 데모 시나리오(28세 사회초년생·서울 특공 관심)에 맞춤. 예치금(300만원)은 기본 자산으로
  // 대부분 이미 충족돼 그래프가 밋밋해지므로, 실질 목표(계약금 등 직접입력)를 기본으로 보여준다.
  const [targetMode, setTargetMode] = useState<"deposit" | "custom">("custom");
  const [region, setRegion] = useState<Region>("seoul_busan");
  const [area, setArea] = useState<AreaTier>("85");
  const [customTarget, setCustomTarget] = useState(40_000_000);

  const [currentAssets, setCurrentAssets] = useState(20_000_000);
  const [monthlySaving, setMonthlySaving] = useState(600_000);

  const [labelA, setLabelA] = useState("일반 적금");
  const [rateA, setRateA] = useState(3.5);
  const [labelB, setLabelB] = useState("청년도약계좌 등 정책상품");
  const [rateB, setRateB] = useState(6.0);

  // 청약 상세모달 "이 청약으로 계획 세우기"에서 넘어온 경우 목표금액을 그 공고 기준으로 채운다.
  // useSearchParams는 Suspense 경계가 필요해 번거로우니, 이 페이지가 전부 클라이언트 전용인 점을
  // 이용해 마운트 시 한 번 window.location에서 직접 읽는다.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- 마운트 시 외부 상태(URL 쿼리·localStorage) 복원 */
    // /me 에 입력해 둔 자금 상황을 초기값으로 깐다. 여기서 값을 바꿔도 프로필은 안 건드린다
    // (시뮬레이터는 "만약에" 를 굴려보는 곳이라, 굴려본 값이 내 정보를 덮으면 안 된다).
    const me = loadProfile();
    setCurrentAssets(me.currentAssets);
    setMonthlySaving(me.monthlySaving);

    const target = Number(new URLSearchParams(window.location.search).get("target"));
    if (target > 0) {
      setTargetMode("custom");
      setCustomTarget(target);
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const targetAmount = targetMode === "deposit" ? depositRequirement(region, area) : customTarget;

  const { reachA, reachB, chartData } = useMemo(() => {
    const a = simulateTimeline(targetAmount, currentAssets, monthlySaving, rateA);
    const b = simulateTimeline(targetAmount, currentAssets, monthlySaving, rateB);
    // 둘 중 늦게 도달하는 쪽 기준 + 여유 6개월까지만 그려서 그래프가 불필요하게 안 늘어지게 한다.
    const horizon = Math.min(240, Math.max(a.reachMonth ?? 240, b.reachMonth ?? 240) + 6);
    const data = a.points
      .slice(0, horizon + 1)
      .map((p, i) => ({ month: p.month, a: p.balance, b: b.points[i].balance }));
    return { reachA: a.reachMonth, reachB: b.reachMonth, chartData: data };
  }, [targetAmount, currentAssets, monthlySaving, rateA, rateB]);

  const diffMonths = reachA !== null && reachB !== null ? reachA - reachB : null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 space-y-6">
      <PageTitle
        title="자금마련 타임라인 시뮬레이터"
        eyebrow="Fund Timeline"
        subtitle="청약 목표금액까지 지금 저축 계획으로 얼마나 걸리는지, 상품을 바꾸면 얼마나 당겨지는지 시뮬레이션합니다. 정보 제공 목적의 시뮬레이션이며 투자·저축 자문이 아닙니다."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_1fr]">
        <div className="space-y-6">
          <Card>
            <SectionLabel>목표금액</SectionLabel>
            <div className="space-y-3">
              <label className={labelClass}>
                <span className={labelTextClass}>기준</span>
                <select
                  className={inputClass}
                  value={targetMode}
                  onChange={(e) => setTargetMode(e.target.value as "deposit" | "custom")}
                >
                  <option value="deposit">청약 예치금 기준(지역·면적)</option>
                  <option value="custom">직접 입력(분양가·계약금 등)</option>
                </select>
              </label>

              {targetMode === "deposit" ? (
                <>
                  <label className={labelClass}>
                    <span className={labelTextClass}>지역</span>
                    <select
                      className={inputClass}
                      value={region}
                      onChange={(e) => setRegion(e.target.value as Region)}
                    >
                      {(Object.keys(REGION_LABELS) as Region[]).map((r) => (
                        <option key={r} value={r}>
                          {REGION_LABELS[r]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className={labelClass}>
                    <span className={labelTextClass}>전용면적</span>
                    <select
                      className={inputClass}
                      value={area}
                      onChange={(e) => setArea(e.target.value as AreaTier)}
                    >
                      {(Object.keys(AREA_LABELS) as AreaTier[]).map((a) => (
                        <option key={a} value={a}>
                          {AREA_LABELS[a]}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              ) : (
                <label className={labelClass}>
                  <span className={labelTextClass}>목표금액(원)</span>
                  <MoneyInput className={inputClass} value={customTarget} onChange={setCustomTarget} />
                </label>
              )}

              <div className="rounded-xl border border-accent/30 bg-accent/10 px-3 py-2 text-sm text-accent font-mono-spec">
                목표: {fmtKRW(targetAmount)}
              </div>
              {targetMode === "deposit" && (
                <>
                  <p className="text-[11px] leading-relaxed text-muted">
                    민영주택 청약예치금 기준(국토부 고시)입니다. 실제 계약금·중도금까지 고려하면 실질
                    필요자금은 이보다 큽니다 — 정확한 분양가를 알고 있으면 &quot;직접 입력&quot;을 쓰세요.
                  </p>
                  <p className="text-[10px] text-muted/70">{DEPOSIT_SOURCE_NOTE}</p>
                </>
              )}
            </div>
          </Card>

          <Card>
            <SectionLabel>현재 상황</SectionLabel>
            <div className="space-y-3">
              <label className={labelClass}>
                <span className={labelTextClass}>현재 자산(원)</span>
                <MoneyInput className={inputClass} value={currentAssets} onChange={setCurrentAssets} />
              </label>
              <label className={labelClass}>
                <span className={labelTextClass}>월 저축 가능액(원)</span>
                <MoneyInput className={inputClass} value={monthlySaving} onChange={setMonthlySaving} />
              </label>
            </div>
          </Card>

          <Card>
            <SectionLabel>비교할 상품 2개</SectionLabel>
            <div className="space-y-4">
              <div className="space-y-2">
                <input
                  type="text"
                  className={`${inputClass} w-full`}
                  value={labelA}
                  onChange={(e) => setLabelA(e.target.value)}
                />
                <label className={labelClass}>
                  <span className={labelTextClass}>연이율(%)</span>
                  <input
                    type="number"
                    className={`${inputClass} font-mono-spec tabular-nums`}
                    value={rateA}
                    min={0}
                    max={30}
                    step={0.1}
                    onChange={(e) => setRateA(Number(e.target.value))}
                  />
                </label>
              </div>
              <div className="space-y-2">
                <input
                  type="text"
                  className={`${inputClass} w-full`}
                  value={labelB}
                  onChange={(e) => setLabelB(e.target.value)}
                />
                <label className={labelClass}>
                  <span className={labelTextClass}>연이율(%)</span>
                  <input
                    type="number"
                    className={`${inputClass} font-mono-spec tabular-nums`}
                    value={rateB}
                    min={0}
                    max={30}
                    step={0.1}
                    onChange={(e) => setRateB(Number(e.target.value))}
                  />
                </label>
              </div>
              <Link
                href="/chat"
                className="flex items-center justify-center gap-1.5 rounded-xl border border-line px-3 py-2 text-xs text-muted transition hover:border-accent hover:text-accent"
              >
                최신 상품 금리는 챗봇에서 확인 →
              </Link>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <SectionLabel>도달 시점 비교</SectionLabel>
            <div className="mb-4 grid grid-cols-2 gap-4">
              <ResultTile label={labelA} months={reachA} />
              <ResultTile label={labelB} months={reachB} />
            </div>
            {diffMonths !== null && diffMonths !== 0 && (
              <p className="mb-4 text-sm text-fg">
                <span className="font-semibold text-accent">{labelB}</span>을 쓰면{" "}
                <span className="font-semibold text-accent">{Math.abs(diffMonths)}개월</span>{" "}
                {diffMonths > 0 ? "더 빨리" : "더 늦게"} 목표에 도달합니다.
              </p>
            )}
            <ResponsiveContainer width="100%" height={340}>
              <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis
                  dataKey="month"
                  tickFormatter={(m) => `${m}개월`}
                  stroke="var(--muted)"
                  fontSize={11}
                />
                <YAxis
                  tickFormatter={(v) => fmtKRWShort(Number(v))}
                  stroke="var(--muted)"
                  fontSize={11}
                  width={64}
                />
                <Tooltip
                  formatter={(v) => fmtKRW(Number(v))}
                  labelFormatter={(m) => `${m}개월차`}
                  contentStyle={TOOLTIP_STYLE}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <ReferenceLine
                  y={targetAmount}
                  stroke="#c7a349"
                  strokeDasharray="4 4"
                  label={{ value: "목표", position: "insideTopRight", fill: "#c7a349", fontSize: 11 }}
                />
                <Line type="monotone" dataKey="a" name={labelA} stroke="#8a6a1c" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="b" name={labelB} stroke="#58c8a0" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <p className="mt-3 text-[11px] leading-relaxed text-muted">
              월복리로 단순화한 시뮬레이션입니다. 실제 상품의 이자 계산 방식(단리·우대금리·비과세 조건 등)과
              다를 수 있으며, 투자·저축 자문이 아닙니다.
            </p>
          </Card>
        </div>
      </div>
    </main>
  );
}

function ResultTile({ label, months }: { label: string; months: number | null }) {
  return (
    <div className="rounded-xl border border-line/60 bg-surface/30 p-4">
      <div className="mb-1 truncate text-xs text-muted">{label}</div>
      <div className="font-mono-spec text-2xl font-semibold text-fg">
        {months === null ? "20년 내 미도달" : months === 0 ? "이미 충족" : `${months}개월`}
      </div>
    </div>
  );
}
