# Midas Touch

Midas Touch 프로젝트의 Python 개발 환경 설정, 폴더 구조 및 실행 가이드입니다.

---

## 📁 디렉토리 구조

Midas Touch는 관심사 분리(Separation of Concerns)를 극대화하고 단방향 의존성을 보장하기 위해 다음과 같은 엔터프라이즈 폴더 레이아웃을 채택하고 있습니다.

```
midas-touch/
├── backend/                    # 실시간 서빙 API & 에이전트 서비스
│   └── app/
│       ├── main.py             # FastAPI 엔트리포인트 (GraphRAG API 및 에이전트 라우터)
│       └── services/
│           └── agent/          # 금융 질의 대응 LangGraph 에이전트 모듈 (MidasAdviser)
│               ├── graph.py        # StateGraph 조립/컴파일 (배선 전용) + 캐시된 get_agent()
│               ├── state.py        # AgentState 스키마 + tool_context 누적 리듀서
│               ├── checkpointer.py # PostgresSaver 멀티턴 영속화 (커넥션 풀)
│               ├── nodes/          # 그래프 노드 (intent · 도구 3종 · synthesize · dispatch 라우팅)
│               └── tools/          # 노드가 호출하는 검색 도구 (persona/graph RAG, tax lookup)
├── pipelines/                  # 배치 데이터 수집/임베딩/지식 그래프 파이프라인
│   ├── data_ingestion/         # 금융/세법 원천 데이터 크롤링, 페르소나 인제스션
│   ├── embedding/              # 대조 학습용 Triplet 데이터셋 구축 및 토큰 청커/마이닝 파이프라인
│   └── knowledge_graph/        # Neo4j 지식 그래프 구축 및 RAG 질의 엔진 (Entity Resolution)
├── shared/                     # 중앙화된 공통 의존성 및 유틸리티 라이브러리
│   ├── database/               # PostgreSQL 통합 커넥터, SQLAlchemy ORM 모델, Alembic 마이그레이션
│   └── utils/                  # 프로젝트 전역 공통 헬퍼 클래스 (로깅, 공통 유틸)
├── infra/                      # 인프라 설정 및 배포 파일 관리 (Docker Compose, 로컬 보안 설정)
└── alembic.ini                 # 데이터베이스 마이그레이션 설정 파일
```

---

## ⚙️ 시작하기 및 패키지 설치

패키지 의존성 도구인 `uv`를 활용하여 개발 환경을 즉시 동기화합니다.
```bash
uv sync
```

---

## 🗄️ 데이터베이스 구조 (PostgreSQL)

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

---

## 🧠 금융 데이터 처리 & RAG 파이프라인 요약

Midas Touch의 통합 데이터 파이프라인은 금융 및 세법 원천 문서를 지능형 토큰 단위로 청킹하고 마크다운 표 구조를 추출하여 데이터셋을 구성하며, 하이브리드 RRF 마이닝을 거쳐 대조 학습용 Triplet을 합성합니다. 이와 동시에 한국어 특화 임베딩(`bge-m3`)과 오픈 스키마 동적 확장을 결합해 Neo4j 지식 그래프를 증분 구축하며, 2-hop 다중 홉(Multi-hop) 서브 그래프 탐색을 통해 구조화된 지식 컨텍스트를 반영하는 Graph-Context-Aware RAG 추론 답변을 산출합니다.

---

## 🕸️ 에이전트 그래프 구조 (LangGraph `StateGraph`)

멀티턴 자산관리 에이전트(MidasAdviser)는 도구 선택을 LLM ReAct 루프에 맡기는 대신, **앞단 intent 분류기가 "어떤 도구를 쓸지"를 한 번에 판정**하고 해당 도구 노드만 결정적으로 실행하는 **intent 분기 그래프**로 구성됩니다. 복합 질문은 여러 도구를 동시에(fan-out) 태워 컨텍스트를 누적한 뒤, `synthesize` 노드가 **단 1회의 LLM 호출**로 최종 답변을 작성합니다. (도구 호출마다 LLM 라운드가 붙는 ReAct 대비 지연·비용을 절감)

```
                                  ┌─────────────────────────┐
                                  │   intent (classify)     │  필요 도구 판정 (structured-output,
                                  │  LLM 라우터 + 키워드 폴백  │  실패 시 키워드 폴백) · tool_context 리셋
                                  └────────────┬────────────┘
   START ───────────────────────────────────►  │
                                  dispatch (conditional fan-out)
              ┌──────────────────────┬─────────┴──────────┬──────────────────────┐
              ▼                      ▼                    ▼                      │ (도구 불필요)
     ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────────┐     │
     │   persona_rag   │   │    graph_rag    │   │  tax_and_market_lookup  │     │
     │ 또래 벤치마킹 검색  │    │ 세법 근거/관계 검색 │   │   절세 조건·시장 수치 조회    │     │
     └────────┬────────┘   └────────┬────────┘   └────────────┬────────────┘     │
              └─────────────────────┴────────tool_context 누적 ┴──────────────────┤
                                                      ▼
                                  ┌──────────────────────────────────────────────────┐
                                  │                  synthesize                      │
                                  │  SYSTEM_PROMPT + 프로필요약 + 누적 컨텍스트로 1회 작문   │
                                  └────────────────────────┬─────────────────────────┘
                                                           ▼
                                                          END
```

* **상태(`AgentState`)**: `messages`(대화 이력, `add_messages` 리듀서) · `user_uuid`(필수) · `profile_summary`(첫 턴 구성 후 재사용) · `route`(고른 도구 목록) · `tool_context`(도구들이 누적한 검색 컨텍스트, `merge_tool_context` 리듀서로 fan-out 결과를 충돌 없이 병합).
* **노드 분리**: 각 노드는 `nodes/` 패키지에 파일 단위로 분리되고, `graph.py`는 이를 import해 **배선(토폴로지)만** 담당합니다. 노드 로직 수정은 `nodes/`에서, 그래프 연결 변경은 `graph.py`에서 합니다.
* **멀티턴 영속화**: `PostgresSaver` 체크포인터로 `thread_id`(=`session_id`)별 대화 상태를 Postgres에 영속화 — 프로세스 재시작·다중 uvicorn 워커 간 세션이 공유됩니다. 체크포인트 테이블은 **Alembic 마이그레이션이 단일 진실원천**이라 `setup()`은 호출하지 않습니다.
* **레거시**: 이전 ReAct 구성(`langchain.agents.create_agent`)은 `graph.py`의 `[LEGACY]` 블록에 주석으로 보존되어 있어 토폴로지 교체로 되돌릴 수 있습니다.

---

## 🚀 실행 명령어 모음

### 1. 데이터베이스 마이그레이션 최신화
```bash
uv run alembic upgrade head
```

### 2. FastAPI 실시간 웹 서버 실행
```bash
PYTHONPATH=. uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
* **Swagger UI 웹 콘솔**: http://localhost:8000/docs

### 3. 멀티턴 금융 에이전트 (LangGraph) 호출

FastAPI 서버 구동 후, 세션 기반 멀티턴 대화형 자산관리 에이전트(`/api/v1/chat`)를 호출합니다.
LangGraph **intent 분기 `StateGraph`**가 질의 성격을 한 번에 분류해 필요한 도구(persona_rag / graph_rag /
tax_and_market_lookup)만 fan-out 실행한 뒤 `synthesize`로 답변을 작성하며(위 [에이전트 그래프 구조](#️-에이전트-그래프-구조-langgraph-stategraph) 참고),
`session_id`(thread_id)별로 대화 맥락이 유지됩니다. `user_uuid`는 필수입니다.

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-session-001",
    "user_uuid": "<users 테이블에 존재하는 UUID>",
    "message": "나와 비슷한 투자자들의 자산 배분을 벤치마크로 보여줘."
  }'
```
* 같은 `session_id`로 다시 호출하면 이전 대화가 이어집니다(멀티턴 메모리).

### 4. 거시경제 지표 수집 배치 가동 (yfinance API 연동)
```bash
# 최근 7일 데이터 배치 수집
PYTHONPATH=. uv run python -m pipelines.data_ingestion.fetch_market_data

# 과거 90일 데이터 백필(Backfill) 실행
PYTHONPATH=. uv run python -m pipelines.data_ingestion.fetch_market_data --backfill
```

### 5. 유저 페르소나 데이터셋 빌드 및 DB 적재
```bash
PYTHONPATH=. uv run python -m pipelines.data_ingestion.ingest_personas --file data/augmented_personas.csv
```

### 6. 금융 임베딩 학습 전처리 파이프라인 실행
```bash
# 전체 문서 파이프라인 가동
PYTHONPATH=. uv run python pipelines/embedding/pipeline.py

# 특정 단일 파일만 전처리 실행
PYTHONPATH=. uv run python pipelines/embedding/pipeline.py --file financial_report.pdf

# 특정 단계 강제 재시작 (체크포인트 무시)
PYTHONPATH=. uv run python pipelines/embedding/pipeline.py --force-rerun query_synthesis
```

### 7. 지식 그래프 구축 및 RAG 질의 테스트
```bash
# Neo4j 지식 그래프 증분 빌드 실행
PYTHONPATH=. uv run python -m pipelines.knowledge_graph.builder

# GraphRAG 질의 추론 테스트 실행
PYTHONPATH=. uv run python -m pipelines.knowledge_graph.test_rag
```

### 8. 손상 PDF 문서 강제 재파싱 복구
```bash
PYTHONPATH=. uv run python -m pipelines.embedding.reingest data/raw_documents/주택과세금_2025.pdf
```

### 9. Neo4j 시각화 확인
* **주소**: [http://localhost:7474](http://localhost:7474) (기본 계정: `neo4j` / `PG_develop_2026_Secure`)
* **조회 쿼리**: `MATCH (n) RETURN n LIMIT 100`