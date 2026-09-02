"""지식그래프 빌드/탐색 라우터.

- 빌드: `pipelines/knowledge_graph/builder.py`를 비동기 작업으로 실행(증분 적재).
- 스냅샷: Neo4j에서 노드/엣지를 끌어와 포스그래프 렌더용 JSON으로 변환.
GraphRAG 질의(근거 서브그래프 포함)는 api/query.py의 `/api/v1/query`가 담당한다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.api.uploads import read_upload_capped
from backend.app.services.jobs import PROJECT_ROOT, job_manager
from shared.database.connector import list_emb_sources
from shared.database.neo4j_client import fetch_graph_snapshot
from shared.database.repositories.embeddings import delete_emb_passages_by_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])

RAW_DIR = PROJECT_ROOT / "data" / "raw_documents"
SUPPORTED_UPLOAD_SUFFIXES = {".pdf", ".txt", ".md", ".jsonl"}


class BuildRequest(BaseModel):
    limit: int = 40  # 이번 실행에서 처리할 미처리 단락 수 (-1이면 전체)


class IngestRequest(BaseModel):
    filename: str


@router.get("/documents")
def list_documents() -> dict:
    """현재 RAG(emb_passages)에 반영된 문서 목록 — 챗봇 지식베이스 패널용."""
    return {"documents": list_emb_sources()}


@router.delete("/documents/{source}")
def delete_document(source: str) -> dict:
    """지식베이스에서 문서 하나를 지운다 — emb_passages 단락 + data/raw_documents/ 원본 파일.

    이미 그래프에 반영된 엔티티/관계는 지우지 않는다(어느 노드가 이 source에서 나왔는지
    추적 안 함). 필요하면 지식그래프 재빌드로 정리한다.
    """
    deleted = delete_emb_passages_by_source(source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"반영된 문서를 찾을 수 없습니다: {source}")
    raw_path = RAW_DIR / Path(source).name
    if raw_path.exists():
        raw_path.unlink()
    return {"source": source, "deleted_passages": deleted}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """금융 문서를 data/raw_documents/에 저장한다 (챗봇 지식베이스 패널의 파일 첨부용)."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다: {suffix} (지원: {sorted(SUPPORTED_UPLOAD_SUFFIXES)})",
        )
    content = await read_upload_capped(file)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / Path(file.filename).name
    dest.write_bytes(content)
    return {"filename": dest.name, "size": len(content)}


@router.post("/ingest/jobs")
async def start_ingest_job(req: IngestRequest) -> dict:
    """업로드된 문서를 파싱·임베딩해 emb_passages에 적재(reingest)한다. 완료 후 그래프 빌드를 실행하면 RAG에 반영된다."""
    target = RAW_DIR / Path(req.filename).name
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"업로드된 파일을 찾을 수 없습니다: {req.filename}")
    cmd = ["uv", "run", "python", "-m", "pipelines.embedding.reingest", str(target)]
    job = job_manager.start("ingest", cmd)
    return {"job_id": job.job_id}


@router.get("/ingest/jobs/{job_id}")
def get_ingest_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
    return job.to_dict()


@router.post("/build/jobs")
async def start_build_job(req: BuildRequest) -> dict:
    """지식그래프 증분 빌드 파이프라인을 비동기로 시작한다."""
    cmd = [
        "uv", "run", "python", "-m", "pipelines.knowledge_graph.builder",
        "--limit", str(req.limit),
    ]
    job = job_manager.start("graph_build", cmd)
    return {"job_id": job.job_id}


@router.get("/build/jobs")
def list_build_jobs() -> dict:
    return {"jobs": [j.to_dict(log_tail=5) for j in job_manager.list("graph_build")]}


@router.get("/build/jobs/{job_id}")
def get_build_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
    return job.to_dict()


@router.get("/snapshot")
def graph_snapshot(limit: int = 200) -> dict:
    """Neo4j에서 (n)-[r]-(m) 관계를 끌어와 포스그래프용 nodes/links로 변환한다."""
    try:
        return fetch_graph_snapshot(limit=limit)
    except Exception as exc:
        logger.exception("Neo4j 스냅샷 조회 실패")
        raise HTTPException(status_code=500, detail="그래프 조회에 실패했습니다.") from exc
