"use client";

import { useCallback, useEffect, useState } from "react";
import { errMsg } from "@/lib/async";
import { FileText, TrashSimple, UploadSimple, Sparkle, ArrowsClockwise } from "@phosphor-icons/react";
import {
  apiUpload,
  buildGraph,
  deleteRagDocument,
  ingestDocument,
  listRagDocuments,
  type JobState,
  type RagDocument,
} from "@/lib/api";
import { useToast } from "@/lib/toast";
import { Spinner } from "@/components/ui";
import JobProgress from "@/components/JobProgress";

/** 챗봇 좌측 지식베이스 패널: 반영된 문서 목록 + 파일 첨부→임베딩→그래프 반영. */
export default function KnowledgePanel() {
  const toast = useToast();
  const [docs, setDocs] = useState<RagDocument[] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [ingestJobId, setIngestJobId] = useState<string | null>(null);
  const [buildJobId, setBuildJobId] = useState<string | null>(null);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const res = await listRagDocuments();
      setDocs(res.documents);
    } catch (e) {
      toast(`문서 목록 로드 실패: ${errMsg(e)}`, "error");
    }
  }, [toast]);

  useEffect(() => {
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 문서 목록 fetch(외부 데이터 구독) */
    void loadDocs();
  }, [loadDocs]);

  // 파일 첨부 → 업로드 → 임베딩(emb_passages 적재) 잡 시작
  const uploadAndIngest = async () => {
    if (!file) return;
    setUploading(true);
    setIngestJobId(null);
    try {
      const up = await apiUpload<{ filename: string }>("/api/v1/graph/upload", file);
      const job = await ingestDocument(up.filename);
      setIngestJobId(job.job_id);
      setFile(null);
      toast(`임베딩 시작: ${up.filename}`, "info");
    } catch (e) {
      toast(`업로드/임베딩 실패: ${errMsg(e)}`, "error");
    } finally {
      setUploading(false);
    }
  };

  const removeDoc = async (source: string) => {
    if (!confirm(`"${source}"를 지식베이스에서 삭제할까요? 이미 임베딩된 단락이 모두 지워집니다.`)) return;
    setDeletingSource(source);
    try {
      await deleteRagDocument(source);
      toast(`"${source}"를 삭제했습니다.`, "success");
      await loadDocs();
    } catch (e) {
      toast(`삭제 실패: ${errMsg(e)}`, "error");
    } finally {
      setDeletingSource(null);
    }
  };

  const onIngestDone = (job: JobState) => {
    if (job.status === "failed") {
      toast("임베딩이 실패했습니다. 로그를 확인하세요.", "error");
      return;
    }
    toast("임베딩 완료! '그래프 반영'을 눌러 지식그래프에 반영하세요.", "success");
    void loadDocs();
  };

  const rebuild = async () => {
    setBuildJobId(null);
    try {
      const job = await buildGraph(-1);
      setBuildJobId(job.job_id);
      toast("지식그래프 반영을 시작했습니다.", "info");
    } catch (e) {
      toast(`그래프 반영 실패: ${errMsg(e)}`, "error");
    }
  };

  return (
    <div className="space-y-4">
      {/* 반영된 파일 */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-medium uppercase tracking-[0.14em] text-muted">
            반영된 파일
          </h3>
          <button
            onClick={loadDocs}
            className="flex h-6 w-6 items-center justify-center rounded-md text-muted transition hover:text-accent"
            aria-label="새로고침"
            title="새로고침"
          >
            <ArrowsClockwise size={14} />
          </button>
        </div>
        {docs === null ? (
          <p className="px-1 text-xs text-muted">불러오는 중…</p>
        ) : docs.length === 0 ? (
          <p className="px-1 text-xs text-muted">반영된 문서가 없습니다.</p>
        ) : (
          <ul className="space-y-1">
            {docs.map((d) => (
              <li
                key={d.source}
                className="group flex items-start gap-1.5 rounded-lg bg-[color-mix(in_srgb,var(--accent)_5%,transparent)] px-2 py-1.5"
              >
                <FileText size={14} className="mt-0.5 shrink-0 text-accent" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs text-fg" title={d.source}>
                    {d.source}
                  </div>
                  <div className="text-[10px] text-muted">{d.passages}개 단락</div>
                </div>
                <button
                  onClick={() => removeDoc(d.source)}
                  disabled={deletingSource === d.source}
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted opacity-80 sm:opacity-0 transition hover:text-negative sm:group-hover:opacity-100 disabled:opacity-40"
                  aria-label={`${d.source} 삭제`}
                  title="지식베이스에서 삭제"
                >
                  {deletingSource === d.source ? (
                    <Spinner className="h-3.5 w-3.5" />
                  ) : (
                    <TrashSimple size={14} />
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 파일 첨부 → 임베딩 */}
      <div className="border-t border-line pt-4">
        <h3 className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-muted">
          파일 추가
        </h3>
        <input
          type="file"
          accept=".pdf,.txt,.md,.jsonl"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="w-full text-xs text-muted file:mr-2 file:rounded-md file:border file:border-line file:bg-transparent file:px-2.5 file:py-1.5 file:text-xs file:text-fg"
        />
        <button
          onClick={uploadAndIngest}
          disabled={!file || uploading}
          className="btn-accent mt-2 flex w-full items-center justify-center gap-1.5 px-3 py-2 text-xs disabled:opacity-40"
        >
          {uploading ? <Spinner className="h-3.5 w-3.5" /> : <UploadSimple size={14} />}
          {uploading ? "업로드 중…" : "업로드 & 임베딩"}
        </button>
        {ingestJobId && (
          <div className="mt-3">
            <JobProgress
              jobId={ingestJobId}
              endpoint="/api/v1/graph/ingest/jobs"
              onDone={onIngestDone}
            />
          </div>
        )}
      </div>

      {/* 지식그래프 반영 */}
      <div className="border-t border-line pt-4">
        <button
          onClick={rebuild}
          className="btn-ghost flex w-full items-center justify-center gap-1.5 px-3 py-2 text-xs"
        >
          <Sparkle size={14} />
          지식그래프 반영 (재빌드)
        </button>
        <p className="mt-1.5 px-1 text-[10px] leading-relaxed text-muted">
          임베딩된 단락을 Neo4j 지식그래프에 반영합니다(챗 답변의 <span className="text-accent">graph_rag 근거</span>가 됨).
          새 문서 임베딩 후 한 번 실행하세요. 반영된 그래프는 <span className="text-fg">그래프</span> 화면에서 시각 추적할 수 있습니다.
        </p>
        <p className="mt-1.5 px-1 text-[10px] leading-relaxed text-warning">
          ⚠ 엔티티 추출(LLM)로 <span className="font-medium">수 분 소요</span>되며, 그동안 같은 LLM 자원을 공유하는
          챗 응답이 느려질 수 있습니다. 시연·발표 중에는 실행하지 마세요.
        </p>
        {buildJobId && (
          <div className="mt-3">
            <JobProgress jobId={buildJobId} endpoint="/api/v1/graph/build/jobs" />
          </div>
        )}
      </div>
    </div>
  );
}
