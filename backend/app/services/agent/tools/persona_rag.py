"""persona_rag 도구 — 트윈 투자자 벤치마킹 검색.

pgvector로 의뢰인과 가장 유사한 '트윈 투자자 페르소나'를 찾아, 그들의 자산배분·성향·선호를
정제 텍스트로 반환한다. **벤치마킹 전용** 도구다 — 세법/시장 수치는 tax_and_market_lookup,
법적 근거는 graph_rag가 책임지므로 여기서는 다루지 않는다(책임 분리, 컨텍스트 중복 제거).

도구는 최종 보고서를 작성하지 않고 RAG 컨텍스트만 반환한다. 최종 작문은 synthesize 노드의
LLM이 담당한다.

NOTE: 의뢰인 '본인'의 유형은 API 레이어가 주입하는 profile_summary로 이미 알 수 있다. 이 도구는
      본인 파악이 아니라 '또래(트윈) 비교'를 위한 것이다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.tools import tool

from shared.database.connector import get_user_by_uuid, search_similar_personas_db

from ._embedding import embed


@tool
def persona_rag(query: str, top_k: int = 3) -> str:
    """의뢰인의 투자 성향·재무 상황과 가장 유사한 '트윈 투자자 페르소나'를 pgvector로 검색해,
    그들의 자산배분·투자성향·종목/섹터 선호를 벤치마킹 컨텍스트로 반환한다.
    "나와 비슷한 투자자들은 어떻게 하나", 권장 자산배분 비율, 또래의 종목/섹터 선호 등
    '또래 벤치마킹'이 필요한 질문에 사용하라. (세법·시장 수치는 이 도구가 다루지 않는다.)

    Args:
        query: 의뢰인의 인적·재무·투자성향을 서술한 자연어 텍스트.
        top_k: 매칭할 유사 페르소나 수 (기본 3).
    """
    # 1. 쿼리 임베딩 (적재와 동일한 bge-m3)
    query_vector = embed(query)

    # 2. pgvector 유사 페르소나 검색
    similar = search_similar_personas_db(query_vector, top_k=top_k)

    # 3. 구조화 프로필 동기화
    twin_profiles: List[Dict[str, Any]] = []
    for sp in similar:
        profile = get_user_by_uuid(sp.get("azure_user_uuid"))
        if profile:
            profile["similarity"] = sp.get("similarity", 0.0)
            twin_profiles.append(profile)

    return _format_twin_context(twin_profiles)


def _format_twin_context(twin_profiles: List[Dict[str, Any]]) -> str:
    """검색된 트윈 페르소나를 LLM 프롬프트용 정제 텍스트 블록으로 포맷한다."""
    lines: List[str] = ["### 유사 성향 투자자 페르소나 군집 (벤치마킹용, Users Database)"]
    if not twin_profiles:
        lines.append(" - 매칭된 유사 페르소나가 없습니다.")
        return "\n".join(lines)

    for idx, p in enumerate(twin_profiles):
        lines.append(f" [유사 투자자 {idx + 1}]")
        lines.append(f"  - 유사도: {p.get('similarity', 0.0):.4f}")
        lines.append(f"  - 나이/성별/직업: {p.get('age')}세 / {p.get('sex')} / {p.get('occupation')}")
        lines.append(f"  - 가족 구성/주거: {p.get('family_type')} / {p.get('housing_type')} ({p.get('district')})")
        lines.append(
            f"  - 자산 총액: {p.get('total_amount'):,} 원 "
            f"(월 수입: {p.get('monthly_income'):,} 원 / 월 가용 투자액: {p.get('monthly_investable'):,} 원)"
        )
        lines.append(
            f"  - 자산 상세 배분: 주식 {p.get('stock_amount'):,} 원 / 채권 {p.get('bond_amount'):,} 원 "
            f"/ 예적금 {p.get('deposit_amount'):,} 원 / 부동산 {p.get('real_estate_amount'):,} 원"
        )
        lines.append(
            f"  - 투자 성향 (1-10): 공격성 {p.get('aggressiveness')} / 금융 이해도 {p.get('financial_literacy')}"
        )
        lines.append(f"  - 선호 자산군 및 개별 관심 종목: {p.get('preferred_asset')} | {p.get('specific_items')}")
        lines.append(
            f"  - 투자 목표 수익률/기간: {p.get('target_return_percent')}% / {p.get('investable_period_months')}개월"
        )
        lines.append(f"  - 유동성 확보 필요 여부: {'필요' if p.get('requires_liquidity') else '불필요'}")
        lines.append("")

    return "\n".join(lines)
