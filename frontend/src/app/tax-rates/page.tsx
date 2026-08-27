"use client";

import { useState } from "react";
import { ArrowRight, CheckCircle, Warning, Sparkle } from "@phosphor-icons/react";
import {
  applyRates,
  extractRates,
  type RateApplyResult,
  type RateDiffRow,
  type RateExtractResult,
} from "@/lib/api";
import { Card, PageTitle, SectionLabel, fmtKRW } from "@/components/ui";

const SAMPLE_AMENDMENT = `2026년 귀속 세법개정안 요약
- 해외주식 양도소득세율을 20%에서 22%로 상향한다.
- 이자·배당 분리과세율은 15.4%로 유지한다.
- 금융소득종합과세 기준을 2,000만원에서 3,000만원으로 상향한다.`;

/** 세율값을 종류에 맞게 렌더 — rate는 퍼센트, amount는 원화. */
function fmtRateValue(kind: "rate" | "amount", value: number): string {
  return kind === "rate" ? `${(value * 100).toFixed(2).replace(/\.?0+$/, "")}%` : fmtKRW(value);
}

function DiffRow({ row }: { row: RateDiffRow }) {
  return (
    <tr className={row.changed ? "bg-[color-mix(in_srgb,var(--gilt)_8%,transparent)]" : ""}>
      <td className="px-3 py-2.5 text-sm text-fg">{row.label}</td>
      <td className="px-3 py-2.5 text-right font-mono-spec text-sm text-muted">
        {fmtRateValue(row.kind, row.old_value)}
      </td>
      <td className="px-2 py-2.5 text-center text-muted">
        {row.changed ? <ArrowRight size={14} className="inline text-gilt" weight="bold" /> : "="}
      </td>
      <td className="px-3 py-2.5 text-right font-mono-spec text-sm font-semibold text-fg">
        {fmtRateValue(row.kind, row.new_value)}
      </td>
      <td className="px-3 py-2.5 text-xs text-muted">{row.new_basis}</td>
    </tr>
  );
}

export default function TaxRatesPage() {
  const [text, setText] = useState(SAMPLE_AMENDMENT);
  const [year, setYear] = useState("2026");
  const [result, setResult] = useState<RateExtractResult | null>(null);
  const [applied, setApplied] = useState<RateApplyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onExtract() {
    setBusy(true);
    setError(null);
    setApplied(null);
    setResult(null);
    try {
      setResult(await extractRates(text, year, false));
    } catch (e) {
      setError(e instanceof Error ? e.message : "추출에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function onApply() {
    if (!result) return;
    setBusy(true);
    setError(null);
    try {
      setApplied(await applyRates(result.proposed));
    } catch (e) {
      setError(e instanceof Error ? e.message : "반영에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-[900px] px-6 py-12">
      <PageTitle
        eyebrow="결정론 계산기 · 개정 대응"
        title="세율 개정안 인입"
        subtitle="개정안을 넣으면 시스템이 세율을 추출하고 현행과 비교합니다. 승인해야만 레지스트리에 반영되며, 세액 산술은 승인 뒤에도 코드가 합니다 — LLM은 추출만, 계산은 하지 않습니다."
      />

      {/* ── 입력 ── */}
      <Card className="space-y-4">
        <SectionLabel>개정안 입력</SectionLabel>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          className="w-full resize-y rounded-lg border border-line bg-surface/40 p-3 font-mono-spec text-sm text-fg outline-none focus:border-accent"
          placeholder="세법개정안 텍스트를 붙여넣으세요…"
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-muted">
            귀속연도
            <input
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className="w-20 rounded-md border border-line bg-surface/40 px-2 py-1 font-mono-spec text-sm text-fg outline-none focus:border-accent"
            />
          </label>
          <button
            onClick={onExtract}
            disabled={busy || !text.trim()}
            className="btn-accent inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Sparkle size={16} weight="fill" />
            {busy && !applied ? "추출 중…" : "세율 추출"}
          </button>
        </div>
      </Card>

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-negative/40 bg-negative/10 px-4 py-3 text-sm text-negative">
          <Warning size={16} weight="fill" /> {error}
        </div>
      )}

      {/* ── 추출 결과 · diff ── */}
      {result && (
        <Card className="mt-6 space-y-4">
          <SectionLabel>현행 대비 변경 (검토)</SectionLabel>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-stone">
                  <th className="px-3 py-2 font-medium">항목</th>
                  <th className="px-3 py-2 text-right font-medium">현행</th>
                  <th className="px-2 py-2" />
                  <th className="px-3 py-2 text-right font-medium">개정</th>
                  <th className="px-3 py-2 font-medium">근거</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/50">
                {result.diff.map((row) => (
                  <DiffRow key={row.field} row={row} />
                ))}
              </tbody>
            </table>
          </div>

          {result.issues.length > 0 ? (
            <div className="space-y-1 rounded-lg border border-negative/40 bg-negative/10 px-4 py-3 text-sm text-negative">
              <p className="font-semibold">검증 실패 — 반영할 수 없습니다</p>
              {result.issues.map((i) => (
                <p key={i} className="text-xs">
                  · {i}
                </p>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm text-positive">
              <CheckCircle size={16} weight="fill" /> 검증 통과 — 세율 범위·형식 이상 없음
            </div>
          )}

          <p className="text-xs leading-relaxed text-muted">
            추출값은 &ldquo;검수 필요&rdquo; 라벨이 붙은 제안입니다. 승인하면 {year} 귀속 계산이 새
            세율을 쓰지만, 기존 2025 귀속 계산과 방어 증명 &ldquo;LLM 개입 없음&rdquo; 불변식은 그대로
            유지됩니다.
          </p>

          <button
            onClick={onApply}
            disabled={busy || !result.can_apply || applied !== null}
            className="btn-accent inline-flex items-center gap-2 disabled:opacity-50"
          >
            <CheckCircle size={16} weight="fill" />
            {applied ? "반영됨" : "승인하고 레지스트리 반영"}
          </button>
        </Card>
      )}

      {/* ── 반영 완료 ── */}
      {applied && (
        <Card className="mt-6 space-y-3" variant="glass">
          <div className="flex items-center gap-2 text-positive">
            <CheckCircle size={20} weight="fill" />
            <span className="font-semibold text-fg">
              {applied.year} 귀속 세율이 레지스트리에 반영되었습니다
            </span>
          </div>
          <p className="text-xs text-muted">{applied.active.provenance}</p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <tbody className="divide-y divide-line/50">
                {Object.entries(applied.active.rates).map(([field, r]) => (
                  <tr key={field}>
                    <td className="px-3 py-2 text-muted">{field}</td>
                    <td className="px-3 py-2 text-right font-mono-spec text-fg">
                      {r.value < 1 ? `${(r.value * 100).toFixed(2).replace(/\.?0+$/, "")}%` : fmtKRW(r.value)}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted">{r.basis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs leading-relaxed text-muted">
            이제 세금 계산기가 {applied.year} 귀속 질의에 이 세율을 사용합니다. 세액 산술은 여전히
            코드가 수행합니다(LLM 개입 없음).
          </p>
        </Card>
      )}
    </div>
  );
}
