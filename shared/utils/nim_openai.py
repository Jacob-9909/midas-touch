import asyncio
import logging
import os
import time

from llama_index.core.base.llms.types import MessageRole
from llama_index.core.llms import LLMMetadata
from llama_index.llms.openai import OpenAI
from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from shared.utils.api_key_rotator import APIKeyRotator
from shared.utils.nim_rate_limit import reserve
from shared.utils.nim_stats import record_failure

logger = logging.getLogger("nim_openai")

# 회전하며 재시도할 예외 유형 정의.
# InternalServerError는 5xx 전반(NIM은 모델 워커가 붐비면 503 ResourceExhausted를 뱉는다)을 덮는다.
RETRY_EXCEPTIONS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


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
        
        # 동적 딜레이 조절을 위한 상태 변수.
        # 분당 호출 수 자체는 nim_rate_limit.reserve()가 정확히 통제하므로 기본값은 0이고,
        # NIM_GRAPH_DELAY는 그 위에 얹는 추가 여유(호출 간 최소 간격) 튜닝 노브로만 남긴다.
        self._min_delay = float(os.environ.get("NIM_GRAPH_DELAY", "0"))
        self._current_delay = self._min_delay
        self._backoff_step = 2.0  # 오류 발생 시 증가할 초 단위
        # 성공하면 절반으로 줄인다. 가산 증가 + 미세 감쇠(0.2초)를 쓰면 시작 직후 커넥션 오류 몇 번에
        # 딜레이가 30초까지 치솟고 사실상 회복되지 않아, 워커를 늘려도 전부 sleep만 하게 된다.
        self._max_delay = 10.0

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

    def _wait_seconds(self) -> float:
        """분당 호출 한도(RPM) 슬롯 예약 대기 + 동적 백오프 딜레이의 합."""
        return reserve(self.api_key) + self._current_delay

    def _apply_delay(self) -> None:
        wait = self._wait_seconds()
        if wait > 0:
            logger.info("[NIM API] 동기 API 호출 전 %.2f초 대기 중... (RPM 슬롯 + 동적 딜레이)", wait)
            time.sleep(wait)

    async def _apply_adelay(self) -> None:
        wait = self._wait_seconds()
        if wait > 0:
            logger.info("[NIM API] 비동기 API 호출 전 %.2f초 대기 중... (RPM 슬롯 + 동적 딜레이)", wait)
            await asyncio.sleep(wait)

    def _handle_success(self) -> None:
        # 성공 시 딜레이를 절반으로 감쇠(Decay). RPM 자체는 nim_rate_limit이 정확히 막으므로
        # 이 딜레이는 일시적 오류에 대한 완충일 뿐, 오래 끌 이유가 없다.
        if self._current_delay > self._min_delay:
            old_delay = self._current_delay
            halved = self._current_delay / 2
            # 0.1초 미만으로 남은 잔여 딜레이는 그냥 최소값으로 스냅(반감만 하면 영원히 0에 못 닿는다)
            self._current_delay = self._min_delay if halved < self._min_delay + 0.1 else halved
            logger.info("[NIM API] 호출 성공! 동적 딜레이 감쇠 적용: %.2f초 -> %.2f초", old_delay, self._current_delay)

    def _handle_api_error(self, exc: Exception) -> None:
        record_failure("pipeline", exc)  # 실패 원인 계측(NIM 안정성 실측)
        # API 오류 또는 지연 발생 시 동적으로 딜레이를 늘림 (가산 증가)
        old_delay = self._current_delay
        self._current_delay = min(self._max_delay, self._current_delay + self._backoff_step)
        
        # 실패한 키를 쿨다운(사용 제외) 처리해 다음 재시도에서 스킵되게 합니다.
        # 429는 창이 지나면 바로 풀리므로 짧게 — 키가 2개뿐인데 5분씩 재우면 둘 다 쿨다운되어
        # 로테이터가 전체 초기화로 되돌리고, 결국 쿨다운이 무의미해집니다.
        old_key = self.api_key
        cooldown = 30.0 if isinstance(exc, RateLimitError) else 300.0
        self._rotator.mark_failed(old_key, duration=cooldown)
        
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
                # 키를 먼저 고르고 그 키의 RPM 슬롯을 예약해야 한다(예약은 키 단위)
                if attempt == 1:
                    self._rotate_key_proactive()
                self._apply_delay()
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
                # 키를 먼저 고르고 그 키의 RPM 슬롯을 예약해야 한다(예약은 키 단위)
                if attempt == 1:
                    self._rotate_key_proactive()
                await self._apply_adelay()
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

    # ── 구조화 출력(structured output) ───────────────────────────────────────
    # NIM(vLLM)의 tool-call 경로는 중첩 스키마를 지키지 못한다. KGSchema를 요구해도
    # {"triplets": [["상장주식","거래구분","장내거래"]]} 처럼 3원소 배열로 평탄화해서 뱉고,
    # llama_index는 파싱 실패를 삼켜(triplets=[]) 조용히 0건이 된다.
    # guided decoding(response_format=json_schema)은 문법 자체를 강제하므로 이 경로로 고정한다.
    # ponytail: 프롬프트를 그대로 한 번 던지는 최소 구현. 스키마가 커져 guided decoding이
    #           느려지면 그때 청크 분할/스키마 축소를 고민한다.
    def _json_schema_format(self, output_cls) -> dict:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": getattr(output_cls, "__name__", "Output"),
                "schema": output_cls.model_json_schema(),
                "strict": True,
            },
        }

    @staticmethod
    def _parse_json_output(output_cls, content: str):
        # guided decoding이라 보통 순수 JSON이지만, 추론형 모델이 앞뒤에 텍스트를 붙이는 경우를 방어
        text = (content or "").strip()
        if not text.startswith("{"):
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end <= start:
                raise ValueError(f"구조화 출력에서 JSON을 찾지 못했습니다: {text[:200]!r}")
            text = text[start : end + 1]
        return output_cls.model_validate_json(text)

    def structured_predict(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        response = self.chat(
            prompt.format_messages(**prompt_args),
            response_format=self._json_schema_format(output_cls),
        )
        return self._parse_json_output(output_cls, response.message.content)

    async def astructured_predict(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        response = await self.achat(
            prompt.format_messages(**prompt_args),
            response_format=self._json_schema_format(output_cls),
        )
        return self._parse_json_output(output_cls, response.message.content)

    # 동기/비동기 메소드 오버라이딩 인터셉트
    def chat(self, *args, **kwargs):
        return self._with_retry(lambda: super(NIMOpenAI, self).chat(*args, **kwargs))

    def complete(self, *args, **kwargs):
        return self._with_retry(lambda: super(NIMOpenAI, self).complete(*args, **kwargs))

    async def achat(self, *args, **kwargs):
        return await self._awith_retry(lambda: super(NIMOpenAI, self).achat(*args, **kwargs))

    async def acomplete(self, *args, **kwargs):
        return await self._awith_retry(lambda: super(NIMOpenAI, self).acomplete(*args, **kwargs))
