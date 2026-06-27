"use client";

import { useCallback, useEffect, useState } from "react";
import { errMsg } from "@/lib/async";
import { Brain, ArrowsClockwise } from "@phosphor-icons/react";
import { getMemoryStats, validateMemory, type MemoryStats } from "@/lib/api";
import { Card, SectionLabel } from "@/components/ui";
import { useToast } from "@/lib/toast";

/** 분석 메모리 누적 현황 — 총 분석 수·검증 수·적중률·평균 수익률 + 결과 검증 트리거. */
export default function MemoryStatsCard({ ticker }: { ticker?: string }) {
  const toast = useToast();
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getMemoryStats(ticker)
      .then(setStats)
      .catch(() => setStats(null));
  }, [ticker]);

  useEffect(() => {
    load();
  }, [load]);

  const validate = async () => {
    setBusy(true);
    try {
      const r = await validateMemory();
      toast(
        r.validated > 0
          ? `검증 ${r.validated}건 — 적중 ${r.correct} / 빗나감 ${r.incorrect}`
          : "검증 대상 없음 (7일 이상 지난 미검증 분석 필요)",
        r.validated > 0 ? "success" : "info",
      );
      load();
    } catch (e) {
      toast(`검증 실패: ${errMsg(e)}`, "error");
    } finally {
      setBusy(false);
    }
  };

  // 메모리 미가용(total 0이고 DB 없음)이면 조용히 숨김 — 노이즈 방지.
  if (!stats || (stats.total === 0 && stats.validated === 0)) return null;

  return (
    <Card>
      <div className="flex items-center justify-between">
        <SectionLabel>
          <span className="inline-flex items-center gap-1.5">
            <Brain size={14} /> 분석 메모리 {ticker ? `· ${ticker}` : "· 전체"}
          </span>
        </SectionLabel>
        <button
          onClick={validate}
          disabled={busy}
          className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-sm disabled:opacity-50"
          title="7일 이상 지난 분석을 현재가와 비교해 적중 여부 채우기"
        >
          <ArrowsClockwise size={14} className={busy ? "animate-spin" : ""} />
          {busy ? "검증 중…" : "결과 검증"}
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="누적 분석" value={`${stats.total}건`} />
        <Tile label="검증 완료" value={`${stats.validated}건`} />
        <Tile
          label="적중률"
          value={stats.validated > 0 ? `${stats.accuracy_pct}%` : "—"}
          tone={stats.accuracy_pct >= 50 ? "up" : stats.validated > 0 ? "down" : undefined}
        />
        <Tile
          label="평균 수익률"
          value={stats.validated > 0 ? `${stats.avg_return_pct >= 0 ? "+" : ""}${stats.avg_return_pct}%` : "—"}
          tone={stats.avg_return_pct >= 0 ? "up" : "down"}
        />
      </div>
    </Card>
  );
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" }) {
  const color = tone === "up" ? "text-[#58c8a0]" : tone === "down" ? "text-[#e2607b]" : "text-fg";
  return (
    <div className="rounded-2xl border border-line bg-[var(--ink-2)]/40 px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 font-display text-lg font-semibold ${color}`}>{value}</div>
    </div>
  );
}
