import logging
import os
import time

logger = logging.getLogger("api_key_rotator")


class APIKeyRotator:
    """NVIDIA API Key 동적 로테이션 및 실패 키 쿨다운(우회) 관리 클래스."""

    def __init__(self) -> None:
        self.keys = self._load_keys()
        self.index = 0
        if not self.keys:
            raise ValueError(
                "NVIDIA API Key not found in environment variables. "
                "Please configure NVIDIA_API_KEY (and optionally NVIDIA_API_KEY_2, etc.) in your .env file."
            )
        # 각 키별 사용 불가 만료 시간(timestamp) 기록
        self.cooldowns = {k: 0.0 for k in self.keys}
        logger.info("APIKeyRotator initialized with %d keys.", len(self.keys))

    def _load_keys(self) -> list[str]:
        keys = []
        if os.environ.get("NVIDIA_API_KEY"):
            keys.append(os.environ.get("NVIDIA_API_KEY"))
        if os.environ.get("NVIDIA_API_KEY_2"):
            keys.append(os.environ.get("NVIDIA_API_KEY_2"))
        
        i = 3
        while True:
            k = os.environ.get(f"NVIDIA_API_KEY_{i}")
            if not k:
                break
            keys.append(k)
            i += 1
            
        if not keys and os.environ.get("NVIDIA_NIM_API_KEY"):
            keys.append(os.environ.get("NVIDIA_NIM_API_KEY"))
            
        seen = set()
        dedup_keys = []
        for k in keys:
            k_strip = k.strip()
            if k_strip and k_strip not in seen:
                seen.add(k_strip)
                dedup_keys.append(k_strip)
        return dedup_keys

    def _get_active_keys(self) -> list[str]:
        now = time.time()
        active = [k for k in self.keys if self.cooldowns[k] <= now]
        if not active:
            # 모든 키가 쿨다운 상태면 강제로 전체 초기화하여 데드락 방지
            logger.warning("모든 API 키가 쿨다운(지연/오류) 상태입니다. 쿨다운을 초기화합니다.")
            for k in self.keys:
                self.cooldowns[k] = 0.0
            return self.keys
        return active

    def get_key(self) -> str:
        """현재 인덱스의 API 키를 가져옵니다. 현재 키가 쿨다운 중이면 가장 빠른 활성 키로 이동합니다."""
        active = self._get_active_keys()  # 항상 비어있지 않음(쿨다운 전부 만료 시 self.keys 반환)
        current_key = self.keys[self.index]
        if current_key not in active:
            self.index = self.keys.index(active[0])
        return self.keys[self.index]

    def rotate(self) -> str:
        """인덱스를 다음 활성 API 키로 회전하고 반환합니다."""
        active = self._get_active_keys()
        if len(active) <= 1:
            self.index = self.keys.index(active[0])
            return self.get_key()
            
        # 활성 키 목록 중에서 현재 키의 다음 순번을 찾아서 설정
        current_key = self.get_key()
        curr_active_idx = active.index(current_key) if current_key in active else -1
        next_active_idx = (curr_active_idx + 1) % len(active)
        self.index = self.keys.index(active[next_active_idx])
        
        logger.info(
            "API key rotated. Current index: %d (Key prefix: %s...)",
            self.index, self.get_key()[:10]
        )
        return self.get_key()

    def mark_failed(self, key: str, duration: float = 300.0) -> None:
        """특정 키에 오류나 타임아웃이 발생한 경우, 일정 시간(초) 동안 선택에서 제외시킵니다."""
        if key in self.cooldowns:
            self.cooldowns[key] = time.time() + duration
            logger.warning(
                "⚠️ API Key (%s...)가 지연/오류로 인해 %.0f초 동안 쿨다운(사용 제한) 상태로 등록되었습니다.",
                key[:10], duration
            )
