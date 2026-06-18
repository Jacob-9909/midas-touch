"""GraphRAG 단발 질의 라우터 — `/api/v1/query`.

프로필·멀티턴 없이 지식그래프 근거만으로 한 번 답하는 엔드포인트(웹 콘솔 GraphRAG 탐색용).
검색은 `agent.tools.graph_rag.retrieve_graph_context`(GraphRAG 단일 구현)를 재사용하고,
작문은 에이전트와 동일한 NIM LLM(`build_chat_model`)으로 통일한다 — 과거 main.py에 있던
130줄 인라인 사본을 제거하고 도구와 단일화했다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services.agent.llm import build_chat_model
from backend.app.services.agent.tools.graph_rag import retrieve_graph_context

router = APIRouter(prefix="/api/v1", tags=["graph-rag"])


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    response: str
    subgraph_triplets: list[str] = []
    source_texts: list[str] = []


_PROMPT_TEMPLATE = """당신은 금융 세법 및 자산 관리 조언을 제공하는 전문 AI 에이전트입니다.
주어진 [지식 그래프 관계망]과 [관련 문서 본문]을 바탕으로 사용자의 질문에 정확하고 구체적으로 답변하십시오.
반드시 법적 근거가 있다면 본문에 기재된 내용을 기반으로 설명하고, 임의의 가정을 하지 마십시오.

[지식 그래프 관계망 (다중 홉 Sub-graph)]
{graph_context}

[관련 문서 본문 (금융 지침서)]
{text_context}

[사용자 질문]
{query}

답변은 한국어로 격식 있게 작성하며, 필요한 경우 관계망에 나타난 세율이나 한도, 근거 법령 등을 조목조목 짚어가며 설명하십시오.
답변:"""


@router.post("/query", response_model=QueryResponse)
def query_graph_rag(request: QueryRequest) -> QueryResponse:
    """GraphRAG 검색 컨텍스트로 단발 답변을 생성한다."""
    try:
        triplets, texts = retrieve_graph_context(request.query)

        graph_context = "\n".join(triplets) if triplets else "추출된 그래프 관계가 없습니다."
        source_texts = texts[:3]
        text_context = "\n\n".join(source_texts) if source_texts else "관련 문서 본문이 없습니다."

        prompt = _PROMPT_TEMPLATE.format(
            graph_context=graph_context,
            text_context=text_context,
            query=request.query,
        )
        answer = build_chat_model(temperature=0.0).invoke(prompt).content

        return QueryResponse(
            query=request.query,
            response=answer,
            subgraph_triplets=triplets,
            source_texts=source_texts,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))
