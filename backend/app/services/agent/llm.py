"""백엔드 에이전트용 LLM 팩토리.

NVIDIA NIM은 OpenAI 호환 엔드포인트이므로 LangChain의 ChatOpenAI 래퍼를 그대로 사용한다.
모델 자체는 교체하지 않으며(.env의 AGENT_LLM_MODEL), function-calling(tools) 포맷을
네이티브로 지원함을 실호출로 확인했다.

다만 순정 ChatOpenAI는 파이프라인 쪽 NIMOpenAI가 갖고 있는 방어 장치가 하나도 없어서
(키 1개 고정 · RPM 슬롯 미예약 · 타임아웃 없음) 지식그래프/임베딩 파이프라인이 도는
동안 사용자 채팅이 429로 죽거나 수 분씩 매달렸다. NIMChatOpenAI가 그 셋을 채운다.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from shared.utils.api_key_rotator import APIKeyRotator
from shared.utils.nim_rate_limit import reserve
from shared.utils.nim_stats import record_failure

logger = logging.getLogger("agent.llm")

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# 재시도 대상: 429 · 타임아웃 · 연결 실패 + 5xx(NIM은 502/503을 꽤 뱉는다).
RETRY_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError)

# 요청 1건이 매달릴 수 있는 최대 시간(초). 사용자 대면 경로라 파이프라인(200초)보다 짧게 잡는다.
REQUEST_TIMEOUT = float(os.environ.get("AGENT_LLM_TIMEOUT", "90"))

# 프로세스당 하나만 두어 키 쿨다운 상태가 호출 간에 유지되게 한다.
_rotator: APIKeyRotator | None = None


def _get_rotator() -> APIKeyRotator:
    global _rotator
    if _rotator is None:
        _rotator = APIKeyRotator()
    return _rotator


def require_env(name: str) -> str:
    """필수 환경변수를 읽고, 없으면 명확한 오류로 실패한다(하드코딩 기본값 금지)."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} 환경변수가 설정되어 있지 않습니다.")
    return value


def _should_retry(exc: Exception) -> bool:
    """재시도할 가치가 있는 오류인지. 400/401/404 같은 클라이언트 오류는 다시 던져도 그대로다."""
    if isinstance(exc, APIStatusError) and not isinstance(exc, RateLimitError):
        return exc.status_code >= 500
    return True


class NIMChatOpenAI(ChatOpenAI):
    """ChatOpenAI + 키 로테이션 · 키별 RPM 슬롯 예약 · 429/5xx 재시도.

    LLM 호출은 네 갈래로 들어온다. `.invoke()`·`.with_structured_output()` 는 `_generate`,
    LangGraph의 `stream_mode="messages"`(SSE 채팅 경로)는 `_stream` 을 탄다. 넷을 다 감싸지
    않으면 실측상 사용자 대면 채팅이 RPM 게이트를 그냥 통과해버린다.
    """

    def _use_key(self, key: str) -> None:
        """이미 만들어진 openai 클라이언트의 키만 갈아끼운다(재생성 불필요)."""
        self.openai_api_key = key  # type: ignore[assignment]
        if self.root_client is not None:
            self.root_client.api_key = key
        if self.root_async_client is not None:
            self.root_async_client.api_key = key

    def _next_key(self) -> str:
        key = _get_rotator().rotate()
        self._use_key(key)
        return key

    def _on_error(self, key: str, exc: Exception) -> None:
        record_failure("agent", exc)  # 실패 원인 계측(NIM 안정성 실측)
        # 429는 잠깐 비켜서면 풀리므로 짧게, 그 외 오류는 키 자체가 문제일 수 있어 길게 쉰다.
        cooldown = 30.0 if isinstance(exc, RateLimitError) else 300.0
        _get_rotator().mark_failed(key, duration=cooldown)
        logger.warning(
            "[NIM] %s 발생 — 키 ...%s 를 %.0f초 쉬게 하고 다음 키로 재시도합니다.",
            type(exc).__name__, key[-4:], cooldown,
        )

    def _attempts(self) -> int:
        return max(2, len(_get_rotator().keys) + 1)

    def _generate(self, *args, **kwargs):
        last: Exception | None = None
        for attempt in range(self._attempts()):
            key = self._next_key()
            time.sleep(reserve(key))
            try:
                return super()._generate(*args, **kwargs)
            except RETRY_EXCEPTIONS as exc:
                if not _should_retry(exc):
                    raise
                self._on_error(key, exc)
                last = exc
                time.sleep(min(2**attempt, 8))
        raise last  # type: ignore[misc]

    async def _agenerate(self, *args, **kwargs):
        last: Exception | None = None
        for attempt in range(self._attempts()):
            key = self._next_key()
            await asyncio.sleep(reserve(key))
            try:
                return await super()._agenerate(*args, **kwargs)
            except RETRY_EXCEPTIONS as exc:
                if not _should_retry(exc):
                    raise
                self._on_error(key, exc)
                last = exc
                await asyncio.sleep(min(2**attempt, 8))
        raise last  # type: ignore[misc]

    # 스트리밍은 첫 청크를 내보낸 뒤에는 재시도할 수 없다(이미 흘린 토큰을 되돌릴 방법이 없다).
    # 그래서 "첫 청크 전에 터진 오류"만 키를 바꿔 재시도하고, 그 이후 오류는 그대로 올린다.
    def _stream(self, *args, **kwargs):
        last: Exception | None = None
        for attempt in range(self._attempts()):
            key = self._next_key()
            time.sleep(reserve(key))
            started = False
            try:
                for chunk in super()._stream(*args, **kwargs):
                    started = True
                    yield chunk
                return
            except RETRY_EXCEPTIONS as exc:
                if started or not _should_retry(exc):
                    raise
                self._on_error(key, exc)
                last = exc
                time.sleep(min(2**attempt, 8))
        raise last  # type: ignore[misc]

    async def _astream(self, *args, **kwargs):
        last: Exception | None = None
        for attempt in range(self._attempts()):
            key = self._next_key()
            await asyncio.sleep(reserve(key))
            started = False
            try:
                async for chunk in super()._astream(*args, **kwargs):
                    started = True
                    yield chunk
                return
            except RETRY_EXCEPTIONS as exc:
                if started or not _should_retry(exc):
                    raise
                self._on_error(key, exc)
                last = exc
                await asyncio.sleep(min(2**attempt, 8))
        raise last  # type: ignore[misc]


def build_chat_model(temperature: float = 0.7, max_tokens: int = 4000) -> NIMChatOpenAI:
    """에이전트 노드에 주입할 NIM 기반 ChatOpenAI 인스턴스를 생성한다."""
    model = require_env("AGENT_LLM_MODEL")
    require_env("NVIDIA_API_KEY")  # 키 부재를 여기서 명확히 실패시킨다

    return NIMChatOpenAI(
        model=model,
        base_url=NIM_BASE_URL,
        api_key=_get_rotator().get_key(),
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=REQUEST_TIMEOUT,
        max_retries=0,  # 같은 키로 재시도해봐야 429는 그대로 — 위 루프가 키를 바꿔가며 재시도한다
        # 구 모델(qwen3-next-80b)은 스트리밍이 delta 4개로만 쪼개져 오면서 비스트리밍보다
        # 2.5배 느려 disable_streaming=True로 껐었다. gpt-oss-120b로 교체 후 실측하니
        # 정상 토큰 단위로 흐르므로(93청크/700토큰) 다시 켠다.
    )
