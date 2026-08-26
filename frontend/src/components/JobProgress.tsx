"use client";

// job_id를 주기적으로 폴링해 진행률 바 + 로그 콘솔을 렌더한다.

import { useEffect, useRef, useState } from "react";
import { errMsg } from "@/lib/async";
import { apiGet, type JobState } from "@/lib/api";

export default function JobProgress({
  jobId,
  endpoint,
  onDone,
}: {
  jobId: string;
  endpoint: string; // 예: "/api/v1/graph/ingest/jobs" 또는 "/api/v1/graph/build/jobs"
  onDone?: (job: JobState) => void;
}) {
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const doneFired = useRef(false);

  useEffect(() => {
    doneFired.current = false;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const j = await apiGet<JobState>(`${endpoint}/${jobId}`);
        if (!active) return;
        setJob(j);
        setError(null);
        if (j.status === "running") {
          timer = setTimeout(poll, 2500);
        } else if (!doneFired.current) {
          doneFired.current = true;
          onDone?.(j);
        }
      } catch (e) {
        if (!active) return;
        setError(errMsg(e));
        timer = setTimeout(poll, 4000);
      }
    };
    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, endpoint]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [job?.logs]);

  if (error && !job)
    return <p className="text-sm text-negative">작업 조회 실패: {error}</p>;
  if (!job) return <p className="text-sm text-muted">작업 시작 중…</p>;

  const statusColor =
    job.status === "succeeded"
      ? "text-positive"
      : job.status === "failed"
        ? "text-negative"
        : "text-accent";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-mono text-muted">job {job.job_id}</span>
        <span className={statusColor}>
          {job.status} · {job.progress}%
        </span>
      </div>
      {/* fill은 scaleX(transform)로만 움직인다 — width 전이는 매 프레임 layout을 다시 계산한다.
          트랙의 overflow-hidden + square 끝이 pill 모양을 유지하므로 scale 왜곡이 보이지 않는다. */}
      <div className="h-2 w-full overflow-hidden rounded-full border border-line">
        <div
          className="h-full w-full origin-left transition-transform duration-300 ease-out"
          style={{
            transform: `scaleX(${Math.min(100, Math.max(0, job.progress)) / 100})`,
            background:
              job.status === "failed"
                ? "var(--negative)"
                : "linear-gradient(90deg, var(--accent-soft), var(--accent))",
          }}
        />
      </div>
      {job.error && <p className="text-sm text-negative">{job.error}</p>}
      <div
        ref={logRef}
        className="scroll-thin max-h-64 overflow-auto rounded-lg border border-line bg-[var(--ink-2)] p-3 font-mono text-xs leading-relaxed text-muted"
      >
        {job.logs.length === 0 ? (
          <span className="text-muted/60">로그 대기 중…</span>
        ) : (
          job.logs.map((l, i) => (
            <div key={i} className="whitespace-pre-wrap">
              {l}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
