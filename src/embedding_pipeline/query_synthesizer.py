"""
query_synthesizer.py
--------------------
NVIDIA NIM API를 활용한 비동기 금융 쿼리 합성 및 2차 검증 모듈.

- 금융 문서 단락(Passage) → LLM → 다양한 형태의 검색 쿼리 N개 자동 생성.
- asyncio + semaphore로 API 동시 호출 제어.
- [고도화] 생성된 쿼리를 LLM을 활용해 2차 검증(Query Validation)하여 무관하거나 부적절한 노이즈 쿼리 필터링.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx

from .config import PipelineConfig
from .document_parser import Passage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------
@dataclass
class SyntheticQuery:
    """LLM이 합성한 쿼리 단일 인스턴스."""

    query_id: str
    passage_id: str
    query_text: str
    query_type: str      # keyword / question / vague_intent / comparison / regulatory
    source_passage: str  # 원본 단락 텍스트 (역참조용)


@dataclass
class SynthesisResult:
    """단락 하나에 대한 전체 합성 결과."""

    passage_id: str
    queries: list[SyntheticQuery]
    elapsed_sec: float
    error: str | None = None


# ---------------------------------------------------------------------------
# 쿼리 타입 분류기 (LLM 출력 후처리)
# ---------------------------------------------------------------------------
_QUERY_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("regulatory", re.compile(r"법|규제|금소법|세법|가이드라인|준수|위반|허가|신고")),
    ("comparison", re.compile(r"vs|대비|차이|비교|어느|더 나은|vs\.")),
    ("question", re.compile(r"무엇|어떻게|왜|언제|누가|얼마나|\?|인가요|인지|나요")),
    ("vague_intent", re.compile(r"방법|추천|좋은|괜찮|어디|어떤|도움|알려|싶어|궁금")),
]


def _classify_query_type(query_text: str) -> str:
    """규칙 기반으로 쿼리 유형을 분류 (LLM 분류 대신 경량 후처리)."""
    for qtype, pattern in _QUERY_TYPE_PATTERNS:
        if pattern.search(query_text):
            return qtype
    return "keyword"


# ---------------------------------------------------------------------------
# NVIDIA NIM 클라이언트 (비동기 httpx 기반)
# ---------------------------------------------------------------------------
class NIMClient:
    """
    NVIDIA NIM OpenAI-compatible API 비동기 클라이언트.
    재시도 로직 + 지수 백오프 포함.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config.nim
        self._headers = {
            "Authorization": f"Bearer {self._cfg.api_key}",
            "Content-Type": "application/json",
        }
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(self._cfg.max_concurrent_requests)

    async def __aenter__(self) -> "NIMClient":
        self._client = httpx.AsyncClient(
            base_url=self._cfg.base_url,
            headers=self._headers,
            timeout=httpx.Timeout(self._cfg.request_timeout),
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._client:
            await self._client.aclose()

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
    ) -> str:
        """단일 chat completion 요청. 실패 시 지수 백오프 재시도."""
        if self._client is None:
            raise RuntimeError("NIMClient를 async context manager로 사용하세요.")

        payload = {
            "model": self._cfg.generation_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._cfg.temperature,
            "top_p": self._cfg.top_p,
            "max_tokens": self._cfg.max_tokens,
        }

        for attempt in range(max_retries):
            try:
                async with self._semaphore:
                    response = await self._client.post(
                        "/chat/completions", json=payload
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

            except httpx.HTTPStatusError as exc:
                # 429 Rate Limit: 반드시 대기 후 재시도
                if exc.response.status_code == 429:
                    wait_sec = 2 ** (attempt + 2)
                    logger.warning(
                        "Rate limit 도달. %d초 대기 후 재시도 (%d/%d)",
                        wait_sec, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait_sec)
                else:
                    logger.error(
                        "HTTP 오류 [%d]: %s", exc.response.status_code, exc.response.text
                    )
                    raise

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                wait_sec = 2 ** attempt
                logger.warning(
                    "네트워크 오류 (%s). %d초 대기 후 재시도 (%d/%d)",
                    exc, wait_sec, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait_sec)

        raise RuntimeError(f"NIM API 요청 {max_retries}회 모두 실패")


# ---------------------------------------------------------------------------
# 쿼리 합성기 핵심 클래스
# ---------------------------------------------------------------------------
class QuerySynthesizer:
    """
    단락 리스트를 받아 LLM 기반 쿼리를 비동기 대량 합성 + 2차 품질 검증.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self._cfg = config
        self._q_cfg = config.query_synthesis
        self._prompts = config.prompts
        self._client: NIMClient | None = None

    async def __aenter__(self) -> "QuerySynthesizer":
        self._client = NIMClient(self._cfg)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.__aexit__(*args)

    # ------------------------------------------------------------------
    # 퍼블릭 API
    # ------------------------------------------------------------------
    async def synthesize_batch(
        self,
        passages: list[Passage],
        progress_callback: asyncio.Queue | None = None,
    ) -> list[SynthesisResult]:
        """단락 리스트 전체에 대해 비동기 병렬 쿼리 합성 및 검증."""
        tasks = [
            self._synthesize_single(p, progress_callback) for p in passages
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return list(results)

    async def synthesize_stream(
        self, passages: list[Passage]
    ) -> AsyncIterator[SynthesisResult]:
        """완료되는 순서대로 SynthesisResult를 스트리밍 반환."""
        queue: asyncio.Queue[SynthesisResult] = asyncio.Queue()

        async def _worker(p: Passage) -> None:
            result = await self._synthesize_single(p, None)
            await queue.put(result)

        tasks = [asyncio.create_task(_worker(p)) for p in passages]
        for _ in range(len(passages)):
            yield await queue.get()

        await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------
    async def _synthesize_single(
        self,
        passage: Passage,
        progress_callback: asyncio.Queue | None,
    ) -> SynthesisResult:
        """단락 하나에 대한 쿼리 합성 및 품질 검증."""
        start = time.perf_counter()

        try:
            # 1단계: 쿼리 합성 생성
            raw_queries = await self._call_llm_synthesis(passage.text)
            queries = self._parse_and_filter(raw_queries, passage)

            # 2단계: 2차 품질 검증 (설정 활성화 시)
            if self._q_cfg.enable_validation and queries:
                validated_queries = await self._validate_queries_batch(queries, passage.text)
                logger.debug(
                    "[%s] 2차 검증 결과: %d개 중 %d개 합격",
                    passage.passage_id, len(queries), len(validated_queries)
                )
                queries = validated_queries

            elapsed = time.perf_counter() - start

            logger.debug(
                "합성 완료 [%s]: %d개 쿼리 (%.2fs)",
                passage.passage_id, len(queries), elapsed,
            )

            if progress_callback:
                await progress_callback.put(passage.passage_id)

            return SynthesisResult(
                passage_id=passage.passage_id,
                queries=queries,
                elapsed_sec=elapsed,
            )

        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            logger.exception(
                "합성 실패 [%s]: %s (%.2fs)",
                passage.passage_id, exc, elapsed,
            )
            return SynthesisResult(
                passage_id=passage.passage_id,
                queries=[],
                elapsed_sec=elapsed,
                error=str(exc),
            )

    async def _call_llm_synthesis(self, passage_text: str) -> list[str]:
        """NIM API를 호출하여 원시 쿼리 문자열 리스트 반환."""
        assert self._client is not None

        dist = self._q_cfg.query_type_distribution
        user_prompt = self._prompts.query_synthesis_user.format(
            passage=passage_text,
            num_queries=self._q_cfg.queries_per_passage,
            keyword_ratio=int(dist["keyword"] * 100),
            question_ratio=int(dist["question"] * 100),
            vague_ratio=int(dist["vague_intent"] * 100),
            comparison_ratio=int(dist["comparison"] * 100),
            regulatory_ratio=int(dist["regulatory"] * 100),
        )

        raw_content = await self._client.chat_completion(
            system_prompt=self._prompts.query_synthesis_system,
            user_prompt=user_prompt,
        )

        return self._extract_json_list(raw_content)

    async def _validate_queries_batch(
        self,
        queries: list[SyntheticQuery],
        passage_text: str,
    ) -> list[SyntheticQuery]:
        """비동기 병렬 호출로 여러 쿼리의 품질을 일괄 검증."""
        tasks = [self._validate_single_query(q, passage_text) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return [q for q, is_valid in zip(queries, results) if is_valid]

    async def _validate_single_query(
        self,
        query: SyntheticQuery,
        passage_text: str,
    ) -> bool:
        """단일 쿼리 품질에 대해 LLM 호출 검증."""
        assert self._client is not None
        
        user_prompt = self._prompts.query_validation_user.format(
            passage=passage_text,
            query=query.query_text,
        )

        try:
            raw_res = await self._client.chat_completion(
                system_prompt=self._prompts.query_validation_system,
                user_prompt=user_prompt,
            )
            # JSON 파싱 및 is_valid 추출
            res_clean = re.sub(r"```(?:json)?\s*", "", raw_res).strip()
            res_clean = res_clean.replace("```", "").strip()
            
            match = re.search(r"\{.*\}", res_clean, re.DOTALL)
            if not match:
                return True # 파싱 에러 대비 보수적 허용
            
            data = json.loads(match.group())
            is_valid = bool(data.get("is_valid", True))
            if not is_valid:
                logger.warning(
                    "부적합 쿼리 필터링 [%s]: '%s' (사유: %s)",
                    query.passage_id, query.query_text, data.get("reason", "N/A")
                )
            return is_valid
        except Exception as exc:
            logger.debug("쿼리 검증 중 실패 (기본값 허용): %s", exc)
            return True

    @staticmethod
    def _extract_json_list(content: str) -> list[str]:
        """LLM 응답에서 JSON 배열을 안전하게 추출."""
        content = re.sub(r"```(?:json)?\s*", "", content).strip()
        content = content.replace("```", "").strip()

        # JSON 배열 패턴 추출 (첫 번째 매칭)
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            logger.warning("JSON 배열을 찾을 수 없음. 응답: %s", content[:200])
            return []

        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [str(q).strip() for q in parsed if isinstance(q, str)]
        except json.JSONDecodeError as exc:
            logger.warning("JSON 파싱 실패: %s", exc)

        return []

    def _parse_and_filter(
        self, raw_queries: list[str], passage: Passage
    ) -> list[SyntheticQuery]:
        """원시 쿼리 문자열 → SyntheticQuery 변환 + 품질 필터링."""
        seen: set[str] = set()
        results: list[SyntheticQuery] = []

        for idx, query_text in enumerate(raw_queries):
            query_text = query_text.strip()
            tokens = query_text.split()
            token_len = len(tokens)

            # 길이 필터
            if token_len < self._q_cfg.min_query_length:
                logger.debug("쿼리 필터링 (너무 짧음): '%s'", query_text)
                continue
            if token_len > self._q_cfg.max_query_length:
                logger.debug("쿼리 필터링 (너무 김): '%s'", query_text)
                continue

            # 중복 필터
            normalized = query_text.lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            # 단락과 동일한 내용 제외
            if query_text == passage.text:
                continue

            qtype = _classify_query_type(query_text)
            results.append(
                SyntheticQuery(
                    query_id=f"{passage.passage_id}_q{idx:03d}",
                    passage_id=passage.passage_id,
                    query_text=query_text,
                    query_type=qtype,
                    source_passage=passage.text,
                )
            )

        return results


# ---------------------------------------------------------------------------
# 유틸: JSONL 직렬화 / 역직렬화
# ---------------------------------------------------------------------------
def synthesis_results_to_jsonl(results: list[SynthesisResult]) -> list[dict]:
    """SynthesisResult 리스트를 JSONL 직렬화 가능한 dict 리스트로 변환."""
    rows = []
    for result in results:
        for q in result.queries:
            rows.append(
                {
                    "query_id": q.query_id,
                    "passage_id": q.passage_id,
                    "query_text": q.query_text,
                    "query_type": q.query_type,
                    "source_passage": q.source_passage,
                    "elapsed_sec": result.elapsed_sec,
                }
            )
    return rows
