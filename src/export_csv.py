import pandas as pd
from datasets import load_dataset

SELECTED_COLUMNS = [
    'professional_persona', 'family_persona', 'persona', 
    'career_goals_and_ambitions', 'sex', 'age', 'marital_status', 
    'education_level', 'bachelors_field', 'occupation', 
    'family_type', 'housing_type', 'district', 'uuid'
]

print("데이터셋 로컬 캐시에서 불러오는 중...")
ds = load_dataset("nvidia/Nemotron-Personas-Korea")
df = ds['train'].to_pandas()

print("필요한 컬럼 추출 중...")
df_filtered = df[SELECTED_COLUMNS].copy()

import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_file = os.path.join(PROJECT_ROOT, "data", "base_personas.csv")
os.makedirs(os.path.dirname(output_file), exist_ok=True)
print(f"'{output_file}' 로 저장하는 중 (용량이 커서 몇 초 정도 걸릴 수 있습니다)...")
df_filtered.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"완료! 총 {len(df_filtered)}개의 데이터가 로컬 프로젝트 디렉토리에 저장되었습니다.")
