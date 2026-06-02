"""
test_rag.py
-----------
LlamaIndex + Neo4j 기반 지식 그래프 RAG (GraphRAG) 질의 추론 테스트 실행 스크립트.

- 이미 구축된 Neo4j Property Graph Store 연결.
- LlamaIndex PropertyGraphIndex 를 불러와 GraphRAG Query Engine 구성.
- 사용자의 복잡한 세무 자연어 질문에 대해 그래프 관계 탐색 및 본문 합성을 조합한 최적 지식 답변 도출.
"""

import os
import sys
import logging
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가 (src 임포트 호환)
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

load_dotenv()

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import PropertyGraphIndex
from llama_index.core.llms import LLMMetadata
from llama_index.core.base.llms.types import MessageRole

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test_graph_rag")


class NIMOpenAI(OpenAI):
    """NVIDIA NIM의 OpenAI 호환 API 연동을 위한 LlamaIndex OpenAI 모델 검증 우회 및 동적 Rate Limit 방지 딜레이 서브클래스."""
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # 동적 딜레이 조절을 위한 상태 변수
        self._min_delay = float(os.environ.get("NIM_GRAPH_DELAY", "2.0"))
        self.current_delay = self._min_delay
        self._backoff_step = 2.0  # 429 발생 시 증가할 초 단위
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
        if self.current_delay > 0:
            logger.info("[NIM API] 동기 API 호출 간 %.2f초 지연 대기 중... (현재 동적 딜레이 기준)", self.current_delay)
            time.sleep(self.current_delay)

    async def _apply_adelay(self) -> None:
        if self.current_delay > 0:
            logger.info("[NIM API] 비동기 API 호출 간 %.2f초 지연 대기 중... (현재 동적 딜레이 기준)", self.current_delay)
            await asyncio.sleep(self.current_delay)

    def _handle_success(self) -> None:
        # 성공 시 딜레이를 점진적으로 최소 딜레이 방향으로 감쇠(Decay)
        if self.current_delay > self._min_delay:
            old_delay = self.current_delay
            self.current_delay = max(self._min_delay, self.current_delay - self._decay_step)
            logger.info("[NIM API] 호출 성공! 동적 딜레이 감쇠 적용: %.2f초 -> %.2f초", old_delay, self.current_delay)

    def _handle_rate_limit(self) -> None:
        # 429 에러 발생 시 동적으로 딜레이를 늘림 (가산 증가)
        old_delay = self.current_delay
        self.current_delay = self.current_delay + self._backoff_step
        logger.warning(
            "⚠️ [NIM API] Rate Limit (429) 감지! 동적 딜레이를 늘립니다: %.2f초 -> %.2f초",
            old_delay, self.current_delay
        )

    # 동기 메소드 오버라이딩 인터셉트
    def chat(self, *args, **kwargs):
        from openai import RateLimitError
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                self._apply_delay()
                res = super().chat(*args, **kwargs)
                self._handle_success()
                return res
            except RateLimitError:
                self._handle_rate_limit()
                if attempt == max_retries:
                    raise
                logger.info("[NIM API] %d번째 재시도 대기...", attempt)
            except Exception as e:
                logger.error("[NIM API] 동기 호출 중 일반 예외 발생: %s", e)
                raise

    def complete(self, *args, **kwargs):
        from openai import RateLimitError
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                self._apply_delay()
                res = super().complete(*args, **kwargs)
                self._handle_success()
                return res
            except RateLimitError:
                self._handle_rate_limit()
                if attempt == max_retries:
                    raise
                logger.info("[NIM API] %d번째 재시도 대기...", attempt)
            except Exception as e:
                logger.error("[NIM API] 동기 호출 중 일반 예외 발생: %s", e)
                raise

    # 비동기 메소드 오버라이딩 인터셉트
    async def achat(self, *args, **kwargs):
        from openai import RateLimitError
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                await self._apply_adelay()
                res = await super().achat(*args, **kwargs)
                self._handle_success()
                return res
            except RateLimitError:
                self._handle_rate_limit()
                if attempt == max_retries:
                    raise
                logger.info("[NIM API] %d번째 비동기 재시도 대기...", attempt)
            except Exception as e:
                logger.error("[NIM API] 비동기 호출 중 일반 예외 발생: %s", e)
                raise

    async def acomplete(self, *args, **kwargs):
        from openai import RateLimitError
        max_retries = 5
        for attempt in range(1, max_retries + 1):
            try:
                await self._apply_adelay()
                res = await super().acomplete(*args, **kwargs)
                self._handle_success()
                return res
            except RateLimitError:
                self._handle_rate_limit()
                if attempt == max_retries:
                    raise
                logger.info("[NIM API] %d번째 비동기 재시도 대기...", attempt)
            except Exception as e:
                logger.error("[NIM API] 비동기 호출 중 일반 예외 발생: %s", e)
                raise



def setup_llamaindex_settings() -> tuple[NIMOpenAI, HuggingFaceEmbedding]:
    """LlamaIndex의 전역 LLM 및 임베딩 모델 설정."""
    nvidia_api_key = os.environ.get("NVIDIA_API_KEY")
    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY 환경 변수가 존재하지 않습니다.")

    # 1. LLM 설정 (NVIDIA NIM - Llama3-70B Instruct 활용)
    llm = NIMOpenAI(
        model=os.environ.get("NIM_GENERATION_MODEL", "meta/llama-3.1-70b-instruct"),
        api_key=nvidia_api_key,
        api_base="https://integrate.api.nvidia.com/v1",
        temperature=0.0,  # 정확한 조언 생성을 위해 0.0 설정
    )

    # 2. 임베딩 설정 (로컬 sentence-transformers/all-MiniLM-L6-v2 모델 사용)
    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        device="cpu",
    )

    Settings.llm = llm
    Settings.embed_model = embed_model
    
    return llm, embed_model


def run_graph_rag_query(query_text: str) -> None:
    """구축된 Neo4j 지식 그래프를 대상으로 GraphRAG 질의 추론 실행."""
    neo4j_url = os.environ.get("NEO4J_URL", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "PG_develop_2026_Secure")

    logger.info("=" * 60)
    logger.info("질의어: %s", query_text)
    logger.info("=" * 60)

    # 1. Neo4j PropertyGraph Store 연결
    graph_store = Neo4jPropertyGraphStore(
        username=neo4j_user,
        password=neo4j_password,
        url=neo4j_url,
        database="neo4j",
    )

    # 2. 기존 구축된 스토어로부터 인덱스 불러오기
    index = PropertyGraphIndex.from_existing(
        property_graph_store=graph_store
    )

    # 3. 그래프 탐색 중심의 Query Engine 구성
    query_engine = index.as_query_engine(
        include_text=True,  # 매핑된 본문 텍스트 청크 포함 (컨텍스트 강화)
        similarity_top_k=3, # 유사도 기준 추출할 노드 개수
    )

    # 4. 추론 실행
    logger.info("GraphRAG 추론 가동 및 Neo4j 그래프 데이터 탐색 중...")
    response = query_engine.query(query_text)

    print("\n" + "✨" * 30)
    print("GraphRAG 최종 답변")
    print("✨" * 30)
    print(response.response)
    print("✨" * 30 + "\n")

    # 디버깅: 노출된 소스 노드 및 에지 정보 가시화
    if hasattr(response, "source_nodes") and response.source_nodes:
        logger.info("참조된 지식 노드 및 관계 정보:")
        for idx, node_with_score in enumerate(response.source_nodes, start=1):
            node = node_with_score.node
            logger.info("  [%d] 참조 출처: %s", idx, node.metadata.get("source", "unknown"))
            # 일부 텍스트 발췌
            snippet = node.text[:100].replace('\n', ' ') + "..."
            logger.info("      요약문: %s", snippet)


def main() -> None:
    # 샘플 질문 리스트 (금융 및 세무 도메인 특화)
    sample_queries = [
        "배당소득에 적용되는 소득세 세율과 한도를 설명해 주세요.",
        "주식 양도소득세의 근거 법령 조항은 무엇인가요?",
        "이자소득은 어떤 세율이 적용되고 무엇을 기준으로 과세되나요?"
    ]

    try:
        setup_llamaindex_settings()
        
        # 첫 번째 샘플 질문 실행 테스트
        run_graph_rag_query(sample_queries[0])
        
    except Exception as exc:
        logger.exception("GraphRAG 테스트 질의 중 오류 발생: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
