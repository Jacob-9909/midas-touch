"""
builder.py
----------
LlamaIndex + Neo4j 기반 세법 및 금융 자산 지식 그래프(Knowledge Graph) 자동 구축 파이프라인.

- data/processed/passages.jsonl 에서 파싱된 금융 단락 로드.
- LlamaIndex PropertyGraphIndex 및 SchemaLLMPathExtractor 활용.
- PostgreSQL 기반 증분 적재 체크포인트 연동 (이미 처리된 단락 자동 스킵).
- NVIDIA NIM API (Llama 3.1 70B)를 사용하여 세법 지식 트리플 자동 추출.
- 로컬 Neo4j Graph DB에 그래프 구조 및 HNSW 인덱스 증분 추가(Append) 적재.
"""

import json
import logging
import os
import sys
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가 (src 임포트 호환)
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

load_dotenv()

# LlamaIndex 라이브러리 임포트
from llama_index.core import Document, Settings
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import (
    PropertyGraphIndex,
    SchemaLLMPathExtractor,
)
from llama_index.core.llms import LLMMetadata
from llama_index.core.base.llms.types import MessageRole

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("graph_builder")


class NIMOpenAI(OpenAI):
    """NVIDIA NIM의 OpenAI 호환 API 연동을 위한 LlamaIndex OpenAI 모델 검증 우회 및 동적 Rate Limit 방지 딜레이 서브클래스."""
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # 동적 딜레이 조절을 위한 상태 변수
        self._min_delay = float(os.environ.get("NIM_GRAPH_DELAY", "2.0"))
        self._current_delay = self._min_delay
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

    def _handle_rate_limit(self) -> None:
        # 429 에러 발생 시 동적으로 딜레이를 늘림 (가산 증가)
        old_delay = self._current_delay
        self._current_delay = self._current_delay + self._backoff_step
        logger.warning(
            "⚠️ [NIM API] Rate Limit (429) 감지! 동적 딜레이를 늘립니다: %.2f초 -> %.2f초",
            old_delay, self._current_delay
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
    logger.info("NVIDIA NIM API LLM 연동 설정 중...")
    llm = NIMOpenAI(
        model=os.environ.get("NIM_GENERATION_MODEL", "meta/llama-3.1-70b-instruct"),
        api_key=nvidia_api_key,
        api_base="https://integrate.api.nvidia.com/v1",
        temperature=0.0,  # 결정론적 지식 추출을 위해 0.0 설정
        max_tokens=4096,
    )

    # 2. 한국어 지원 임베딩 설정 (로컬 sentence-transformers/all-MiniLM-L6-v2 모델 사용)
    logger.info("로컬 sentence-transformers/all-MiniLM-L6-v2 임베딩 모델 로드 중 (CPU)...")
    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        device="cpu",
    )

    # 전역 설정 주입
    Settings.llm = llm
    Settings.embed_model = embed_model
    
    return llm, embed_model


def load_passages_as_documents() -> list[Document]:
    """PostgreSQL 데이터베이스(emb_passages)에서 금융 지침서 단락들을 읽어 LlamaIndex Document로 변환."""
    logger.info("PostgreSQL 데이터베이스(emb_passages)에서 금융 단락 로드 중...")
    documents = []
    
    try:
        from src.db.connector import db_cursor
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT passage_id, text, source, metadata FROM emb_passages;")
            rows = cursor.fetchall()
            
            for row in rows:
                p_id, text, source, meta_json = row
                
                if isinstance(meta_json, str):
                    meta = json.loads(meta_json)
                else:
                    meta = meta_json or {}
                
                # 메타데이터 구성
                metadata = {
                    "passage_id": p_id,
                    "source": source,
                    "file_type": meta.get("file_type", "txt"),
                    "chunk_index": meta.get("chunk_index", 0),
                }
                
                # LlamaIndex Document 생성
                doc = Document(
                    text=text,
                    id_=p_id,
                    metadata=metadata,
                    excluded_embed_metadata_keys=["passage_id"],
                    excluded_llm_metadata_keys=["passage_id"],
                )
                documents.append(doc)
    except Exception as exc:
        logger.error("DB에서 passages 로드 중 오류 발생: %s", exc)
        raise
        
    logger.info("총 %d개의 금융 문서 단락 로드 완료.", len(documents))
    return documents


def init_checkpoint_table() -> None:
    """Initialize the graph_checkpoints table in PostgreSQL if it doesn't exist."""
    sql = """
    CREATE TABLE IF NOT EXISTS graph_checkpoints (
        passage_id VARCHAR(100) PRIMARY KEY,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        from src.db.connector import db_cursor
        with db_cursor() as (_, cursor):
            cursor.execute(sql)
        logger.info("PostgreSQL graph_checkpoints 테이블 초기화 완료.")
    except Exception as exc:
        logger.error("checkpoint 테이블 초기화 오류: %s", exc)
        raise


def get_processed_passage_ids() -> set[str]:
    """Fetch the set of already processed passage IDs from PostgreSQL."""
    sql = "SELECT passage_id FROM graph_checkpoints;"
    try:
        from src.db.connector import db_cursor
        with db_cursor() as (_, cursor):
            cursor.execute(sql)
            rows = cursor.fetchall()
            return {row[0] for row in rows}
    except Exception as exc:
        logger.error("이미 처리된 passage_id 조회 오류: %s", exc)
        return set()


def save_processed_passage_ids(passage_ids: list[str]) -> None:
    """Save the successfully processed passage IDs to PostgreSQL."""
    if not passage_ids:
        return
    sql = """
    INSERT INTO graph_checkpoints (passage_id)
    VALUES (%s)
    ON CONFLICT (passage_id) DO NOTHING;
    """
    try:
        from src.db.connector import db_cursor
        with db_cursor() as (_, cursor):
            params = [(pid,) for pid in passage_ids]
            cursor.executemany(sql, params)
        logger.info("성공적으로 처리된 %d개의 passage_id를 PostgreSQL에 기록했습니다.", len(passage_ids))
    except Exception as exc:
        logger.error("processed passage_id 저장 오류: %s", exc)


def build_knowledge_graph(llm: OpenAI, documents: list[Document]) -> None:
    """Neo4j 데이터베이스에 세법 및 금융 자산 지식 그래프 자동 구축."""
    if not documents:
        logger.info("새로 적재할 문서가 없습니다.")
        return

    neo4j_url = os.environ.get("NEO4J_URL", "bolt://localhost:7687")
    neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "PG_develop_2026_Secure")

    logger.info("Neo4j Graph Database 연결 설정 중 (%s)...", neo4j_url)
    
    # 1. Neo4j PropertyGraph Store 생성
    graph_store = Neo4jPropertyGraphStore(
        username=neo4j_user,
        password=neo4j_password,
        url=neo4j_url,
        database="neo4j",
    )

    # 2. 세법 전용 스키마 지식 추출 가이드 정의 (Strict Schema Extractor)
    logger.info("금융 세법/자산 전용 스키마 지식 추출 프롬프트/가이드 구성 중...")
    
    from enum import Enum
    
    # 허용 엔티티 종류 (Enum 정의)
    class Entities(str, Enum):
        AssetClass = "AssetClass"       # 자산군
        IncomeType = "IncomeType"       # 소득유형
        TaxRule = "TaxRule"             # 세율규칙
        LegalReference = "LegalReference" # 근거법령
        PortfolioItem = "PortfolioItem"   # 종목/상품
    
    # 허용 관계 종류 (Enum 정의)
    class Relations(str, Enum):
        BELONGS_TO = "BELONGS_TO"
        GENERATES = "GENERATES"
        SUBJECT_TO = "SUBJECT_TO"
        BASED_ON = "BASED_ON"
    
    # 유효 관계 제약조건 스키마 정의 (List[Tuple[str, str, str]])
    kg_validation_schema = [
        ("PortfolioItem", "BELONGS_TO", "AssetClass"),
        ("AssetClass", "GENERATES", "IncomeType"),
        ("IncomeType", "SUBJECT_TO", "TaxRule"),
        ("PortfolioItem", "SUBJECT_TO", "TaxRule"),
        ("TaxRule", "BASED_ON", "LegalReference"),
    ]

    # Schema 기반 LLM 지식 추출기 세팅
    schema_extractor = SchemaLLMPathExtractor(
        llm=llm,
        possible_entities=Entities,
        possible_relations=Relations,
        kg_validation_schema=kg_validation_schema,
        strict=True,  # 스키마에 엄격히 부합하는 노드/관계만 추출
        num_workers=1, # RPM 한도 준수를 위해 동시성 1 유지
    )
    
    extractors = [schema_extractor]

    # 3. PropertyGraphIndex 빌드 및 Neo4j 적재 (루프를 돌며 순차적 처리 및 즉시 커밋)
    total_docs = len(documents)
    logger.info("지식 그래프 구축 및 Neo4j 추가 적재 시작 (총 %d개 단락 순차 처리)...", total_docs)
    logger.info("기존 Neo4j 데이터를 보존하고 추가 적재합니다.")
    
    start_time = time.perf_counter()
    success_count = 0
    
    for idx, doc in enumerate(documents, start=1):
        logger.info("-" * 50)
        logger.info("[%d / %d] passage_id: %s 처리 시작...", idx, total_docs, doc.id_)
        # 문장 일부 출력 (로깅용)
        snippet = doc.text[:60].replace('\n', ' ') + "..."
        logger.info("내용 일부: %s", snippet)
        
        try:
            # 단일 문서에 대해 PropertyGraphIndex 구축 수행 (Neo4j에 자동 반영)
            PropertyGraphIndex.from_documents(
                [doc],
                property_graph_store=graph_store,
                kg_extractors=extractors,
                show_progress=False,
            )
            # 성공 즉시 DB 체크포인트 테이블에 기록
            save_processed_passage_ids([doc.id_])
            success_count += 1
            logger.info("[%d / %d] passage_id: %s 처리 성공 및 PostgreSQL 체크포인트 기록 완료.", idx, total_docs, doc.id_)
        except (KeyboardInterrupt, SystemExit):
            logger.warning("⚠️ 사용자에 의해 작업이 인터럽트 되었습니다. 루프를 중단합니다.")
            raise
        except Exception as exc:
            logger.error("❌ [%d / %d] passage_id: %s 처리 중 오류 발생: %s", idx, total_docs, doc.id_, exc)
            logger.warning("안정성을 위해 작업을 중단합니다. 다음 실행 시 이 지점부터 이어서 진행됩니다.")
            break
            
    elapsed = time.perf_counter() - start_time
    logger.info("=" * 60)
    logger.info("지식 그래프 구축 세션 종료 (성공: %d/%d, 소요 시간: %.2f초)", success_count, total_docs, elapsed)
    logger.info("웹 브라우저로 http://localhost:7474 에 접속하여 그래프를 확인하세요.")
    logger.info("=" * 60)


def main() -> None:
    try:
        # 1. PostgreSQL 체크포인트 테이블 초기화
        init_checkpoint_table()
        
        # 2. 전역 설정 세팅
        llm, embed_model = setup_llamaindex_settings()
        
        # 3. 모든 문서 단락 로드
        all_documents = load_passages_as_documents()
        
        # 4. 이미 처리된 passage_id 필터링
        processed_ids = get_processed_passage_ids()
        unprocessed_documents = [doc for doc in all_documents if doc.id_ not in processed_ids]
        
        logger.info("전체 %d개 단락 중 이미 처리된 단락: %d개, 미처리 단락: %d개", 
                    len(all_documents), len(processed_ids), len(unprocessed_documents))
        
        if not unprocessed_documents:
            logger.info("🎉 모든 단락이 이미 Neo4j 지식 그래프에 적재 완료되었습니다!")
            return
            
        # 5. 비용 및 시간 관리를 위해 상위 40개 미처리 단락만 선별하여 진행
        target_docs = unprocessed_documents[:40]
        logger.info("이번 실행에서 처리할 %d개의 미처리 단락으로 그래프 빌드를 시작합니다.", len(target_docs))
        
        build_knowledge_graph(llm, target_docs)
        
    except Exception as exc:
        logger.exception("지식 그래프 생성 도중 오류 발생: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
