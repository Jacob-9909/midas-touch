"""
jobs.py
-------
인메모리 비동기 작업(JobManager).

긴 배치 파이프라인(임베딩 파인튜닝셋 생성 / 지식그래프 빌드)을 기존 CLI 모듈을
`asyncio.create_subprocess_exec`로 그대로 실행하고, stdout을 라인 버퍼에 적재한다.
프론트엔드는 job_id로 상태/진행률/로그 tail을 폴링한다.

주의: 인메모리 보관이라 서버 재시작 시 작업 이력은 휘발한다(프로토타입 범위).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

# 프로젝트 루트 (PYTHONPATH=. 로 실행되는 백엔드 기준)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 작업 메타/로그 영속화 디렉토리 (서버 재시작에도 이력 보존)
JOBS_DIR = PROJECT_ROOT / "data" / "jobs"
_MAX_PERSIST_LOGS = 500
_MAX_IN_MEMORY_LOGS = 1000
_MAX_JOBS = 100

# 진행률 추정용 패턴
#  - 임베딩 파이프라인:  "[2/4] ..." 형태의 단계 로그
#  - 명시적 퍼센트:      "coverage=83.0%" 등에 휩쓸리지 않도록 단계 패턴을 우선한다.
_STAGE_RE = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")


@dataclass
class Job:
    job_id: str
    kind: str  # "finetune" | "graph_build"
    cmd: list[str]
    status: str = "running"  # running | succeeded | failed
    progress: int = 0  # 0~100 (추정)
    logs: list[str] = field(default_factory=list)
    result: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def to_dict(self, log_tail: int = 200) -> dict:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs[-log_tail:],
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }

    def persist(self) -> None:
        """작업 상태를 JSON 파일로 저장한다(로그는 최근 분량만)."""
        try:
            JOBS_DIR.mkdir(parents=True, exist_ok=True)
            data = asdict(self)
            data["logs"] = self.logs[-_MAX_PERSIST_LOGS:]
            (JOBS_DIR / f"{self.job_id}.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001 - 영속화 실패가 작업을 막지 않도록
            pass


class JobManager:
    """비동기 작업 레지스트리. 작업 이력은 data/jobs/에 영속화된다."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._load_persisted()

    def _load_persisted(self) -> None:
        """디스크에 저장된 작업 이력을 복원한다. 미완료(running) 작업은 중단 처리."""
        if not JOBS_DIR.exists():
            return
        for path in JOBS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                job = Job(
                    job_id=data["job_id"],
                    kind=data["kind"],
                    cmd=data.get("cmd", []),
                    status=data.get("status", "failed"),
                    progress=data.get("progress", 0),
                    logs=data.get("logs", []),
                    result=data.get("result"),
                    error=data.get("error"),
                    created_at=data.get("created_at", time.time()),
                    finished_at=data.get("finished_at"),
                )
                # 이전 프로세스에서 실행 중이던 작업은 서버 재시작으로 더 이상 살아있지 않다.
                if job.status == "running":
                    job.status = "failed"
                    job.error = "서버 재시작으로 작업이 중단되었습니다."
                    job.finished_at = job.finished_at or time.time()
                self._jobs[job.job_id] = job
            except Exception:  # noqa: BLE001
                continue

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self, kind: str | None = None) -> list[Job]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        if kind:
            jobs = [j for j in jobs if j.kind == kind]
        return jobs

    def start(self, kind: str, cmd: list[str]) -> Job:
        """작업을 등록하고 백그라운드로 subprocess를 실행한다."""
        # 최대 작업 수 초과 시 완료된 가장 오래된 작업부터 정리
        if len(self._jobs) >= _MAX_JOBS:
            completed = [j for j in self._jobs.values() if j.status in {"succeeded", "failed"}]
            if completed:
                oldest = min(completed, key=lambda j: j.created_at)
                self._jobs.pop(oldest.job_id, None)

        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id=job_id, kind=kind, cmd=cmd)
        self._jobs[job_id] = job
        job.persist()
        # 현재 이벤트 루프에서 백그라운드 태스크로 실행
        asyncio.create_task(self._run(job))
        return job

    async def _run(self, job: Job) -> None:
        # PYTHONPATH=. 보장 (CLI 모듈이 프로젝트 루트 기준 import를 함)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        env.setdefault("PYTHONUNBUFFERED", "1")

        job.logs.append(f"$ {' '.join(job.cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *job.cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = f"프로세스 시작 실패: {exc}"
            job.finished_at = time.time()
            job.persist()
            return

        assert proc.stdout is not None
        line_no = 0
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if not line:
                continue
            job.logs.append(line)
            if len(job.logs) > _MAX_IN_MEMORY_LOGS * 2:
                job.logs = job.logs[-_MAX_IN_MEMORY_LOGS:]
            line_no += 1
            # 진행률 추정: "[n/total]" 단계 로그가 보이면 갱신
            m = _STAGE_RE.search(line)
            if m:
                cur, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    job.progress = min(99, round(cur / total * 100))
            # 주기적으로 영속화 (모든 줄마다 쓰면 과도하므로 일정 간격)
            if line_no % 20 == 0:
                job.persist()

        rc = await proc.wait()
        job.finished_at = time.time()
        if rc == 0:
            job.status = "succeeded"
            job.progress = 100
        else:
            job.status = "failed"
            job.error = f"프로세스가 비정상 종료했습니다 (exit code {rc})"
        job.persist()


# 앱 전역에서 공유하는 단일 인스턴스
job_manager = JobManager()
