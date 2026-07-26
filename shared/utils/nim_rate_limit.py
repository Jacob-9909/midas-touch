"""NVIDIA NIM 호출 속도 제한(기본 40 req/min per API key) 강제 모듈.

지식그래프 빌더 · 엔티티 정제 · 쿼리 합성은 트리거가 각각 다르고
backend/app/services/jobs.py가 이들을 **별도 subprocess**로 띄우기 때문에,
프로세스 내부 세마포어/딜레이만으로는 계정 전체 호출량을 제한할 수 없다.
(각 파이프라인이 "나는 40 RPM 지켰다"고 믿어도 동시에 두 개가 돌면 80 RPM)

그래서 API 키별로 파일 락 + "예약된 호출 시각" 목록을 공유해, 어느 프로세스에서
호출하든 60초 창 안에 rpm개를 넘지 않도록 슬롯을 나눠 갖는다.

사용법 (호출 직전):
    wait = reserve(api_key)          # 슬롯 예약, 대기해야 할 초 반환
    time.sleep(wait)                 # 동기
    await asyncio.sleep(wait)        # 비동기 (이벤트 루프 안 막힘)

락은 슬롯 계산 동안만 잡고 대기는 락 밖에서 하므로, 느린 호출자가 다른
프로세스를 막지 않는다.
"""

from __future__ import annotations

import bisect
import fcntl
import hashlib
import logging
import os
import struct
import time
from pathlib import Path

logger = logging.getLogger("nim_rate_limit")

WINDOW_SECONDS = 60.0

# ponytail: 단일 머신 기준(파일 락). 여러 노드로 흩어지면 Redis/DB 기반으로 올려야 함.
_STATE_DIR = Path(
    os.environ.get(
        "NIM_RATELIMIT_DIR",
        Path(__file__).resolve().parents[2] / "data" / "ratelimit",
    )
)


def _rpm() -> int:
    """분당 허용 호출 수. 0 이하면 제한을 끈다."""
    return int(os.environ.get("NIM_RPM", "40"))


def _slot_file(api_key: str) -> Path:
    # 키 원문을 파일명에 노출하지 않기 위해 해시 사용
    digest = hashlib.sha256(api_key.encode()).hexdigest()[:16]
    return _STATE_DIR / f"{digest}.slots"


def reserve(api_key: str, rpm: int | None = None) -> float:
    """호출 슬롯 1개를 예약하고 호출 전 대기해야 할 초를 반환한다."""
    limit = _rpm() if rpm is None else rpm
    if limit <= 0 or not api_key:
        return 0.0

    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        path = _slot_file(api_key)
        now = time.time()
        with open(path, "a+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                raw = f.read()
                count = len(raw) // 8
                slots = list(struct.unpack(f"{count}d", raw[: count * 8])) if count else []

                # 이미 지나간 창의 예약은 버린다
                slots = sorted(t for t in slots if t > now - WINDOW_SECONDS)

                if len(slots) < limit:
                    start = now
                else:
                    # 뒤에서 limit번째 예약이 창을 벗어나는 시점 이후로 밀어낸다
                    start = max(now, slots[-limit] + WINDOW_SECONDS)

                bisect.insort(slots, start)
                f.seek(0)
                f.truncate()
                f.write(struct.pack(f"{len(slots)}d", *slots))
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except OSError as exc:
        # 상태 파일을 못 쓰는 환경이라도 호출 자체는 막지 않는다(백오프가 뒷단에서 방어)
        logger.warning("레이트리밋 상태 파일 접근 실패, 제한 없이 진행합니다: %s", exc)
        return 0.0

    wait = max(0.0, start - now)
    if wait > 0:
        logger.info(
            "[NIM RPM] 키 ...%s 분당 %d회 한도 도달. %.2f초 대기 후 호출합니다.",
            api_key[-4:], limit, wait,
        )
    return wait


def _demo() -> None:
    """40 RPM 한도가 실제로 창을 넘겨 밀어내는지 확인."""
    import tempfile

    global _STATE_DIR
    with tempfile.TemporaryDirectory() as tmp:
        _STATE_DIR = Path(tmp)
        key = "nvapi-test-key"

        # 한도 5로 5회는 즉시 통과
        waits = [reserve(key, rpm=5) for _ in range(5)]
        assert all(w == 0.0 for w in waits), waits

        # 6번째부터는 첫 예약이 창을 벗어날 때까지(≈60초) 밀린다
        sixth = reserve(key, rpm=5)
        assert 59.0 < sixth <= 60.0, sixth
        seventh = reserve(key, rpm=5)
        assert 59.0 < seventh <= 60.0 and seventh >= sixth, (sixth, seventh)

        # 다른 키는 독립적인 창을 쓴다
        assert reserve("nvapi-other-key", rpm=5) == 0.0

        # rpm<=0 이면 제한 없음
        assert reserve(key, rpm=0) == 0.0

        # 파일이 프로세스 경계를 넘어 공유되는지: 같은 디렉터리를 다시 읽어도 예약이 남아있다
        assert _slot_file(key).exists()

    _demo_cross_process()
    print("nim_rate_limit demo OK")


def _demo_cross_process() -> None:
    """이 모듈의 존재 이유(별개 subprocess 간 창 공유)를 실제 프로세스로 검증.

    워커 3개 × 8회 = 24건을 한도 12로 예약시키고, 슬롯 파일에 기록된 값으로
    어떤 60초 창에도 12건을 넘지 않는지 본다. 락이 없으면 24건이 전부 t≈0에 몰린다.
    """
    import struct
    import subprocess
    import sys
    import tempfile

    key, rpm, workers, per = "nvapi-crossproc-demo", 12, 3, 8
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "NIM_RATELIMIT_DIR": tmp}
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        code = (
            "from shared.utils.nim_rate_limit import reserve\n"
            f"[reserve({key!r}, rpm={rpm}) for _ in range({per})]\n"
        )
        procs = [subprocess.Popen([sys.executable, "-c", code], env=env) for _ in range(workers)]
        for p in procs:
            assert p.wait() == 0, "예약 워커가 실패했다"

        digest = hashlib.sha256(key.encode()).hexdigest()[:16]
        raw = (Path(tmp) / f"{digest}.slots").read_bytes()
        slots = sorted(struct.unpack(f"{len(raw) // 8}d", raw))

        assert len(slots) == workers * per, len(slots)
        worst = max(sum(1 for u in slots if t <= u < t + WINDOW_SECONDS) for t in slots)
        assert worst <= rpm, f"60초 창에 {worst}건 예약됨 (한도 {rpm}) — 창이 공유되지 않았다"
        # 한도를 넘는 요청은 다음 창으로 밀려야 하므로 전체 span이 한 창 이상이어야 한다
        assert slots[-1] - slots[0] >= WINDOW_SECONDS - 0.01, slots[-1] - slots[0]


if __name__ == "__main__":
    _demo()
