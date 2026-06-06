"""
main.py
-------
FastAPI 기반 실시간 Midas Touch 금융 자산 관리 및 GraphRAG 질의 웹 API 서비스 엔트리포인트.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shared.database.connector import get_connection

app = FastAPI(
    title="Midas Touch API Server",
    description="금융 특화 임베딩 및 Neo4j GraphRAG 기반 자산관리 조언 서비스 API",
    version="1.0.0",
)


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    response: str


@app.get("/")
def read_root():
    return {"message": "Welcome to Midas Touch API Server"}


@app.get("/health")
def health_check():
    # 간단한 PostgreSQL 연결 헬스체크
    try:
        conn = get_connection()
        conn.close()
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy ({exc})"
        
    return {
        "status": "healthy",
        "database": db_status,
        "neo4j": "bolt://localhost:7687"
    }


@app.post("/api/v1/query", response_model=QueryResponse)
def query_graph_rag(request: QueryRequest):
    """
    GraphRAG 자연어 질의 엔진을 호출하여 답변을 생성합니다.
    """
    try:
        from pipelines.knowledge_graph.test_rag import run_graph_rag_query, setup_llamaindex_settings
        
        # LlamaIndex Settings 세팅
        setup_llamaindex_settings()
        
        # 질의 엔진 가동 (테스트용 콘솔 출력이므로, 실제 서빙 시에는 텍스트를 리턴하도록 확장 가능)
        # 본 테스트를 위해 동기식 실행
        # RAG 응답을 가로채기 위해 pipelines.knowledge_graph.test_rag 에 구현된 run_graph_rag_query 의 본문 로직 활용
        from llama_index.core import Settings
        from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
        from llama_index.core.indices.property_graph import PropertyGraphIndex, VectorContextRetriever
        
        neo4j_url = os.environ.get("NEO4J_URL", "bolt://localhost:7687")
        neo4j_user = os.environ.get("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.environ.get("NEO4J_PASSWORD", "PG_develop_2026_Secure")
        
        graph_store = Neo4jPropertyGraphStore(
            username=neo4j_user,
            password=neo4j_password,
            url=neo4j_url,
            database="neo4j",
        )
        index = PropertyGraphIndex.from_existing(property_graph_store=graph_store)
        
        vector_retriever = VectorContextRetriever(
            graph_store=graph_store,
            embed_model=Settings.embed_model,
            similarity_top_k=5,
            path_depth=1,
        )
        retrieved_nodes = vector_retriever.retrieve(request.query)
        
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

        if node_names:
            cypher_query = """
            MATCH (n)-[r]-(m)
            WHERE n.name IN $node_names OR m.name IN $node_names
            RETURN n.name AS source, labels(n)[0] AS s_label, type(r) AS rel, m.name AS target, labels(m)[0] AS t_label
            LIMIT 35
            """
            records = graph_store.structured_query(cypher_query, {"node_names": list(node_names)})
            for rec in records:
                source = rec.get("source")
                rel = rel_type = rec.get("rel")
                target = rec.get("target")
                s_lbl = rec.get("s_label", "")
                t_lbl = rec.get("t_label", "")
                subgraph_triplets.append(f"({source}:{s_lbl}) -[{rel}]-> ({target}:{t_lbl})")

        graph_context_str = "\n".join(set(subgraph_triplets)) if subgraph_triplets else "추출된 그래프 관계가 없습니다."
        
        unique_texts = []
        for txt in text_contexts:
            if txt not in unique_texts:
                unique_texts.append(txt)
        text_context_str = "\n\n".join(unique_texts[:3])
        
        prompt = f"""당신은 금융 세법 및 자산 관리 조언을 제공하는 전문 AI 에이전트입니다.
주어진 [지식 그래프 관계망]과 [관련 문서 본문]을 바탕으로 사용자의 질문에 정확하고 구체적으로 답변하십시오.
반드시 법적 근거가 있다면 본문에 기재된 내용을 기반으로 설명하고, 임의의 가정을 하지 마십시오.

[지식 그래프 관계망 (다중 홉 Sub-graph)]
{graph_context_str}

[관련 문서 본문 (금융 지침서)]
{text_context_str}

[사용자 질문]
{request.query}

답변은 한국어로 격식 있게 작성하며, 필요한 경우 관계망에 나타난 세율이나 한도, 근거 법령 등을 조목조목 짚어가며 설명하십시오.
답변:"""

        response = Settings.llm.complete(prompt)
        answer = response.text if hasattr(response, "text") else str(response)
        
        return QueryResponse(query=request.query, response=answer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
