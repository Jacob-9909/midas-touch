"use client";

import { useEffect, useState } from "react";
import { errMsg } from "@/lib/async";
import { Play, UploadSimple } from "@phosphor-icons/react";
import { apiGet, apiPost, apiUpload, type JobState } from "@/lib/api";
import OGHeroCard from "@/components/bits/OGHeroCard";
import LiveSyncBadge from "@/components/bits/LiveSyncBadge";
import { Card } from "@/components/ui";
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

// 이미 DB에 적재된 대조학습 코퍼스 현황(업로드 없이도 표시).
interface CorpusStats {
  train_count: number;
  eval_count: number;
  query_count: number;
  passage_count: number;
  source_count: number;
  avg_margin: number;
  by_type: { query_type: string; count: number }[];
  train_preview: Triplet[];
}

function fmt(n: number | undefined): string {
  return (n ?? 0).toLocaleString();
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
  const [activeTab, setActiveTab] = useState<"ingest" | "train">("ingest");
  const [corpus, setCorpus] = useState<CorpusStats | null>(null);

  // 이미 구축해둔 코퍼스 현황은 진입 즉시 조회한다(업로드 전에도 빈 화면이 아니게).
  useEffect(() => {
    let alive = true;
    apiGet<CorpusStats>("/api/v1/finetune/corpus")
      .then((c) => alive && setCorpus(c))
      .catch(() => alive && setCorpus(null));
    return () => {
      alive = false;
    };
  }, []);

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
      toast(`문서 업로드 완료: ${res.filename}`, "success");
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
      toast("지식 인제스천 & 대조학습 파이프라인을 시작했습니다.", "info");
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
      toast("LoRA 파인튜닝 모델 학습을 시작했습니다.", "info");
    } catch (e) {
      toast(`학습 실행 실패: ${errMsg(e)}`, "error");
    }
  };

  const onTrainDone = (job: JobState) => {
    if (job.status === "failed") {
      toast("모델 학습이 실패했습니다. 로그를 확인하세요.", "error");
      return;
    }
    if (job.status === "succeeded") {
      toast("LoRA 모델 학습 완료! 산출물: TRAINING_OUTPUT_DIR/final", "success");
    }
  };

  const loadPreview = async (job: JobState) => {
    if (job.status === "failed") {
      toast("파이프라인 처리가 실패했습니다. 로그를 확인하세요.", "error");
      return;
    }
    if (job.status !== "succeeded" || !subDir) return;
    toast("지식 인제스천 및 대조학습 데이터셋 생성 완료!", "success");
    try {
      const p = await apiGet<DatasetPreview>(
        `/api/v1/finetune/datasets?sub_dir=${encodeURIComponent(subDir)}`,
      );
      setPreview(p);
      setActiveTab("train");
    } catch (e) {
      toast(`데이터셋 프리뷰 로드 실패: ${errMsg(e)}`, "error");
    }
  };

  return (
    <div className="space-y-6">
      {/* OGHeroCard Header */}
      <OGHeroCard
        categoryTag="MLOPS & MODEL TRAINING"
        title="금융 AI 파인튜닝 & 지식 파이프라인"
        subtitle="PDF, 보고서 문서에서 지식 데이터셋을 자동 추출하고, BGE-M3 대조학습 및 LoRA 파인튜닝으로 나만의 AI 투자 가이드를 생성합니다."
        badgeContent={<LiveSyncBadge state={busy ? "training" : "live"} label={busy ? "PROCESSING" : "ENGINE READY"} />}
        metrics={[
          { label: "RAG INGESTION", value: "BGE-M3 Hard Negative" },
          { label: "LORA ENGINE", value: "PyTorch & Accelerate" },
        ]}
      />

      {/* MLOps Status Summary Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="border border-line/60 bg-[#090d16] p-3.5 rounded-lg flex items-center gap-3">
          <div className="h-10 w-10 rounded bg-accent/15 border border-accent/30 flex items-center justify-center text-accent font-bold">
            RAG
          </div>
          <div>
            <div className="text-xs text-muted font-mono-spec">지식 베이스 (emb_passages)</div>
            <div className="text-sm font-semibold text-fg">
              {corpus
                ? `${fmt(corpus.passage_count)} 단락 · 문서 ${fmt(corpus.source_count)}종`
                : "집계 중…"}
            </div>
          </div>
        </div>
        <div className="border border-line/60 bg-[#090d16] p-3.5 rounded-lg flex items-center gap-3">
          <div className="h-10 w-10 rounded bg-positive/15 border border-positive/30 flex items-center justify-center text-positive font-bold">
            BGE
          </div>
          <div>
            <div className="text-xs text-muted font-mono-spec">대조학습 트리플렛 (BGE-M3 마이닝)</div>
            <div className="text-sm font-semibold text-fg">
              {corpus
                ? `${fmt(corpus.train_count + corpus.eval_count)}건 · train ${fmt(corpus.train_count)} / eval ${fmt(corpus.eval_count)}`
                : "집계 중…"}
            </div>
          </div>
        </div>
        <div className="border border-line/60 bg-[#090d16] p-3.5 rounded-lg flex items-center gap-3">
          <div className="h-10 w-10 rounded bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 font-bold">
            LoRA
          </div>
          <div>
            <div className="text-xs text-muted font-mono-spec">LLM 합성 쿼리 (anchor)</div>
            <div className="text-sm font-semibold text-fg">
              {corpus ? `${fmt(corpus.query_count)}건 생성 완료` : "집계 중…"}
            </div>
          </div>
        </div>
      </div>

      {/* Mode Selector Tabs (Swiss Sleek Pill Segmented Control) */}
      <div className="flex flex-wrap items-center gap-2 font-mono-spec text-xs bg-[#090d16]/80 p-1.5 rounded-full border border-line-50">

        <button
          onClick={() => setActiveTab("ingest")}
          className={`px-4 py-2 rounded-full font-semibold transition-all duration-200 ${
            activeTab === "ingest"
              ? "bg-accent/20 text-accent border border-accent/40 shadow-[0_0_12px_rgba(212,175,96,0.2)]"
              : "text-muted hover:text-fg border border-transparent"
          }`}
        >
          📚 1. 문서 지식 즉시 등록 (Instant RAG Ingestion)
        </button>
        <button
          onClick={() => setActiveTab("train")}
          className={`px-4 py-2 rounded-md font-semibold transition ${
            activeTab === "train"
              ? "bg-accent text-bg"
              : "bg-surface text-muted hover:text-fg"
          }`}
        >
          🎯 2. 대조학습 Triplets &amp; LoRA 파인튜닝
        </button>
      </div>

      {/* Tab 1: Instant RAG Ingestion */}
      {activeTab === "ingest" && (
        <Card className="animate-rise space-y-4">
          <div>
            <h2 className="text-base font-semibold text-fg flex items-center gap-2">
              <span>📚</span> 금융 문서 등록 &amp; RAG 인덱싱 파이프라인
            </h2>
            <p className="text-xs text-muted mt-1">
              증권사 리포트, 채권 개요서, 법률/세무 문서(PDF, TXT, MD, JSONL)를 업로드하면 실시간 텍스트 청킹(Chunking)을 거쳐 
              에이전트 챗봇 RAG 검색 테이블(<code className="text-fg font-mono">emb_passages</code>) 및 지식 그래프에 즉시 반영됩니다.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 border border-line/50 p-4 rounded-lg bg-[#080c14]">
            <input
              type="file"
              accept=".pdf,.txt,.md,.jsonl"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm text-muted file:mr-3 file:rounded-lg file:border file:border-line file:bg-transparent file:px-4 file:py-2 file:text-sm file:text-fg cursor-pointer"
            />
            <button
              onClick={upload}
              disabled={!file || busy}
              className="btn-ghost flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-40"
            >
              <UploadSimple size={15} />
              {busy ? "문서 업로드 중…" : "문서 파일 업로드"}
            </button>
            {uploadedName && (
              <button
                onClick={startJob}
                className="btn-accent flex items-center gap-1.5 px-4 py-2 text-sm"
              >
                <Play weight="fill" size={14} />
                지식 인제스천 &amp; 파이프라인 실행
              </button>
            )}
          </div>

          {uploadedName && (
            <p className="text-xs text-accent font-mono-spec">
              ✓ 업로드된 문서 파일: <span className="text-fg font-semibold">{uploadedName}</span>
            </p>
          )}
        </Card>
      )}

      {/* Tab 2: Contrastive Triplets & LoRA Fine-tuning */}
      {activeTab === "train" && (
        <Card className="animate-rise space-y-4">
          <div>
            <h2 className="text-base font-semibold text-fg flex items-center gap-2">
              <span>🎯</span> 금융 특화 LLM / Embedding 대조학습 (Triplets &amp; LoRA)
            </h2>
            <p className="text-xs text-muted mt-1">
              마이닝된 하드 네거티브(Hard Negative) <code className="text-fg font-mono">(Query, Positive, Negative)</code> 
              대조학습 셋으로 도메인 특화 금융 임베딩 모델 및 LLM LoRA 어댑터를 학습시킵니다.
            </p>
          </div>

          {!preview && !uploadedName && (
            <div className="p-4 border border-line/40 rounded-lg bg-[#080c14] text-xs text-muted">
              ℹ️ 아래는 지금까지 <span className="text-accent font-semibold">DB에 구축해둔 대조학습 코퍼스</span>입니다.
              새 문서를 반영하려면 <span className="text-accent font-semibold">&ldquo;📚 문서 지식 즉시 등록&rdquo;</span> 탭에서 업로드 후 파이프라인을 실행하세요.
            </div>
          )}

          {preview && (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line/40 pb-2">
                <div>
                  <h3 className="text-sm font-semibold text-fg">이번 문서에서 마이닝된 데이터셋 프리뷰</h3>
                  <p className="text-xs text-muted">
                    학습 데이터(train) <span className="text-accent font-bold">{preview.train_count}건</span> · 평가 데이터(eval) <span className="text-fg font-bold">{preview.eval_count}건</span>
                  </p>
                </div>
                <button
                  onClick={startTrain}
                  className="btn-accent flex items-center gap-1.5 px-4 py-2 text-sm"
                >
                  <Play weight="fill" size={14} />
                  LoRA 파인튜닝 모델 학습 개시
                </button>
              </div>
              <TripletTable rows={preview.train_preview} />
            </div>
          )}

          {/* 업로드 전(=이번 세션 산출물 없음)에는 DB에 쌓아둔 전체 코퍼스를 보여준다. */}
          {!preview && corpus && (
            <div className="space-y-3">
              <div className="border-b border-line/40 pb-2">
                <h3 className="text-sm font-semibold text-fg">구축된 대조학습 코퍼스 현황 (전체)</h3>
                <p className="text-xs text-muted">
                  트리플렛 <span className="text-accent font-bold">{fmt(corpus.train_count + corpus.eval_count)}건</span>
                  {" · "}합성 쿼리 <span className="text-fg font-bold">{fmt(corpus.query_count)}건</span>
                  {" · "}평균 마진 <span className="font-mono text-fg">{corpus.avg_margin.toFixed(3)}</span>
                </p>
              </div>
              {corpus.by_type.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {corpus.by_type.map((t) => (
                    <span
                      key={t.query_type}
                      className="rounded-full border border-line px-2.5 py-0.5 text-xs text-muted"
                    >
                      {t.query_type} <span className="text-accent">{fmt(t.count)}</span>
                    </span>
                  ))}
                </div>
              )}
              <p className="text-xs text-muted">
                마진(margin)이 큰 순서로 상위 {corpus.train_preview.length}건 — 하드 네거티브가 잘 분리된 샘플입니다.
              </p>
              <TripletTable rows={corpus.train_preview} />
            </div>
          )}
        </Card>
      )}

      {jobId && (
        <Card className="animate-rise">
          <h2 className="mb-3 text-sm font-medium text-fg flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
            지식 인제스천 &amp; 데이터셋 생성 파이프라인 진행 상황
          </h2>
          <JobProgress
            jobId={jobId}
            endpoint="/api/v1/finetune/jobs"
            onDone={loadPreview}
          />
        </Card>
      )}

      {trainJobId && (
        <Card className="animate-rise">
          <h2 className="mb-3 text-sm font-medium text-fg flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-positive animate-pulse" />
            LoRA 파인튜닝 모델 학습 진행 상황
          </h2>
          <JobProgress
            jobId={trainJobId}
            endpoint="/api/v1/finetune/jobs"
            onDone={onTrainDone}
          />
          <p className="mt-3 text-xs text-muted">
            학습 완료 후 모델 배포: <code className="text-fg">.env</code>의{" "}
            <code className="text-fg">AGENT_EMBEDDING_MODEL</code>을 산출물 경로
            (<code className="text-fg">TRAINING_OUTPUT_DIR/final</code>)로 업데이트하고 백엔드를 재시작하면 파인튜닝 모델이 즉시 동기화됩니다.
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
