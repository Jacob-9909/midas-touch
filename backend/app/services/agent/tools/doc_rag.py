"""doc_rag 도구 — 공공기관 지침서 및 세법 해설서 원문 단락 검색.

`emb_passages`에 적재된 국토교통부, 한국부동산원, 금융감독원, 경찰청, 국세청 발간 공식 문서 단락을 pgvector로
검색해 **원문 그대로** 반환한다. tax_and_market_lookup의 구조화 세법 규칙(tax_rules 24행)이나
graph_rag의 지식그래프가 다루지 못하는 세부 요건, 기준금액, 계산식, 사례, 청약 제도, 사기예방 매뉴얼을 여기서 커버한다.

각 단락에 출처(source, passage_id)를 붙여 반환한다 — 근거를 보여주고, 근거가 없으면 답하지
않는다는 이 프로젝트의 원칙 때문에 출처 표기는 선택이 아니다.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from shared.database.connector import search_similar_passages_db

from ._embedding import embed


@tool
def doc_rag(query: str, top_k: int = 6) -> str:
    """공공기관 공식 지침서(국토교통부/한국부동산원 청약 제도안내, 금융감독원 사기예방 종합매뉴얼, 국세청 주식/주택 세법 해설서) 원문 단락을 pgvector로 검색해 반환한다.
    청약 가점 84점 기준표, 청약통장 전환 및 유형별 요건, 금융사기 10대 수법 및 피해 구제 절차,
    양도소득세 대주주 기준, 증여세/상속세 공제 한도와 계산식, 취득세/재산세/종부세 세율표,
    주택임대소득 과세요건, 1세대 1주택 비과세 요건, 신고/납부 절차 등
    **구체적인 공공기관 규정, 제도 조건, 기한, 금액, 계산식**이 필요한 질문에 사용하라.

    Args:
        query: 검색할 자연어 질문(사용자 질문을 그대로 넘기면 된다).
        top_k: 가져올 단락 수 (기본 6).
    """
    passages = search_similar_passages_db(embed(query), top_k=top_k)
    return _format_passages(passages)


def _format_passages(passages: list[dict[str, Any]]) -> str:
    """검색된 단락을 출처가 붙은 LLM 프롬프트용 텍스트 블록으로 포맷한다."""
    lines: list[str] = ["### 공공기관 공식 지침서 및 세법 해설서 원문 발췌 (emb_passages, 출처 표기 필수)"]
    if not passages:
        lines.append(" - 검색된 문서 단락이 없습니다.")
        return "\n".join(lines)

    for idx, p in enumerate(passages):
        lines.append(
            f"\n[발췌 {idx + 1}] 출처: {p.get('source')} / passage_id: {p.get('passage_id')} "
            f"(유사도 {float(p.get('similarity') or 0):.4f})"
        )
        lines.append(str(p.get("text") or "").strip())

    lines.append(
        "\n※ 위 발췌는 공공기관 발간 공식 지침서 원문이다. 답변에 인용할 때 어느 출처의 어느 단락인지"
        " 밝히고, 발췌에 없는 수치나 요건은 지어내지 마라."
    )
    return "\n".join(lines)
