"""NIM 호출 실패를 한 줄씩 추가 기록해 '불안정'의 실제 원인을 계측한다.

목적: NIM이 실제로 무엇으로(429 / 타임아웃 / 연결끊김 / 5xx / 410) 얼마나 자주
터지는지 실측해서, 폴백 프로바이더를 붙일지 vs 키만 늘릴지를 데이터로 정하기 위함.
(체감 "불안정"만으로 게이트웨이 스왑 같은 큰 결정을 내리지 않으려는 것)

- append는 짧은 줄이면 POSIX에서 원자적이라, jobs.py가 별도 subprocess로 띄우는
  파이프라인(KG 빌더·엔티티 정제·쿼리 합성·페르소나)의 실패까지 프로세스 경계를
  넘어 한 파일에 모인다. 이게 로그 tee보다 나은 이유: 429는 이 동시성에서 나온다.
- 계측이 본 호출을 죽이면 안 되므로 전부 best-effort(예외 삼킴).
- 포맷은 TSV: <epoch>\t<path>\t<예외타입>\t<status_code>. 집계는 셸 한 줄로 충분:
    cut -f3,4 logs/nim_stats.tsv | sort | uniq -c | sort -rn
  또는 `python -m shared.utils.nim_stats` 로 시간당 실패율까지 본다.

# ponytail: 실패만 기록(분모=총요청 미기록). 시간당 건수 + 타입 분포로 "무엇이
#           지배적인가"는 답이 나온다. 실패율(%)이 필요해지면 성공 경로에도 record.
"""

from __future__ import annotations

import os
import time
from collections import Counter
from pathlib import Path

FILE = Path(os.environ.get("NIM_STATS_FILE", "logs/nim_stats.tsv"))


def record_failure(path: str, exc: Exception, file: Path = FILE) -> None:
    """실패 1건 기록. path 는 호출 갈래("agent" | "pipeline")."""
    try:
        status = getattr(exc, "status_code", "") or ""
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("a") as f:
            f.write(f"{time.time():.0f}\t{path}\t{type(exc).__name__}\t{status}\n")
    except Exception:
        pass  # 계측이 본 호출을 막으면 본말전도


def summary(file: Path = FILE) -> dict:
    """(예외타입, status)·(갈래)별 건수와 시간당 실패율을 집계한다."""
    rows = [l.split("\t") for l in file.read_text().splitlines() if l]
    ts = [int(r[0]) for r in rows if r and r[0].isdigit()]
    span_h = max((max(ts) - min(ts)) / 3600, 1 / 3600) if ts else 1.0
    return {
        "total": len(rows),
        "per_hour": round(len(rows) / span_h, 1),
        "by_kind": dict(Counter((r[2], r[3]) for r in rows if len(r) >= 4)),
        "by_path": dict(Counter(r[1] for r in rows if len(r) >= 2)),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:  # 실제 파일 집계 출력
        import json

        print(json.dumps(summary(Path(sys.argv[1])), ensure_ascii=False, indent=2))
    else:  # 자체 점검
        import tempfile

        class _Boom(Exception):
            status_code = 429

        tmp = Path(tempfile.mkdtemp()) / "s.tsv"
        record_failure("agent", _Boom(), tmp)
        record_failure("pipeline", TimeoutError(), tmp)
        record_failure("agent", _Boom(), tmp)
        s = summary(tmp)
        assert s["total"] == 3, s
        assert s["by_kind"][("_Boom", "429")] == 2, s  # status는 TSV 왕복 후 문자열
        assert s["by_kind"][("TimeoutError", "")] == 1, s
        assert s["by_path"] == {"agent": 2, "pipeline": 1}, s
        print("ok", s)
