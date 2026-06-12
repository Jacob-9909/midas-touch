"""persona_rag 도구 — 트윈 투자자 페르소나 검색.

기존 MidasAdviser.get_recommendation의 1~6단계(임베딩 → pgvector 유사 페르소나 검색 →
Azure SQL 프로필/세법/시장 동기화 → 컨텍스트 포맷)에서 **LLM 호출 직전까지**를 추출한 것.
도구는 최종 보고서를 작성하지 않고, 정제된 RAG 컨텍스트 텍스트를 반환한다.
최종 작문은 LangGraph agent 노드의 LLM이 담당한다.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.tools import tool

from shared.database.connector import (
    get_all_tax_rules,
    get_latest_market_snapshots,
    get_user_by_uuid,
    search_similar_personas_db,
)

from ._embedding import embed


@tool
def persona_rag(query: str, top_k: int = 3) -> str:
    """사용자의 투자 성향·재무 상황 텍스트와 가장 유사한 '트윈 투자자 페르소나'를 pgvector로
    검색하고, 그들의 자산배분·한국 세법·최신 거시경제 지표를 종합한 컨텍스트를 반환한다.
    벤치마크할 유사 투자자, 권장 자산배분 비율, 또래 투자자의 종목/섹터 선호를 묻는 질문에 사용하라.

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

    # 4. 세법 + 시장 스냅샷
    tax_rules = get_all_tax_rules()
    market_snapshots = get_latest_market_snapshots()

    return _format_rag_context(twin_profiles, tax_rules, market_snapshots)


def _format_rag_context(
    twin_profiles: List[Dict[str, Any]],
    tax_rules: List[Dict[str, Any]],
    market_snapshots: List[Dict[str, Any]],
) -> str:
    """검색된 엔티티를 LLM 프롬프트용 정제 텍스트 블록으로 포맷한다."""
    lines: List[str] = []

    # 1. 유사 트윈 페르소나
    lines.append("### 1. 유사 성향 투자자 페르소나 군집 (Users Database)")
    if not twin_profiles:
        lines.append(" - 매칭된 유사 페르소나가 없습니다.")
    else:
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

    # 2. 시장 스냅샷
    lines.append("### 2. 최신 실시간 시장 거시경제 지표 스냅샷 (Market Snapshots)")
    if not market_snapshots:
        lines.append(" - 연동된 경제 지표 데이터가 존재하지 않습니다.")
    else:
        grouped: Dict[str, List[str]] = {}
        for ms in market_snapshots:
            dt = ms.get("data_type", "etc")
            info_line = (
                f"  - {ms.get('sub_key')}: {float(ms.get('value') or 0):,.2f} {ms.get('unit', '')} "
                f"(출처: {ms.get('source', '')}, 기준일: {ms.get('snapshot_date')})"
            )
            grouped.setdefault(dt, []).append(info_line)
        for dt, info_list in grouped.items():
            lines.append(f" [{dt.upper()} 지표]")
            lines.extend(info_list)
        lines.append("")

    # 3. 세법 규칙
    lines.append("### 3. 대한민국 자산 종류별 세법 및 공제 규칙 (Tax Rules)")
    if not tax_rules:
        lines.append(" - 연동된 세법 데이터가 존재하지 않습니다.")
    else:
        for idx, r in enumerate(tax_rules):
            lines.append(f" [세법 규칙 {idx + 1}]")
            lines.append(f"  - 대상 자산: {r.get('asset_type')} (소득 구분: {r.get('income_type')})")
            min_amt = f"{r.get('min_amount'):,}원" if r.get("min_amount") is not None else "없음"
            max_amt = f"{r.get('max_amount'):,}원" if r.get("max_amount") is not None else "없음"
            lines.append(f"  - 적용 금액 기준: {min_amt} ~ {max_amt}")
            lines.append(
                f"  - 적용 세율: {float(r.get('tax_rate') or 0) * 100:.2f}% "
                f"(지방소득세 별도: {float(r.get('local_tax_rate') or 0) * 100:.2f}%)"
            )
            deduction = f"{r.get('deduction_limit'):,}원" if r.get("deduction_limit") else "없음"
            lines.append(f"  - 주요 공제 혜택 한도: {deduction}")
            lines.append(f"  - 상세 내용: {r.get('description')} ({r.get('legal_basis')})")
            lines.append("")

    return "\n".join(lines)
