import asyncio
import itertools
import os
import re
import sys

import pandas as pd
from dotenv import load_dotenv
from huggingface_hub import HfApi
from openai import AsyncOpenAI
from pydantic import BaseModel
from tqdm import tqdm as sync_tqdm
from tqdm.asyncio import tqdm

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 경로를 sys.path에 추가해 shared.database.connector 임포트 가능하게 함
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.database.connector import bulk_upsert_portfolios, bulk_upsert_users
from shared.utils.api_key_rotator import APIKeyRotator
from shared.utils.nim_rate_limit import reserve

# 권장 자산배분 6개 자산군 (portfolios 테이블 비율 컬럼과 1:1, 합계 100)
RATIO_KEYS = ["stock", "bond", "deposit", "real_estate", "gold", "cash"]


# structured output 스키마 — 프롬프트 JSON 구조와 1:1.
# response_format으로 강제하면 콤마 누락·잘림 같은 파싱 에러 클래스가 사라진다.
class _AssetTypes(BaseModel):
    stock: int
    bond: int
    deposit: int
    real_estate: int


class _AssetSize(BaseModel):
    total_amount: int
    asset_types: _AssetTypes
    specific_items: str
    monthly_income: int
    monthly_investable: int


class _InvestmentPropensity(BaseModel):
    aggressiveness: int
    preferred_asset: str
    financial_literacy: int


class _InvestmentGoal(BaseModel):
    target_return_percent: int
    investable_period_months: int
    requires_liquidity: int


class _RecommendedAllocation(BaseModel):
    strategy_name: str
    stock: int
    bond: int
    deposit: int
    real_estate: int
    gold: int
    cash: int


class FinanceProfile(BaseModel):
    asset_size: _AssetSize
    investment_propensity: _InvestmentPropensity
    investment_goal: _InvestmentGoal
    recommended_allocation: _RecommendedAllocation

# ==========================================
# 1. 설정 (Settings)
# ==========================================
# 생성할 데이터 수 지정
NUM_SAMPLES = 200
# 초당 요청 수 제어 (딜레이를 단축하여 대기 시간 단축)
DELAY_BETWEEN_REQUESTS = 0.5 

# NVIDIA NIM (OpenAI 호환 엔드포인트). 인증은 .env의 NVIDIA_API_KEY(+ _2, _3 ...).
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
_clients = None

# NIM 모델이 json_schema 강제를 거부하면 자동으로 프롬프트-only JSON 모드로 내려간다.
_use_schema = True


def _get_client() -> tuple[str, AsyncOpenAI]:
    """NIM 클라이언트를 지연 생성(테스트가 키 없이 모듈을 임포트할 수 있게 함).

    키가 여러 개면 호출마다 라운드로빈해 레이트리밋을 키별로 분산한다.
    """
    global _clients
    if _clients is None:
        keys = APIKeyRotator().keys
        _clients = itertools.cycle(
            [
                (k, AsyncOpenAI(api_key=k, base_url=NIM_BASE_URL, max_retries=0, timeout=200.0))
                for k in keys
            ]
        )
    return next(_clients)


MODEL_NAME = os.environ.get("PERSONA_GENERATION_MODEL")
if not MODEL_NAME:
    raise RuntimeError("PERSONA_GENERATION_MODEL 환경변수가 설정되어 있지 않습니다.")

# 사용할 기존 컬럼
SELECTED_COLUMNS = [
    'professional_persona', 'family_persona', 'persona', 
    'career_goals_and_ambitions', 'sex', 'age', 'marital_status', 
    'education_level', 'bachelors_field', 'occupation', 
    'family_type', 'housing_type', 'district'
]

# ==========================================
# 2. 프롬프트 템플릿
# ==========================================
PROMPT_TEMPLATE = """당신은 금융 데이터를 분석하고 페르소나에 맞는 가상의 금융 프로필을 정교하게 생성하는 전문가입니다.
다음은 한 사람의 기본 페르소나 정보입니다:

{persona_context}

위 사람의 특성을 바탕으로 아래의 금융 및 투자 관련 항목들을 유추하여 JSON 형식으로만 생성해주세요.
반드시 아래 제공된 JSON 구조와 타입(숫자, 문자열 등)을 정확하게 지켜야 하며, 다른 부연 설명은 절대 추가하지 마세요.

출력해야 할 JSON 예시 (중괄호 등 JSON 문법을 완벽히 지켜주세요):
{{
  "asset_size": {{
    "total_amount": 50000000,
    "asset_types": {{
      "stock": 15000000,
      "bond": 0,
      "deposit": 35000000,
      "real_estate": 0
    }},
    "specific_items": "삼성전자, 청약예금",
    "monthly_income": 3500000,
    "monthly_investable": 1000000
  }},
  "investment_propensity": {{
    "aggressiveness": 7,
    "preferred_asset": "국내 주식, ETF",
    "financial_literacy": 8
  }},
  "investment_goal": {{
    "target_return_percent": 15,
    "investable_period_months": 36,
    "requires_liquidity": 0
  }},
  "recommended_allocation": {{
    "strategy_name": "성장형 60/40",
    "stock": 55,
    "bond": 15,
    "deposit": 10,
    "real_estate": 10,
    "gold": 5,
    "cash": 5
  }}
}}

[제약 조건]
- asset_types의 하위 값들(stock, bond, deposit, real_estate)은 각 자산의 실제 보유 금액(원화 기준 정수)이어야 하며, 이 값들의 합은 반드시 total_amount와 정확히 일치해야 합니다.
- aggressiveness, financial_literacy는 1~10 사이의 숫자입니다.
- recommended_allocation은 이 사람의 현재 보유가 아니라, 투자성향·목표·기간을 반영해 '권장'하는 이상적 자산배분 비율(%)입니다. stock/bond/deposit/real_estate/gold/cash 6개 값의 합이 100에 가깝도록 하고, 공격성이 높고 기간이 길수록 주식 비중을, 유동성이 필요하면 현금/예적금 비중을 높이세요. strategy_name은 20자 이내 한국어 전략명입니다.
- 모든 금액이나 퍼센트, 개월 수는 문자열이 아닌 정수(숫자)로 입력하세요."""

# ==========================================
# 3. 비동기 데이터 생성 함수
# ==========================================
def extract_json(text):
    """LLM 출력에서 JSON 부분만 추출하는 헬퍼 함수"""
    # 1. 마크다운 코드 블록 확인
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    
    # 2. 코드 블록이 없을 경우 가장 바깥쪽 중괄호를 찾음
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and start < end:
        return text[start:end+1]
    
    return text

def normalize_ratios(alloc):
    """권장 배분 6개 비율을 합계 정확히 100.00으로 정규화(portfolios CHECK 제약 충족)."""
    vals = {k: max(0.0, float(alloc.get(k, 0) or 0)) for k in RATIO_KEYS}
    total = sum(vals.values())
    if total <= 0:
        # 안전망: 정보가 없으면 보수적 균등 배분
        return {**{k: 0.0 for k in RATIO_KEYS}, "deposit": 50.0, "cash": 50.0}
    scaled = {k: round(v / total * 100, 2) for k, v in vals.items()}
    # 반올림 잔차를 가장 큰 버킷에 흡수시켜 합을 정확히 100으로 맞춘다
    top = max(scaled, key=scaled.get)
    scaled[top] = round(scaled[top] + (100.0 - sum(scaled.values())), 2)
    return scaled

async def generate_finance_data(row, semaphore):
    """개별 행에 대해 LLM을 호출하여 금융 데이터를 생성합니다."""
    async with semaphore:
        # 1. 컨텍스트 구성
        persona_context = "\n".join([f"- {col}: {row[col]}" for col in SELECTED_COLUMNS if pd.notna(row[col])])
        prompt = PROMPT_TEMPLATE.format(persona_context=persona_context)
        
        max_retries = 3
        base_wait_time = 3.0
        
        global _use_schema

        for attempt in range(max_retries):
            try:
                # 2. NIM 호출 (스키마 강제로 잘림/파싱에러 방지)
                kwargs = {}
                if _use_schema:
                    kwargs["response_format"] = {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "FinanceProfile",
                            "schema": FinanceProfile.model_json_schema(),
                        },
                    }
                key, client = _get_client()
                # 키별 분당 호출 한도 슬롯 예약 (다른 파이프라인과 창을 공유)
                await asyncio.sleep(reserve(key))
                response = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=3000,
                    **kwargs,
                )

                # 3. 파싱 — 스키마 강제 여부와 무관하게 본문에서 JSON을 추출해 검증한다.
                content = response.choices[0].message.content or ""
                finance_data = FinanceProfile.model_validate_json(
                    extract_json(content)
                ).model_dump()

                # 행 데이터에 병합하기 위해 딕셔너리 구조 평탄화 (Flatten)
                result = row.to_dict()
                result['total_amount'] = finance_data['asset_size']['total_amount']
                result['stock_amount'] = finance_data['asset_size']['asset_types']['stock']
                result['bond_amount'] = finance_data['asset_size']['asset_types']['bond']
                result['deposit_amount'] = finance_data['asset_size']['asset_types']['deposit']
                result['real_estate_amount'] = finance_data['asset_size']['asset_types']['real_estate']
                
                result['has_stock'] = 1 if result['stock_amount'] > 0 else 0
                result['has_bond'] = 1 if result['bond_amount'] > 0 else 0
                result['has_deposit'] = 1 if result['deposit_amount'] > 0 else 0
                result['has_real_estate'] = 1 if result['real_estate_amount'] > 0 else 0

                result['specific_items'] = finance_data['asset_size']['specific_items']
                result['monthly_income'] = finance_data['asset_size']['monthly_income']
                result['monthly_investable'] = finance_data['asset_size']['monthly_investable']
                
                result['aggressiveness'] = finance_data['investment_propensity']['aggressiveness']
                result['preferred_asset'] = finance_data['investment_propensity']['preferred_asset']
                result['financial_literacy'] = finance_data['investment_propensity']['financial_literacy']
                
                result['target_return_percent'] = finance_data['investment_goal']['target_return_percent']
                result['investable_period_months'] = finance_data['investment_goal']['investable_period_months']
                result['requires_liquidity'] = finance_data['investment_goal']['requires_liquidity']

                # 권장 자산배분 카드 (portfolios 테이블용 비율 + 전략명)
                alloc = finance_data['recommended_allocation']
                result['strategy_name'] = str(alloc.get('strategy_name', ''))[:100]
                for k, v in normalize_ratios(alloc).items():
                    result[f'{k}_ratio'] = v

                return result
                
            except Exception as e:
                error_msg = str(e).replace("\n", " ")
                # 모델/엔드포인트가 json_schema를 지원하지 않으면 스키마 없이 재시도
                if _use_schema and ("response_format" in error_msg or "json_schema" in error_msg):
                    _use_schema = False
                    print(f"\n[알림] 모델이 json_schema를 거부했습니다. 프롬프트 기반 JSON 모드로 전환합니다. | {error_msg}")
                    continue
                if attempt < max_retries - 1:
                    wait_time = base_wait_time * (2 ** attempt)
                    print(f"\n[오류 발생 - 재시도 {attempt+1}/{max_retries}] uuid: {row.get('uuid', '알수없음')} | {wait_time}초 대기 | {error_msg}")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"\n[오류 발생 - 최종 건너뜀] uuid: {row.get('uuid', '알수없음')} | {error_msg}")
                    return None

async def main():
    print("1. 로컬 CSV 데이터셋 로드 중...")
    
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    input_file = os.path.join(PROJECT_ROOT, "data", "base_personas.csv")
    
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print(f"오류: '{input_file}' 파일이 없습니다. 먼저 export_csv.py를 실행해주세요!")
        return
    
    # 생성할 데이터 수만큼 샘플링. GEN_START_INDEX로 오프셋 지정 가능
    # (이미 생성된 앞쪽 행을 건너뛰고 뒷부분만 채울 때 사용).
    START_INDEX = int(os.environ.get("GEN_START_INDEX", "0"))
    df_sample = df.iloc[START_INDEX : START_INDEX + NUM_SAMPLES]
    print(f"2. 행 {START_INDEX}~{START_INDEX + len(df_sample) - 1} ({len(df_sample)}개) 생성을 시작합니다.")
    
    # 동시 요청 수 제어 (속도 향상을 위해 6개로 확장)
    semaphore = asyncio.Semaphore(4)
    
    # 실시간 진행률 출력을 위한 수동 tqdm 설정
    pbar = tqdm(total=len(df_sample), desc="생성 진행률")
    
    async def process_row(row):
        result = await generate_finance_data(row, semaphore)
        pbar.update(1)
        return result
        
    # 올바른 비율 제한(Rate Limit) 적용: 1.6초마다 하나씩 요청을 스케줄링합니다.
    tasks = []
    for _, row in df_sample.iterrows():
        tasks.append(asyncio.create_task(process_row(row)))
        await asyncio.sleep(DELAY_BETWEEN_REQUESTS)
    
    # 모든 태스크가 완료될 때까지 대기
    results = await asyncio.gather(*tasks)
    pbar.close()
    
    # None(오류) 제외
    valid_results = [r for r in results if r is not None]
    
    print(f"\n3. 생성 완료! 총 {len(valid_results)}개의 유효한 데이터가 생성되었습니다.")
    
    # 4. DataFrame으로 변환 및 저장
    new_df = pd.DataFrame(valid_results)
    
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_file = os.path.join(PROJECT_ROOT, "data", "augmented_personas.csv")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    # 오프셋 실행 시 기존 CSV(앞쪽 행들)를 보존하기 위해 append.
    append = START_INDEX > 0 and os.path.exists(output_file)
    new_df.to_csv(
        output_file,
        mode="a" if append else "w",
        header=not append,
        index=False,
        encoding="utf-8-sig",
    )
    print(f"4. 결과가 '{output_file}'에 {'추가' if append else '저장'}되었습니다.")

    # 데이터 미리보기
    if not new_df.empty:
        print("\n[생성된 데이터 미리보기]")
        display_cols = ['age', 'total_amount', 'monthly_income', 'aggressiveness', 'target_return_percent']
        print(new_df[display_cols].head())

    # 4.5. PostgreSQL에 직접 upsert
    print(f"\n4.5. PostgreSQL(users)에 {len(new_df)}건 적재 중...")
    int_cols = [
        "has_stock", "has_bond", "has_deposit", "has_real_estate", "requires_liquidity",
        "stock_amount", "bond_amount", "deposit_amount", "real_estate_amount",
    ]
    for col in int_cols:
        if col in new_df.columns:
            new_df[col] = new_df[col].fillna(0).astype(int)
    rows = [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in new_df.to_dict(orient="records")
    ]
    BATCH_SIZE = 50
    saved = 0
    with sync_tqdm(total=len(rows), unit="rows") as pbar:
        for i in range(0, len(rows), BATCH_SIZE):
            saved += bulk_upsert_users(rows[i : i + BATCH_SIZE])
            pbar.update(min(BATCH_SIZE, len(rows) - i))
    print(f"    완료! {saved}/{len(rows)}건 적재.")

    # 4.6. 권장 자산배분을 portfolios 테이블에 적재 (대시보드 '권장 포트폴리오' 카드용)
    pf_rows = [
        {
            "uuid": r.get("uuid"),
            "name": r.get("strategy_name"),
            "strategy_name": r.get("strategy_name"),
            **{f"{k}_ratio": r.get(f"{k}_ratio", 0) for k in RATIO_KEYS},
        }
        for r in rows
        if r.get("uuid")
    ]
    print(f"\n4.6. PostgreSQL(portfolios)에 {len(pf_rows)}건 적재 중...")
    pf_saved = 0
    with sync_tqdm(total=len(pf_rows), unit="rows") as pbar:
        for i in range(0, len(pf_rows), BATCH_SIZE):
            pf_saved += bulk_upsert_portfolios(pf_rows[i : i + BATCH_SIZE])
            pbar.update(min(BATCH_SIZE, len(pf_rows) - i))
    print(f"    완료! {pf_saved}/{len(pf_rows)}건 적재.")

    # 5. 허깅페이스 비공개 데이터셋에 업로드
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        print("\n5. 허깅페이스 데이터셋에 업로드 중...")
        api = HfApi()
        repo_id = "Jacob-9909/midas-touch-finance"
        try:
            api.create_repo(repo_id=repo_id, repo_type="dataset", private=True, token=hf_token, exist_ok=True)
        except Exception:
            pass
        api.upload_file(
            path_or_fileobj=output_file,
            path_in_repo="augmented_personas.csv",
            repo_id=repo_id,
            repo_type="dataset",
            token=hf_token,
        )
        print(f"   완료! https://huggingface.co/datasets/{repo_id}")
    else:
        print("\n[경고] HF_TOKEN이 없어 허깅페이스 업로드를 건너뜁니다.")

if __name__ == "__main__":
    asyncio.run(main())
