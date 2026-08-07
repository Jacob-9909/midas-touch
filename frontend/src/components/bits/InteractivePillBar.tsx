"use client";

import { ReactNode } from "react";

export interface FilterPillItem {
  id: string;
  label: string;
  count?: number;
  tooltip?: string;
  icon?: ReactNode;
}

interface InteractivePillBarProps {
  items: FilterPillItem[];
  activeId: string;
  onChange: (id: string) => void;
  className?: string;
}

export default function InteractivePillBar({
  items,
  activeId,
  onChange,
  className = "",
}: InteractivePillBarProps) {
  return (
    <div className={`flex flex-wrap items-center gap-2 rounded-2xl border border-line-50 bg-[#090d16]/80 p-1.5 backdrop-blur-md ${className}`}>
      {items.map((item) => {
        const isActive = item.id === activeId;
        return (
          <div key={item.id} className="group relative">
            <button
              onClick={() => onChange(item.id)}
              className={`relative flex items-center gap-2 rounded-full px-4 py-2 text-xs font-mono-spec transition-all duration-200 ${
                isActive
                  ? "bg-accent/20 text-accent font-semibold border border-accent/50 shadow-[0_0_14px_rgba(212,175,96,0.25)]"
                  : "text-muted hover:text-fg hover:bg-surface/80 border border-transparent"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.count !== undefined && (
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-mono ${isActive ? "bg-accent/30 text-accent" : "bg-line/40 text-muted"}`}>
                  {item.count}
                </span>
              )}
            </button>

            {/* Rich Hover Explanation Tooltip */}
            {item.tooltip && (
              <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 opacity-0 transition-all duration-200 group-hover:opacity-100 z-50 w-48 rounded-lg border border-line-50 bg-[#0c1220]/95 p-2 text-center text-[11px] text-muted shadow-lg backdrop-blur-md">
                {item.tooltip}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
