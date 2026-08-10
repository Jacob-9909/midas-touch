# Midas Touch

자산 관리 및 투자 분석을 위한 AI 에이전트 기반 플랫폼입니다. LangGraph 기반 멀티턴 대화, pgvector/Neo4j GraphRAG, 주식 및 청약 데이터 분석, BGE-M3 파인튜닝 파이프라인을 제공합니다.

---

## 시스템 흐름

```
[User Request] -> [FastAPI /api/v1] -> [LangGraph Intent Router]
                                              │
             ┌────────────────────────────────┴──────────────────────────────┐
             ▼                                                               ▼
    [PostgreSQL / pgvector / Neo4j]                                  [yfinance / 청약 API / 웹검색]
    (유저 프로필, 세법, 지식그래프)                                     (주식 시세, 기술지표, 분양 공고)
             │                                                               │
             └────────────────────────────────┬──────────────────────────────┘
                                              ▼
                                   [Synthesize 작문]
                                              │
                                              ▼
                                [Next.js 16 콘솔 / SSE 스트리밍]
```

---

## 주요 기능

### 챗봇 (/chat)
- LangGraph 기반 멀티턴 에이전트 및 PostgresSaver 세션 저장
- Intent 판정 후 9개 툴 병렬 실행 및 SSE 토큰 스트리밍 응답

### 주식 분석 및 백테스트 (/stocks)
- yfinance 연동 기술지표 스냅샷(RSI, MACD, KDJ, BB, ATR) 및 진단 코멘트
- 매매 전략 백테스트, 파라미터 그리드 서치, 과거 분석 이력(stock_analysis_memory) 검증

### 청약 정보 (/cheongyak)
- 공공데이터 API 기반 APT, 오피스텔, 무순위, 공공임대 공고 조회
- 주택형별 경쟁률, 당첨 가점, 특별공급 현황 상세 조회 및 챗봇 연계

### 지식그래프 및 GraphRAG (/graph, /query)
- Neo4j 기반 세법 및 자산 관계 지식그래프 증분 구축
- D3 Force 2D 시각화 및 근거 서브그래프/원문 출처 조회 API (/query)

### 파인튜닝 파이프라인 (/finetune)
- 금융 및 세법 문서 파싱, 질문 합성, BGE-M3 대조학습용 Triplet 데이터셋 생성
- 비동기 subprocess 작업 실행 및 진행률/로그 확인

### 대시보드 및 금리 리서치 (/dashboard, /)
- 포트폴리오 자산배분 차트 및 또래 투자자 그룹 벤치마킹
- 주요 시장 지표(KOSPI, S&P500, VIX 등) 및 미·일·한 기준금리 브리핑

---

## 기술 스택 및 개발 환경

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4
- **Backend**: Python 3.12, FastAPI, Uvicorn, LangGraph, LangChain, Alembic
- **Database**: PostgreSQL 16 (pgvector), Neo4j Graph DB
- **LLM / Model**: NVIDIA NIM (openai/gpt-oss-120b, BAAI/bge-m3), Tavily, yfinance
- **Package & Tooling**: uv (pyproject.toml 기반 패키지 관리), ruff (린터), pytest (단위/통합 테스트)

---

## 디렉토리 구조

```
midas-touch/
├── openwiki/         # 상세 위키 문서 모음
├── backend/          # FastAPI REST API 및 에이전트 서비스
│   └── app/
│       ├── api/      # HTTP 라우터 (chat, stocks, cheongyak, graph, finetune 등)
│       └── services/ # 주식 분석 엔진, 청약 클라이언트, 에이전트 노드/툴
├── frontend/         # Next.js 16 프론트엔드 웹 콘솔
├── pipelines/        # 데이터 수집, 파인튜닝, Neo4j 빌더 파이프라인
├── shared/           # PostgreSQL/Neo4j 클라이언트, NIM Rate Limiter
├── tests/            # 백엔드, 라우터, 단위/통합 테스트
├── dev.sh            # 개발 환경 실행 스크립트 (Backend + Frontend)
└── start.sh          # 프로덕션 빌드 및 실행 스크립트
```

---

## 실행 방법

### 1. 의존성 설치 및 DB 마이그레이션

`uv` 패키지 관리자를 사용해 개발 및 런처 환경을 동기화합니다.

```bash
uv sync
(cd frontend && npm install)
uv run alembic upgrade head
```

### 2. 앱 실행

```bash
# 개발 모드 (백엔드 :8000 / 프론트엔드 :3000)
./dev.sh

# 프로덕션 모드
./start.sh
```

### 3. 코드 린팅 및 테스트

```bash
# 린팅 (ruff)
uv run ruff check .

# 테스트 (pytest)
uv run pytest
```

---

## 참고 문서

상세 기능 및 구조 설명은 [openwiki/](file:///Users/jacob/Develop/midas-touch/openwiki) 디렉토리를 참고하세요.

- [Quickstart](file:///Users/jacob/Develop/midas-touch/openwiki/quickstart.md)
- [Architecture](file:///Users/jacob/Develop/midas-touch/openwiki/architecture.md)
- [Agents](file:///Users/jacob/Develop/midas-touch/openwiki/agents.md)
- [API Reference](file:///Users/jacob/Develop/midas-touch/openwiki/api.md)