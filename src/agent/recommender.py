"""Midas Touch RAG-based Financial Recommendation Agent.

This module implements the MidasAdviser class which integrates local Sentence-Transformers
(nlpai-lab/KURE-v1) and NVIDIA NIM DeepSeek flash model to provide macro-aware, tax-optimized
wealth management suggestions using twin-persona semantic search.
"""

import os
import sys
from typing import Any, Dict, List

from openai import OpenAI
from sentence_transformers import SentenceTransformer

from db.connector import (
    get_all_tax_rules,
    get_latest_market_snapshots,
    get_user_by_uuid,
    search_similar_personas_db,
)


class MidasAdviser:
    _embedding_model: SentenceTransformer | None = None
    _llm_client: OpenAI | None = None
    EMBEDDING_MODEL_NAME = "nlpai-lab/KURE-v1"
    LLM_MODEL_NAME = "meta/llama-3.3-70b-instruct"
    LLM_BASE_URL = "https://integrate.api.nvidia.com/v1"

    def __init__(self) -> None:
        # Load embedding model (cached globally)
        if MidasAdviser._embedding_model is None:
            print(f"Loading local embedding model ({self.EMBEDDING_MODEL_NAME})...")
            MidasAdviser._embedding_model = SentenceTransformer(self.EMBEDDING_MODEL_NAME)
            print("Embedding model loaded successfully.")

        # Set up LLM client (NVIDIA NIM DeepSeek flash)
        if MidasAdviser._llm_client is None:
            api_key = os.environ.get("NVIDIA_API_KEY", "")
            if not api_key:
                print("⚠️ [경고] NVIDIA_API_KEY가 환경변수에 존재하지 않습니다. 어드바이저 LLM 기능이 실패할 수 있습니다.")
            MidasAdviser._llm_client = OpenAI(
                base_url=self.LLM_BASE_URL,
                api_key=api_key,
            )

    def _get_embedding(self, text: str) -> List[float]:
        """Generate a 1024-dimensional embedding vector from text using KURE-v1."""
        if not MidasAdviser._embedding_model:
            raise RuntimeError("Embedding model not initialized.")
        return MidasAdviser._embedding_model.encode(text).tolist()

    def get_recommendation(self, query: str, top_k: int = 3) -> str:
        """Analyze the query, pull hybrid RAG contexts from Azure SQL and Supabase, and generate advice."""
        print(f"\n[MidasAdviser] 입력 분석 중: '{query}'")

        # 1. Embed query
        print(f"1. URE 임베딩 벡터 생성 중...")
        query_vector = self._get_embedding(query)

        # 2. Vector search in Supabase for similar personas
        print(f"2. Supabase pgvector에서 유사 투자자 페르소나 매칭 중 (Top-{top_k})...")
        similar_personas = search_similar_personas_db(query_vector, top_k=top_k)
        print(f"   - {len(similar_personas)}개의 유사 페르소나 매칭 완료.")

        # 3. Retrieve structured twin user profiles from Azure SQL
        print(f"3. Azure SQL Database에서 유사 페르소나의 금융 프로필 동기화 중...")
        twin_profiles = []
        for idx, sp in enumerate(similar_personas):
            uuid = sp.get("azure_user_uuid")
            similarity = sp.get("similarity", 0.0)
            profile = get_user_by_uuid(uuid)
            if profile:
                # Add similarity score to profile dict for LLM reference
                profile["similarity"] = similarity
                twin_profiles.append(profile)
                print(f"   - 매칭 {idx+1}: {profile.get('occupation')} / 나이: {profile.get('age')}세 / 유사도: {similarity:.4f}")

        # 4. Fetch Korean tax rules from Azure SQL
        print(f"4. 한국 세법 절세 규칙(Tax Rules) 동기화 중...")
        tax_rules = get_all_tax_rules()
        print(f"   - 총 {len(tax_rules)}개의 세액 공제 및 세율 조건 수집 완료.")

        # 5. Fetch latest macroeconomic snapshots
        print(f"5. 최신 시장 거시경제 환경(Market Snapshots) 연동 중...")
        market_snapshots = get_latest_market_snapshots()
        print(f"   - 총 {len(market_snapshots)}개의 실시간 핵심 경제 지표 연동 완료.")

        # 6. Format RAG Context and Prompt
        print(f"6. 금융 RAG 지식 컨텍스트 병합 및 자문 의뢰서 작성 중...")
        context_str = self._format_rag_context(twin_profiles, tax_rules, market_snapshots)

        # 7. Generate Response using NVIDIA NIM LLM
        print(f"7. {self.LLM_MODEL_NAME} 금융 어드바이저 모델 연산 시작...")
        system_prompt = (
            "당신은 Midas Touch의 수석 자산관리사이자 한국인 자산관리/절세/포트폴리오 설계에 특화된 초개인화 전문 금융 어드바이저입니다. "
            "데이터베이스로부터 추출된 최신 시장 거시경제 지표, 한국 세법(소득세법 등), 그리고 유사 투자자들의 성공적인 금융 프로필 데이터를 종합 분석하여, "
            "의뢰인(고객)에게 가장 이상적이고 신뢰도 높은 자산 배분 제안 및 종합 재무 로드맵 보고서를 친절하고 전문적인 어조로 작성해 주세요."
        )

        user_prompt = f"""[자문 의뢰인 신규 요약 정보]
{query}

--------------------------------------------------------------------------------
[RAG 금융 지식 컨텍스트 (유사 페르소나, 한국 세법, 최신 거시경제 상황)]
{context_str}
--------------------------------------------------------------------------------

의뢰인의 성향과 요구사항, 그리고 위 RAG 금융 지식 컨텍스트를 치밀하게 대조 분석하여 아래 목차에 맞춘 '초개인화 자산관리 보고서'를 한국어로 격조 있게 작성해 주세요.

[필수 보고서 양식]
1. 요약 (Executive Summary)
   - 의뢰인의 투자 성향, 재무적 강점/취약점, 핵심 추천 테마 요약
2. 유사 투자자 벤치마크 분석 (Twin Persona Analysis)
   - 추천 시스템이 매칭한 유사 투자자들(유사도 점수 언급)의 자산 구성 양상 분석 및 의뢰인이 벤치마크할 수 있는 시사점 제안
3. 거시경제 시장 진단 및 투자 방향 (Macroeconomic Analysis)
   - 연동된 실시간 거시경제 지표(환율, 금리, 자산 인덱스 수치 언급 필수)를 바탕으로 현재 시점이 투자하기에 어떤 국면이며, 각 자산군(주식, 채권, 예적금, 원자재)에 어떻게 작용하는지 진단
4. 자산 배분 전략 및 맞춤형 포트폴리오 제안 (Portfolio Recommendations)
   - 주식, 채권, 예적금, 대체자산(원자재 등)의 구체적인 타겟 배분 비율(예: 주식 40%, 채권 30% 등, 총합 100%)을 백분율 수치로 명시하고 그 정당성을 거시경제 상황과 융합하여 설명
   - 의뢰인의 preferred_asset 및 유사 투자자들의 specific_items를 참고하여 관심 가져볼 만한 구체적인 투자 종목군/섹터 제안
5. 1:1 맞춤형 세금/절세 로드맵 (Tax-Saving Advice)
   - tax_rules를 바탕으로 의뢰인 상황(소득, 자산 수준)에 맞춰 가장 절세 효과를 극대화할 수 있는 구체적인 비과세/분리과세 금융 상품 및 연금 절세 전략 제시 (예: ISA, 개인연금, 퇴직연금, 채권 비과세 등)
6. 실행 가이드 및 행동 촉구 (Actionable Roadmap)
   - 목표 달성(등록금 마련, 아파트 구입 등)을 위해 앞으로 1~3개월 내에 당장 실천해야 할 구체적인 재무적 행동 가이드 단계 제시
"""

        try:
            response = MidasAdviser._llm_client.chat.completions.create(
                model=self.LLM_MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )
            report = response.choices[0].message.content
            print("🎉 포트폴리오 추천서 자문이 성공적으로 완료되었습니다.")
            return report if report else "제안서 생성에 실패했습니다."
        except Exception as e:
            print(f"❌ LLM 호출 중 오류 발생: {e}")
            raise

    def _format_rag_context(
        self,
        twin_profiles: List[Dict[str, Any]],
        tax_rules: List[Dict[str, Any]],
        market_snapshots: List[Dict[str, Any]],
    ) -> str:
        """Format Azure SQL & Supabase retrieved entities into a clean, text block for LLM prompts."""
        lines = []

        # 1. Format Similar Twins
        lines.append("### 1. 유사 성향 투자자 페르소나 군집 (Azure SQL Users Database)")
        if not twin_profiles:
            lines.append(" - 매칭된 유사 페르소나가 없습니다.")
        else:
            for idx, p in enumerate(twin_profiles):
                lines.append(f" [유사 투자자 {idx+1}]")
                lines.append(f"  - 유사도: {p.get('similarity', 0.0):.4f}")
                lines.append(f"  - 나이/성별/직업: {p.get('age')}세 / {p.get('sex')} / {p.get('occupation')}")
                lines.append(f"  - 가족 구성/주거: {p.get('family_type')} / {p.get('housing_type')} ({p.get('district')})")
                lines.append(f"  - 자산 총액: {p.get('total_amount'):,} 원 (월 수입: {p.get('monthly_income'):,} 원 / 월 가용 투자액: {p.get('monthly_investable'):,} 원)")
                lines.append(f"  - 자산 상세 배분: 주식 {p.get('stock_amount'):,} 원 / 채권 {p.get('bond_amount'):,} 원 / 예적금 {p.get('deposit_amount'):,} 원 / 부동산 {p.get('real_estate_amount'):,} 원")
                lines.append(f"  - 투자 성향 (1-10): 공격성 {p.get('aggressiveness')} / 금융 이해도 {p.get('financial_literacy')}")
                lines.append(f"  - 선호 자산군 및 개별 관심 종목: {p.get('preferred_asset')} | {p.get('specific_items')}")
                lines.append(f"  - 투자 목표 수익률/기간: {p.get('target_return_percent')}% / {p.get('investable_period_months')}개월")
                lines.append(f"  - 유동성 확보 필요 여부: {'필요' if p.get('requires_liquidity') else '불필요'}")
                lines.append("")

        # 2. Format Market Snapshots
        lines.append("### 2. 최신 실시간 시장 거시경제 지표 스냅샷 (Azure SQL Market Snapshots)")
        if not market_snapshots:
            lines.append(" - 연동된 경제 지표 데이터가 존재하지 않습니다.")
        else:
            # Group by data_type
            grouped: Dict[str, List[str]] = {}
            for ms in market_snapshots:
                dt = ms.get("data_type", "etc")
                key = ms.get("sub_key")
                unit = ms.get("unit", "")
                src = ms.get("source", "")
                date = ms.get("snapshot_date")
                
                info_line = f"  - {key}: {float(ms.get('value') or 0):,.2f} {unit} (출처: {src}, 기준일: {date})"
                grouped.setdefault(dt, []).append(info_line)

            for dt, info_list in grouped.items():
                lines.append(f" [{dt.upper()} 지표]")
                lines.extend(info_list)
            lines.append("")

        # 3. Format Tax Rules
        lines.append("### 3. 대한민국 자산 종류별 관련 세법 및 공제 규칙 (Azure SQL Tax Rules)")
        if not tax_rules:
            lines.append(" - 연동된 세법 데이터가 존재하지 않습니다.")
        else:
            for idx, r in enumerate(tax_rules):
                lines.append(f" [세법 규칙 {idx+1}]")
                lines.append(f"  - 대상 자산: {r.get('asset_type')} (소득 구분: {r.get('income_type')})")
                min_amt = f"{r.get('min_amount'):,}원" if r.get("min_amount") is not None else "없음"
                max_amt = f"{r.get('max_amount'):,}원" if r.get("max_amount") is not None else "없음"
                lines.append(f"  - 적용 금액 기준: {min_amt} ~ {max_amt}")
                lines.append(f"  - 적용 세율: {float(r.get('tax_rate') or 0)*100:.2f}% (지방소득세 별도: {float(r.get('local_tax_rate') or 0)*100:.2f}%)")
                lines.append(f"  - 주요 공제 혜택 한도: {f'{r.get('deduction_limit'):,}원' if r.get('deduction_limit') else '없음'}")
                lines.append(f"  - 상세 내용: {r.get('description')} ({r.get('legal_basis')})")
                lines.append("")

        return "\n".join(lines)
