# Midas Touch Design System — "Bullion Terminal"

> version: 1.0 (2026-08)
> 이전 체계(docs/DESIGN-revolut.md — 마케팅 사이트용 두 모드 밴드)를 대체한다.
> 구현 단일 출처는 `frontend/src/app/globals.css`다. 이 문서는 그 해설이다.

## 왜 바꿨나

이 앱의 실체는 마케팅 페이지가 아니라 **데이터 콘솔**이다(청약 가점표·백테스트·
시뮬레이터·지식그래프). Revolut 마케팅 언어(흰 카탈로그 밴드)는 로그인 도구와
맞지 않았고, "Midas"라는 브랜드도 UI에서 발화하지 않았다. Linear/Vercel 계열의
근흑색 데이터 콘솔에 골드를 정체성 컬러로 찍는 지금 체계가 제품·브랜드·타깃
(20–30대 도구형 웹앱 유저) 모두와 맞물린다.

## 팔레트

### 다크 콘솔 (보조 테마)

| 토큰 | 값 | 용도 |
|---|---|---|
| `--ink` | `#101116` | 캔버스 base. 순흑 금지 — 장시간 상주 화면의 눈 피로 방지 |
| `--ink-2` | `#17181e` | 인셋·입력 배경 |
| `--ink-1` | `#1d1f26` | 카드 표면 |
| `--surface` | `#262933` | hover lift |
| `--line` | `#32353f` | 헤어라인 |
| `--fg` | `#e8e9ec` | 본문 |
| `--muted` | `#8b8f99` | 보조 텍스트 (4.5:1+) |
| `--accent` | `#d4af37` | 골드 — 아래 "골드 디스플린" 참조 |

### 라이트 크림 원장 (기본 테마)

| 토큰 | 값 |
|---|---|
| `--ink` | `#faf7f0` (웜 크림 캔버스) |
| `--ink-2` | `#f7f4ed` |
| `--ink-1` | `#ffffff` (카드) |
| `--surface` | `#f2eee5` |
| `--line` | `#e3ded2` |
| `--fg` | `#26241f` |
| `--accent` | `#a67c00` (크림 위 대비 확보용 다크 골드) |

### 시맨틱 색 — 골드와 절대 섞지 않는다

| 토큰 | 라이트 | 다크 | 용도 |
|---|---|---|---|
| `--positive` | `#1f6f54` | `#3fb68b` | 상승·충족·적중 |
| `--negative` | `#b33830` | `#e5484d` | 하락·미달·리스크 |
| `--warning` | `#9a6a1f` | `#e08a3c` | 보류·주의 |

Tailwind 유틸은 `text-positive` / `bg-negative/10` 형태로 노출된다.
**emerald/amber/rose 같은 Tailwind 원시 팔레트를 상태색으로 쓰지 않는다.**

## 골드 디스플린

골드(`--accent`)는 다음 세 용도로만 쓴다:

1. 목표·달성 신호 (진행률, 달성 배지)
2. 주 CTA·활성 상태 (활성 탭, 가이드 버튼, 포커스 링)
3. 브랜드 스탬프 (로고 글리프, "AI 콘솔" 같은 한 단어)

큰 면적·본문·차트 다중 계열에는 금지. viewport 안에 골드 요소가 2개 넘게
보이면 하나는 내려라.

## 타이포

- **본문/UI**: Inter(라틴) + Pretendard Variable(한글) — `npm: pretendard`
- **숫자**: Geist Mono + `tabular-nums` (`.font-mono-spec`) — 표에서 우측 정렬
- **디스플레이**: `.font-display` = weight 500 · line-height 1.05 · 자간 -0.02em
- 스케일: 12 / 14(base) / 16 / 20 / 24px. 콘솔이라 과한 히어로 크기를 쓰지 않는다.

## Radius & 여백

| 토큰 | 값 | 용도 |
|---|---|---|
| `--r-sm` | 6px | 버튼·입력 (`--r-pill` 아님!) |
| `--r-md` | 8px | 카드 (`.glass`, `.surface-raised`) |
| `--r-lg` | 12px | 패널·모달 |
| `--r-pill` | 9999px | 배지·탭만 |

Tailwind 원시 클래스 매핑: `rounded-lg`(8)=카드, `rounded-xl`(12)=패널,
`rounded-2xl`은 @theme 오버라이드로 12px 수렴. 새 코드는 토큰을 쓴다.

여백 리듬: 데이터 화면 `py-[72px]` + `max-w-[1200px] px-6`,
히어로 등 밴드성 섹션 88–120px. 이 값에서 벗어난 컨테이너를 만들지 않는다.

## 깊이 원칙

그림자 없음. 깊이는 세 가지로만:
1. 표면 명도 사다리 (canvas → ink-2 → ink-1 → surface/hover)
2. `.surface-raised` — 캔버스에 전경 4.5%를 섞은 반 단 위 표면(히어로 등)
3. 헤어라인 1px

발광(glow)·글래스(blur)·그라디언트 장식 금지. WebGL 앰비언트도 제거됐다.

## 공용 컴포넌트 규격

| 컴포넌트 | 위치 | 비고 |
|---|---|---|
| `Card` | components/ui.tsx | `.glass` 기반. variant는 editorial/subtle/interactive |
| `SegmentedTabs` | components/SegmentedTabs.tsx | 제네릭. 탭 복붙 금지 — 반드시 이것만 |
| `PageTitle` | components/ui.tsx | eyebrow + display 제목 + subtitle |
| `SectionLabel` | components/ui.tsx | 모노 소제목 + 골드 점. 아래에 "읽는 법" 설명을 붙일 것 |
| `GuideTour` | components/GuideTour.tsx | data-tour 앵커 방식. 단계 전환은 페이드 아웃→이동→페이드 인 |
| `SiteFooter` | components/SiteFooter.tsx | 챗 등 앱형 라우트에선 스스로 숨음 |
| `LandingGuide` / 각 페이지 TOUR | page 단위 | storageKey: `midas.tour.<page>.v1` |

## 데이터 정직성

UI가 "실시간", "LIVE"라고 읽히는 장식은 실시간이 아니면 쓰지 않는다.
출처·시점을 명시한다(예: `yfinance · 2026. 8. 22.`). 차트는 반드시 실제
시계열(`/api/v1/stocks/price-history`)을 그리고, 색 근거(오늘 등락 vs 구간 추세)를
일치시킨다.

## 가이드 투어 패턴

복잡한 화면에는 GuideTour를 붙인다:
- 대상 요소에 `data-tour="<step-id>"`, 투어는 `storageKey`로 1회 자동 실행
- 재실행 버튼은 골드 외곽 pill("사용 가이드") — 히어로 우상단 또는 PageTitle 옆
- 설명 문구는 "무엇을 어디에 넣는지"가 아니라 "이 화면을 어떻게 읽는지"를 기준으로 쓴다
