"use client";

// react-force-graph-2d는 canvas/window에 의존하므로 SSR 비활성 동적 임포트.

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LinkObject, NodeObject } from "react-force-graph-2d";
import type { GraphNode, GraphSnapshot } from "@/lib/api";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => <p className="text-sm text-muted">그래프 로딩 중…</p>,
});

const NODE_COLOR = "#60a5fa";
const NODE_HI = "#ffffff";

export default function GraphView({
  data,
  highlight = [],
}: {
  data: GraphSnapshot;
  highlight?: string[];
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const hi = useMemo(() => new Set(highlight), [highlight]);

  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>();
    data.nodes.forEach((n) => m.set(n.id, n));
    return m;
  }, [data]);

  useEffect(() => {
    const update = () => {
      if (wrapRef.current) setWidth(wrapRef.current.clientWidth);
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return (
    <div ref={wrapRef} className="w-full">
      <div className="relative overflow-hidden rounded-lg border border-line bg-[var(--ink-2)]">
        <ForceGraph2D
          graphData={data}
          width={width}
          height={520}
          backgroundColor="rgba(0,0,0,0)"
          // 시뮬레이션을 빨리 식혀 CPU 점유를 끊는다(기본 15s 연속 계산 → 정지).
          cooldownTicks={80}
          warmupTicks={20}
          // 기본 렌더(커스텀 캔버스 X)라 정지 후 재페인트가 없어 가볍다.
          nodeRelSize={4}
          nodeColor={(n: NodeObject) =>
            hi.has(String(n.id)) ? NODE_HI : NODE_COLOR
          }
          nodeVal={(n: NodeObject) => (hi.has(String(n.id)) ? 3 : 1)}
          nodeLabel={(n: NodeObject) =>
            `${n.id} (${(n as { group?: string }).group ?? ""})`
          }
          linkColor={() => "rgba(255,255,255,0.15)"}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          // 관계명은 hover 툴팁으로만(매 프레임 캔버스 렌더 제거).
          linkLabel={(l: LinkObject) => (l as { rel?: string }).rel ?? ""}
          onNodeClick={(n: NodeObject) =>
            setSelected(nodeById.get(String(n.id)) ?? null)
          }
        />

        {selected && (
          <div className="absolute right-3 top-3 max-h-[480px] w-64 overflow-auto rounded-lg border border-line bg-[var(--ink-1)]/95 p-3 text-xs shadow-lg backdrop-blur">
            <div className="mb-2 flex items-start justify-between gap-2">
              <span className="text-[10px] uppercase tracking-wider text-muted">
                {selected.group}
              </span>
              <button
                onClick={() => setSelected(null)}
                className="text-muted hover:text-fg"
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
            <p className="mb-2 break-words text-sm font-medium text-fg">
              {selected.id}
            </p>
            {selected.props && Object.keys(selected.props).length > 0 ? (
              <dl className="space-y-1">
                {Object.entries(selected.props).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="shrink-0 text-muted">{k}</dt>
                    <dd className="break-words text-fg">{String(v)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-muted">상세 속성이 없습니다.</p>
            )}
          </div>
        )}
      </div>
      <p className="mt-1.5 text-[11px] text-muted">
        노드에 마우스를 올리면 이름·관계명, 클릭하면 상세정보가 보입니다.
      </p>
    </div>
  );
}
