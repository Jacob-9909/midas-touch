"use client";

import { ReactNode } from "react";
import { Flame, Star, TrendUp } from "@phosphor-icons/react";
import ShinyText from "./ShinyText";

interface PopularCardProps {
  title: string;
  category: string;
  description?: string;
  rank?: number;
  votesCount?: string;
  stats?: Array<{ label: string; value: string }>;
  tags?: string[];
  action?: ReactNode;
  onClick?: () => void;
  className?: string;
}

export default function PopularCard({
  title,
  category,
  description,
  rank,
  votesCount = "998+",
  stats,
  tags,
  action,
  onClick,
  className = "",
}: PopularCardProps) {
  return (
    <div
      onClick={onClick}
      className={`popular-glow group relative flex h-full flex-col justify-between rounded-2xl border border-accent/40 bg-gradient-to-b from-[#0f172a]/90 via-[#0c1220]/80 to-[#070b14]/90 p-5 shadow-2xl backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-accent hover:shadow-[0_12px_40px_rgba(212,175,96,0.22)] ${
        onClick ? "cursor-pointer" : ""
      } ${className}`}
    >
      <div>
        {/* Header Badge Row */}
        <div className="flex items-center justify-between gap-2 pb-3">
          <div className="flex items-center gap-2">
            {rank && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent font-mono-spec text-[10px] font-bold text-slate-950 shadow-[0_0_8px_rgba(212,175,96,0.6)]">
                #{rank}
              </span>
            )}
            <span className="rounded-full border border-accent/40 bg-accent/15 px-2.5 py-0.5 font-mono-spec text-[10px] font-semibold uppercase tracking-wider text-accent">
              {category}
            </span>
          </div>

          <div className="flex items-center gap-1.5 rounded-full border border-orange-500/40 bg-orange-500/10 px-2.5 py-0.5 font-mono-spec text-[10px] font-bold text-orange-400">
            <Flame size={12} weight="fill" className="animate-bounce text-orange-400" />
            <span>POPULAR · {votesCount}</span>
          </div>
        </div>

        {/* Title & Description */}
        <h3 className="font-display text-lg font-bold text-fg group-hover:text-accent transition-colors duration-200">
          <ShinyText text={title} speed={4} className="group-hover:text-accent" />
        </h3>

        {description && (
          <p className="mt-2 text-xs leading-relaxed text-muted line-clamp-3 font-sans">
            {description}
          </p>
        )}

        {/* Stats Grid */}
        {stats && stats.length > 0 && (
          <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl border border-line/40 bg-surface/40 p-2.5 backdrop-blur-md">
            {stats.map((s, idx) => (
              <div key={idx} className="space-y-0.5">
                <span className="font-mono-spec text-[9px] uppercase text-muted">{s.label}</span>
                <div className="font-mono text-xs font-bold text-fg">{s.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tags */}
        {tags && tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <span
                key={t}
                className="rounded-full border border-line/40 bg-ink/60 px-2 py-0.5 text-[9px] font-mono-spec text-muted"
              >
                #{t}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Action Footer */}
      {action && (
        <div className="mt-5 border-t border-line/50 pt-3 flex items-center justify-between">
          <div className="flex items-center gap-1 text-[10px] text-accent font-mono-spec">
            <TrendUp size={14} />
            <span>HOT DEMAND</span>
          </div>
          {action}
        </div>
      )}
    </div>
  );
}
