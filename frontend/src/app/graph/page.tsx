"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useReducedMotion } from "motion/react";
import { errMsg } from "@/lib/async";
import { MagnifyingGlass, ArrowUp } from "@phosphor-icons/react";
import {
  apiGet,
  apiPost,
  type GraphSnapshot,
  type QueryResponse,
} from "@/lib/api";
import { Card, PageTitle } from "@/components/ui";
import { MOCK_GRAPH, withMock } from "@/lib/mock-data";
import { useToast } from "@/lib/toast";
import GraphView from "@/components/GraphView";

// WebGL은 서버에서 못 돈다. 이 페이지가 앱의 유일한 WebGL 캔버스를 소유한다.
const Radar = dynamic(() => import("@/components/bits/Radar"), { ssr: false });

function RadarSweep() {
  return (
    <Radar
      // scale이 클수록 좌표가 커져 원이 작아진다. 1.0이 정사각 컨테이너를 꽉 채우는 값.
      scale={1.0}
      ringCount={5}
      spokeCount={8}
      ringThickness={0.05}
      spokeThickness={0.008}
      sweepSpeed={0.5}
      sweepWidth={2.2}
      falloff={1.6}
      brightness={1.0}
      enableMouseInteraction={false}
    />
  );
}

export default function GraphPage() {
  const toast = useToast();
  const reduceMotion = useReducedMotion();
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [snapLoading, setSnapLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<QueryResponse | null>(null);
  const [asking, setAsking] = useState(false);

  const loadSnapshot = async () => {
    setSnapLoading(true);
    try {
      const s = await withMock(
        apiGet<GraphSnapshot>("/api/v1/graph/snapshot?limit=150"),
        MOCK_GRAPH,
        "그래프 스냅샷",
      );
      setSnapshot(s);
      if (s.nodes.length === 0) toast("그래프가 비어 있습니다. 챗봇 지식베이스 패널에서 문서를 반영하세요.", "info");
    } catch (e) {
      toast(`스냅샷 로드 실패: ${errMsg(e)}`, "error");
    } finally {
      setSnapLoading(false);
    }
  };

  const ask = async () => {
    if (!query.trim() || asking) return;
    setAsking(true);
    setAnswer(null);
    try {
      const res = await apiPost<QueryResponse>("/api/v1/query", {
        query: query.trim(),
      });
      setAnswer(res);
    } catch (e) {
      toast(`질의 실패: ${errMsg(e)}`, "error");
    } finally {
      setAsking(false);
    }
  };

  const highlight = answer
    ? Array.from(
        new Set(
          answer.subgraph_triplets.flatMap((t) => {
            const m = t.match(/\(([^:]+):/g);
            return m ? m.map((x) => x.slice(1, -1)) : [];
          }),
        ),
      )
    : [];

  return (
    <main className="mx-auto max-w-[1200px] space-y-6 px-6 py-[72px]">
      <PageTitle
        eyebrow="Knowledge Graph"
        title="지식그래프 — 근거 추적"
        subtitle="챗봇 답변의 법령 근거(graph_rag)를 그리는 시각 백엔드입니다. 구조를 탐색하고 GraphRAG로 근거 서브그래프를 질의하세요."
      />

      {/* 문서 인입 동선 안내 — 업로드·그래프 반영은 챗 지식베이스 패널이 단일 입구다(여기엔 빌드 콘솔을 두지 않는다). */}
      <Card className="animate-rise">
        <p className="text-xs leading-relaxed text-muted">
          <span className="font-medium text-fg">문서 추가·그래프 반영</span>은 챗봇 화면의{" "}
          <span className="text-accent">지식베이스 패널</span>에서 합니다 — 업로드 → 임베딩 → 그래프
          반영이 한 곳에서 이어집니다. 이 페이지는 그렇게 반영된 그래프를 <strong>탐색·질의</strong>하는
          근거 추적 면입니다.
        </p>
      </Card>

      {/* 스냅샷 시각화 */}
      <Card className="animate-rise">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-fg">그래프 구조</h2>
          <button
            onClick={loadSnapshot}
            disabled={snapLoading}
            className="btn-ghost px-4 py-1.5 text-sm disabled:opacity-40"
          >
            {snapLoading ? "불러오는 중…" : snapshot ? "새로고침" : "스냅샷 불러오기"}
          </button>
        </div>
        {snapshot ? (
          snapshot.nodes.length === 0 ? (
            <p className="text-sm text-muted">
              그래프가 비어 있습니다. 챗봇 지식베이스 패널에서 문서를 반영하세요.
            </p>
          ) : (
            <>
              <p className="mb-2 text-xs text-muted">
                노드 {snapshot.nodes.length} · 관계 {snapshot.links.length}
                {highlight.length > 0 && " · 흰 테두리 = RAG 근거 노드"}
              </p>
              <GraphView data={snapshot} highlight={highlight} />
            </>
          )
        ) : (
          // 빈 상태 = "스캔 대기". 레이더 스윕이 그 상태를 그대로 말해준다.
          // 텍스트 뒤에 깔면 링이 글자를 관통해 읽기를 망치므로, 계기판처럼 분리해 나란히 둔다.
          // reduced-motion이면 캔버스 없이 안내 문구만 남는다.
          <div className="flex flex-col items-center gap-6 rounded-lg border border-line/50 bg-[var(--ink)] px-6 py-10 sm:flex-row sm:justify-center sm:gap-10">
            {!reduceMotion && (
              <div className="h-36 w-36 shrink-0 [mask-image:radial-gradient(closest-side,black_60%,transparent_100%)]">
                <RadarSweep />
              </div>
            )}
            <div className="text-center sm:text-left">
              <span className="font-mono-spec text-[10px] uppercase tracking-[0.22em] text-accent">
                Standing by · 스캔 대기
              </span>
              <p className="mt-2 text-sm text-muted">
                버튼을 눌러 Neo4j 그래프 스냅샷을 시각화하세요.
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* GraphRAG 질의 */}
      <Card className="animate-rise">
        <h2 className="mb-3 text-sm font-medium text-fg">GraphRAG 질의</h2>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="예: 1세대 1주택 양도소득세 비과세 요건은?"
            className="field flex-1 px-4 py-2.5 text-sm"
          />
          <button
            onClick={ask}
            disabled={asking || !query.trim()}
            className="btn-accent flex items-center gap-1.5 px-5 py-2.5 text-sm disabled:opacity-40"
          >
            <MagnifyingGlass weight="bold" size={15} />
            {asking ? "조회 중…" : "질의"}
          </button>
        </div>

        {answer && (
          <div className="mt-5 space-y-4">
            <div className="whitespace-pre-wrap rounded-lg border border-line bg-[var(--ink-2)] p-4 text-sm leading-relaxed">
              {answer.response}
            </div>
            {answer.subgraph_triplets.length > 0 && (
              <div>
                <h3 className="mb-1 text-xs font-medium uppercase tracking-[0.18em] text-muted">
                  근거 그래프 관계망
                </h3>
                <div className="space-y-1 rounded-lg border border-line bg-[var(--ink-2)] p-3 font-mono text-xs text-muted">
                  {answer.subgraph_triplets.map((t, i) => (
                    <div key={i}>{t}</div>
                  ))}
                </div>
                <p className="mt-2 flex items-center gap-1 text-xs text-muted">
                  <ArrowUp size={13} />
                  위 그래프 스냅샷을 불러오면 이 근거 노드들이 강조됩니다.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>
    </main>
  );
}
