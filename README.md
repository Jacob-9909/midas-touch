# Midas Touch

Midas Touch 프로젝트의 Python 개발 환경 및 데이터베이스 버전 관리 설정 안내입니다.

## 개발 환경 설정

`uv`를 사용하여 가상환경 및 패키지 의존성을 관리합니다.

1. **패키지 설치**:
   ```bash
   uv sync
   ```

---

## 데이터베이스 & Alembic 마이그레이션 관리

본 프로젝트는 구조화된 데이터 저장을 위한 **Azure SQL Database**와 벡터 검색 및 RAG 지원을 위한 **Supabase (pgvector)** 두 가지 데이터베이스를 운영하며, 각 DB의 스키마 버전을 **Alembic**을 통해 개별 관리합니다.

### 📂 디렉토리 구조 (Directory Structure)
데이터베이스 인프라 리소스와 순수 파이썬 모듈이 다음과 같이 분리되어 있습니다:
* `database/schema/`: 원본 SQL 스키마 정의 (`azure_schema.sql`, `supabase_schema.sql`)
* `database/seeds/`: 초기화 시드 데이터 SQL (`seed_tax_rules.sql`)
* `database/migrations/`: Alembic 마이그레이션 버전 관리 공간 (`azure/`, `supabase/`)
* `src/db/`: 데이터베이스 연결용 재사용 가능한 Python 커넥터 모듈 및 SQLAlchemy ORM 모델
* `scripts/`: 데이터 파이프라인 업로드 및 유틸리티 실행 스크립트 (`save_to_azure.py` 등)

### 1. 환경 변수 설정 (`.env`)
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 양식에 맞게 정보를 입력합니다.
```env
# Azure SQL Database 접속 정보
AZURE_SQL_SERVER=your-azure-sql-server.database.windows.net
AZURE_SQL_DATABASE=midas-touch-finance
AZURE_SQL_USER=your-username
AZURE_SQL_PASSWORD=your-password

# Supabase 직접 연결 (pgvector 마이그레이션용)
SUPABASE_DB_URL=postgresql://postgres.xxx:password@aws-pooler.supabase.com:6543/postgres
```

### 2. 스키마 변경 시 마이그레이션 명령어

스키마가 변경(SQLAlchemy ORM 모델 수정)되었을 때 아래 명령어를 사용하여 버전 파일을 생성하고 데이터베이스에 적용합니다.

#### 🔹 Azure SQL Database (정형 데이터)
* **ORM 모델**: `src/db/models/azure_models.py`
* **마이그레이션 생성**:
  ```bash
  uv run alembic -c alembic_azure.ini revision --autogenerate -m "변경 내용 기재"
  ```
* **데이터베이스 적용**:
  ```bash
  uv run alembic -c alembic_azure.ini upgrade head
  ```

#### 🔹 Supabase PostgreSQL (벡터 및 캐시)
* **ORM 모델**: `src/db/models/supabase_models.py`
* **마이그레이션 생성**:
  ```bash
  uv run alembic -c alembic_supabase.ini revision --autogenerate -m "변경 내용 기재"
  ```
* **데이터베이스 적용**:
  ```bash
  uv run alembic -c alembic_supabase.ini upgrade head
  ```