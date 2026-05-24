"""CSV → Azure SQL 적재 스크립트.

generate_finance_data.py가 생성한 augmented_personas.csv를 읽어
Azure SQL users 테이블에 upsert합니다.

실행:
    uv run python src/db/save_to_azure.py
    uv run python src/db/save_to_azure.py --file data/augmented_personas.csv --batch 100
"""

import argparse
import os
import sys

import pandas as pd
from tqdm import tqdm

# 프로젝트 루트 경로 설정
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connector import bulk_upsert_users, apply_schema


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"로드 완료: {len(df):,}행 / 컬럼: {list(df.columns)}")
    return df


def df_to_rows(df: pd.DataFrame) -> list[dict]:
    """DataFrame → connector가 기대하는 dict 리스트로 변환."""
    bool_cols = ["has_stock", "has_bond", "has_deposit", "has_real_estate", "requires_liquidity"]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    # NaN → None (pyodbc는 None을 NULL로 처리)
    return [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="페르소나 CSV → Azure SQL 적재")
    parser.add_argument(
        "--file", "-f",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "augmented_personas.csv",
        ),
        help="입력 CSV 경로 (기본값: data/augmented_personas.csv)",
    )
    parser.add_argument("--batch", "-b", type=int, default=50, help="배치 크기 (기본 50)")
    parser.add_argument("--init-schema", action="store_true", help="스키마 초기화 후 적재")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"파일 없음: {args.file}")
        print("먼저 generate_finance_data.py를 실행해 augmented_personas.csv를 생성하세요.")
        sys.exit(1)

    if args.init_schema:
        print("스키마 초기화 중...")
        apply_schema()
        print("스키마 초기화 완료.")

    df = load_csv(args.file)
    rows = df_to_rows(df)

    total = len(rows)
    saved = 0
    print(f"\n총 {total:,}건을 Azure SQL에 적재합니다. (배치 크기: {args.batch})")

    with tqdm(total=total, unit="rows") as pbar:
        for i in range(0, total, args.batch):
            batch = rows[i : i + args.batch]
            count = bulk_upsert_users(batch)
            saved += count
            pbar.update(len(batch))

    print(f"\n완료! {saved:,}/{total:,}건 적재.")


if __name__ == "__main__":
    main()
