"""파인튜닝 데이터셋 생성 라우터.

금융 문서를 업로드 → 임베딩 대조학습 triplet 파이프라인을 비동기 작업으로 실행
(`pipelines/embedding/pipeline.py --file`) → 진행률/로그 폴링 → 생성된 train/eval
JSONL triplet을 프리뷰한다. 파이프라인 로직 자체는 기존 CLI를 그대로 재사용한다.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.services.jobs import PROJECT_ROOT, job_manager

router = APIRouter(prefix="/api/v1/finetune", tags=["finetune"])

RAW_DIR = PROJECT_ROOT / "data" / "raw_documents"
SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".jsonl"}


def _sub_dir_for(filename: str) -> str:
    """pipeline.py가 --file 모드에서 쓰는 격리 폴더명과 동일하게 산출 (NFC stem)."""
    return unicodedata.normalize("NFC", Path(filename).stem)


class StartJobRequest(BaseModel):
    filename: str


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    """금융 문서를 data/raw_documents/에 저장한다."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 형식입니다: {suffix} (지원: {sorted(SUPPORTED_SUFFIXES)})",
        )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_DIR / Path(file.filename).name
    content = await file.read()
    dest.write_bytes(content)
    return {"filename": dest.name, "size": len(content), "sub_dir": _sub_dir_for(dest.name)}


@router.post("/jobs")
async def start_finetune_job(req: StartJobRequest) -> dict:
    """업로드된 파일에 대해 임베딩 파인튜닝셋 생성 파이프라인을 비동기로 시작한다."""
    target = RAW_DIR / Path(req.filename).name
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"업로드된 파일을 찾을 수 없습니다: {req.filename}")
    cmd = [
        "uv", "run", "python", "pipelines/embedding/pipeline.py",
        "--file", target.name,
    ]
    job = job_manager.start("finetune", cmd)
    return {"job_id": job.job_id, "sub_dir": _sub_dir_for(target.name)}


@router.get("/jobs")
def list_finetune_jobs() -> dict:
    return {"jobs": [j.to_dict(log_tail=5) for j in job_manager.list("finetune")]}


@router.get("/jobs/{job_id}")
def get_finetune_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
    return job.to_dict()


def _read_jsonl_preview(path: Path, limit: int) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= limit:
                break
    return rows


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


@router.get("/datasets")
def preview_dataset(sub_dir: str, limit: int = 20) -> dict:
    """생성된 train/eval triplet JSONL을 프리뷰한다 (query/positive/negative/margin)."""
    base = PROJECT_ROOT / "data" / unicodedata.normalize("NFC", sub_dir) / "dataset"
    train_path = base / "train_triplets.jsonl"
    eval_path = base / "eval_triplets.jsonl"
    if not train_path.exists() and not eval_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"아직 생성된 데이터셋이 없습니다: {base}",
        )
    return {
        "sub_dir": sub_dir,
        "train_count": _count_lines(train_path),
        "eval_count": _count_lines(eval_path),
        "train_preview": _read_jsonl_preview(train_path, limit),
        "eval_preview": _read_jsonl_preview(eval_path, limit),
    }
