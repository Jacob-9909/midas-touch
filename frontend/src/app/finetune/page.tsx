"use client";

import { useState } from "react";
import { errMsg } from "@/lib/async";
import { Play, UploadSimple } from "@phosphor-icons/react";
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
  const [trainJobId, setTrainJobId] = useState<string | null>(null);
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
      toast(`업로드 실패: ${errMsg(e)}`, "error");
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
      toast(`실행 실패: ${errMsg(e)}`, "error");
    }
  };

  const startTrain = async () => {
    if (!uploadedName) return;
    try {
      const res = await apiPost<{ job_id: string }>(
        "/api/v1/finetune/train/jobs",
        { filename: uploadedName },
      );
      setTrainJobId(res.job_id);
      toast("LoRA 파인튜닝 학습을 시작했습니다.", "info");
    } catch (e) {
      toast(`학습 실행 실패: ${errMsg(e)}`, "error");
    }
  };

  const onTrainDone = (job: JobState) => {
    if (job.status === "failed") {
      toast("학습이 실패했습니다. 로그를 확인하세요.", "error");
      return;
    }
    if (job.status === "succeeded") {
      toast("학습 완료! 산출물: TRAINING_OUTPUT_DIR/final", "success");
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
      toast(`프리뷰 로드 실패: ${errMsg(e)}`, "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageTitle
        eyebrow="Fine-tune"
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
            className="btn-ghost flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-40"
          >
            <UploadSimple size={15} />
            {busy ? "업로드 중…" : "업로드"}
          </button>
          {uploadedName && (
            <button
              onClick={startJob}
              className="btn-accent flex items-center gap-1.5 px-4 py-2 text-sm"
            >
              <Play weight="fill" size={14} />
              파이프라인 실행
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
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium text-fg">생성된 데이터셋 프리뷰</h2>
            <button
              onClick={startTrain}
              className="btn-accent flex items-center gap-1.5 px-4 py-2 text-sm"
            >
              <Play weight="fill" size={14} />
              LoRA 파인튜닝 학습
            </button>
          </div>
          <p className="mb-4 text-xs text-muted">
            train {preview.train_count}건 · eval {preview.eval_count}건
          </p>
          <TripletTable rows={preview.train_preview} />
        </Card>
      )}

      {trainJobId && (
        <Card className="animate-rise">
          <h2 className="mb-3 text-sm font-medium text-fg">학습 진행 상황</h2>
          <JobProgress
            jobId={trainJobId}
            endpoint="/api/v1/finetune/jobs"
            onDone={onTrainDone}
          />
          <p className="mt-3 text-xs text-muted">
            학습 완료 후 적용: <code className="text-fg">.env</code>의{" "}
            <code className="text-fg">AGENT_EMBEDDING_MODEL</code>을 산출물 경로
            (<code className="text-fg">TRAINING_OUTPUT_DIR/final</code>)로 바꾸고 백엔드를 재시작하세요.
            단, persona/그래프 임베딩도 같은 모델로 재적재해야 검색 공간이 일치합니다.
          </p>
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
              <td className="px-3 py-2 font-mono text-accent">
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
