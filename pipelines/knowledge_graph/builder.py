"""
builder.py
----------
LlamaIndex + Neo4j 기반 세법 및 금융 자산 지식 그래프(Knowledge Graph) 자동 구축 파이프라인.

- data/processed/passages.jsonl 에서 파싱된 금융 단락 로드.
- LlamaIndex PropertyGraphIndex 및 SchemaLLMPathExtractor 활용.
- PostgreSQL 기반 증분 적재 체크포인트 연동 (이미 처리된 단락 자동 스킵).
- NVIDIA NIM(OpenAI 호환 엔드포인트)을 사용하여 세법 지식 트리플 자동 추출.
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
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import (
    PropertyGraphIndex,
    SchemaLLMPathExtractor,
)
from shared.utils.nim_openai import NIMOpenAI
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from queue import Queue

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("graph_builder")

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# 외부 라이브러리(HTTP 요청, OpenAI, Hugging Face 등)의 불필요한 INFO 로그 억제
for noisy_logger in [
    "httpx",
    "httpcore",
    "openai",
    "urllib3",
    "sentence_transformers",
    "transformers",
    "huggingface_hub",
    "llama_index",
]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)



def setup_llamaindex_settings() -> tuple[NIMOpenAI, HuggingFaceEmbedding]:
    """LlamaIndex의 전역 LLM 및 임베딩 모델 설정."""
    # 1. LLM 설정 (NVIDIA NIM - OpenAI 호환 엔드포인트)
    #    NIMOpenAI가 다중 NVIDIA_API_KEY 로테이션과 동적 딜레이(레이트리밋 회피)를 담당한다.
    logger.info("NVIDIA NIM LLM 연동 설정 중...")
    nim_model = os.environ.get("NIM_GENERATION_MODEL")
    if not nim_model:
        raise RuntimeError("NIM_GENERATION_MODEL 환경변수가 설정되어 있지 않습니다.")
    llm = NIMOpenAI(
        model=nim_model,
        api_base=NIM_BASE_URL,
        temperature=0.0,  # 결정론적 지식 추출을 위해 0.0 설정
        max_tokens=4096,
    )

    # 2. 한국어 지원 임베딩 설정 (로컬 BAAI/bge-m3 모델 사용)
    logger.info("로컬 BAAI/bge-m3 임베딩 모델 로드 중 (CPU)...")
    embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-m3",
        device="cpu",
    )

    # 전역 설정 주입
    Settings.llm = llm
    Settings.embed_model = embed_model
    
    # 한국어 bge-m3 모델의 로컬 스레드 안정성을 보장하기 위해 Lock 적용 오버라이딩
    orig_get_text_embedding = embed_model.get_text_embedding
    orig_get_text_embedding_batch = embed_model.get_text_embedding_batch
    orig_aget_text_embedding = embed_model.aget_text_embedding
    orig_aget_text_embedding_batch = embed_model.aget_text_embedding_batch
    
    embed_lock = Lock()
    
    def thread_safe_get_text_embedding(*args, **kwargs):
        with embed_lock:
            return orig_get_text_embedding(*args, **kwargs)
            
    def thread_safe_get_text_embedding_batch(*args, **kwargs):
        with embed_lock:
            return orig_get_text_embedding_batch(*args, **kwargs)
            
    async def thread_safe_aget_text_embedding(*args, **kwargs):
        with embed_lock:
            return await orig_aget_text_embedding(*args, **kwargs)
            
    async def thread_safe_aget_text_embedding_batch(*args, **kwargs):
        with embed_lock:
            return await orig_aget_text_embedding_batch(*args, **kwargs)
            
    object.__setattr__(embed_model, 'get_text_embedding', thread_safe_get_text_embedding)
    object.__setattr__(embed_model, 'get_text_embedding_batch', thread_safe_get_text_embedding_batch)
    object.__setattr__(embed_model, 'aget_text_embedding', thread_safe_aget_text_embedding)
    object.__setattr__(embed_model, 'aget_text_embedding_batch', thread_safe_aget_text_embedding_batch)
    
    return llm, embed_model



def load_passages_as_documents() -> list[Document]:
    """PostgreSQL 데이터베이스(emb_passages)에서 금융 지침서 단락들을 읽어 LlamaIndex Document로 변환."""
    logger.info("PostgreSQL 데이터베이스(emb_passages)에서 금융 단락 로드 중...")
    documents = []
    
    try:
        from shared.database.connector import db_cursor
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
        from shared.database.connector import db_cursor
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
        from shared.database.connector import db_cursor
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
        from shared.database.connector import db_cursor
        with db_cursor() as (_, cursor):
            params = [(pid,) for pid in passage_ids]
            cursor.executemany(sql, params)
        logger.debug("성공적으로 처리된 %d개의 passage_id를 PostgreSQL에 기록했습니다.", len(passage_ids))
    except Exception as exc:
        logger.error("processed passage_id 저장 오류: %s", exc)


def build_knowledge_graph(documents: list[Document], delay: float = 0.0) -> None:
    """Neo4j 데이터베이스에 세법 및 금융 자산 지식 그래프 자동 구축."""
    if not documents:
        logger.info("새로 적재할 문서가 없습니다.")
        return

    neo4j_url = os.environ.get("NEO4J_URL")
    neo4j_user = os.environ.get("NEO4J_USERNAME")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")

    logger.info("Neo4j Graph Database 연결 설정 중 (%s)...", neo4j_url)
    
    # 1. Neo4j PropertyGraph Store 생성
    graph_store = Neo4jPropertyGraphStore(
        username=neo4j_user,
        password=neo4j_password,
        url=neo4j_url,
        database="neo4j",
    )

    # 병렬 처리 시 Neo4j schema refresh의 동시성 버그(pop from empty list) 방지 및 속도 향상을 위해 get_schema 오버라이드
    orig_get_schema = graph_store.get_schema
    def thread_safe_get_schema(refresh=False, *args, **kwargs):
        # ingestion 단계에서는 refresh를 강제로 False로 전달하여 리프레시를 건너뜁니다.
        return orig_get_schema(refresh=False, *args, **kwargs)
    object.__setattr__(graph_store, "get_schema", thread_safe_get_schema)


    # 2. 세법 전용 스키마 지식 추출 가이드 정의 (Strict Schema Extractor)
    logger.info("금융 세법/자산 전용 스키마 지식 추출 프롬프트/가이드 구성 중...")
    
    from enum import Enum
    
    # 허용 엔티티 종류 (Enum 정의 - LlamaIndex 내부 검증기에서 대문자로 변환되므로 값을 대문자로 정의해야 함)
    class Entities(str, Enum):
        AssetClass = "ASSETCLASS"                 # 자산군 (예: 주식, 채권, 연금, 부동산)
        PortfolioItem = "PORTFOLIOITEM"           # 종목/상품 (예: ISA, IRP, 일반적금, 청년도약계좌)
        IncomeType = "INCOMETYPE"                 # 소득유형 (예: 배당소득, 이자소득, 양도소득, 연금소득)
        TaxRule = "TAXRULE"                       # 세율/세제규칙 (예: 비과세혜택규정, 배당소득세율규칙)
        LegalReference = "LEGALREFERENCE"         # 근거법령 (예: 소득세법 제14조, 금소법)
        TaxExemptCondition = "TAXEXEMPTCONDITION" # 비과세/감면 요건 (예: 5년이상납입유지, 가입당시소득5천만원이하)
        ContributionLimit = "CONTRIBUTIONLIMIT"   # 납입/투자 한도 (예: 연간 1800만원한도, 납입한도 2천만원)
        TaxRateInfo = "TAXRATEINFO"               # 구체적 세율 정보 (예: 15.4% 세율, 9% 원천징수)
    
    # 허용 관계 종류 (Enum 정의)
    class Relations(str, Enum):
        BELONGS_TO = "BELONGS_TO"
        GENERATES = "GENERATES"
        SUBJECT_TO = "SUBJECT_TO"
        BASED_ON = "BASED_ON"
    
    # 유효 관계 제약조건 스키마 정의 (List[Tuple[str, str, str]])
    kg_validation_schema = [
        ("PORTFOLIOITEM", "BELONGS_TO", "ASSETCLASS"),
        ("ASSETCLASS", "GENERATES", "INCOMETYPE"),
        ("INCOMETYPE", "SUBJECT_TO", "TAXRULE"),
        ("PORTFOLIOITEM", "SUBJECT_TO", "TAXRULE"),
        ("TAXRULE", "BASED_ON", "LEGALREFERENCE"),
        ("PORTFOLIOITEM", "HAS_LIMIT", "CONTRIBUTIONLIMIT"),
        ("ASSETCLASS", "HAS_LIMIT", "CONTRIBUTIONLIMIT"),
        ("TAXEXEMPTCONDITION", "PROVIDES_BENEFIT", "INCOMETYPE"),
        ("TAXEXEMPTCONDITION", "PROVIDES_BENEFIT", "TAXRULE"),
        ("TAXEXEMPTCONDITION", "APPLIES_WHEN", "PORTFOLIOITEM"),
        ("TAXEXEMPTCONDITION", "APPLIES_WHEN", "INCOMETYPE"),
        ("TAXRULE", "DEFINES_RATE", "TAXRATEINFO"),
        ("TAXRATEINFO", "BASED_ON", "LEGALREFERENCE"),
    ]

    custom_extract_prompt = (
        "당신은 금융 및 세법 전문 지식 그래프 추출기입니다.\n"
        "주어진 텍스트 본문에서 한국 금융 세제와 자산 운용에 관련된 노드(Entity)와 관계(Relationship)를 정확하게 추출하십시오.\n\n"
        "### 기본(Base) 스키마 가이드:\n"
        "1. 엔티티 유형(Entities) 정의:\n"
        "   - ASSETCLASS (자산군): 예) 주식, 채권, 연금, 부동산\n"
        "   - PORTFOLIOITEM (종목/상품): 예) ISA, IRP, 일반적금, 청년도약계좌\n"
        "   - INCOMETYPE (소득유형): 예) 배당소득, 이자소득, 양도소득, 연금소득\n"
        "   - TAXRULE (세율/세제규칙): 예) 비과세혜택규정, 배당소득세율규칙\n"
        "   - LEGALREFERENCE (근거법령): 예) 소득세법 제14조, 금융소비자보호법\n"
        "   - TAXEXEMPTCONDITION (비과세/감면 요건): 예) 5년이상납입유지, 가입당시소득5천만원이하\n"
        "   - CONTRIBUTIONLIMIT (납입/투자 한도): 예) 연간 1800만원한도, 납입한도 2천만원\n"
        "   - TAXRATEINFO (구체적 세율 정보): 예) 15.4% 세율, 9% 원천징수\n"
        "2. 관계 유형(Relations) 정의:\n"
        "   - BELONGS_TO, GENERATES, SUBJECT_TO, BASED_ON, HAS_LIMIT, APPLIES_WHEN, PROVIDES_BENEFIT, DEFINES_RATE\n\n"
        "### ⚠️ 동적 스키마 확장 규칙 (중요):\n"
        "- 본문을 분석할 때 위의 기본 스키마에 딱 들어맞지 않지만, 세무/금융 맥락상 매우 중요하다고 판단되는 고유한 개념이나 속성\n"
        "  (예: 특정 세금 우대 혜택 명칭, 특별 공제 대상, 대주주 판정 요건 등)이 등장하는 경우,\n"
        "  **새로운 엔티티 유형 및 관계 유형을 동적으로 창안하여 자유롭게 추출하십시오.**\n"
        "- 단, 무분별한 노드 난립을 막기 위해 개념이 명확하고 중복되지 않는 용어를 사용하십시오.\n\n"
        "최대 {max_triplets_per_chunk}개의 추출된 경로로 출력을 제한하십시오.\n"
        "-------\n"
        "{text}\n"
        "-------\n"
    )

    # 2. API 키 로드 및 각 모델별 LLM + Extractor 풀 빌드
    #    키 1개당 추출기 1개 = 병렬 워커 1개 (키별로 레이트리밋을 분산)
    extractors = []

    # 환경변수에서 NVIDIA API 키 목록 동적 로드
    nim_keys = []
    if os.environ.get("NVIDIA_API_KEY"):
        nim_keys.append(os.environ.get("NVIDIA_API_KEY"))
    if os.environ.get("NVIDIA_API_KEY_2"):
        nim_keys.append(os.environ.get("NVIDIA_API_KEY_2"))
    
    i = 3
    while True:
        k = os.environ.get(f"NVIDIA_API_KEY_{i}")
        if not k:
            break
        nim_keys.append(k)
        i += 1
        
    if not nim_keys:
        raise RuntimeError(
            "NVIDIA_API_KEY가 설정되어 있지 않습니다. .env에 최소 1개의 키를 추가하세요."
        )

    nim_model = os.environ.get("NIM_GENERATION_MODEL")
    for idx, key in enumerate(nim_keys, start=1):
        # NIMOpenAI를 쓰면 호출마다 키별 RPM 슬롯 예약(nim_rate_limit) + 429 백오프가 적용된다.
        nim_llm = NIMOpenAI(
            model=nim_model,
            api_key=key,
            api_base=NIM_BASE_URL,
            temperature=0.0,
            max_tokens=10000,
        )
        extractors.append((
            SchemaLLMPathExtractor(
                llm=nim_llm,
                possible_entities=Entities,
                possible_relations=Relations,
                kg_validation_schema=kg_validation_schema,
                strict=False,
                extract_prompt=custom_extract_prompt,
                num_workers=1,
            ),
            f"NVIDIA-NIM-{idx}"
        ))

    num_workers = len(extractors)
    logger.info("총 %d개의 병렬 추출기(NVIDIA NIM 키 %d개)를 준비했습니다.",
                num_workers, len(nim_keys))
    
    # 3. ThreadPoolExecutor 빌드 및 Neo4j 적재 (루프를 돌며 병렬 처리 및 즉시 커밋)
    total_docs = len(documents)
    logger.info("지식 그래프 구축 및 Neo4j 추가 적재 시작 (총 %d개 단락 병렬 처리)...", total_docs)
    logger.info("기존 Neo4j 데이터를 보존하고 추가 적재합니다.")
    
    start_time = time.perf_counter()
    success_count = 0
    
    # 스레드 안전하게 공유할 큐와 락
    extractor_queue = Queue()
    for ext, name in extractors:
        extractor_queue.put((ext, name))
        
    progress_lock = Lock()
    
    def worker_task(doc, doc_idx):
        # 큐에서 사용 가능한 추출기 대여
        ext, w_name = extractor_queue.get()
        
        with progress_lock:
            logger.info("[%d/%d] [%s] %s 시작...", doc_idx, total_docs, w_name, doc.id_)
            
        max_retries = 3
        backoff = 2.0  # 초
        success = False
        
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    # 단일 문서에 대해 PropertyGraphIndex 구축 수행 (Neo4j에 자동 반영)
                    PropertyGraphIndex.from_documents(
                        [doc],
                        property_graph_store=graph_store,
                        kg_extractors=[ext],
                        show_progress=False,
                    )
                    # 성공 즉시 DB 체크포인트 테이블에 기록
                    with progress_lock:
                        save_processed_passage_ids([doc.id_])
                        nonlocal success_count
                        success_count += 1
                        logger.info("✅ [%d/%d] [%s] %s 완료!", doc_idx, total_docs, w_name, doc.id_)
                    success = True
                    break
                except Exception as exc:
                    with progress_lock:
                        if attempt < max_retries:
                            sleep_time = backoff * (2 ** (attempt - 1))
                            logger.warning(
                                "⚠️ [%d/%d] [%s] %s 오류 (%d/%d 시도), %s초 후 재시도: %s",
                                doc_idx, total_docs, w_name, doc.id_, attempt, max_retries, sleep_time, exc
                            )
                            time.sleep(sleep_time)
                        else:
                            logger.error("❌ [%d/%d] [%s] %s 최종 실패 (%d/%d 시도): %s", 
                                         doc_idx, total_docs, w_name, doc.id_, attempt, max_retries, exc)
            
            if delay > 0:
                logger.info("[%s] 작업 완료. 다음 작업 시작 전 %.2f초 대기합니다...", w_name, delay)
                time.sleep(delay)
                
            return success
        finally:
            # 사용 후 큐에 반납
            extractor_queue.put((ext, w_name))

    # ThreadPoolExecutor를 통한 병렬 실행 (모든 작업을 큐에 넣고 워커별 개별 진행)
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_task, doc, idx) for idx, doc in enumerate(documents, start=1)]
        for fut in futures:
            try:
                fut.result()
            except KeyboardInterrupt:
                logger.warning("⚠️ 사용자에 의해 작업이 인터럽트 되었습니다. 중단을 시도합니다.")
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            except Exception:
                pass
            
    elapsed = time.perf_counter() - start_time
    logger.info("=" * 60)
    logger.info("지식 그래프 구축 세션 종료 (성공: %d/%d, 소요 시간: %.2f초)", success_count, total_docs, elapsed)
    logger.info("웹 브라우저로 http://localhost:7474 에 접속하여 그래프를 확인하세요.")
    logger.info("=" * 60)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="LlamaIndex + Neo4j 금융 세법 지식 그래프 자동 구축 파이프라인")
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=40,
        help="이번 실행에서 처리할 미처리 단락의 최대 개수 (기본값: 40, 전체를 처리하려면 -1 입력)"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.0,
        help="각 NIM 추출기가 작업을 완료한 후 다음 작업을 시작하기 전 대기할 시간(초) (기본값: 0.0)"
    )
    args = parser.parse_args()

    try:
        # 1. PostgreSQL 체크포인트 테이블 초기화
        init_checkpoint_table()
        
        # 2. 전역 설정 세팅 (Settings.llm / Settings.embed_model 주입)
        setup_llamaindex_settings()
        
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
            
        # 5. 비용 및 시간 관리를 위해 지정된 개수만큼 미처리 단락 선별하여 진행
        limit = args.limit
        if limit < 0:
            target_docs = unprocessed_documents
            logger.info("이번 실행에서 미처리 단락 전체(%d개)를 대상으로 그래프 빌드를 시작합니다.", len(target_docs))
        else:
            target_docs = unprocessed_documents[:limit]
            logger.info("이번 실행에서 처리할 %d개의 미처리 단락으로 그래프 빌드를 시작합니다.", len(target_docs))
        
        build_knowledge_graph(target_docs, delay=args.delay)
        
    except Exception as exc:
        logger.exception("지식 그래프 생성 도중 오류 발생: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
