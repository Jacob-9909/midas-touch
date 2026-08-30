"use client";

import { useState } from "react";
import { KOREA_VIEWBOX, PROVINCES, type Province } from "./korea-geo";

const [, , VW, VH] = KOREA_VIEWBOX.split(" ").map(Number);

// 공고 수 → 채움 농도 (0건은 비활성 톤).
function fill(count: number, active: boolean, hovered: boolean): string {
  if (active) return "color-mix(in srgb, var(--accent) 55%, transparent)";
  if (hovered) return "color-mix(in srgb, var(--accent) 40%, transparent)";
  if (count === 0) return "var(--ink-2)";
  const pct = count >= 6 ? 34 : count >= 3 ? 22 : 12;
  return `color-mix(in srgb, var(--accent) ${pct}%, transparent)`;
}

// 선택 시도의 bbox 를 12% 패딩 주고 화면에 꽉 채우는 transform.
function focusTransform(p: Province | null): string {
  if (!p) return "translate(0px, 0px) scale(1)";
  const [x, y, w, h] = p.bbox;
  const k = Math.min(VW / (w * 1.24), VH / (h * 1.24));
  return `translate(${VW / 2 - (x + w / 2) * k}px, ${VH / 2 - (y + h / 2) * k}px) scale(${k})`;
}

export default function KoreaMap({
  counts,
  total,
  selected,
  onSelect,
}: {
  counts: Record<string, number>;
  /** 전체 공고 수. counts 를 합치면 안 된다 — 지역명·주소가 두 시도에 걸리는 공고는
   *  두 번 세어져 바로 위 KPI 카드("전체 N건")와 어긋난 수가 찍힌다(실측 108 vs 109). */
  total: number;
  selected: string | null;
  onSelect: (short: string | null) => void;
}) {
  const [hovered, setHovered] = useState<Province | null>(null);
  const focused = PROVINCES.find((p) => p.short === selected) ?? null;
  const k = focused ? Math.min(VW / (focused.bbox[2] * 1.24), VH / (focused.bbox[3] * 1.24)) : 1;

  const currentProvince = hovered ?? focused;
  const currentCount = currentProvince
    ? counts[currentProvince.short] ?? 0
    : total;

  return (
    <div className="flex flex-col items-center">
      <svg
        viewBox={KOREA_VIEWBOX}
        className="h-auto w-full max-w-[320px] select-none cursor-pointer"
        role="group"
        aria-label="시도별 청약 공고 지도"
        onClick={() => onSelect(null)}
      >
        <g
          style={{
            transform: focusTransform(focused),
            transformOrigin: "0 0",
            transition: "transform 0.5s var(--ease-out)",
          }}
        >
          {PROVINCES.map((p) => {
            const count = counts[p.short] ?? 0;
            const active = p.short === selected;
            const isHovered = hovered?.short === p.short;
            return (
              <path
                key={p.code}
                d={p.d}
                role="button"
                tabIndex={0}
                aria-label={`${p.full} 공고 ${count}건`}
                aria-pressed={active}
                onMouseEnter={() => setHovered(p)}
                onMouseLeave={() => setHovered(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(active ? null : p.short);
                }}
                onKeyDown={(e) => {
                  if (e.key !== "Enter" && e.key !== " ") return;
                  e.preventDefault();
                  onSelect(active ? null : p.short);
                }}
                className="cursor-pointer outline-none transition-[fill,opacity] duration-200"
                style={{
                  fill: fill(count, active, isHovered),
                  stroke: active || isHovered ? "var(--accent)" : "var(--line)",
                  strokeWidth: (active || isHovered ? 2.5 : 1.2) / k,
                  opacity: selected && !active && !isHovered ? 0.35 : 1,
                }}
              />
            );
          })}
        </g>
      </svg>

      {/* ── 지도 하단 인터랙티브 피드백 뱃지 ── */}
      <div className="mt-2.5 flex w-full max-w-[320px] items-center justify-between rounded-xl border border-line bg-surface/60 px-3 py-1.5 text-xs shadow-soft backdrop-blur-sm">
        <span className="font-semibold text-fg">
          {currentProvince ? currentProvince.full : "전국 전체"}
        </span>
        <span className="font-mono-spec text-[11px] font-semibold text-accent">
          공고 {currentCount}건
          {selected && !hovered && " (선택됨)"}
        </span>
      </div>
    </div>
  );
}
