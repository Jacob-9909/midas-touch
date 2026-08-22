# Frontend Guide

The frontend is a **Next.js 16** application using the new App Router. It provides a single‑page‑application‑style console that talks to the FastAPI backend via the helper library in `frontend/src/lib/api.ts`.

**Design system**: "Bullion Terminal" — 근흑색 데이터 콘솔(다크 보조) + 크림 원장(라이트 기본) + 골드 정체성 컬러. 단일 출처는 `frontend/src/app/globals.css`, 해설은 [`docs/DESIGN-bullion-terminal.md`](../docs/DESIGN-bullion-terminal.md).

## Project Structure

```
frontend/
├── src/
│   ├── app/               # Top-level pages
│   │   ├── page.tsx        # Landing/dashboard gateway (+ LandingGuide tour)
│   │   ├── chat/page.tsx   # Chat UI – SSE streaming + node progress status line
│   │   ├── stocks/page.tsx # Stock analysis – quick-analysis, backtest, watchlist (+ guide tour)
│   │   ├── cheongyak/page.tsx # Housing project list & detail modals (+ guide tour)
│   │   ├── me/page.tsx     # 청약가점·자금 상황 입력 (localStorage, 서버 미전송)
│   │   ├── simulator/page.tsx # 자금마련 타임라인 시뮬레이터 (+ guide tour)
│   │   ├── graph/page.tsx  # Interactive Neo4j force-graph visualisation
│   │   └── login/page.tsx  # Email/password login (AUTH_ENABLED 시)
│   │   # (/finetune, /dashboard/[uuid] 는 MVP 컷으로 삭제)
│   ├── components/
│   │   ├── ui.tsx          # Card, PageTitle, SectionLabel, Spinner, LoadingBlock, AnimatedNumber
│   │   ├── SegmentedTabs.tsx # 유일한 세그먼트 탭 구현 — 탭 복붙 금지
│   │   ├── GuideTour.tsx   # data-tour 앵커 스포트라이트 투어 (페이드 전환)
│   │   ├── LandingGuide.tsx / SiteFooter.tsx / ProfileNudge.tsx
│   │   ├── NavBar.tsx      # Header – core/engine 그룹 내비 + 테마 토글
│   │   ├── GraphView.tsx   # canvas 기반 force-graph viewer (토큰 실측 tokenColor())
│   │   ├── MoneyInput.tsx / JobProgress.tsx
│   │   └── bits/           # CountUp, DecryptedText, MiniSparkline, Radar, SpecularMetricCard
│   ├── lib/
│   │   ├── api.ts          # REST wrapper + SSE streamChat(token/status 이벤트 파싱)
│   │   ├── my-profile.ts   # /me 입력값 저장·요약 (localStorage)
│   │   ├── cheongyak-score.ts # 84점 만점 청약가점 계산(「주택공급에 관한 규칙」 별표1)
│   │   ├── simulate.ts     # 자금마련 타임라인 계산(브라우저 전용)
│   │   ├── theme.tsx       # dark/light 클래스 on <html> (기본 light, localStorage 영속)
│   │   ├── user-context.tsx # AUTH_ENABLED 시 로그인 신원/토큰, 아니면 데모 페르소나 스위처
│   │   └── toast.tsx       # Global toast system
│   └── globals.css         # 디자인 토큰 단일 출처 (--ink/--accent/--positive 등 + .btn-*/.glass/.field)
└── package.json            # next, react, phosphor-icons, pretendard, recharts, react-force-graph-2d
```

## State Management

* **User selection / auth** – `useSelectedUser` from `user-context.tsx`. `NEXT_PUBLIC_AUTH_ENABLED=true`면 로그인으로 신원을 정하고 백엔드 `current_uuid` 인증과 맞물린다. 끄면 localStorage 페르소나로 하위호환.
* **Profile** – `my-profile.ts`의 `loadProfile/saveProfile`. 입력값은 브라우저에만 저장되고, 챗 첫 턴에 `profileSummary()` 요약 문자열만 서버로 전송된다.
* **Theme** – `useTheme` toggles a CSS class on `<html>`; default는 light(크림), choice persists across reloads.
* **Chat streaming** – `streamChat` parses `{"type":"token"}` and `{"type":"status"}` events; status 라벨("세법 지식그래프 탐색…" 등)은 응답 버블 위 모노 캡션으로 표시된다.
* **Async jobs** – `JobProgress` polls `/api/v1/jobs/{id}`.

## Key UI Interactions

| Page | Core Interaction | Backend Endpoint |
|------|------------------|------------------|
| **Landing (`/`)** | 3단계 여정 카드 → 각 화면 진입 | — |
| **Me (`/me`)** | 가점·1순위 요건·자금 입력 → 즉시 대조 판정 | 없음(localStorage) |
| **Chat** | Send message → stream LLM response (+ Knowledge Panel tab) | `POST /api/v1/chat/stream` |
| **Stocks** | Ticker 검색 → quick-analysis / backtest / grid-search | `GET /api/v1/stocks/quick-analysis`, `POST .../backtest`, `GET .../price-history` |
| **Cheongyak** | 공고 목록(Korean map 필터) + 상세 모달에서 1순위 재판정 | Various `/api/v1/cheongyak/...` |
| **Simulator** | 목표금액·저축액 → 도달 개월 그래프(상품 비교) | 없음(브라우저 계산) |
| **Graph** | Build graph snapshot → visualiser → GraphRAG 질의 | `POST /api/v1/graph/build/jobs`, `GET /api/v1/graph/snapshot` |

## Guide Tours

복잡한 화면에는 `GuideTour`를 붙인다: 대상에 `data-tour="<step-id>"`, 페이지마다 `TOUR` 상수 + `midas.tour.<page>.v1` storageKey(첫 방문 1회 자동 실행), PageTitle 옆 골드 외곽 pill 재시작 버튼. 현재 적용: `/`(LandingGuide) · `/stocks` · `/cheongyak` · `/simulator` · `/me`.

## How to Extend

* New page: `frontend/src/app/<name>/page.tsx` 생성.
* New component: `frontend/src/components/` 아래 배치. 탭은 반드시 `SegmentedTabs` 재사용.
* New API call: `frontend/src/lib/api.ts`에 타입과 함께 함수 추가.
* 색 추가 금지 — 먼저 `globals.css` 토큰을 확인하라. 상태색은 positive/negative/warning만.

## Development Tips

* `./dev.sh` – backend (uvicorn :8000) + frontend (:3000) 동시 실행.
* 프로덕션 빌드 확인: `cd frontend && npm run build`.
* SSE 디버깅: devtools Network에서 `chat/stream` — `data:` 라인이 token/status/done 이벤트.
