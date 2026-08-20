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

const NODE_COLOR = "#c7a349";
const NODE_HI = "#ffffff";

// 엔티티 유형(group)별 색 — 다크 캔버스에서 읽히고 골드 브랜드와 충돌 않는 뮤트 팔레트.
// 많은 유형 순으로 앞에서부터 배정한다.
const GROUP_PALETTE = [
  "#c7a349", "#5eb0b7", "#9b8cff", "#e08aa8",
  "#7fb069", "#e0a458", "#6aa9e0", "#c98f6a",
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
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const hi = useMemo(() => new Set(highlight), [highlight]);

  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>();
    data.nodes.forEach((n) => m.set(n.id, n));
    return m;
  }, [data]);

  // 요약 인덱스용 집계: 총 엔티티/관계 수 + 엔티티 유형(group)별 개수(많은 순) + 유형별 색.
  const summary = useMemo(() => {
    const byGroup = new Map<string, number>();
    for (const n of data.nodes) byGroup.set(n.group, (byGroup.get(n.group) ?? 0) + 1);
    const groups = [...byGroup.entries()].sort((a, b) => b[1] - a[1]);
    const colorByGroup = new Map<string, string>();
    groups.forEach(([g], i) => colorByGroup.set(g, GROUP_PALETTE[i % GROUP_PALETTE.length]));
    const max = groups.length ? groups[0][1] : 1;
    return { total: data.nodes.length, links: data.links.length, groups, colorByGroup, max };
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
            hi.has(String(n.id))
              ? NODE_HI
              : (summary.colorByGroup.get((n as { group?: string }).group ?? "") ?? NODE_COLOR)
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

        {/* 요약 인덱스 — 우상단 기본 표시. 노드를 클릭하면 아래 상세 패널이 이 자리를 대신한다. */}
        {!selected && (
          <div className="absolute right-3 top-3 w-60 rounded-lg border border-line bg-[var(--ink-1)]/90 p-3 text-xs shadow-lg backdrop-blur">
            <div className="mb-1.5 flex items-baseline justify-between gap-2">
              <span className="text-[10px] uppercase tracking-wider text-muted">그래프 요약</span>
              <span className="font-mono-spec text-sm font-semibold text-accent">
                {summary.total}
                <span className="ml-1 text-[10px] font-normal text-muted">엔티티</span>
              </span>
            </div>
            <p className="mb-2.5 border-b border-line/50 pb-2 text-[11px] text-muted">
              관계 {summary.links}개 · 유형 {summary.groups.length}종
            </p>
            <div className="max-h-52 space-y-2 overflow-auto pr-0.5">
              {summary.groups.map(([g, c]) => {
                const color = summary.colorByGroup.get(g);
                return (
                  <div key={g} className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    <span
                      className="w-14 shrink-0 truncate text-fg"
                      title={g || "(미분류)"}
                    >
                      {g || "(미분류)"}
                    </span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-line/30">
                      <span
                        className="block h-full rounded-full"
                        style={{
                          width: `${Math.max(6, (c / summary.max) * 100)}%`,
                          backgroundColor: color,
                        }}
                      />
                    </span>
                    <span className="w-5 shrink-0 text-right font-mono-spec text-muted">
                      {c}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

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
