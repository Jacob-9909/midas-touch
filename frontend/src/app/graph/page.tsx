"use client";

import { useState } from "react";
import {
  apiGet,
  apiPost,
  type GraphSnapshot,
  type QueryResponse,
} from "@/lib/api";
import { Card, PageTitle } from "@/components/ui";
import { useToast } from "@/lib/toast";
import JobProgress from "@/components/JobProgress";
import GraphView from "@/components/GraphView";

export default function GraphPage() {
  const toast = useToast();
  const [limit, setLimit] = useState(40);
  const [buildJobId, setBuildJobId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<GraphSnapshot | null>(null);
  const [snapLoading, setSnapLoading] = useState(false);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<QueryResponse | null>(null);
  const [asking, setAsking] = useState(false);

  const startBuild = async () => {
    try {
      const res = await apiPost<{ job_id: string }>("/api/v1/graph/build/jobs", {
        limit,
      });
      setBuildJobId(res.job_id);
      toast("그래프 빌드를 시작했습니다.", "info");
    } catch (e) {
      toast(`빌드 실행 실패: ${e instanceof Error ? e.message : e}`, "error");
    }
  };

  const loadSnapshot = async () => {
    setSnapLoading(true);
    try {
      const s = await apiGet<GraphSnapshot>("/api/v1/graph/snapshot?limit=150");
      setSnapshot(s);
      if (s.nodes.length === 0) toast("그래프가 비어 있습니다. 먼저 빌드하세요.", "info");
    } catch (e) {
      toast(`스냅샷 로드 실패: ${e instanceof Error ? e.message : e}`, "error");
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
      toast(`질의 실패: ${e instanceof Error ? e.message : e}`, "error");
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
    <div className="space-y-6">
      <PageTitle
        title="지식그래프"
        subtitle="세법·금융 지식그래프를 빌드하고, 구조를 탐색하고, GraphRAG로 질의합니다."
      />

      {/* 빌드 */}
      <Card className="animate-rise">
        <h2 className="mb-3 text-sm font-medium text-fg">지식그래프 증분 빌드</h2>
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-muted">
            처리 단락 수
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="field ml-2 w-24 px-3 py-1.5 text-sm"
            />
          </label>
          <button onClick={startBuild} className="btn-gold px-4 py-2 text-sm">
            빌드 실행 ▶
          </button>
          <span className="text-xs text-muted">-1 입력 시 전체 처리</span>
        </div>
        {buildJobId && (
          <div className="mt-4">
            <JobProgress jobId={buildJobId} endpoint="/api/v1/graph/build/jobs" />
          </div>
        )}
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
              그래프가 비어 있습니다. 먼저 빌드를 실행하세요.
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
          <p className="text-sm text-muted">
            버튼을 눌러 Neo4j 그래프 스냅샷을 시각화하세요.
          </p>
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
            className="btn-gold px-5 py-2.5 text-sm disabled:opacity-40"
          >
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
                <p className="mt-2 text-xs text-muted">
                  ↑ 위 그래프 스냅샷을 불러오면 이 근거 노드들이 강조됩니다.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
