"use client";

import { useRef, useState } from "react";
import { ArrowRight, CheckCircle, Warning, FilePdf, ShieldCheck, Sparkle } from "@phosphor-icons/react";
import {
  extractRates,
  extractRatesUpload,
  type RateDiffRow,
  type RateExtractResult,
} from "@/lib/api";
import { Card, PageTitle, SectionLabel, Skeleton, Spinner, fmtKRW } from "@/components/ui";

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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function onExtract() {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await extractRates(text, year, false));
    } catch (e) {
      setError(e instanceof Error ? e.message : "세율 추출에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await extractRatesUpload(file, year, false));
    } catch (e) {
      setError(e instanceof Error ? e.message : "파일 추출에 실패했습니다.");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="mx-auto max-w-[900px] px-6 py-12">
      <PageTitle
        eyebrow="결정론 계산기 · 개정 대응"
        title="세율 개정안 인입 (미리보기)"
        subtitle="개정안 텍스트를 붙여넣거나 PDF·파일을 올리면 시스템이 세율을 추출해 현행과 비교·검증합니다. 자동 반영은 하지 않습니다 — 세율은 코드 상수로만 결정되는 결정론 불변식을 지키기 위해서입니다. LLM은 추출만, 계산은 코드가 합니다."
      />

      {/* ── 입력 (텍스트 붙여넣기 + 파일 업로드) ── */}
      <Card className="space-y-4">
        <SectionLabel>개정안 텍스트 입력</SectionLabel>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          className="field w-full resize-y p-3 font-mono-spec text-sm"
          placeholder="세법개정안 텍스트를 붙여넣으세요…"
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-muted">
            귀속연도
            <input
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className="field w-20 px-2.5 py-1 text-sm font-mono-spec"
            />
          </label>

          <button
            onClick={onExtract}
            disabled={busy || !text.trim()}
            className="btn-accent inline-flex items-center gap-2 disabled:opacity-50"
          >
            <Sparkle size={16} weight="fill" />
            {busy ? "추출 중…" : "세율 추출"}
          </button>

          <span className="text-xs text-muted">또는</span>

          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.md"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
            }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="btn-ghost inline-flex items-center gap-2 disabled:opacity-50"
          >
            <FilePdf size={16} />
            개정안 파일 업로드
          </button>
        </div>
        <p className="text-xs text-muted">
          위 기본 예시로 1초 만에 테스트하거나, PDF·TXT·MD 파일을 직접 올릴 수 있습니다.
          PDF는 서버가 표까지 텍스트로 추출해 세율을 뽑고 현행과 비교합니다.
        </p>
      </Card>

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-negative/40 bg-negative/10 px-4 py-3 text-sm text-negative">
          <Warning size={16} weight="fill" /> {error}
        </div>
      )}

      {/* ── 로딩 상태 ── */}
      {busy && (
        <Card className="mt-6 space-y-4 border-accent/40 bg-accent/[0.04] p-5 animate-pulse">
          <div className="flex items-center gap-2.5 text-sm font-semibold text-accent">
            <Spinner className="h-4 w-4 text-accent" />
            <span>AI 세법 개정안 분석 및 조문 추출 중… (약 5~10초 소요)</span>
          </div>
          <div className="space-y-2 pt-1">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        </Card>
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
              <p className="font-semibold">검증 실패 — 형식·범위 이상</p>
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

          <div className="flex items-start gap-2.5 rounded-lg border border-accent/30 bg-accent/[0.06] px-4 py-3">
            <ShieldCheck size={16} weight="bold" className="mt-0.5 shrink-0 text-accent" />
            <p className="text-xs leading-relaxed text-fg/80">
              <span className="font-semibold text-fg">여기까지가 미리보기입니다.</span> 추출·비교
              결과를 런타임에 자동 반영하지 않습니다 — 세율은 코드 상수(레지스트리)로만 결정되어야
              같은 질문에 <span className="text-accent">항상 같은 세액</span>이 나오는 결정론 불변식이
              지켜지기 때문입니다. 실제 개정 반영은 코드 리뷰·릴리스를 거친 레지스트리 변경으로만
              이뤄집니다. <span className="text-muted">근거 확인은 여기서, 반영은 코드로.</span>
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
