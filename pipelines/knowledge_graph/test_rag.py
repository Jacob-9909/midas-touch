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
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import PropertyGraphIndex
from shared.utils.nim_openai import NIMOpenAI

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test_graph_rag")


def setup_llamaindex_settings() -> tuple[NIMOpenAI, HuggingFaceEmbedding]:
    """LlamaIndex의 전역 LLM 및 임베딩 모델 설정."""
    # 1. LLM 설정 (NVIDIA NIM - Llama3-70B Instruct 활용)
    llm = NIMOpenAI(
        model=os.environ.get("NIM_GENERATION_MODEL", "meta/llama-3.1-70b-instruct"),
        api_base="https://integrate.api.nvidia.com/v1",
        temperature=0.0,  # 정확한 조언 생성을 위해 0.0 설정
    )

    # 2. 임베딩 설정 (로컬 BAAI/bge-m3 모델 사용)
    embed_model = HuggingFaceEmbedding(
        model_name="BAAI/bge-m3",
        device="cpu",
    )

    Settings.llm = llm
    Settings.embed_model = embed_model
    
    return llm, embed_model


def run_graph_rag_query(query_text: str) -> None:
    """구축된 Neo4j 지식 그래프를 대상으로 다중 홉(Multi-hop) GraphRAG 질의 추론 실행."""
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

    # 3. 1단계: 벡터 검색으로 연관 노드 및 본문 텍스트 청크 추출
    logger.info("1단계: 질문과 유사한 핵심 지식 노드 검색 중...")
    from llama_index.core.indices.property_graph import VectorContextRetriever
    vector_retriever = VectorContextRetriever(
        graph_store=graph_store,
        embed_model=Settings.embed_model,
        similarity_top_k=5,
        path_depth=1,
    )
    
    retrieved_nodes = vector_retriever.retrieve(query_text)
    
    # 4. 2단계: 검색된 노드들과 연결된 2-hop 범위 내의 세법/자산 관계망(Subgraph) 탐색
    logger.info("2단계: Neo4j 그래프망 내에서 2-hop 다중 홉 관계 탐색 및 구조 추출...")
    subgraph_triplets = []
    text_contexts = []
    
    node_names = set()
    for node_with_score in retrieved_nodes:
        node = node_with_score.node
        node_name = node.metadata.get("name") or node.text.split("\n")[0]
        if node_name:
            node_names.add(node_name)
        if node.text:
            text_contexts.append(node.text)

    # Neo4j Cypher 쿼리를 직접 수행하여 다중 홉 구조 추출
    if node_names:
        cypher_query = """
        MATCH (n)-[r]-(m)
        WHERE n.name IN $node_names OR m.name IN $node_names
        RETURN n.name AS source, labels(n)[0] AS s_label, type(r) AS rel, m.name AS target, labels(m)[0] AS t_label
        LIMIT 35
        """
        try:
            records = graph_store.structured_query(cypher_query, {"node_names": list(node_names)})
            for rec in records:
                source = rec.get("source")
                rel = rec.get("rel")
                target = rec.get("target")
                s_lbl = rec.get("s_label", "")
                t_lbl = rec.get("t_label", "")
                subgraph_triplets.append(f"({source}:{s_lbl}) -[{rel}]-> ({target}:{t_lbl})")
        except Exception as cy_exc:
            logger.warning("Cypher 기반 다중 홉 관계 추출 실패 (Fallback 적용): %s", cy_exc)

    # 5. 3단계: 그래프 관계망과 본문 텍스트 컨텍스트 결합
    logger.info("3단계: 수집된 그래프 컨텍스트 및 텍스트 융합...")
    
    graph_context_str = "\n".join(set(subgraph_triplets)) if subgraph_triplets else "추출된 그래프 관계가 없습니다."
    
    # 본문 텍스트 중복 제거 및 결합
    unique_texts = []
    for txt in text_contexts:
        if txt not in unique_texts:
            unique_texts.append(txt)
    text_context_str = "\n\n".join(unique_texts[:3]) # 상위 3개 본문 적용
    
    # 6. 4단계: Graph-Context-Aware 프롬프트 기반 LLM 답변 생성 중
    logger.info("4단계: Graph-Context-Aware 프롬프트 기반 LLM 답변 생성 중...")
    
    prompt = f"""당신은 금융 세법 및 자산 관리 조언을 제공하는 전문 AI 에이전트입니다.
주어진 [지식 그래프 관계망]과 [관련 문서 본문]을 바탕으로 사용자의 질문에 정확하고 구체적으로 답변하십시오.
반드시 법적 근거가 있다면 본문에 기재된 내용을 기반으로 설명하고, 임의의 가정을 하지 마십시오.

[지식 그래프 관계망 (다중 홉 Sub-graph)]
{graph_context_str}

[관련 문서 본문 (금융 지침서)]
{text_context_str}

[사용자 질문]
{query_text}

답변은 한국어로 격식 있게 작성하며, 필요한 경우 관계망에 나타난 세율이나 한도, 근거 법령 등을 조목조목 짚어가며 설명하십시오.
답변:"""

    start_time = time.perf_counter()
    response = Settings.llm.complete(prompt)
    elapsed = time.perf_counter() - start_time
    
    print("\n" + "✨" * 30)
    print(f"GraphRAG 최종 답변 (소요 시간: {elapsed:.2f}초)")
    print("✨" * 30)
    print(response.text if hasattr(response, "text") else str(response))
    print("✨" * 30 + "\n")
    
    # 디버깅 정보 출력
    if subgraph_triplets:
        logger.info("참조된 지식 그래프 트리플 (총 %d건):", len(subgraph_triplets))
        for trip in list(set(subgraph_triplets))[:10]:
            logger.info("  %s", trip)


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
