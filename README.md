# Midas Touch

Midas Touch 프로젝트의 Python 개발 환경 설정, 폴더 구조 및 실행 가이드입니다.

---

## 📁 디렉토리 구조

Midas Touch는 관심사 분리(Separation of Concerns)를 극대화하고 단방향 의존성을 보장하기 위해 다음과 같은 엔터프라이즈 폴더 레이아웃을 채택하고 있습니다.

```
midas-touch/
├── backend/                    # 실시간 서빙 API & 에이전트 서비스 (FastAPI)
│   └── app/
│       ├── main.py             # FastAPI 엔트리포인트 (CORS·라우터 등록·GraphRAG /query)
│       ├── api/                # HTTP 라우터
│       │   ├── chat.py             # 멀티턴 챗봇·스트리밍(SSE)·세션 목록/기록/삭제
│       │   ├── users.py            # 유저 목록/상세, 시장지표, 세율 (대시보드 조회)
│       │   ├── finetune.py         # 문서 업로드 → 파인튜닝셋 생성 작업·데이터셋 프리뷰
│       │   └── graph.py            # 지식그래프 빌드 작업·Neo4j 스냅샷
│       └── services/
│           ├── jobs.py         # 비동기 작업(JobManager): CLI 파이프라인 subprocess + 진행률·로그 영속화
│           └── agent/          # 금융 질의 대응 LangGraph 에이전트 (MidasAdviser)
│               ├── graph.py        # StateGraph 조립/컴파일 (배선 전용) + 캐시된 get_agent()
│               ├── state.py        # AgentState 스키마 + tool_context 누적 리듀서
│               ├── checkpointer.py # PostgresSaver 멀티턴 영속화 (커넥션 풀)
│               ├── nodes/          # 그래프 노드 (intent · 도구 3종 · synthesize · dispatch 라우팅)
│               └── tools/          # 노드가 호출하는 검색 도구 (persona/graph RAG, tax lookup)
├── frontend/                   # 웹 콘솔 (Next.js 16 · App Router · TypeScript · Tailwind)
│   └── src/
│       ├── app/                # 페이지: / (대시보드) · /chat · /finetune · /graph · /dashboard/[uuid]
│       ├── components/         # NavBar · Card/Skeleton(ui) · JobProgress · GraphView(포스그래프)
│       └── lib/                # api(fetch·SSE) · theme(다크/라이트) · toast · user-context
├── pipelines/                  # 배치 데이터 수집/임베딩/지식 그래프 파이프라인
│   ├── data_ingestion/         # 금융/세법 원천 데이터 크롤링, 페르소나 인제스션
│   ├── embedding/              # 대조 학습용 Triplet 데이터셋 구축 및 토큰 청커/마이닝 파이프라인
│   └── knowledge_graph/        # Neo4j 지식 그래프 구축 및 RAG 질의 엔진 (Entity Resolution)
├── shared/                     # 중앙화된 공통 의존성 및 유틸리티 라이브러리
│   ├── database/               # PostgreSQL 통합 커넥터, SQLAlchemy ORM 모델, Alembic 마이그레이션
│   └── utils/                  # 프로젝트 전역 공통 헬퍼 클래스 (로깅, 공통 유틸)
├── tests/                      # 통합 테스트 (test_agent.py · test_api.py)
├── infra/                      # 인프라 설정 (Docker Compose, 로컬 보안 설정)
├── data/                       # 원천 문서·생성 데이터셋·작업 이력(jobs/) [git 미추적]
├── dev.sh                      # 개발 런처 (백엔드 --reload + 프론트 next dev)
├── start.sh                    # 프로덕션 런처 (next build/start + uvicorn --workers)
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

## 🖥️ 웹 콘솔 기능 (Backend API · Frontend)

기존 파이프라인/에이전트 기능을 브라우저에서 사용할 수 있는 통합 웹 콘솔이다.
프론트(Next.js, :3000)가 백엔드(FastAPI, :8000)를 호출하며, 긴 배치 작업은 **비동기 작업 +
진행률 폴링**으로 처리한다(기존 CLI를 subprocess로 재사용). 인증/권한은 아직 없다(로컬 콘솔 전제).

### Backend API (FastAPI · prefix `/api/v1`)

| 분류 | 엔드포인트 | 설명 |
|------|-----------|------|
| 챗봇 | `POST /chat` | 멀티턴 답변(단건). `session_id`·`user_uuid`·`message` |
| 챗봇 | `POST /chat/stream` | 동일하되 **SSE 토큰 스트리밍**(synthesize 답변만) |
| 챗봇 | `GET /chat/sessions` | 세션 목록(체크포인터 기반, `?user_uuid` 필터) |
| 챗봇 | `GET /chat/history/{session_id}` | 세션 대화 기록(user/assistant) 복원 |
| 챗봇 | `DELETE /chat/sessions/{session_id}` | 세션 대화 기록 삭제 |
| 대시보드 | `GET /users` · `GET /users/{uuid}` | 유저 목록 / 프로필+포트폴리오 |
| 대시보드 | `GET /market/snapshots` · `GET /tax-rules` | 최신 시장지표 / 세율 |
| 파인튜닝 | `POST /finetune/upload` | 금융 문서(PDF·TXT·MD·JSONL) 업로드 |
| 파인튜닝 | `POST /finetune/jobs` · `GET /finetune/jobs/{id}` | 파이프라인 작업 시작 / 진행률·로그 |
| 파인튜닝 | `GET /finetune/datasets?sub_dir=` | 생성된 train/eval triplet 프리뷰 |
| 그래프 | `POST /graph/build/jobs` · `GET …/{id}` | 지식그래프 증분 빌드 작업 / 진행률 |
| 그래프 | `GET /graph/snapshot?limit=` | Neo4j 노드/엣지 스냅샷(포스그래프용 JSON) |
| GraphRAG | `POST /query` | 질의 답변 + 근거 서브그래프·출처 본문 |
| 기타 | `GET /` · `GET /health` | 루트 / DB·Neo4j 헬스체크 · `GET /docs` Swagger |

### Frontend 페이지 (Next.js)

| 경로 | 기능 |
|------|------|
| `/` | 유저 목록·검색·선택, 최신 시장지표 카드 |
| `/chat` | 멀티턴 에이전트 챗봇 — 실시간 스트리밍, 좌측 세션 사이드바(불러오기·삭제) |
| `/finetune` | 문서 업로드 → 파이프라인 실행 → 진행률·로그 → triplet 데이터셋 프리뷰 |
| `/graph` | 지식그래프 빌드 → 인터랙티브 포스그래프 → GraphRAG 질의·근거 노드 강조 |
| `/dashboard/[uuid]` | 유저 프로필 + 자산배분·포트폴리오 도넛 차트 |

공통: 다크/라이트 테마 토글, 토스트 알림, 로딩 스켈레톤, 반응형 레이아웃.

---

## 🚀 실행 명령어 모음

### 1. 준비 (의존성 · DB 마이그레이션)
```bash
uv sync                         # 백엔드/파이프라인 의존성 동기화
(cd frontend && npm install)    # 프론트 의존성
uv run alembic upgrade head     # DB 스키마 + 체크포인트 테이블 최신화
```

### 2. 웹 콘솔 실행 (백엔드 + 프론트)
```bash
./dev.sh        # 개발: 백엔드(:8000,--reload) + 프론트(:3000,HMR) 동시 — Ctrl+C로 모두 종료
./start.sh      # 프로덕션: next build/start + uvicorn --workers (재시작 없음)
```
* 개별 실행: `./dev.sh backend` / `./dev.sh frontend` (start.sh도 동일)
* 백엔드 수동 실행: `PYTHONPATH=. uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`
* 웹 콘솔 http://localhost:3000 · **Swagger UI** http://localhost:8000/docs

### 3. 멀티턴 에이전트 직접 호출 (API)
`session_id`(=thread_id)별로 대화 맥락이 유지되며 `user_uuid`는 필수다. intent 분기 그래프가
필요한 도구만 fan-out 실행 후 `synthesize`로 작문한다(위 [에이전트 그래프 구조](#️-에이전트-그래프-구조-langgraph-stategraph) 참고).
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"user-session-001","user_uuid":"<users UUID>","message":"나와 비슷한 투자자들의 자산 배분을 벤치마크로 보여줘."}'
```
* 스트리밍은 동일 바디로 `POST /api/v1/chat/stream` (SSE).

### 4. 배치 파이프라인 (CLI — 웹 콘솔의 작업 버튼과 동일 로직)
```bash
# 거시경제 지표 수집 (yfinance) — 기본 최근 7일 / --backfill 시 과거 90일
PYTHONPATH=. uv run python -m pipelines.data_ingestion.fetch_market_data [--backfill]

# 유저 페르소나 데이터셋 빌드 및 DB 적재
PYTHONPATH=. uv run python -m pipelines.data_ingestion.ingest_personas --file data/augmented_personas.csv

# 임베딩 파인튜닝셋 생성 — 전체 / 단일 파일(--file) / 특정 단계 강제 재실행(--force-rerun)
PYTHONPATH=. uv run python pipelines/embedding/pipeline.py [--file financial_report.pdf] [--force-rerun query_synthesis]

# 지식 그래프 증분 빌드 / GraphRAG 질의 테스트
PYTHONPATH=. uv run python -m pipelines.knowledge_graph.builder
PYTHONPATH=. uv run python -m pipelines.knowledge_graph.test_rag

# 손상 PDF 문서 강제 재파싱 복구
PYTHONPATH=. uv run python -m pipelines.embedding.reingest data/raw_documents/주택과세금_2025.pdf
```

### 5. 테스트
```bash
PYTHONPATH=. uv run python -m unittest discover tests -v   # test_agent(에이전트/DB) + test_api(라우터)
```

### 6. Neo4j 시각화 확인
* 웹 콘솔 `/graph`(인터랙티브 포스그래프) 또는 Neo4j Browser [http://localhost:7474](http://localhost:7474)
* 기본 계정 `neo4j` / `PG_develop_2026_Secure` · 조회 `MATCH (n) RETURN n LIMIT 100`