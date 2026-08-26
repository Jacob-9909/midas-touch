"""synthesize 노드 — 모인 검색 컨텍스트로 최종 답변을 1회 작문한다."""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage, SystemMessage

from ..llm import build_chat_model
from ..prompts import SYSTEM_PROMPT
from ..state import AgentState

# doc_rag 결과 블록(tools/doc_rag._format_passages)의 발췌 헤더에서 출처를 뽑는 정규식.
# 예: "[발췌 2] 출처: 국세청 주식과 세금 / passage_id: a1b2c3 (유사도 0.8123)"
_CITATION_RE = re.compile(
    r"^\[발췌 \d+\] 출처: (?P<source>.+?) / passage_id: (?P<passage_id>\S+)",
    re.MULTILINE,
)

# 답변 말미에 코드가 직접 붙이는 출처 섹션 헤더(프론트엔드가 이 형식으로 감지한다).
_SOURCES_HEADER = "출처:"


def _doc_rag_sources(contexts: list[str]) -> list[tuple[str, str]]:
    """tool_context의 doc_rag 결과([doc_rag 결과] 접두 항목)에서 (source, passage_id)를 추출한다.

    등장 순서를 유지하고 중복은 제거한다. 조회 실패([doc_rag 조회 실패])나 빈 검색 결과는
    발췌 헤더가 없어 자연스럽게 제외된다.
    """
    sources: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ctx in contexts:
        if not ctx.startswith("[doc_rag 결과]"):
            continue
        for m in _CITATION_RE.finditer(ctx):
            key = (m.group("source"), m.group("passage_id"))
            if key not in seen:
                seen.add(key)
                sources.append(key)
    return sources


def _sources_footer(sources: list[tuple[str, str]]) -> str:
    """출처 섹션을 LLM 개입 없이 결정적으로 조립한다.

    형식 규약(프론트엔드 chat-sources.ts와 짝을 이룸): "---" 다음 '출처:' 헤더, 그리고
    "[n] source (passage_id)" 항목들이 이어진다.
    """
    lines = ["---", _SOURCES_HEADER]
    lines.extend(
        f"[{idx}] {source} ({passage_id})"
        for idx, (source, passage_id) in enumerate(sources, start=1)
    )
    return "\n".join(lines)


def synthesize_node(state: AgentState) -> dict:
    system_parts = [SYSTEM_PROMPT]

    summary = (state.get("profile_summary") or "").strip()
    if summary:
        system_parts.append(summary)

    contexts = state.get("tool_context") or []
    if contexts:
        joined = "\n\n".join(contexts)
        system_parts.append(
            "다음은 이번 질문을 위해 검색된 컨텍스트입니다. 이 컨텍스트에 근거해서만 "
            "수치·법령·세율을 제시하고, 임의 가정을 하지 마십시오.\n\n" + joined
        )
    else:
        # 빈 턴에도 grounding 지시를 유지해야 모델이 세율·수치를 지어내지 않는다.
        system_parts.append(
            "이번 질문을 위해 검색된 컨텍스트가 없습니다. 세율·법령·시장 수치 등 근거가 "
            "필요한 내용은 임의로 생성하지 말고, 확인이 필요함을 안내하십시오."
        )

    system_prompt = "\n\n".join(system_parts)

    # 시스템 프롬프트 + 누적 대화 이력으로 1회 작문(작문 일관성을 위해 기본값보다 낮은 온도).
    messages = [SystemMessage(content=system_prompt)] + list(state.get("messages") or [])
    reply: AIMessage = build_chat_model(temperature=0.3).invoke(messages)

    # LLM이 출처를 지어내지 않도록, doc_rag 근거가 있으면 출처 섹션을 코드가 직접 덧붙인다.
    sources = _doc_rag_sources(contexts)
    if sources:
        base = reply.content if isinstance(reply.content, str) else str(reply.content)
        reply.content = f"{base}\n\n{_sources_footer(sources)}"
    return {"messages": [reply]}
