# Midas Touch

> **AI 기반의 올인원 금융 & 자산 어시스턴트**  
> 복잡한 세법, 주식 분석, 부동산 청약 정보를 AI 에이전트와 대화하며 직관적으로 확인하세요.

---

## 🏛️ 시스템 아키텍처 (Architecture)

<p align="center">
  <img src="architecture.svg" alt="Midas Touch System Architecture" width="100%" />
</p>

---

## 📱 핵심 기능

* 💬 **AI 금융 챗봇 (`/chat`)**  
  * 주식 시세, 세법, 청약 공고, 최신 금융 뉴스를 통합 분석하여 실시간 스트리밍으로 답변합니다.
  * 복잡한 질문도 필요한 도구들을 스스로 판단해 안전하고 객관적인 정보를 제공합니다.

* 📈 **주식 분석 & 백테스트 (`/stocks`)**  
  * RSI, MACD 등 주요 기술지표 자동 진단과 AI 분석 코멘트를 제공합니다.
  * 과거 데이터 기반의 전략 백테스트로 수익률과 리스크를 시뮬레이션합니다.

* 🏠 **부동산 청약 알리미 (`/cheongyak`)**  
  * 공공데이터 기반 아파트, 오피스텔, 무순위(줍줍), 임대주택 공고를 실시간 조회합니다.
  * 주택형별 경쟁률, 당첨 가점 커트라인, 특별공급 조건을 한눈에 비교합니다.

* 🕸️ **세법 지식그래프 (`/graph`)**  
  * 복잡한 세법과 절세 전략을 인터랙티브 2D 네트워크 그래프로 시각화합니다.
  * AI가 어떤 법령과 근거를 참고했는지 원문과 함께 투명하게 확인합니다.

* 📊 **스마트 대시보드 (`/dashboard`)**  
  * KOSPI, S&P500, 주요국 기준금리 등 실시간 시장 지표를 모니터링합니다.
  * 또래 투자자 그룹과의 포트폴리오 비교 및 자산 배분 차트를 제공합니다.

---

## ⚡ 빠른 시작 (Quick Start)

### 1. 사전 준비
* **Python 3.12+** (`uv` 설치 권장)
* **Node.js 20+**
* **Docker** (DB 컨테이너 구동용)

### 2. 환경 설정
```bash
# 환경 변수 파일 생성
cp .env.example .env
```
> `.env` 파일에 NVIDIA NIM, Tavily, 공공데이터 등의 API 키를 입력합니다.

### 3. 앱 실행
`dev.sh` 스크립트를 실행하면 필요한 DB 컨테이너와 백엔드/프론트엔드가 자동으로 실행됩니다.

```bash
# 로컬 개발 서버 실행 (Backend :8000 / Frontend :3000)
./dev.sh
```

* **웹 콘솔 접속**: [http://localhost:3000](http://localhost:3000)
* **API 문서 (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ 기술 스택

* **Frontend**: Next.js 16 (React 19), Tailwind CSS, GSAP, D3.js
* **Backend**: FastAPI, LangGraph, LangChain, PostgreSQL (pgvector), Neo4j
* **AI & Data**: NVIDIA NIM (`gpt-oss-120b`, `bge-m3`), yfinance, 청약홈 공공데이터 API
* **Tooling**: uv, Docker Compose, pytest, ruff

---

## 📂 프로젝트 구조

```
midas-touch/
├── frontend/       # Next.js 웹 콘솔 UI
├── backend/        # FastAPI API 및 LangGraph 에이전트 서비스
├── pipelines/      # 데이터 수집, 임베딩, 지식그래프 빌더
├── shared/         # 공통 DB 커넥터 및 유틸리티
├── openwiki/       # 상세 아키텍처 및 도메인 문서 모음
├── dev.sh          # 로컬 개발 통합 실행 스크립트
└── start.sh        # 프로덕션 실행 스크립트
```

---

## 📖 상세 문서

시스템 아키텍처, 에이전트 설계, API 명세 등 자세한 내용은 [OpenWiki](openwiki/quickstart.md)를 참고하세요.

* [OpenWiki Quickstart](openwiki/quickstart.md)
* [시스템 아키텍처](openwiki/architecture.md)
* [에이전트 구조](openwiki/agents.md)
* [API 명세서](openwiki/api.md)