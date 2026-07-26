"use client";

import { KOREA_VIEWBOX, PROVINCES, type Province } from "./korea-geo";

const [, , VW, VH] = KOREA_VIEWBOX.split(" ").map(Number);

// 공고 수 → 채움 농도 (0건은 비활성 톤).
function fill(count: number, active: boolean): string {
  if (active) return "color-mix(in srgb, var(--accent) 55%, transparent)";
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
  selected,
  onSelect,
}: {
  counts: Record<string, number>;
  selected: string | null;
  onSelect: (short: string | null) => void;
}) {
  const focused = PROVINCES.find((p) => p.short === selected) ?? null;
  const k = focused ? Math.min(VW / (focused.bbox[2] * 1.24), VH / (focused.bbox[3] * 1.24)) : 1;

  return (
    <svg
      viewBox={KOREA_VIEWBOX}
      className="h-auto w-full max-w-[320px] select-none"
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
          return (
            <path
              key={p.code}
              d={p.d}
              role="button"
              tabIndex={0}
              aria-label={`${p.full} 공고 ${count}건`}
              aria-pressed={active}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(active ? null : p.short);
              }}
              onKeyDown={(e) => {
                if (e.key !== "Enter" && e.key !== " ") return;
                e.preventDefault();
                onSelect(active ? null : p.short);
              }}
              className="cursor-pointer outline-none transition-[fill,opacity] duration-300 hover:brightness-125 focus-visible:brightness-125"
              style={{
                fill: fill(count, active),
                stroke: active ? "var(--accent)" : "var(--line)",
                strokeWidth: (active ? 2.5 : 1.2) / k,
                opacity: selected && !active ? 0.35 : 1,
              }}
            />
          );
        })}
      </g>
    </svg>
  );
}
