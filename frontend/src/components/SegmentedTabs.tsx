"use client";

/** 세그먼트 탭 — 앱 전역에서 하나의 규격만 쓰게 하는 공용 컴포넌트.
 *
 * 이전에는 stocks·chat·cheongyak·NavBar가 같은 비주얼을 제각각 복붙하고 있었고
 * 활성 배경 투명도조차 /20과 /15로 갈라져 있었다. 터미널 규격(globals.css):
 * 인셋 트랙(ink-2) + pill 버튼, 활성만 골드 도장(15%). */
import type { ReactNode } from "react";

export interface SegmentedTab<T extends string = string> {
  id: T;
  label: string;
  icon?: ReactNode;
}

export default function SegmentedTabs<T extends string>({
  tabs,
  active,
  onChange,
  className = "",
}: {
  tabs: readonly SegmentedTab<T>[];
  active: T;
  onChange: (id: T) => void;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={`flex gap-1 rounded-[var(--r-pill)] border border-line bg-[var(--ink-2)] p-1 ${className}`}
    >
      {tabs.map((t) => {
        const is = t.id === active;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={is}
            onClick={() => onChange(t.id)}
            className={`flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-[var(--r-pill)] border px-3 py-1.5 font-mono-spec text-xs transition-colors duration-150 ${
              is
                ? "border-accent/40 bg-accent/15 font-semibold text-accent"
                : "border-transparent text-muted hover:bg-surface hover:text-fg"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
