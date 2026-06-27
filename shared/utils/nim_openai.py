import os
import time
import logging
import asyncio
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import LLMMetadata
from llama_index.core.base.llms.types import MessageRole
from shared.utils.api_key_rotator import APIKeyRotator
from openai import RateLimitError, APITimeoutError, APIConnectionError

logger = logging.getLogger("nim_openai")

# 회전하며 재시도할 예외 유형 정의 (429 Rate Limit, 타임아웃, 연결 실패 등)
RETRY_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError)


class NIMOpenAI(OpenAI):
    """NVIDIA NIM의 OpenAI 호환 API 연동을 위한 LlamaIndex OpenAI 모델 검증 우회,
    동적 Rate Limit 방지 딜레이, 그리고 다중 API 키 자동 로테이션 서브클래스."""
    
    def __init__(self, *args, **kwargs) -> None:
        temp_rotator = APIKeyRotator()
        # API 키가 명시적으로 제공되지 않은 경우 rotator에서 첫 번째 키를 가져와 주입
        if "api_key" not in kwargs or not kwargs["api_key"]:
            kwargs["api_key"] = temp_rotator.get_key()
            
        # openai SDK 내부의 동일 키 재시도 메커니즘을 비활성화(0)하여,
        # API 지연/오류 발생 시 즉시 우리 외곽 루프에서 API 키를 회전할 수 있도록 유도합니다.
        kwargs["max_retries"] = 0

        # 타임아웃 기본값을 200.0초로 지정하여 API 지연 시 너무 오래 대기하지 않고 다음 키로 전환하게 합니다.
        if "timeout" not in kwargs or kwargs["timeout"] is None:
            kwargs["timeout"] = 200.0
            
        super().__init__(*args, **kwargs)
        
        # Pydantic BaseModel의 필드 빌드로 인한 초기화 무효화 방지를 위해 super().__init__ 이후 속성 지정
        self._rotator = temp_rotator
        
        # 동적 딜레이 조절을 위한 상태 변수
        self._min_delay = float(os.environ.get("NIM_GRAPH_DELAY", "2.0"))
        self._current_delay = self._min_delay
        self._backoff_step = 2.0  # 오류 발생 시 증가할 초 단위
        self._decay_step = 0.2    # 성공 시 점진적으로 감소할 초 단위

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=131072,  # Llama 3.1 70B의 128k 컨텍스트 지원
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=True,
            model_name=self.model,
            system_role=MessageRole.SYSTEM,
        )

    def _apply_delay(self) -> None:
        if self._current_delay > 0:
            logger.info("[NIM API] 동기 API 호출 간 %.2f초 지연 대기 중... (현재 동적 딜레이 기준)", self._current_delay)
            time.sleep(self._current_delay)

    async def _apply_adelay(self) -> None:
        if self._current_delay > 0:
            logger.info("[NIM API] 비동기 API 호출 간 %.2f초 지연 대기 중... (현재 동적 딜레이 기준)", self._current_delay)
            await asyncio.sleep(self._current_delay)

    def _handle_success(self) -> None:
        # 성공 시 딜레이를 점진적으로 최소 딜레이 방향으로 감쇠(Decay)
        if self._current_delay > self._min_delay:
            old_delay = self._current_delay
            self._current_delay = max(self._min_delay, self._current_delay - self._decay_step)
            logger.info("[NIM API] 호출 성공! 동적 딜레이 감쇠 적용: %.2f초 -> %.2f초", old_delay, self._current_delay)

    def _handle_api_error(self, exc: Exception) -> None:
        # API 오류 또는 지연 발생 시 동적으로 딜레이를 늘림 (가산 증가)
        old_delay = self._current_delay
        self._current_delay = self._current_delay + self._backoff_step
        
        # 실패한 키는 5분 동안 쿨다운(사용 제외) 처리하여 다음 재시도 및 호출에서 스킵되게 합니다.
        old_key = self.api_key
        self._rotator.mark_failed(old_key, duration=300.0)
        
        # API 키 회전 (쿨다운된 키는 제외하고 남은 활성 키 중에서 선택됨)
        new_key = self._rotator.rotate()
        self.api_key = new_key
        
        # 캐싱된 OpenAI 클라이언트들의 api_key 동적 교체
        if self._client is not None:
            self._client.api_key = new_key
        if self._aclient is not None:
            self._aclient.api_key = new_key
            
        logger.warning(
            "⚠️ [NIM API] API 오류/지연 감지 (%s)! API 키를 교체하고 동적 딜레이를 늘립니다: %.2f초 -> %.2f초 | 키: %s... -> %s...",
            type(exc).__name__, old_delay, self._current_delay, old_key[:10], new_key[:10]
        )

    def _rotate_key_proactive(self) -> None:
        """호출마다 선제적으로 API 키를 회전하여 Rate Limit을 골고루 분산시킵니다."""
        old_key = self.api_key
        new_key = self._rotator.rotate()
        self.api_key = new_key
        
        if self._client is not None:
            self._client.api_key = new_key
        if self._aclient is not None:
            self._aclient.api_key = new_key
            
        logger.info(
            "[NIM API] 선제적 API 키 교체: %s... -> %s...",
            old_key[:10], new_key[:10]
        )

    # 키 회전 + 동적 딜레이 retry 루프 (sync/async 공통 골격)
    def _with_retry(self, call):
        max_retries = len(self._rotator.keys) * 2
        for attempt in range(1, max_retries + 1):
            try:
                self._apply_delay()
                if attempt == 1:
                    self._rotate_key_proactive()
                res = call()
                self._handle_success()
                return res
            except RETRY_EXCEPTIONS as exc:
                self._handle_api_error(exc)
                if attempt == max_retries:
                    raise
                logger.info("[NIM API] %d번째 재시도 대기...", attempt)
            except Exception as e:
                logger.error("[NIM API] 동기 호출 중 일반 예외 발생: %s", e)
                raise

    async def _awith_retry(self, acall):
        max_retries = len(self._rotator.keys) * 2
        for attempt in range(1, max_retries + 1):
            try:
                await self._apply_adelay()
                if attempt == 1:
                    self._rotate_key_proactive()
                res = await acall()
                self._handle_success()
                return res
            except RETRY_EXCEPTIONS as exc:
                self._handle_api_error(exc)
                if attempt == max_retries:
                    raise
                logger.info("[NIM API] %d번째 비동기 재시도 대기...", attempt)
            except Exception as e:
                logger.error("[NIM API] 비동기 호출 중 일반 예외 발생: %s", e)
                raise

    # 동기/비동기 메소드 오버라이딩 인터셉트
    def chat(self, *args, **kwargs):
        return self._with_retry(lambda: super(NIMOpenAI, self).chat(*args, **kwargs))

    def complete(self, *args, **kwargs):
        return self._with_retry(lambda: super(NIMOpenAI, self).complete(*args, **kwargs))

    async def achat(self, *args, **kwargs):
        return await self._awith_retry(lambda: super(NIMOpenAI, self).achat(*args, **kwargs))

    async def acomplete(self, *args, **kwargs):
        return await self._awith_retry(lambda: super(NIMOpenAI, self).acomplete(*args, **kwargs))
