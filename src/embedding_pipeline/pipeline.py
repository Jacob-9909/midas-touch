"""
pipeline.py
-----------
1단계 임베딩 파인튜닝 데이터셋 생성 전체 파이프라인 오케스트레이터.

실행 흐름:
  1. 금융 문서 로드 (PDF, TXT, MD) → 정밀 파싱 및 단락 청킹 (DocumentParser)
  2. NIM LLM으로 쿼리 합성 및 2차 LLM 품질 검증 (비동기 병렬)
  3. KURE-v1 교사 임베딩 모델로 하드 네거티브 마이닝 (OOM 안전 연산)
  4. 삼중쌍 조립 → 학습/평가셋 분리 → JSONL 저장
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from src.embedding_pipeline.config import PipelineConfig, DEFAULT_CONFIG
from src.embedding_pipeline.document_parser import DocumentParser, Passage
from src.embedding_pipeline.dataset_builder import (
    DatasetIO,
    DatasetSplitter,
    TripletAssembler,
    compute_dataset_stats,
)
from src.embedding_pipeline.hard_negative_miner import HardNegativeMiner, compute_mining_stats
from src.embedding_pipeline.query_synthesizer import (
    QuerySynthesizer,
    SyntheticQuery,
    synthesis_results_to_jsonl,
)

# ---------------------------------------------------------------------------
# 로거 설정
# ---------------------------------------------------------------------------
def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 고도화된 단락 로더 (PDF, TXT, MD 대응 및 체크포인트 재사용)
# ---------------------------------------------------------------------------
class PassageLoader:
    """
    금융 문서 디렉토리에서 단락을 통합 수집 및 로드하는 컴포넌트.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config
        self._paths = config.paths
        self._parser = DocumentParser(config)

    def load(self) -> list[Passage]:
        """
        원천 디렉토리에서 문서를 로드하고 파싱 및 청킹.
        """
        # 이미 전처리된 단락 파일이 있으면 재사용 (체크포인트)
        if self._paths.passages_jsonl.exists():
            logger.info(
                "전처리된 단락 파일 발견: %s (재사용)", self._paths.passages_jsonl
            )
            return self._load_jsonl(self._paths.passages_jsonl)

        raw_dir = self._paths.raw_documents_dir
        if not raw_dir.exists():
            # 원천 디렉토리가 없으면 기본 디렉토리들을 생성하고 경고
            self._paths.ensure_dirs()
            raise FileNotFoundError(
                f"원천 문서 디렉토리를 찾을 수 없습니다: {raw_dir.absolute()}\n"
                "해당 경로에 분석할 금융 문서(.pdf, .txt, .md)들을 배치하고 다시 시도하세요."
            )

        passages: list[Passage] = []
        # 지원 확장자 수집
        supported_suffixes = {".pdf", ".txt", ".md", ".jsonl"}
        
        # 파일 수집 후 정렬하여 결정론적 수집 유도
        file_paths = [
            p for p in raw_dir.iterdir()
            if p.is_file() and p.suffix.lower() in supported_suffixes
        ]
        file_paths.sort()

        if not file_paths:
            logger.warning(
                "원천 문서 디렉토리에 처리 가능한 파일(.pdf, .txt, .md)이 없습니다: %s",
                raw_dir.absolute()
            )
            return []

        for file_path in file_paths:
            if file_path.suffix.lower() == ".jsonl":
                # 기존에 포맷팅된 jsonl Passage 파일이 들어온 경우 직독
                passages.extend(self._load_jsonl(file_path))
            else:
                # PDF, MD, TXT 통합 파싱 및 청킹
                passages.extend(self._parser.parse_file(file_path))

        logger.info("총 %d개 단락 수집 및 전처리 완료.", len(passages))

        if passages:
            # 전처리 결과 저장 (다음 실행 시 재사용)
            self._save_jsonl(passages)
            
        return passages

    @staticmethod
    def _load_jsonl(path: Path) -> list[Passage]:
        passages = []
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    passages.append(
                        Passage(
                            passage_id=data.get(
                                "passage_id", f"{path.stem}_{line_no:06d}"
                            ),
                            text=data["text"],
                            source=data.get("source", path.stem),
                            metadata={
                                k: v
                                for k, v in data.items()
                                if k not in ("passage_id", "text", "source")
                            },
                        )
                    )
                except (KeyError, json.JSONDecodeError) as exc:
                    logger.warning("%s:%d 파싱 실패: %s", path.name, line_no, exc)
        return passages

    def _save_jsonl(self, passages: list[Passage]) -> None:
        path = self._paths.passages_jsonl
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for p in passages:
                row = {
                    "passage_id": p.passage_id,
                    "text": p.text,
                    "source": p.source,
                    **p.metadata,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        logger.info("전처리된 단락 캐시 저장 완료: %s", path)


# ---------------------------------------------------------------------------
# 체크포인트 관리
# ---------------------------------------------------------------------------
class CheckpointManager:
    """파이프라인 단계별 체크포인트 저장/로드."""

    def __init__(self, config: PipelineConfig) -> None:
        self._dir = config.paths.checkpoint_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, stage: str, data: Any) -> None:
        path = self._dir / f"{stage}.jsonl"
        if isinstance(data, list) and data and isinstance(data[0], dict):
            with open(path, "w", encoding="utf-8") as f:
                for row in data:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            logger.info("체크포인트 저장 [%s]: %s", stage, path)
        else:
            logger.warning("체크포인트 저장 실패 [%s]: 지원되지 않는 데이터 형식", stage)

    def load(self, stage: str) -> list[dict] | None:
        path = self._dir / f"{stage}.jsonl"
        if not path.exists():
            return None
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        logger.info("체크포인트 로드 [%s]: %d 행", stage, len(rows))
        return rows

    def exists(self, stage: str) -> bool:
        return (self._dir / f"{stage}.jsonl").exists()


# ---------------------------------------------------------------------------
# 메인 파이프라인
# ---------------------------------------------------------------------------
class EmbeddingDatasetPipeline:
    """
    금융 특화 임베딩 대조 학습 데이터셋 생성 전체 파이프라인.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config
        self._ckpt = CheckpointManager(config)
        config.paths.ensure_dirs()

    async def run(
        self,
        force_rerun_stages: list[str] | None = None,
        persist_db: bool = True,
    ) -> dict:
        """
        전체 파이프라인 실행.

        Args:
            persist_db: True이면 각 단계 결과를 PostgreSQL에도 적재.
        """
        force = set(force_rerun_stages or [])
        total_start = time.perf_counter()

        logger.info("=" * 60)
        logger.info("금융 임베딩 데이터셋 생성 파이프라인 시작")
        logger.info("=" * 60)

        # ── 1단계: 단락 로드 (PDF, TXT, MD 대응) ─────────────────────
        passages = self._run_stage_passage_loading()
        if not passages:
            logger.warning("로드된 금융 단락이 전혀 없습니다. 데이터를 raw_documents 에 배치해 주세요.")
            return {"error": "No data found"}

        if persist_db:
            self._db_persist_passages(passages)

        # ── 2단계: 쿼리 합성 및 2차 검증 (비동기) ───────────────────
        queries = await self._run_stage_query_synthesis(passages, force)
        if not queries:
            logger.error("합성된 유효 쿼리가 전혀 없습니다. NIM 설정을 확인해 주세요.")
            return {"error": "Query synthesis failed or all filtered"}

        if persist_db:
            self._db_persist_queries(queries)

        # ── 3단계: 하드 네거티브 마이닝 (OOM 보호 연산) ─────────────
        mining_results, mining_stats = self._run_stage_hard_negative_mining(
            passages, queries, force
        )

        # ── 4단계: 삼중쌍 조립 + 저장 (Margin 스코어 보존) ──────────
        dataset_stats, train_triplets, eval_triplets = self._run_stage_dataset_assembly(
            queries, mining_results
        )

        if persist_db:
            self._db_persist_triplets(train_triplets, eval_triplets)

        total_elapsed = time.perf_counter() - total_start
        summary = {
            "total_passages": len(passages),
            "total_queries": len(queries),
            "mining_stats": mining_stats,
            "dataset_stats": dataset_stats,
            "total_elapsed_sec": round(total_elapsed, 2),
        }

        logger.info("=" * 60)
        logger.info("파이프라인 완료! 총 소요 시간: %.1f초", total_elapsed)
        logger.info("최종 학습 데이터셋: %s", self._cfg.paths.train_dataset_jsonl.absolute())
        logger.info("최종 평가 데이터셋: %s", self._cfg.paths.eval_dataset_jsonl.absolute())
        logger.info("=" * 60)

        return summary

    # ------------------------------------------------------------------
    # 단계별 메서드
    # ------------------------------------------------------------------
    def _run_stage_passage_loading(self) -> list[Passage]:
        logger.info("[1/4] 금융 문서 로드 및 청킹 시작...")
        loader = PassageLoader(self._cfg)
        passages = loader.load()
        logger.info("[1/4] 단락 로드 완료: %d개", len(passages))
        return passages

    async def _run_stage_query_synthesis(
        self,
        passages: list[Passage],
        force: set[str],
    ) -> list[SyntheticQuery]:
        logger.info("[2/4] 쿼리 합성 및 2차 LLM 품질 검증 시작...")
        stage = "query_synthesis"

        # 체크포인트 확인
        if stage not in force and self._ckpt.exists(stage):
            raw_rows = self._ckpt.load(stage)
            if raw_rows:
                queries = [
                    SyntheticQuery(
                        query_id=r["query_id"],
                        passage_id=r["passage_id"],
                        query_text=r["query_text"],
                        query_type=r["query_type"],
                        source_passage=r["source_passage"],
                    )
                    for r in raw_rows
                ]
                logger.info("[2/4] 체크포인트에서 쿼리 로드: %d개", len(queries))
                return queries

        # LLM 쿼리 합성 실행
        stage_start = time.perf_counter()
        async with QuerySynthesizer(self._cfg) as synth:
            results = await synth.synthesize_batch(passages)

        # 실패 통계 로깅
        failed = [r for r in results if r.error]
        if failed:
            logger.warning("%d개 단락 합성 실패", len(failed))

        queries = [
            q for result in results for q in result.queries
        ]
        logger.info(
            "[2/4] 쿼리 합성 완료: %d개 (%.1fs)",
            len(queries), time.perf_counter() - stage_start,
        )

        # 체크포인트 저장
        rows = synthesis_results_to_jsonl(results)
        self._ckpt.save(stage, rows)

        return queries

    def _run_stage_hard_negative_mining(
        self,
        passages: list[Passage],
        queries: list[SyntheticQuery],
        force: set[str],
    ) -> tuple[list, dict]:
        from src.embedding_pipeline.hard_negative_miner import MiningResult

        logger.info("[3/4] 하드 네거티브 마이닝 시작...")
        stage = "hard_negative_mining"

        if stage not in force and self._ckpt.exists(stage):
            raw_rows = self._ckpt.load(stage)
            if raw_rows:
                logger.info("[3/4] 체크포인트에서 마이닝 결과 로드: %d 행", len(raw_rows))
                # 체크포인트 데이터를 MiningResult로 복원
                mining_results = self._deserialize_mining_results(raw_rows)
                stats = compute_mining_stats(mining_results)
                return mining_results, stats

        stage_start = time.perf_counter()
        miner = HardNegativeMiner(self._cfg)

        # 임베딩 캐시 확인
        cache_path = self._cfg.paths.checkpoint_dir / "passage_embeddings.npy"
        cache_loaded = miner.load_embeddings_cache(cache_path, passages)
        if not cache_loaded:
            miner.index_passages(passages)
            miner.save_embeddings_cache(cache_path)

        mining_results = miner.mine(queries)
        stats = compute_mining_stats(mining_results)

        logger.info(
            "[3/4] 마이닝 완료: %d 쌍 (%.1fs) | coverage=%.1f%%",
            stats["total_hard_negatives"],
            time.perf_counter() - stage_start,
            stats["coverage_ratio"] * 100,
        )

        # 체크포인트 저장
        ckpt_rows = self._serialize_mining_results(mining_results)
        self._ckpt.save(stage, ckpt_rows)

        return mining_results, stats

    def _run_stage_dataset_assembly(
        self,
        queries: list[SyntheticQuery],
        mining_results: list,
    ) -> tuple[dict, list, list]:
        logger.info("[4/4] 삼중쌍 조립 및 저장 시작...")
        stage_start = time.perf_counter()

        assembler = TripletAssembler(self._cfg)
        triplets = assembler.assemble(
            queries=queries,
            mining_results=mining_results,
            use_in_batch_fallback=True,
        )

        splitter = DatasetSplitter(self._cfg)
        train_triplets, eval_triplets = splitter.split(triplets)

        DatasetIO.save_jsonl(train_triplets, self._cfg.paths.train_dataset_jsonl)
        DatasetIO.save_jsonl(eval_triplets, self._cfg.paths.eval_dataset_jsonl)

        stats = compute_dataset_stats(triplets)
        logger.info(
            "[4/4] 조립 완료: train=%d, eval=%d (%.1fs)",
            len(train_triplets), len(eval_triplets),
            time.perf_counter() - stage_start,
        )
        return stats, train_triplets, eval_triplets

    # ------------------------------------------------------------------
    # DB 적재 헬퍼
    # ------------------------------------------------------------------
    def _db_persist_passages(self, passages: list[Passage]) -> None:
        try:
            from src.db.connector import bulk_upsert_emb_passages
            rows = [{"passage_id": p.passage_id, "text": p.text, "source": p.source, "metadata": p.metadata} for p in passages]
            count = bulk_upsert_emb_passages(rows)
            logger.info("[DB] emb_passages 적재 완료: %d건", count)
        except Exception as exc:
            logger.warning("[DB] emb_passages 적재 실패 (파이프라인은 계속): %s", exc)

    def _db_persist_queries(self, queries: list[SyntheticQuery]) -> None:
        try:
            from src.db.connector import bulk_upsert_emb_queries
            rows = [{"query_id": q.query_id, "passage_id": q.passage_id, "query_text": q.query_text, "query_type": q.query_type, "source_passage": q.source_passage} for q in queries]
            count = bulk_upsert_emb_queries(rows)
            logger.info("[DB] emb_synthetic_queries 적재 완료: %d건", count)
        except Exception as exc:
            logger.warning("[DB] emb_synthetic_queries 적재 실패 (파이프라인은 계속): %s", exc)

    def _db_persist_triplets(self, train_triplets: list, eval_triplets: list) -> None:
        try:
            from src.db.connector import bulk_upsert_emb_triplets
            from dataclasses import asdict
            train_rows = [asdict(t) for t in train_triplets]
            eval_rows = [asdict(t) for t in eval_triplets]
            t_count = bulk_upsert_emb_triplets(train_rows, "train")
            e_count = bulk_upsert_emb_triplets(eval_rows, "eval")
            logger.info("[DB] emb_training_triplets 적재 완료: train=%d, eval=%d", t_count, e_count)
        except Exception as exc:
            logger.warning("[DB] emb_training_triplets 적재 실패 (파이프라인은 계속): %s", exc)

    # ------------------------------------------------------------------
    # 직렬화 / 역직렬화 헬퍼
    # ------------------------------------------------------------------
    @staticmethod
    def _serialize_mining_results(results: list) -> list[dict]:
        rows = []
        for r in results:
            for hn in r.hard_negatives:
                rows.append(
                    {
                        "query_id": r.query_id,
                        "passage_id": r.passage_id,
                        "hn_passage_id": hn.passage_id,
                        "hn_passage_text": hn.passage_text,
                        "hn_similarity_score": hn.similarity_score,
                        "positive_score": hn.positive_score,
                        "margin": hn.margin,
                    }
                )
        return rows

    @staticmethod
    def _deserialize_mining_results(rows: list[dict]) -> list:
        from src.embedding_pipeline.hard_negative_miner import MiningResult, HardNegativeCandidate
        from collections import defaultdict

        grouped: dict[str, list] = defaultdict(list)
        meta: dict[str, str] = {}

        for row in rows:
            qid = row["query_id"]
            meta[qid] = row["passage_id"]
            grouped[qid].append(
                HardNegativeCandidate(
                    query_id=qid,
                    passage_id=row["hn_passage_id"],
                    passage_text=row["hn_passage_text"],
                    similarity_score=row["hn_similarity_score"],
                    positive_score=row["positive_score"],
                    margin=row["margin"],
                )
            )

        return [
            MiningResult(
                query_id=qid,
                passage_id=meta[qid],
                hard_negatives=candidates,
            )
            for qid, candidates in grouped.items()
        ]


# ---------------------------------------------------------------------------
# CLI 엔트리포인트
# ---------------------------------------------------------------------------
async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="금융 특화 임베딩 대조 학습 데이터셋 생성 파이프라인"
    )
    parser.add_argument(
        "--force-rerun",
        nargs="*",
        choices=["query_synthesis", "hard_negative_mining"],
        default=[],
        help="강제 재실행할 파이프라인 단계 (체크포인트 무시)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    config = DEFAULT_CONFIG
    try:
        config.validate()
    except ValueError as exc:
        logger.error("설정 검증 실패: %s", exc)
        raise SystemExit(1) from exc

    pipeline = EmbeddingDatasetPipeline(config)
    summary = await pipeline.run(force_rerun_stages=args.force_rerun)

    print("\n" + "=" * 50)
    print("파이프라인 완료 요약")
    print("=" * 50)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
