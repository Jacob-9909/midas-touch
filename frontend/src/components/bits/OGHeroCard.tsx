"use client";

import { ReactNode } from "react";
import ShinyText from "./ShinyText";

interface OGHeroCardProps {
  categoryTag: string;
  title: string;
  subtitle: string;
  metrics?: Array<{ label: string; value: string; delta?: string; isPositive?: boolean }>;
  actions?: ReactNode;
  badgeContent?: ReactNode;
  className?: string;
}

export default function OGHeroCard({
  categoryTag,
  title,
  subtitle,
  metrics,
  actions,
  badgeContent,
  className = "",
}: OGHeroCardProps) {
  return (
    <div className={`relative overflow-hidden rounded-3xl border border-line-50 bg-[#0c1220]/90 p-6 sm:p-8 shadow-2xl backdrop-blur-xl ${className}`}>
      {/* Background Ambient Mesh Light */}
      <div className="pointer-events-none absolute -top-24 -right-24 h-80 w-80 rounded-full bg-accent/15 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-24 h-80 w-80 rounded-full bg-emerald-500/10 blur-3xl" />

      <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-2xl space-y-3">
          <div className="flex items-center gap-3">
            <span className="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 font-mono-spec text-[11px] font-semibold uppercase tracking-widest text-accent shadow-[0_0_12px_rgba(212,175,96,0.2)]">
              [{categoryTag}]
            </span>
            {badgeContent}
          </div>

          <h1 className="font-display text-2xl font-bold tracking-tight text-fg sm:text-4xl">
            <ShinyText text={title} speed={5} className="bg-gradient-to-r from-fg via-fg/90 to-accent bg-clip-text" />
          </h1>
          <p className="text-xs font-sans leading-relaxed text-muted sm:text-sm">
            {subtitle}
          </p>

          {actions && <div className="pt-2 flex flex-wrap items-center gap-3">{actions}</div>}
        </div>

        {/* Metrics Grid Callout Panel */}
        {metrics && metrics.length > 0 && (
          <div className="grid grid-cols-2 gap-3 rounded-2xl border border-line/40 bg-surface/60 p-4 backdrop-blur-md lg:w-80">
            {metrics.map((m, idx) => (
              <div key={idx} className="space-y-1">
                <span className="font-mono-spec text-[10px] text-muted uppercase">{m.label}</span>
                <div className="font-mono text-base font-bold text-fg sm:text-lg">{m.value}</div>
                {m.delta && (
                  <span className={`text-[10px] font-semibold ${m.isPositive ? "text-emerald-400" : "text-rose-400"}`}>
                    {m.isPositive ? "▲" : "▼"} {m.delta}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
