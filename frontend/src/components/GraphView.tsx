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

// 5대 핵심 도메인 시맨틱 팔레트 (Neon Ledger 디자인 시스템 연동)
export interface NodeCategory {
  id: string;
  label: string;
  color: string;
}

export const NODE_CATEGORIES: NodeCategory[] = [
  { id: "tax", label: "세법 / 세율 규정", color: "#6c5cff" },
  { id: "legal", label: "법령 조문 / 근거", color: "#faad13" },
  { id: "asset", label: "부동산 / 자산 유형", color: "#05c168" },
  { id: "condition", label: "감면 / 공제 / 요건", color: "#06b6d4" },
  { id: "household", label: "가구 / 기간 요건", color: "#ff4d67" },
  { id: "etc", label: "기타 엔티티", color: "#9094a8" },
];

export function getNodeCategory(rawGroup?: string): NodeCategory {
  if (!rawGroup) return NODE_CATEGORIES[5];
  const g = rawGroup.toUpperCase();
  if (
    g.includes("TAX") ||
    g.includes("RATE") ||
    g.includes("BRACKET") ||
    g.includes("AMOUNT") ||
    g.includes("BASE") ||
    g.includes("LIMIT") ||
    g.includes("보유기간")
  ) {
    if (g.includes("EXEMPT")) return NODE_CATEGORIES[3];
    return NODE_CATEGORIES[0];
  }
  if (
    g.includes("LEGAL") ||
    g.includes("LAW") ||
    g.includes("ARTICLE") ||
    g.includes("POLICY") ||
    g.includes("CLAUSE")
  ) {
    return NODE_CATEGORIES[1];
  }
  if (
    g.includes("HOUSING") ||
    g.includes("ASSET") ||
    g.includes("PORTFOLIO") ||
    g.includes("PROJECT") ||
    g.includes("REGION") ||
    g.includes("STOCK") ||
    g.includes("PROPERTY")
  ) {
    return NODE_CATEGORIES[2];
  }
  if (
    g.includes("CONDITION") ||
    g.includes("EXEMPT") ||
    g.includes("DEDUCTION") ||
    g.includes("INCOME") ||
    g.includes("REQUIREMENT")
  ) {
    return NODE_CATEGORIES[3];
  }
  if (
    g.includes("HOUSEHOLD") ||
    g.includes("FAMILY") ||
    g.includes("DATE") ||
    g.includes("TIMEFRAME") ||
    g.includes("COMPOSITE") ||
    g.includes("PERSON")
  ) {
    return NODE_CATEGORIES[4];
  }
  return NODE_CATEGORIES[5];
}

// canvas fillStyle 은 var() 를 파싱하지 못하므로 렌더 시점에 토큰 값을 실측해 치환한다.
function tokenColor(varName: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || fallback;
}

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
  const lineColor = tokenColor("--line", "#2a2d35");

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
        {/* 상단 5대 시맨틱 카테고리 범례 바 */}
        <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 border-b border-line bg-[var(--ink-1)] px-3.5 py-2 text-xs">
          <span className="text-[11px] font-bold text-muted shrink-0">도메인 범례:</span>
          {NODE_CATEGORIES.slice(0, 5).map((cat) => (
            <div key={cat.id} className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0 shadow-sm"
                style={{ backgroundColor: cat.color }}
              />
              <span className="text-[11px] font-medium text-muted">{cat.label}</span>
            </div>
          ))}
          {hi.size > 0 && (
            <div className="flex items-center gap-1.5 sm:ml-auto">
              <span className="h-2.5 w-2.5 rounded-full shrink-0 bg-white ring-2 ring-accent" />
              <span className="text-[11px] font-bold text-accent">RAG 근거 노드 ({hi.size})</span>
            </div>
          )}
        </div>

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
          nodeColor={(n: NodeObject) => {
            if (hi.has(String(n.id))) return "#ffffff";
            const group = (n as { group?: string }).group;
            return getNodeCategory(group).color;
          }}
          nodeVal={(n: NodeObject) => (hi.has(String(n.id)) ? 3.5 : 1.2)}
          nodeLabel={(n: NodeObject) =>
            `${n.id} (${(n as { group?: string }).group ?? ""})`
          }
          linkColor={() => lineColor}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          // 관계명은 hover 툴팁으로만(매 프레임 캔버스 렌더 제거).
          linkLabel={(l: LinkObject) => (l as { rel?: string }).rel ?? ""}
          onNodeClick={(n: NodeObject) =>
            setSelected(nodeById.get(String(n.id)) ?? null)
          }
        />

        {selected && (
          <div className="absolute right-3 top-12 max-h-[440px] w-64 overflow-auto rounded-lg border border-line bg-[var(--ink-1)] p-3 text-xs shadow-lg">
            <div className="mb-2 flex items-start justify-between gap-2">
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white"
                style={{ backgroundColor: getNodeCategory(selected.group).color }}
              >
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
        노드에 마우스를 올리면 이름과 관계명, 클릭하면 상세정보가 보입니다.
      </p>
    </div>
  );
}
