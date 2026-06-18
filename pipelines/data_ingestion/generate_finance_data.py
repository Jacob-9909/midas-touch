import asyncio
import json
import os
import re
import sys
import pandas as pd
from datasets import load_dataset
from huggingface_hub import HfApi
from openai import AsyncOpenAI
from tqdm import tqdm as sync_tqdm
from tqdm.asyncio import tqdm
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 경로를 sys.path에 추가해 shared.database.connector 임포트 가능하게 함
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shared.database.connector import bulk_upsert_users

# ==========================================
# 1. 설정 (Settings)
# ==========================================
# 생성할 데이터 수 지정
NUM_SAMPLES = 50

# 초당 요청 수 제어 (딜레이를 단축하여 대기 시간 단축)
DELAY_BETWEEN_REQUESTS = 0.5 

# 클라이언트 설정 (환경 변수 또는 .env에 NVIDIA_API_KEY가 설정되어 있어야 합니다)
client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_API_KEY", ""),
    timeout=300.0
)

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
  }}
}}

[제약 조건]
- asset_types의 하위 값들(stock, bond, deposit, real_estate)은 각 자산의 실제 보유 금액(원화 기준 정수)이어야 하며, 이 값들의 합은 반드시 total_amount와 정확히 일치해야 합니다.
- aggressiveness, financial_literacy는 1~10 사이의 숫자입니다.
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

async def generate_finance_data(row, semaphore):
    """개별 행에 대해 LLM을 호출하여 금융 데이터를 생성합니다."""
    async with semaphore:
        # 1. 컨텍스트 구성
        persona_context = "\n".join([f"- {col}: {row[col]}" for col in SELECTED_COLUMNS if pd.notna(row[col])])
        prompt = PROMPT_TEMPLATE.format(persona_context=persona_context)
        
        max_retries = 3
        base_wait_time = 3.0
        
        for attempt in range(max_retries):
            try:
                # 2. LLM 호출 (JSON 파싱을 위해 stream=False 사용)
                response = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=3000,
                )
                
                content = response.choices[0].message.content
                json_str = extract_json(content)
                
                # 3. JSON 파싱
                finance_data = json.loads(json_str)
                
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
                
                return result
                
            except Exception as e:
                error_msg = str(e).replace("\n", " ")
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
    
    # 생성할 데이터 수만큼 샘플링
    df_sample = df.head(NUM_SAMPLES)
    print(f"2. {NUM_SAMPLES}개의 샘플에 대해 데이터 생성을 시작합니다.")
    
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
    new_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"4. 결과가 '{output_file}'에 저장되었습니다.")

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
