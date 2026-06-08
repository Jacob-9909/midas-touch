"""
builder.py
----------
LlamaIndex + Neo4j 기반 세법 및 금융 자산 지식 그래프(Knowledge Graph) 자동 구축 파이프라인.

- data/processed/passages.jsonl 에서 파싱된 금융 단락 로드.
- LlamaIndex PropertyGraphIndex 및 SchemaLLMPathExtractor 활용.
- PostgreSQL 기반 증분 적재 체크포인트 연동 (이미 처리된 단락 자동 스킵).
- Google Gemini API (gemini-2.5-flash)를 사용하여 세법 지식 트리플 자동 추출.
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
from llama_index.llms.google_genai import GoogleGenAI

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("graph_builder")


def setup_llamaindex_settings() -> tuple[GoogleGenAI, HuggingFaceEmbedding]:
    """LlamaIndex의 전역 LLM 및 임베딩 모델 설정."""
    # 1. LLM 설정 (Vertex AI 경유 Gemini - gemini-2.5-flash 활용)
    #    AI Studio API 키 대신 Vertex AI를 사용해 GCP 무료 평가판 크레딧으로 청구되도록 함.
    #    인증은 서비스 계정 키(GOOGLE_APPLICATION_CREDENTIALS)를 통한 ADC로 자동 처리.
    logger.info("Vertex AI (Gemini) LLM 연동 설정 중...")
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        raise ValueError(
            "GOOGLE_CLOUD_PROJECT가 설정되지 않았습니다. .env에 GOOGLE_CLOUD_PROJECT와 "
            "GOOGLE_APPLICATION_CREDENTIALS(서비스 계정 키 경로)를 추가하세요."
        )
    llm = GoogleGenAI(
        model=os.environ.get("GEMINI_GENERATION_MODEL", "gemini-2.5-flash"),
        temperature=0.0,  # 결정론적 지식 추출을 위해 0.0 설정
        max_tokens=4096,
        vertexai_config={"project": project, "location": location},
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
        logger.info("성공적으로 처리된 %d개의 passage_id를 PostgreSQL에 기록했습니다.", len(passage_ids))
    except Exception as exc:
        logger.error("processed passage_id 저장 오류: %s", exc)


def build_knowledge_graph(llm: GoogleGenAI, documents: list[Document]) -> None:
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

    custom_system_prompt = (
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
        "- 단, 무분별한 노드 난립을 막기 위해 개념이 명확하고 중복되지 않는 용어를 사용하십시오."
    )

    # Schema 기반 LLM 지식 추출기 세팅
    schema_extractor = SchemaLLMPathExtractor(
        llm=llm,
        possible_entities=Entities,
        possible_relations=Relations,
        kg_validation_schema=kg_validation_schema,
        strict=False,  # 기본 스키마 외에 LLM이 제안한 새로운 노드/관계도 동적으로 허용
        system_prompt=custom_system_prompt,
        num_workers=2, # Vertex AI의 넉넉한 할당량을 활용하기 위해 동시성 상향 조정
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
