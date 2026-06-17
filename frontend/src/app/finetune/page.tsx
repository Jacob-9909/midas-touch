"use client";

import { useState } from "react";
import { apiGet, apiPost, apiUpload, type JobState } from "@/lib/api";
import { Card, PageTitle } from "@/components/ui";
import { useToast } from "@/lib/toast";
import JobProgress from "@/components/JobProgress";

interface Triplet {
  query_text: string;
  positive_text: string;
  negative_text: string;
  query_type: string;
  margin: number;
}

interface DatasetPreview {
  sub_dir: string;
  train_count: number;
  eval_count: number;
  train_preview: Triplet[];
  eval_preview: Triplet[];
}

export default function FinetunePage() {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [uploadedName, setUploadedName] = useState<string | null>(null);
  const [subDir, setSubDir] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [busy, setBusy] = useState(false);

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const res = await apiUpload<{ filename: string; sub_dir: string }>(
        "/api/v1/finetune/upload",
        file,
      );
      setUploadedName(res.filename);
      setSubDir(res.sub_dir);
      setPreview(null);
      setJobId(null);
      toast(`업로드 완료: ${res.filename}`, "success");
    } catch (e) {
      toast(`업로드 실패: ${e instanceof Error ? e.message : e}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const startJob = async () => {
    if (!uploadedName) return;
    try {
      const res = await apiPost<{ job_id: string; sub_dir: string }>(
        "/api/v1/finetune/jobs",
        { filename: uploadedName },
      );
      setJobId(res.job_id);
      setSubDir(res.sub_dir);
      toast("파이프라인을 시작했습니다.", "info");
    } catch (e) {
      toast(`실행 실패: ${e instanceof Error ? e.message : e}`, "error");
    }
  };

  const loadPreview = async (job: JobState) => {
    if (job.status === "failed") {
      toast("파이프라인이 실패했습니다. 로그를 확인하세요.", "error");
      return;
    }
    if (job.status !== "succeeded" || !subDir) return;
    toast("데이터셋 생성 완료!", "success");
    try {
      const p = await apiGet<DatasetPreview>(
        `/api/v1/finetune/datasets?sub_dir=${encodeURIComponent(subDir)}`,
      );
      setPreview(p);
    } catch (e) {
      toast(`프리뷰 로드 실패: ${e instanceof Error ? e.message : e}`, "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle
        title="파인튜닝셋 생성"
        subtitle="금융 문서(PDF·TXT·MD)를 올리면 대조학습 triplet 데이터셋을 생성합니다."
      />

      <Card className="animate-rise">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".pdf,.txt,.md,.jsonl"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm text-muted file:mr-3 file:rounded-lg file:border file:border-line file:bg-transparent file:px-4 file:py-2 file:text-sm file:text-fg"
          />
          <button
            onClick={upload}
            disabled={!file || busy}
            className="btn-ghost px-4 py-2 text-sm disabled:opacity-40"
          >
            {busy ? "업로드 중…" : "업로드"}
          </button>
          {uploadedName && (
            <button onClick={startJob} className="btn-gold px-4 py-2 text-sm">
              파이프라인 실행 ▶
            </button>
          )}
        </div>
        {uploadedName && (
          <p className="mt-3 text-sm text-muted">
            업로드됨: <span className="text-fg">{uploadedName}</span>
          </p>
        )}
      </Card>

      {jobId && (
        <Card className="animate-rise">
          <h2 className="mb-3 text-sm font-medium text-fg">파이프라인 진행 상황</h2>
          <JobProgress
            jobId={jobId}
            endpoint="/api/v1/finetune/jobs"
            onDone={loadPreview}
          />
        </Card>
      )}

      {preview && (
        <Card className="animate-rise">
          <h2 className="mb-1 text-sm font-medium text-fg">생성된 데이터셋 프리뷰</h2>
          <p className="mb-4 text-xs text-muted">
            train {preview.train_count}건 · eval {preview.eval_count}건
          </p>
          <TripletTable rows={preview.train_preview} />
        </Card>
      )}
    </div>
  );
}

function TripletTable({ rows }: { rows: Triplet[] }) {
  if (rows.length === 0)
    return <p className="text-sm text-muted">표시할 행이 없습니다.</p>;
  return (
    <div className="scroll-thin max-h-[480px] overflow-auto rounded-lg border border-line">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-[var(--ink-2)] text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">쿼리 (anchor)</th>
            <th className="px-3 py-2 font-medium">positive</th>
            <th className="px-3 py-2 font-medium">hard-negative</th>
            <th className="px-3 py-2 font-medium">margin</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t, i) => (
            <tr key={i} className="border-t border-line/60 align-top">
              <td className="max-w-[220px] px-3 py-2 text-fg">
                {t.query_text}
                <div className="mt-0.5 text-[10px] text-muted">{t.query_type}</div>
              </td>
              <td className="max-w-[260px] px-3 py-2 text-positive">
                {truncate(t.positive_text)}
              </td>
              <td className="max-w-[260px] px-3 py-2 text-negative">
                {truncate(t.negative_text)}
              </td>
              <td className="px-3 py-2 font-mono text-gold">
                {Number(t.margin).toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function truncate(s: string, n = 160): string {
  return s.length > n ? s.slice(0, n) + "…" : s;
}
