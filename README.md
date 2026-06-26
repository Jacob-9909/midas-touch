# Midas Touch

Midas Touch 프로젝트의 Python 개발 환경 설정, 폴더 구조 및 실행 가이드입니다.

---

## 📁 디렉토리 구조

Midas Touch는 관심사 분리(Separation of Concerns)를 극대화하고 단방향 의존성을 보장하기 위해 다음과 같은 엔터프라이즈 폴더 레이아웃을 채택하고 있습니다.

```
midas-touch/
├── backend/                    # 실시간 서빙 API & 에이전트 서비스 (FastAPI)
│   └── app/
│       ├── main.py             # FastAPI 엔트리포인트 (CORS·8개 라우터 등록·헬스체크)
│       ├── api/                # HTTP 라우터 (prefix /api/v1)
│       │   ├── chat.py             # 멀티턴 챗봇·스트리밍(SSE)·세션 목록/기록/삭제
│       │   ├── users.py            # 유저 목록/상세, 시장지표, 세율 (대시보드 조회)
│       │   ├── stocks.py           # 종목 빠른분석·백테스트·그리드서치·분석메모리 통계/검증
│       │   ├── cheongyak.py        # 청약홈 분양 공고 목록·상세(경쟁률·가점·특별공급)
│       │   ├── research.py         # 미·일·한 기준금리 라이브 브리핑(온디맨드)
│       │   ├── finetune.py         # 문서 업로드 → 파인튜닝셋 생성 작업·데이터셋 프리뷰
│       │   ├── graph.py            # 지식그래프 빌드 작업·Neo4j 스냅샷
│       │   └── query.py            # GraphRAG /query (근거 서브그래프 + 출처 본문)
│       └── services/
│           ├── jobs.py         # 비동기 작업(JobManager): CLI 파이프라인 subprocess + 진행률·로그 영속화
│           ├── chat_service.py # 에이전트 호출·세션 처리 공통 서비스
│           ├── trading/        # 종목 분석 엔진 (yfinance)
│           │   ├── stock_analyzer.py   # 기술지표 스냅샷(RSI·MACD·KDJ·BB·ATR) + 백테스트/그리드서치
│           │   ├── ai_analysis.py      # LLM 종합 코멘트 (F&G·VIX·프로필 결합)
│           │   └── analysis_memory.py  # 과거 분석 이력 저장·유사패턴 회상·정확도 캘리브레이션
│           ├── cheongyak/      # 청약홈 공공데이터 API 클라이언트
│           └── agent/          # 금융 질의 대응 LangGraph 에이전트 (MidasAdviser)
│               ├── graph.py        # StateGraph 조립/컴파일 (배선 전용) + 캐시된 get_agent()
│               ├── state.py        # AgentState 스키마 + tool_context 누적 리듀서
│               ├── checkpointer.py # PostgresSaver 멀티턴 영속화 (커넥션 풀)
│               ├── prompts.py      # SYSTEM_PROMPT 등 작문 프롬프트
│               ├── nodes/          # 그래프 노드 (intent · 도구 9종 · synthesize · dispatch 라우팅)
│               └── tools/          # 노드가 호출하는 검색 도구 (persona/graph RAG, tax, web/*)
├── frontend/                   # 웹 콘솔 (Next.js 16 · App Router · TypeScript · Tailwind)
│   └── src/
│       ├── app/                # 페이지: / · /chat · /stocks · /cheongyak · /graph · /finetune · /dashboard/[uuid]
│       ├── components/         # NavBar · Card/Skeleton(ui) · JobProgress · GraphView(포스그래프) · Reveal
│       └── lib/                # api(fetch·SSE) · theme(다크/라이트) · toast · user-context · chat-seed
├── pipelines/                  # 배치 데이터 수집/임베딩/지식 그래프 파이프라인
│   ├── data_ingestion/         # 금융/세법 원천 데이터 크롤링, 페르소나 인제스션
│   ├── embedding/              # 대조 학습용 Triplet 데이터셋 구축 및 토큰 청커/마이닝 파이프라인
│   └── knowledge_graph/        # Neo4j 지식 그래프 구축 및 RAG 질의 엔진 (Entity Resolution)
├── shared/                     # 중앙화된 공통 의존성 및 유틸리티 라이브러리
│   ├── database/               # PostgreSQL+pgvector 커넥터, ORM 모델, 리포지토리, Alembic 마이그레이션, neo4j_client
│   └── utils/                  # 프로젝트 전역 공통 헬퍼 (로깅, NIM/OpenAI 래퍼 등)
├── tests/                      # 통합 테스트 (test_agent.py · test_api.py · test_unit.py)
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

## 🤖 LLM · 임베딩 모델 구성

모델은 코드에 하드코딩하지 않고 전부 `.env` 환경변수로 주입합니다(`agent/llm.py`의 `require_env`는 기본값 없이 강제). 호출 경로는 **NVIDIA NIM**(OpenAI 호환 엔드포인트 `https://integrate.api.nvidia.com/v1`)과 **Google Gemini**(Vertex AI) 두 가지입니다.

| 환경변수 | 현재 모델 | 용도 |
|----------|-----------|------|
| `AGENT_LLM_MODEL` | `deepseek-ai/deepseek-v4-pro` | 에이전트 답변·보고서 생성 (LangGraph) |
| `PERSONA_GENERATION_MODEL` | `deepseek-ai/deepseek-v4-pro` | 합성 투자자 페르소나 생성 |
| `NIM_GENERATION_MODEL` | `deepseek-ai/deepseek-v4-pro` | 임베딩 파이프라인 쿼리 합성 |
| `GEMINI_GENERATION_MODEL` | `gemini-2.5-flash` | 지식 그래프 빌더 |
| `GEMINI_VISION_MODEL` | `gemini-2.5-flash` | 비전 기반 PDF 전사(텍스트레이어 손상 문서) |
| `AGENT_EMBEDDING_MODEL` | `BAAI/bge-m3` | 에이전트 쿼리 임베딩(1024차원, persona_embeddings와 동일해야 함) |
| `TEACHER_EMBEDDING_MODEL` | `BAAI/bge-m3` | 하드 네거티브 마이닝 교사 임베딩 |
| `STUDENT_EMBEDDING_MODEL` | `BAAI/bge-m3` | 파인튜닝 대상 학생 임베딩 |

> 임베딩은 파인튜닝 완료 후 `TRAINING_OUTPUT_DIR`(예: `./output/kure-finance-v1`) 경로의 모델로 교체할 수 있습니다.

---

## 🗄️ 데이터베이스 구조 (PostgreSQL + pgvector)

의미 벡터는 별도 벡터DB 없이 **PostgreSQL + pgvector**(`Vector(1024)` 컬럼)로 통합 저장하며, 지식 그래프의 노드/관계만 **Neo4j**에 둡니다.

* **비즈니스 & 세법 데이터**:
  - `users`: 사용자 프로필, 자산 및 투자성향 정보.
  - `portfolios` & `portfolio_items`: 포트폴리오 자산 비중 및 개별 종목 명세.
  - `tax_rules`: 한국 세법 기준 소득별 세율 및 공제 한도.
  - `legal_references` & `market_snapshots`: 세법 근거 법령 및 일별 시장 지표.
  - `chat_sessions`: 챗봇 세션 메타데이터(제목·소유 유저 등).
* **의미 벡터 데이터 (pgvector · 1024차원)**:
  - `news_embeddings`, `strategy_docs`, `macro_indicators`, `persona_embeddings`.
* **종목 분석 메모리**:
  - `stock_analysis_memory`: 과거 종목 분석 결과(지표·전망)를 jsonb로 적재 → 유사 패턴 회상 및 신뢰도 캘리브레이션. 최초 사용 시 `CREATE TABLE IF NOT EXISTS`로 자기완결 생성(마이그레이션 불필요).
* **학습 파이프라인 & 체크포인트 데이터**:
  - `emb_passages`: 청킹된 금융 원천 단락.
  - `emb_synthetic_queries`: LLM이 합성한 사용자 질문.
  - `emb_training_triplets`: 최종 조립 완료된 대조 학습용 삼중쌍 데이터셋.
  - `graph_checkpoints`: 지식 그래프 적재 완료 단락 체크포인트.
* **LangGraph 체크포인트**: `PostgresSaver`가 멀티턴 대화 상태를 Postgres에 영속화(Alembic 마이그레이션이 단일 진실원천).

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
                                  dispatch (conditional fan-out — 도구 0~N개 선택)
              ┌─────────────────────────────────┴─────────────────────────────┐ (도구 불필요)
              ▼                                                                │
     ┌──────────────────────── 도구 노드 9종 (필요한 것만 병렬 실행) ───────────────────┐  │
     │  persona_rag · graph_rag · tax_and_market_lookup       (내부 DB/그래프)      │  │
     │  product_research · news_research · nts_law_research   (라이브 웹 검색)       │  │
     │  stock_backtest · stock_quick · cheongyak_lookup       (외부 API/yfinance)   │  │
     └────────────────────────────┬───────tool_context 누적 ──────────────────────┘  │
                                  ▼                                                  │
                                  ┌──────────────────────────────────────────────────┐
                                  │                  synthesize                      │◄─┘
                                  │  SYSTEM_PROMPT + 프로필요약 + 누적 컨텍스트로 1회 작문   │
                                  └────────────────────────┬─────────────────────────┘
                                                           ▼
                                                          END
```

**도구 노드 9종**

| 도구 | 분류 | 역할 |
|------|------|------|
| `persona_rag` | 내부 DB | 또래 벤치마킹 — 유사 투자자의 권장 자산배분·종목/섹터 선호 (pgvector) |
| `graph_rag` | 내부 그래프 | 세법 조항의 법적 근거·세율 출처·자산 간 관계 (Neo4j) |
| `tax_and_market_lookup` | 내부 DB | 특정 자산의 절세 조건·현재 시장 수치 빠른 조회 |
| `product_research` | 라이브 | 국내 금융상품 현재 금리/조건 (네이버 검색) |
| `news_research` | 라이브 | 미·일·한 기준금리 동향·정책 맥락 (웹 검색) |
| `nts_law_research` | 라이브 | 국세청 법령해석(유권해석) 최신 사례 |
| `stock_backtest` | 외부 API | 특정 종목 과거 성과/백테스트 (yfinance) |
| `stock_quick` | 외부 API | 특정 종목 현 시점 기술지표 진단(RSI·MACD·이동평균 등) |
| `cheongyak_lookup` | 외부 API | 최근·예정 청약(분양) 공고 (청약홈) |

> 내부 DB로 충분하면 라이브/외부 도구는 굳이 고르지 않도록 intent 프롬프트가 안내하며, 도구가 불필요하면 곧장 `synthesize`로 직행합니다.

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
| 주식 | `GET /stocks/quick-analysis?ticker=` | 현 시점 기술지표 스냅샷 + LLM 코멘트(분석메모리 회상 포함) |
| 주식 | `GET /stocks/strategies` · `GET /stocks/ticker-search?q=` | 백테스트 전략 목록 / 티커 자동완성 |
| 주식 | `POST /stocks/backtest` · `POST /stocks/grid-search` | 단일 백테스트 / 파라미터 그리드서치 |
| 주식 | `POST /stocks/analysis` | 분석 결과를 메모리에 저장 |
| 주식 | `GET /stocks/memory/stats` · `POST /stocks/memory/validate` | 분석메모리 통계·정확도 / 과거 예측 검증 |
| 청약 | `GET /cheongyak/list/{kind}` | 분양 공고 목록(apt·officetel·remaining·opt·public-rent) |
| 청약 | `GET /cheongyak/detail/{...}/housing-types\|competition\|scores\|special-supply` | 공고 상세(주택형·경쟁률·가점·특별공급) |
| 리서치 | `GET /research/rate-briefing` | 미·일·한 기준금리 동향 라이브 브리핑(온디맨드) |
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
| `/stocks` | 종목 분석 — 빠른분석/백테스트 탭, 티커 자동완성, 그리드서치, 분석메모리 통계 카드, 결과를 챗으로 넘기기 |
| `/cheongyak` | 청약 분양정보 — 유형 탭(APT·오피스텔·무순위/잔여·임의공급·공공임대), 상세 모달(경쟁률·가점·특별공급), 챗 상담 연계 |
| `/graph` | 지식그래프 빌드 → 인터랙티브 포스그래프 → 노드 클릭 상세 뷰 → GraphRAG 질의·근거 노드 강조 |
| `/finetune` | 문서 업로드 → 파이프라인 실행 → 진행률·로그 → triplet 데이터셋 프리뷰 |
| `/dashboard/[uuid]` | 유저 프로필 + 자산배분·포트폴리오 도넛 차트 |

공통: 다크/라이트 테마 토글, 토스트 알림, 로딩 스켈레톤, 반응형 레이아웃. 상단 NavBar는 **main**(대시보드·챗봇·주식분석·청약)과 **engine**(지식그래프·파인튜닝셋) 그룹으로 구분됩니다.

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