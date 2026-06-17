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
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# 프로젝트 루트 (PYTHONPATH=. 로 실행되는 백엔드 기준)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

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


class JobManager:
    """단일 프로세스 내에서 동작하는 비동기 작업 레지스트리."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self, kind: str | None = None) -> list[Job]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        if kind:
            jobs = [j for j in jobs if j.kind == kind]
        return jobs

    def start(self, kind: str, cmd: list[str]) -> Job:
        """작업을 등록하고 백그라운드로 subprocess를 실행한다."""
        job_id = uuid.uuid4().hex[:12]
        job = Job(job_id=job_id, kind=kind, cmd=cmd)
        self._jobs[job_id] = job
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
            return

        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if not line:
                continue
            job.logs.append(line)
            # 진행률 추정: "[n/total]" 단계 로그가 보이면 갱신
            m = _STAGE_RE.search(line)
            if m:
                cur, total = int(m.group(1)), int(m.group(2))
                if total > 0:
                    job.progress = min(99, round(cur / total * 100))

        rc = await proc.wait()
        job.finished_at = time.time()
        if rc == 0:
            job.status = "succeeded"
            job.progress = 100
        else:
            job.status = "failed"
            job.error = f"프로세스가 비정상 종료했습니다 (exit code {rc})"


# 앱 전역에서 공유하는 단일 인스턴스
job_manager = JobManager()
