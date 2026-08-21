"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageTitle, SectionLabel } from "@/components/ui";
import { MoneyInput } from "@/components/MoneyInput";
import {
  DEFAULT_PROFILE,
  FIRST_PRIORITY_SOURCE_NOTE,
  SIDO,
  firstPriorityChecks,
  loadProfile,
  regionOf,
  saveProfile,
  type MyProfile,
  type Sido,
} from "@/lib/my-profile";
import {
  AREA_LABELS,
  DEPOSIT_SOURCE_NOTE,
  depositRequirement,
  type AreaTier,
} from "@/lib/simulate";
import {
  DEPENDENTS_NOTE,
  MAX_SCORE,
  SCORE_SOURCE_NOTE,
  totalCheongyakScore,
} from "@/lib/cheongyak-score";

const input =
  "w-full rounded-xl border border-line bg-[var(--ink-2)]/50 px-3 py-2 text-sm text-fg outline-none focus:border-accent font-mono-spec tabular-nums";
const field = "flex flex-col gap-1.5";
const labelText = "text-xs text-muted";

export default function MyProfilePage() {
  const [p, setP] = useState<MyProfile>(DEFAULT_PROFILE);

  useEffect(() => {
    // 마운트 1회 localStorage 복원. 서버엔 localStorage 없어 lazy init 불가 → effect가 정답.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setP(loadProfile());
  }, []);

  const set = <K extends keyof MyProfile>(k: K, v: MyProfile[K]) => {
    const next = { ...p, [k]: v };
    setP(next);
    saveProfile(next);
  };

  const score = totalCheongyakScore(p);
  const checks = firstPriorityChecks(p);
  const unmet = checks.filter((c) => !c.ok);
  const needDeposit = depositRequirement(regionOf(p.sido), p.targetArea);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 space-y-6">
      <PageTitle
        title="내 정보"
        eyebrow="My Profile"
        subtitle="청약 심사에 실제로 들어가는 항목만 받습니다. 입력값은 이 브라우저에만 저장되며 서버로 전송되지 않습니다. 여기 넣은 값이 청약 가점·1순위 자격 안내·자금 시뮬레이터·상담 챗봇에 그대로 쓰입니다."
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_minmax(0,380px)]">
        <div className="space-y-6">
          {/* ── 가점 3요소 ── */}
          <Card className="space-y-4">
            <SectionLabel>청약 가점 (84점 만점)</SectionLabel>

            <label className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <input
                type="checkbox"
                className="h-3.5 w-3.5 accent-[var(--accent)]"
                checked={p.under30Unmarried}
                onChange={(e) => set("under30Unmarried", e.target.checked)}
              />
              만 30세 미만이면서 미혼
              <span className="text-[10px] text-muted/70">
                (무주택기간은 만 30세부터 계산 — 30세 이전 혼인 시 혼인신고일부터. 해당하면 무주택기간 0점)
              </span>
            </label>

            <div className="grid gap-3 sm:grid-cols-3">
              <label className={field}>
                <span className={labelText}>무주택기간(년)</span>
                <input
                  type="number" min={0} max={30} step={0.5}
                  className={`${input} disabled:opacity-40`}
                  disabled={p.under30Unmarried}
                  value={p.under30Unmarried ? 0 : p.homelessYears}
                  onChange={(e) => set("homelessYears", Number(e.target.value))}
                />
              </label>
              <label className={field}>
                <span className={labelText}>부양가족수(명, 본인 제외)</span>
                <input
                  type="number" min={0} max={10} step={1} className={input}
                  value={p.dependents}
                  onChange={(e) => set("dependents", Number(e.target.value))}
                />
              </label>
              <label className={field}>
                <span className={labelText}>청약통장 가입기간(년)</span>
                <input
                  type="number" min={0} max={30} step={0.5} className={input}
                  value={p.subscriptionYears}
                  onChange={(e) => set("subscriptionYears", Number(e.target.value))}
                />
              </label>
            </div>

            <p className="text-[10px] leading-relaxed text-muted/70">{DEPENDENTS_NOTE}</p>
            <p className="text-[10px] text-muted/70">{SCORE_SOURCE_NOTE}</p>
          </Card>

          {/* ── 1순위 자격 ── */}
          <Card className="space-y-4">
            <SectionLabel>1순위 자격 (민영주택 일반공급)</SectionLabel>

            <div className="grid gap-3 sm:grid-cols-3">
              <label className={field}>
                <span className={labelText}>거주 지역(시/도)</span>
                <select
                  className={input}
                  value={p.sido}
                  onChange={(e) => set("sido", e.target.value as Sido)}
                >
                  {SIDO.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </label>
              <label className={field}>
                <span className={labelText}>해당 지역 거주기간(년)</span>
                <input
                  type="number" min={0} max={50} step={0.5} className={input}
                  value={p.residenceYears}
                  onChange={(e) => set("residenceYears", Number(e.target.value))}
                />
              </label>
              <label className={field}>
                <span className={labelText}>관심 전용면적</span>
                <select
                  className={input}
                  value={p.targetArea}
                  onChange={(e) => set("targetArea", e.target.value as AreaTier)}
                >
                  {(Object.keys(AREA_LABELS) as AreaTier[]).map((a) => (
                    <option key={a} value={a}>{AREA_LABELS[a]}</option>
                  ))}
                </select>
              </label>
            </div>

            <label className={field}>
              <span className={labelText}>
                청약통장 납입 총액(원) — 기준금액 {needDeposit.toLocaleString("ko-KR")}원
              </span>
              <MoneyInput
                className={input}
                value={p.subscriptionDeposit}
                onChange={(v) => set("subscriptionDeposit", v)}
              />
            </label>
            <p className="text-[10px] leading-relaxed text-muted/70">
              민영주택은 납입 <b>횟수</b>가 아니라 납입 <b>총액</b>이 기준입니다(횟수 요건은 국민주택). {DEPOSIT_SOURCE_NOTE}
            </p>

            <div className="grid gap-2 sm:grid-cols-2">
              {([
                ["noHouseOwnership", "세대구성원 전원 무주택"],
                ["isHouseholder", "내가 세대주"],
                ["regulatedArea", "규제지역(투기과열지구·청약과열지역)"],
                ["wonLotteryIn5Years", "세대구성원 중 최근 5년 내 당첨 이력"],
              ] as const).map(([key, label]) => (
                <label key={key} className="flex items-center gap-2 text-xs text-fg">
                  <input
                    type="checkbox"
                    className="h-3.5 w-3.5 accent-[var(--accent)]"
                    checked={p[key]}
                    onChange={(e) => set(key, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <p className="text-[10px] leading-relaxed text-muted/70">
              규제지역 지정은 정부 고시로 수시로 바뀌어 앱이 자동 판단하지 않습니다 — 청약하려는 공고문에서 확인해 체크하세요.
              체크하면 세대주·거주기간·당첨이력 요건이 추가로 적용됩니다.
            </p>
          </Card>

          {/* ── 자금 ── */}
          <Card className="space-y-4">
            <SectionLabel>자금 상황</SectionLabel>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className={field}>
                <span className={labelText}>현재 자산(원)</span>
                <MoneyInput className={input} value={p.currentAssets} onChange={(v) => set("currentAssets", v)} />
              </label>
              <label className={field}>
                <span className={labelText}>월 저축 가능액(원)</span>
                <MoneyInput className={input} value={p.monthlySaving} onChange={(v) => set("monthlySaving", v)} />
              </label>
              <label className={field}>
                <span className={labelText}>연소득(원)</span>
                <MoneyInput className={input} value={p.annualIncome} onChange={(v) => set("annualIncome", v)} />
              </label>
            </div>
            <p className="text-[10px] text-muted/70">
              자금마련 시뮬레이터의 초기값으로 쓰입니다. 시뮬레이터에서 값을 바꿔도 이 프로필은 그대로 유지됩니다.
            </p>
          </Card>
        </div>

        {/* ── 결과 요약 (sticky) ── */}
        <div className="space-y-6 lg:sticky lg:top-6 lg:self-start">
          <Card className="space-y-3">
            <SectionLabel>내 청약 가점</SectionLabel>
            <div className="rounded-xl border border-accent/30 bg-accent/10 px-4 py-3 text-center font-mono-spec">
              <div className="text-3xl font-bold tabular-nums text-accent">
                {score}
                <span className="text-base text-muted">/{MAX_SCORE}</span>
              </div>
            </div>
          </Card>

          <Card className="space-y-3">
            <SectionLabel>1순위 요건 대조</SectionLabel>
            <div
              className={`rounded-xl border px-3 py-2 text-sm ${
                unmet.length === 0
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-400"
              }`}
            >
              {unmet.length === 0
                ? "입력값 기준 요건을 모두 충족합니다"
                : `${unmet.length}개 항목이 기준에 미달합니다`}
            </div>

            <ul className="space-y-2">
              {checks.map((c) => (
                <li key={c.label} className="flex gap-2 text-xs">
                  <span className={c.ok ? "text-emerald-400" : "text-amber-400"}>
                    {c.ok ? "✓" : "✕"}
                  </span>
                  <span className="min-w-0">
                    <span className="text-fg">{c.label}</span>
                    {c.regulatedOnly && (
                      <span className="ml-1 text-[10px] text-muted/70">(규제지역)</span>
                    )}
                    <span className="block font-mono-spec tabular-nums text-[11px] leading-relaxed text-muted">
                      {c.detail}
                    </span>
                  </span>
                </li>
              ))}
            </ul>

            <p className="text-[10px] leading-relaxed text-muted/70">{FIRST_PRIORITY_SOURCE_NOTE}</p>
          </Card>

          <Card className="space-y-2">
            <SectionLabel>이 정보로 이어서</SectionLabel>
            {[
              ["/cheongyak", "내 가점으로 공고 보기"],
              ["/simulator", "자금마련 시뮬레이터"],
              ["/chat", "이 조건으로 상담하기"],
            ].map(([href, label]) => (
              <Link
                key={href}
                href={href}
                className="flex items-center justify-between rounded-xl border border-line px-4 py-2.5 text-sm transition hover:border-accent hover:text-accent"
              >
                {label}
                <span className="text-muted">→</span>
              </Link>
            ))}
          </Card>
        </div>
      </div>
    </main>
  );
}
