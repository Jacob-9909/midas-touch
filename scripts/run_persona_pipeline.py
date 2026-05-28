"""Midas Touch Persona Ingestion and Vector Embedding Pipeline Orchestrator.

This script:
1. Bootstraps the Supabase pgvector schema (idempotent setup of tables, indexes, and RPC functions).
2. Loads augmented_personas.csv.
3. Generates 1024-dimensional Korean retrieval embeddings using nlpai-lab/KURE-v1 (local sentence-transformers).
4. Bulk upserts the persona texts and embeddings into Supabase persona_embeddings table.
"""

import os
import sys
import argparse
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

# Set up project root and source path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "src"))

import psycopg2
from sentence_transformers import SentenceTransformer

load_dotenv()


def bootstrap_supabase_schema() -> None:
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("DATABASE_URL 또는 SUPABASE_DB_URL이 설정되지 않아 스키마 부트스트랩을 건너뜁니다.")
        return
        
    schema_path = os.path.join(project_root, "database", "schema", "postgres_schema.sql")
    if not os.path.exists(schema_path):
        print(f"스키마 파일 없음: {schema_path}")
        return

    print("1. PostgreSQL 기존 테이블 정리 및 통합 스키마 초기화 중...")
    with open(schema_path, encoding="utf-8") as f:
        sql_schema = f.read()

    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            # Execute entire schema script at once
            cursor.execute(sql_schema)
            conn.commit()
        conn.close()
        print("   PostgreSQL 통합 스키마 및 RPC 함수 부트스트랩 성공 (1024차원 KURE-v1 최적화 완료).")
    except Exception as e:
        print(f"⚠️ PostgreSQL 스키마 초기화 중 예외 발생: {e}")
        print("   (경고: 테이블 수정 권한을 확인해 주세요.)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Midas Touch 페르소나 임베딩 및 Supabase 적재 파이프라인")
    parser.add_argument(
        "--file", "-f",
        default=os.path.join(project_root, "data", "augmented_personas.csv"),
        help="입력 augmented_personas.csv 경로",
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=50,
        help="Supabase 적재 배치 크기 (기본값: 50)",
    )
    args = parser.parse_args()

    # 1. Schema Bootstrap
    bootstrap_supabase_schema()

    # 2. Check source CSV
    if not os.path.exists(args.file):
        print(f"❌ 입력 파일 없음: {args.file}")
        print("   먼저 `uv run src/data_pipeline/generate_finance_data.py`를 가동하여 augmented_personas.csv를 생성해 주세요.")
        sys.exit(1)

    print("\n2. 페르소나 데이터셋 로드 중...")
    df = pd.read_csv(args.file, encoding="utf-8-sig")
    print(f"   성공적으로 로드함: {len(df):,}행 추출 완료.")

    if "uuid" not in df.columns:
        print("❌ 오류: CSV에 'uuid' 컬럼이 존재하지 않습니다.")
        sys.exit(1)

    # 3. Load Embedding Model
    print("\n3. 고려대학교 한국어 URE 임베딩 모델(nlpai-lab/KURE-v1) 로드 중...")
    print("   (Hugging Face에서 최초 1회 다운로드가 진행되므로 네트워크 상황에 따라 시간이 소요될 수 있습니다.)")
    try:
        model = SentenceTransformer("nlpai-lab/KURE-v1")
        print("   KURE-v1 모델 로드 성공. (임베딩 차원: 1024)")
    except Exception as e:
        print(f"❌ KURE-v1 임베딩 모델 로드 실패: {e}")
        sys.exit(1)

    # 4. Generate Embeddings & Prepare rows
    print("\n4. 페르소나 프로필 병합 및 의미론적(Semantic) 임베딩 벡터 빌드 중...")
    rows_to_insert = []
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="임베딩 생성"):
        uuid = row.get("uuid")
        if pd.isna(uuid):
            continue
            
        # Concatenate demographic and LLM-augmented persona fields
        text_parts = []
        for col in ["persona", "professional_persona", "family_persona", "career_goals_and_ambitions"]:
            val = row.get(col)
            if val and not pd.isna(val):
                text_parts.append(str(val))
                
        persona_text = "\n".join(text_parts).strip()
        if not persona_text:
            persona_text = f"Persona profile for user with UUID: {uuid}"

        # Generate KURE-v1 1024-dim embedding
        embedding_vec = model.encode(persona_text).tolist()
        
        rows_to_insert.append({
            "azure_user_uuid": str(uuid),
            "persona_text": persona_text,
            "embedding": embedding_vec
        })

    # 5. Direct Bulk Upsert to Consolidated PostgreSQL DB
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("❌ 오류: DATABASE_URL 또는 SUPABASE_DB_URL 환경변수가 존재하지 않아 적재를 종료합니다.")
        sys.exit(1)

    print(f"\n5. PostgreSQL pgvector(persona_embeddings)에 {len(rows_to_insert):,}건 적재를 시작합니다...")
    
    upsert_sql = """
    INSERT INTO persona_embeddings (azure_user_uuid, persona_text, embedding, updated_at)
    VALUES (%s, %s, %s, NOW())
    ON CONFLICT (azure_user_uuid) DO UPDATE SET
        persona_text = EXCLUDED.persona_text,
        embedding = EXCLUDED.embedding,
        updated_at = NOW();
    """

    saved_count = 0
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cursor:
            for i in range(0, len(rows_to_insert), args.batch_size):
                batch = rows_to_insert[i: i + args.batch_size]
                batch_params = [
                    (r["azure_user_uuid"], r["persona_text"], r["embedding"])
                    for r in batch
                ]
                # Execute batch
                cursor.executemany(upsert_sql, batch_params)
                saved_count += len(batch)
                print(f"   [적재 진행] {saved_count:,} / {len(rows_to_insert):,} 완료")
            conn.commit()
        conn.close()
        print(f"\n🎉 파이프라인 완수! 총 {saved_count:,}개의 페르소나 벡터가 PostgreSQL에 성공적으로 동기화되었습니다.")
    except Exception as e:
        print(f"❌ PostgreSQL 적재 작업 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
