"""graph_rag 도구 — Neo4j 지식그래프 2-hop 서브그래프 검색.

GraphRAG 검색 로직의 **단일 구현처**. `retrieve_graph_context()`가 (관계망 트리플, 근거 본문)
원자료를 반환하고, 이를 두 곳이 공유한다:
- `graph_rag` 도구: 에이전트 synthesize용 정제 텍스트로 포맷.
- `backend.app.api.query`의 `/api/v1/query`: QueryResponse(트리플/본문 분리)로 직렬화.

성능/안정성:
- Neo4j 그래프 스토어와 retriever는 **모듈 1회 생성 후 재사용**한다(매 호출 재연결/드라이버 누수 방지).
- 검색 임베딩은 _embedding의 단일 bge-m3 인스턴스를 공유한다(메모리 1벌, persona_rag와 동일 공간).
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.tools import tool

from ..llm import require_env
from ._embedding import get_llamaindex_embedding


@lru_cache(maxsize=1)
def _get_retriever_bundle():
    """Neo4j 그래프 스토어 + VectorContextRetriever를 1회 생성해 캐시한다.

    그래프 '검색'에는 LLM이 필요 없지만 PropertyGraphIndex.from_existing이 Settings.llm을
    요구하므로(미설정 시 기본 OpenAI로 떨어져 키 오류) NIM LLM을 전역에 세팅해 둔다.
    모델명은 .env(NIM_GENERATION_MODEL)에서만 읽는다(하드코딩 기본값 없음).
    """
    from llama_index.core import Settings
    from llama_index.core.indices.property_graph import (
        PropertyGraphIndex,
        VectorContextRetriever,
    )
    from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

    from shared.utils.nim_openai import NIMOpenAI

    # 통합 bge-m3(단일 인스턴스 공유) + NIM LLM 전역 설정
    Settings.embed_model = get_llamaindex_embedding()
    Settings.llm = NIMOpenAI(
        model=require_env("NIM_GENERATION_MODEL"),
        api_base="https://integrate.api.nvidia.com/v1",
        temperature=0.0,
    )

    graph_store = Neo4jPropertyGraphStore(
        username=require_env("NEO4J_USERNAME"),
        password=require_env("NEO4J_PASSWORD"),
        url=require_env("NEO4J_URL"),
        database="neo4j",
    )
    PropertyGraphIndex.from_existing(property_graph_store=graph_store)

    retriever = VectorContextRetriever(
        graph_store=graph_store,
        embed_model=Settings.embed_model,
        similarity_top_k=5,
        path_depth=1,
    )
    return graph_store, retriever


def retrieve_graph_context(query: str) -> tuple[list[str], list[str]]:
    """질의로 Neo4j 2-hop 서브그래프를 검색해 (관계망 트리플, 근거 본문)을 반환한다.

    두 리스트 모두 중복이 제거돼 있다(트리플은 정렬). 관계 추출이 실패하면 사유를 트리플
    리스트에 한 줄로 남긴다. GraphRAG 검색의 **유일한 구현**으로, 도구와 /query가 공유한다.
    """
    graph_store, retriever = _get_retriever_bundle()

    # 1단계: 벡터 검색으로 연관 노드/본문 추출
    retrieved_nodes = retriever.retrieve(query)

    node_names: set[str] = set()
    text_contexts: list[str] = []
    for node_with_score in retrieved_nodes:
        node = node_with_score.node
        node_name = node.metadata.get("name") or node.text.split("\n")[0]
        if node_name:
            node_names.add(node_name)
        if node.text:
            text_contexts.append(node.text)

    # 2단계: Cypher로 2-hop 관계망 추출
    subgraph_triplets: list[str] = []
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
                subgraph_triplets.append(
                    f"({rec.get('source')}:{rec.get('s_label', '')}) "
                    f"-[{rec.get('rel')}]-> "
                    f"({rec.get('target')}:{rec.get('t_label', '')})"
                )
        except Exception as exc:  # noqa: BLE001 - 관계 추출 실패 시 텍스트 컨텍스트로 폴백
            subgraph_triplets.append(f"(관계 추출 실패: {exc})")

    triplets = sorted(set(subgraph_triplets))

    unique_texts: list[str] = []
    for txt in text_contexts:
        if txt not in unique_texts:
            unique_texts.append(txt)

    return triplets, unique_texts


@tool
def graph_rag(query: str) -> str:
    """Neo4j 금융·세법 지식그래프에서 질의와 관련된 2-hop 서브그래프(관계망)와 근거 문서 본문을
    검색해 반환한다. 세법 조항의 법적 근거, 세율·공제 한도의 출처, 자산 간 관계 등 '근거'가
    필요한 질문에 사용하라.

    Args:
        query: 세법·자산 관계를 묻는 자연어 질문.
    """
    triplets, texts = retrieve_graph_context(query)

    graph_context_str = "\n".join(triplets) if triplets else "추출된 그래프 관계가 없습니다."
    text_context_str = "\n\n".join(texts[:3]) if texts else "관련 문서 본문이 없습니다."

    return f"[지식 그래프 관계망 (2-hop Sub-graph)]\n{graph_context_str}\n\n[근거 문서 본문]\n{text_context_str}"
