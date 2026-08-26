# Neon Ledger — 디자인 시스템 v2

> 이전 체계: `DESIGN-bullion-terminal.md`(무채색 콘솔 미니멀 — 그림자·발광 금지, r=6).
> "올드하다"는 피드백에 따라 2026.08 웹플로우 레퍼런스 3종의 **추출값 기반**으로 재설계했다.

## 근거 레퍼런스와 추출값

| 소스 | 추출 | 채택 |
|---|---|---|
| [Finantech X](https://finantechtemplate-showcase.webflow.io) | 캔버스 `#060606`, 블루 `#1d88fe`/`#05c168`, 카드 r=16~24, 섹션 그라디언트 페이드 | 극흑 캔버스, 큰 라운드, positive 그린 |
| [Homies 3D](https://homies-f662e0.webflow.io) | 인디고 `#4a42e7`, 앰버 `#faad13`, 플레이ful r=20~40, Neue Machina 디스플레이 | 인디고 액션색, 앰버 골드, chunky 디스플레이 톤 |
| [Accounting Dashboard](https://accounting-dashboard.webflow.io) | KPI 카드 패턴, pill 버튼, Outfit, 라이트 뉴트럴 | 라이트 모드를 크림→쿨 뉴트럴로 교체 |

## 토큰 (`globals.css`)

- **캔버스 사다리**: `--ink #0a0a10 → --ink-2 #11111a(인셋) → --ink-1 #15151f(카드) → --surface #1d1d2a(hover)`
- **액센트 이원화**:
  - `--accent #6c5cff` 일렉트릭 인디고 = 액션·포커스·링크·주 CTA
  - `--gilt #faad13` 앰버 골드 = Midas 도장 포인트(로고 글리프·스텝 라벨 등 드물게)
- **시맨틱**: positive `#05c168` / negative `#ff4d67` / warning `#ff8a3d`
- **radius**: 입력 12 / 카드·패널 20 / 모달 24 / **버튼·배지 pill** (구: 6/8/12)
- **그림자**: 부활. `--shadow-1`(카드), `--shadow-2`(부유) — 인디고 틴트 글로우 포함
- **라이트 모드**: 크림 원장 → 쿨 뉴트럴(`#f6f7fb` + 화이트 카드), accent는 대비용 진한 인디고

## 타이포그래피

- 본문: Inter + Pretendard (유지)
- **디스플레이: Space Grotesk** (`--font-display`) — Neue Machina의 기하학적 톤을
  무료 폰트로 대체. weight 600, lineHeight 1.05, 자간 -0.02em
- 숫자: Geist Mono tabular-nums (유지)

## 신규 유틸리티

| 클래스 | 용도 |
|---|---|
| `.grad-text` | 인디고→앰버 그라디언트 텍스트(히어로 강조 어절 전용) |
| `.aurora` | 섹션 배경 오로라 블롭(::before 인디고 / ::after 앰버, blur 96px) |
| `.band-fade-top` | Finantech식 섹션 상단 마스크 페이드 |

## 컴포넌트 변화

- **NavBar**: full-bleed 평평한 바 → **floating glass pill**(top-3, blur-xl, shadow)
- **버튼**: fg 반전 6px → 인디고 그라디언트 pill + 호버 글로우/리프트
- **카드(.glass)**: 다크에서 반투명 + `backdrop-blur(12px)` 글라스
- **필드**: 포커스 시 인디고 3px 링
- **eyebrow**: 중립 → 인디고 틴트 pill

## 마이그레이션 노트

- 클래스명(`glass`, `btn-accent`, `field`, `lift`…)은 불변 — 페이지 코드 수정 없이 스킨만 교체됐다.
- 골드를 쓰던 곳 중 상호작용 요소는 accent(인디고)로 옮기고, gilt는 식별·장식 포인트로만 남긴다.
- 후속 작업: 데이터 화면(청약·시뮬레이터·주식) KPI 카드 리패키징, 차트 팔레트 정합화.
