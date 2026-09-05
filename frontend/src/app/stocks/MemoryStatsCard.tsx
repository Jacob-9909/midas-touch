"use client";

import { useCallback, useEffect, useState } from "react";
import { errMsg } from "@/lib/async";
import { Brain, ArrowsClockwise } from "@phosphor-icons/react";
import {
  getHorizonStats,
  getMemoryStats,
  validateMemory,
  type HorizonStats,
  type MemoryStats,
} from "@/lib/api";
import { Card, SectionLabel } from "@/components/ui";
import { useToast } from "@/lib/toast";

const HORIZONS = [
  ["24h", "24시간"],
  ["3d", "3일"],
  ["1w", "1주"],
  ["1m", "1개월"],
] as const;

/**
 * 분석 메모리 누적 현황 — 총 분석 수·검증 수·적중률·평균 수익률 + 결과 검증 트리거.
 *
 * showcase=true(랜딩)면 시간축별(24h/3d/1w/1m) 적중률까지 펼치고, 표본이 0건이어도
 * 카드를 숨기지 않는다. 대신 "수집 중"으로 적어 0%로 오해되지 않게 한다.
 */
export default function MemoryStatsCard({
  ticker,
  showcase = false,
}: {
  ticker?: string;
  showcase?: boolean;
}) {
  const toast = useToast();
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [horizons, setHorizons] = useState<HorizonStats["horizons"]>({});
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getMemoryStats(ticker)
      .then((s) => {
        setStats(s);
        setFailed(false);
      })
      .catch(() => {
        setStats(null);
        setFailed(true);
      });
    if (!showcase) return;
    getHorizonStats(ticker)
      .then((h) => setHorizons(h.horizons ?? {}))
      .catch(() => setHorizons({}));
  }, [ticker, showcase]);

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
  // 단 showcase(랜딩)에서는 이게 제품의 첫 문장이라 빈 상태도 정직하게 보여준다.
  if (!showcase && (!stats || (stats.total === 0 && stats.validated === 0))) return null;

  const validated = stats?.validated ?? 0;

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
          className="btn-ghost min-h-0 flex items-center gap-1.5 px-3 py-1.5 text-sm disabled:opacity-50"
          title="7일 이상 지난 분석을 현재가와 비교해 적중 여부 채우기"
        >
          <ArrowsClockwise size={14} className={busy ? "animate-spin" : ""} />
          {busy ? "검증 중…" : "결과 검증"}
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="누적 분석" value={stats ? `${stats.total}건` : "—"} />
        <Tile label="검증 완료" value={stats ? `${validated}건` : "—"} />
        <Tile
          label="적중률"
          value={stats && validated > 0 ? `${stats.accuracy_pct}%` : "—"}
          tone={
            !stats || validated === 0 ? undefined : stats.accuracy_pct >= 50 ? "up" : "down"
          }
        />
        <Tile
          label="평균 수익률"
          value={
            stats && validated > 0
              ? `${stats.avg_return_pct >= 0 ? "+" : ""}${stats.avg_return_pct}%`
              : "—"
          }
          tone={
            !stats || validated === 0 ? undefined : stats.avg_return_pct >= 0 ? "up" : "down"
          }
        />
      </div>

      {showcase && (
        <div className="mt-4 border-t border-line/60 pt-4">
          <div className="mb-2 font-mono-spec text-[10px] uppercase tracking-widest text-muted">
            시간축별 적중률 · Horizon Accuracy
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {HORIZONS.map(([key, label]) => {
              // n이 0이면 적중률 필드는 의미가 없다 → 숫자로 찍지 않는다.
              const h = horizons[key];
              const ok = h && h.n > 0 ? h : null;
              return (
                <Tile
                  key={key}
                  label={label}
                  value={ok ? `${ok.accuracy_pct}%` : "수집 중"}
                  sub={
                    ok
                      ? `표본 ${ok.n}건 · 평균 ${ok.avg_return_pct >= 0 ? "+" : ""}${ok.avg_return_pct}%`
                      : "검증 표본 0건"
                  }
                  tone={ok ? (ok.accuracy_pct >= 50 ? "up" : "down") : undefined}
                />
              );
            })}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            {failed
              ? "검증 기록을 불러오지 못했습니다. 백엔드(:8000) 연결을 확인하세요."
              : validated === 0
                ? "아직 채점된 전망이 없습니다. 전망은 먼저 기록만 되고, 예측 기간이 지난 뒤 실제 주가와 대조해 적중 여부가 채워집니다. 위 [결과 검증] 버튼으로 직접 채점을 돌릴 수 있습니다."
                : "적중률이 낮은 구간에서는 다음 전망의 자신감(신뢰도)을 그만큼 낮춰서 표시합니다."}
          </p>
        </div>
      )}
    </Card>
  );
}

function Tile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "up" | "down";
}) {
  const color = tone === "up" ? "text-positive" : tone === "down" ? "text-negative" : "text-fg";
  return (
    <div className="rounded-2xl border border-line bg-[var(--ink-2)]/40 px-4 py-3">
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 font-display text-lg font-semibold ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 font-mono-spec text-[10px] text-muted">{sub}</div>}
    </div>
  );
}
