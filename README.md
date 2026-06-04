# Midas Touch

Midas Touch 프로젝트의 Python 개발 환경 설정 및 통합 파이프라인 가이드입니다.

---

## ⚙️ 개발 환경 및 시작하기

### 1. 패키지 의존성 설치 (`uv` 활용)
```bash
uv sync
```

### 2. 환경 변수 설정 (`.env`)
루트에 `.env` 파일을 생성하고 아래 연결 정보를 입력합니다.
```env
# Unified PostgreSQL
DATABASE_URL=postgresql://postgres:PG_develop_2026_Secure@0.tcp.jp.ngrok.io:28613/postgres
POSTGRES_HOST=0.tcp.jp.ngrok.io
POSTGRES_PORT=28613
POSTGRES_USER=postgres
POSTGRES_PASSWORD=PG_develop_2026_Secure
POSTGRES_DB=postgres

# NVIDIA NIM API (임베딩 파이프라인 쿼리 합성용 LLM)
NVIDIA_API_KEY=nvapi-xxxxxx

# Google Gemini API (지식 그래프 builder LLM + 손상 PDF 비전 파싱용)
GEMINI_API_KEY=AIzaSy-xxxxxx
GEMINI_GENERATION_MODEL=gemini-2.5-flash

# Neo4j Graph Database
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=PG_develop_2026_Secure
NIM_GRAPH_DELAY=2.0
```

---

## 🗄️ 데이터베이스 및 마이그레이션 (PostgreSQL)

### 📊 간단한 테이블 구조 요약
* **비즈니스 & 세법 데이터**:
  - `users`: 사용자 프로필, 자산 및 투자성향 정보.
  - `portfolios` & `portfolio_items`: 포트폴리오 자산 비중 및 개별 종목 명세.
  - `tax_rules`: 한국 세법 기준 소득별 세율 및 공제 한도.
  - `legal_references` & `market_snapshots`: 세법 근거 법령 및 일별 시장 지표.
* **의미 벡터 데이터 (1024차원 HNSW)**:
  - `news_embeddings`, `strategy_docs`, `macro_indicators`, `persona_embeddings` 등.
* **학습 파이프라인 & 체크포인트 데이터**:
  - `emb_passages`: 청킹된 금융 원천 단락.
  - `emb_synthetic_queries`: LLM이 합성한 사용자 질문.
  - `emb_training_triplets`: 최종 조립 완료된 대조 학습용 삼중쌍 데이터셋.
  - `graph_checkpoints`: 지식 그래프 적재 완료 단락 체크포인트.

### 데이터베이스 마이그레이션 최신화
```bash
uv run alembic upgrade head
```

---

## 🧠 금융 특화 임베딩 파인튜닝 파이프라인

금융 문서를 가공하여 임베딩 모델 학습용 Triplet 데이터셋을 구축하고 PostgreSQL에 적재하는 파이프라인입니다.

### 🔄 데이터 생성 프로세스 (Workflow)
1. **문서 청킹**: 금융 원천 문서를 읽고 의미 단락(`Passage`) 단위로 정제 분할 후 캐싱.
2. **LLM 쿼리 합성**: NIM API를 이용해 각 단락별 5가지 유형(키워드/질문/비정형 등)의 사용자 질문 합성.
3. **하드 네거티브 마이닝**: 교사 모델(`KURE-v1`) 유사도를 기준으로 가장 헷갈리기 쉬운 오답 단락 선별.
4. **Triplet 조립**: `(질문, 정답 단락, 오답 단락)` 대조 학습용 삼중쌍 조립 후 학습/평가 데이터 분할.

### 🚀 실행 명령어

#### 1) 전체 문서 파이프라인 실행
```bash
uv run python src/embedding_pipeline/pipeline.py
```

#### 2) 특정 단일 문서만 실행
```bash
uv run python src/embedding_pipeline/pipeline.py --file financial_report.pdf
```

#### 3) 단계별 강제 재실행 (체크포인트 무시)
```bash
uv run python src/embedding_pipeline/pipeline.py --force-rerun query_synthesis
```

---

## 🕸️ Neo4j + LlamaIndex GraphRAG 지식 그래프 파이프라인

세법 및 금융 데이터로부터 트리플(노드/관계)을 추출하여 로컬 Neo4j 지식 그래프를 증분 구축하고, 이를 탐색하여 GraphRAG 자연어 질의응답을 수행합니다. 트리플 추출 LLM은 **Google Gemini (`gemini-2.5-flash`)** 를 사용합니다 (Neo4j 5.26 기준).

> **손상 PDF 자동 처리**: 텍스트 레이어가 손상되었거나 스캔본인 PDF는 파서가 자동 감지하여 페이지를 이미지로 렌더링 후 Gemini 비전으로 전사합니다. 손상 PDF만 따로 재적재하려면:
> ```bash
> uv run python -m scripts.reingest_pdf data/raw_documents/<문서>.pdf
> ```

### 🚀 실행 및 시각화 명령어

#### 1) 지식 그래프 증분 적재 실행 (PostgreSQL 체크포인트 기반 스킵 동작)
```bash
uv run python -m src.knowledge_graph.builder
```

#### 2) GraphRAG 질의 추론 테스트 실행
```bash
uv run python -m src.knowledge_graph.test_rag
```

#### 3) 실시간 지식망 시각화 (Neo4j 웹 콘솔)
- **주소**: [http://localhost:7474](http://localhost:7474)
- **계정**: `neo4j` / `PG_develop_2026_Secure`
- **시각화 쿼리**: `MATCH (n) RETURN n LIMIT 100`