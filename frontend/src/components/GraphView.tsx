"use client";

// react-force-graph-2d는 canvas/window에 의존하므로 SSR 비활성 동적 임포트.

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphSnapshot } from "@/lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => <p className="text-sm text-muted">그래프 로딩 중…</p>,
});

// 라벨(group)별 색상 팔레트
const COLORS = [
  "#fbbf24", "#34d399", "#60a5fa", "#f472b6",
  "#a78bfa", "#fb923c", "#22d3ee", "#facc15",
];

export default function GraphView({
  data,
  highlight = [],
}: {
  data: GraphSnapshot;
  highlight?: string[];
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const hi = useMemo(() => new Set(highlight), [highlight]);

  useEffect(() => {
    const update = () => {
      if (wrapRef.current) setWidth(wrapRef.current.clientWidth);
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const groups = useMemo(() => {
    const g = Array.from(new Set(data.nodes.map((n) => n.group)));
    return g;
  }, [data]);

  const colorFor = (group: string) =>
    COLORS[groups.indexOf(group) % COLORS.length];

  return (
    <div ref={wrapRef} className="w-full">
      <div className="mb-2 flex flex-wrap gap-2 text-xs">
        {groups.map((g) => (
          <span key={g} className="flex items-center gap-1 text-muted">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: colorFor(g) }}
            />
            {g}
          </span>
        ))}
      </div>
      <div className="overflow-hidden rounded-lg border border-line bg-[var(--ink-2)]">
        <ForceGraph2D
          graphData={data}
          width={width}
          height={520}
          backgroundColor="rgba(0,0,0,0)"
          linkColor={() => "rgba(255,255,255,0.18)"}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          nodeRelSize={5}
          nodeLabel={(n: { id?: string | number; group?: string }) =>
            `${n.id} (${n.group})`
          }
          nodeCanvasObject={(
            node: {
              id?: string | number;
              x?: number;
              y?: number;
              group?: string;
            },
            ctx: CanvasRenderingContext2D,
            scale: number,
          ) => {
            const label = String(node.id ?? "");
            const isHi = hi.has(label);
            const r = isHi ? 6 : 4;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
            ctx.fillStyle = colorFor(node.group ?? "Entity");
            ctx.fill();
            if (isHi) {
              ctx.strokeStyle = "#fff";
              ctx.lineWidth = 1.5 / scale;
              ctx.stroke();
            }
            if (scale > 1.2 || isHi) {
              const fontSize = Math.max(10 / scale, 2);
              ctx.font = `${fontSize}px sans-serif`;
              ctx.fillStyle = isHi ? "#fff" : "rgba(255,255,255,0.7)";
              ctx.fillText(label, (node.x ?? 0) + r + 1, (node.y ?? 0) + 3);
            }
          }}
        />
      </div>
    </div>
  );
}
