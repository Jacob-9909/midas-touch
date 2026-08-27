"use client";

/** 세그먼트 탭 — 앱 전역에서 하나의 규격만 쓰게 하는 공용 컴포넌트.
 *
 * 이전에는 stocks·chat·cheongyak·NavBar가 같은 비주얼을 제각각 복붙하고 있었고
 * 활성 배경 투명도조차 /20과 /15로 갈라져 있었다. 터미널 규격(globals.css):
 * 인셋 트랙(ink-2) + pill 버튼, 활성만 골드 도장(15%). */
import { useId, type ReactNode, type KeyboardEvent } from "react";
import { motion, useReducedMotion } from "motion/react";

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
  const layoutId = useId();
  const reduce = useReducedMotion();

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const currentIndex = tabs.findIndex((t) => t.id === active);
    if (currentIndex === -1) return;

    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = (currentIndex + 1) % tabs.length;
      onChange(tabs[nextIndex].id);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
      onChange(tabs[prevIndex].id);
    } else if (e.key === "Home") {
      e.preventDefault();
      onChange(tabs[0].id);
    } else if (e.key === "End") {
      e.preventDefault();
      onChange(tabs[tabs.length - 1].id);
    }
  };

  return (
    <div
      role="tablist"
      onKeyDown={handleKeyDown}
      className={`flex gap-1 rounded-[var(--r-pill)] border border-line bg-[var(--ink-2)] p-1 ${className}`}
    >
      {tabs.map((t) => {
        const is = t.id === active;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={is}
            tabIndex={is ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={`relative flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-[var(--r-pill)] px-3 py-1.5 font-mono-spec text-xs outline-none transition-all duration-150 active:scale-[0.98] ${
              is
                ? "font-semibold text-accent"
                : "text-muted hover:text-fg"
            }`}
          >
            {is && (
              <motion.span
                layoutId={reduce ? undefined : `segmented-tab-${layoutId}`}
                className="absolute inset-0 rounded-[inherit] border border-accent/40 bg-accent/15"
                transition={{ type: "spring", bounce: 0.15, duration: 0.3 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-1.5">
              {t.icon}
              {t.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
