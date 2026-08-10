"use client";

import { useMemo } from "react";
import PulseDot from "./PulseDot";
import { ArrowClockwise, CheckCircle, Warning, Cpu } from "@phosphor-icons/react";

export type SyncState = "live" | "syncing" | "idle" | "error" | "training";

interface LiveSyncBadgeProps {
  state: SyncState;
  label?: string;
  latencyMs?: number;
  lastUpdated?: string;
  showDetailsOnHover?: boolean;
  className?: string;
}

export default function LiveSyncBadge({
  state,
  label,
  latencyMs,
  lastUpdated,
  showDetailsOnHover = true,
  className = "",
}: LiveSyncBadgeProps) {
  const config = useMemo(() => {
    switch (state) {
      case "live":
        return { color: "positive" as const, defaultLabel: "LIVE SYNC", Icon: CheckCircle };
      case "syncing":
        return { color: "accent" as const, defaultLabel: "SYNCING", Icon: ArrowClockwise };
      case "training":
        return { color: "accent" as const, defaultLabel: "TRAINING", Icon: Cpu };
      case "error":
        return { color: "negative" as const, defaultLabel: "DISCONNECTED", Icon: Warning };
      default:
        return { color: "neutral" as const, defaultLabel: "IDLE", Icon: CheckCircle };
    }
  }, [state]);

  return (
    <div className={`group relative inline-flex items-center gap-2 rounded-full border border-line-50 bg-surface/70 px-3 py-1 text-xs font-mono-spec backdrop-blur-md transition-all hover:border-accent/40 ${className}`}>
      <PulseDot color={config.color} size="sm" />
      <span className="font-semibold uppercase tracking-wider text-fg/90">
        {label || config.defaultLabel}
      </span>

      {latencyMs !== undefined && (
        <span className="border-l border-line/60 pl-2 text-[10px] text-muted">
          {latencyMs}ms
        </span>
      )}

      {/* Hover Card / Tooltip */}
      {showDetailsOnHover && (
        <div className="pointer-events-none absolute top-full left-1/2 mt-2 -translate-x-1/2 opacity-0 transition-all duration-200 group-hover:opacity-100 z-50 w-48 rounded-lg border border-line-50 bg-[#0c1220]/95 p-2.5 text-[11px] shadow-xl backdrop-blur-md">
          <div className="flex items-center justify-between text-muted pb-1 border-b border-line/40">
            <span>상태</span>
            <span className="font-bold text-fg uppercase">{state}</span>
          </div>
          {lastUpdated && (
            <div className="flex items-center justify-between text-muted pt-1">
              <span>최종 동기화</span>
              <span className="font-mono">{lastUpdated}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
