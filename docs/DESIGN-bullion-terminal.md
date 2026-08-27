# Midas Touch Design System — "Neon Ledger"

> version: 2.0 (2026-08)
> 이전 체계(Bullion Terminal v1.0 / Revolut)를 발전적으로 계승·통합한다.
> 구현 단일 출처는 `frontend/src/app/globals.css`다. 이 문서는 그 해설 및 엔터프라이즈 UI 가이드라인이다.

## 디자인 정체성: Neon Ledger (네온 렛저)

이 앱은 **검증 가능한 AI 금융 보안 비서 및 데이터 콘솔**이다.
Linear / Stripe / Bloomberg 계열의 정제된 금융 콘솔 인터페이스에 **일렉트릭 인디고(`--accent`)**를 액션·링크 주 색상으로, **앰버 골드(`--gilt`)**를 신뢰·목표·증명 도장으로 활용하여 전문성과 미래지향성을 조화시킨다.

---

## 1. 팔레트 및 명도 대비 (WCAG 2.1 AA 준수)

### 다크 테마 (기본 콘솔: `html.dark`)

| 토큰 | 값 | 용도 / 설명 |
|---|---|---|
| `--ink` | `#0a0a10` | 캔버스 base. 눈 피로를 줄이는 딥 옵시디언 |
| `--ink-2` | `#11111a` | 인셋, 입력 필드(`.field`), 트랙 배경 |
| `--ink-1` | `#15151f` | 카드 표면(`.glass`, `.surface-raised`) |
| `--surface` | `#1d1d2a` | Hover lift, 인터랙티브 서브 배경 |
| `--line` | `#262637` | 1px 헤어라인 테두리 |
| `--fg` | `#eceef4` | 주요 본문 텍스트 (명도 대비 14.6:1, AAA) |
| `--muted` | `#9094a8` | 보조 텍스트 (명도 대비 5.4:1, AA) |
| `--stone` | `#6d7186` | 캡션 및 비활성 메타 (대비 3.4:1) |
| `--accent` | `#6c5cff` | 일렉트릭 인디고 (주요 액션, 포커스 링, 프라이머리 버튼) |
| `--gilt` | `#faad13` | 앰버 골드 (목표 달성, 방어 증명 도장, 스텝 인디케이터) |

### 라이트 테마 (보조 콘솔: `html.light`)

> [!IMPORTANT]
> 라이트 테마에서는 흰색/크림 캔버스 위 가독성을 위해 **고대비 조색**된 전용 토큰을 사용합니다.

| 토큰 | 값 | 용도 / 명도 대비 (WCAG AA) |
|---|---|---|
| `--ink` | `#f6f7fb` | 쿨 그레이 캔버스 base |
| `--ink-2` | `#eef0f6` | 인셋·입력 배경 |
| `--ink-1` | `#ffffff` | 카드 및 패널 표면 |
| `--surface` | `#eceef5` | Hover 및 서브 영역 |
| `--line` | `#dfe2ec` | 헤어라인 테두리 |
| `--fg` | `#191b2a` | 주요 본문 (대비 15.6:1, AAA) |
| `--muted` | `#5d6172` | 보조 텍스트 (대비 6.2:1, AA) |
| `--stone` | `#63677a` | 보조 모노 라벨 (대비 5.5:1, AA) |
| `--accent` | `#5546e8` | 다크 인디고 (대비 6.1:1, AA) |
| `--gilt` | `#8a5800` | 딥 앰버 (대비 6.1:1, AA) — 흰색 위 시인성 보장 |

### 시맨틱 상태 색상

| 상태 | 토큰 | 라이트 | 다크 | 용도 |
|---|---|---|---|---|
| 성공 / 상승 | `--positive` | `#11845b` | `#05c168` | 수익, 자격 충족, 방어 성공 |
| 경고 / 주의 | `--warning` | `#b35600` | `#ff8a3d` | 마감 임박, 요건 미달 주의 |
| 에러 / 위험 | `--negative` | `#dc2f52` | `#ff4d67` | 피싱 사기, 손절, 입력 오류 |

---

## 2. 타이포그래피 규칙

- **본문 / UI**: Inter(영문) + Pretendard Variable(한글)
- **수치 / 금융 지표**: Geist Mono + `tabular-nums lining-nums` (`.font-mono-spec`)
  - 모든 금액, 퍼센티지, 수량 열은 표에서 **우측 정렬(`text-right`)** 처리.
- **디스플레이 타이틀**: Space Grotesk (`.font-display`) — weight 600, line-height 1.15
- **글자 크기 계층**:
  - `text-[10px]` / `text-[11px]`: 뱃지, 메타데이터, 타임스탬프
  - `text-xs` (12px): 폼 라벨, 보조 설명
  - `text-sm` (14px): 기본 본문 및 테이블 셀
  - `text-base` / `text-lg` (16~18px): 카드 타이틀
  - `text-xl` ~ `text-3xl`: 섹션 타이틀 및 핵심 지표 KPI

---

## 3. Radius & Elevation

| 토큰 | 값 | 적용 컴포넌트 |
|---|---|---|
| `--r-sm` | 12px | 작은 뱃지, 태그 |
| `--r-md` | 14px | 토스트, 툴팁, 드롭다운 메뉴 |
| `--r-lg` | 20px | 대시보드 카드, 그리드 타일 |
| `--r-xl` | 24px | 상세 모달 패널, 바텀 시트 |
| `--r-pill` | 9999px | 버튼(`.btn-accent`, `.btn-ghost`), 탭 컨테이너, 상태 캡슐 |

### 깊이와 섀도 (Elevation)
1. **표면 명도 사다리**: `var(--ink)` (캔버스) → `var(--ink-2)` (인셋) → `var(--ink-1)` (카드) → `var(--surface)` (호버)
2. **`--shadow-1`**: 기본 카드 및 네비게이션 바 부유 섀도
3. **`--shadow-2`**: 모달, 토스트, 드롭다운 오버레이 섀도
4. **`--glow`**: 인디고 액션 포커스 링 및 주요 액센트 발광

---

## 4. 인터랙션 & 모션 원칙 (Emil Kowalski & Apple Guidelines)

1. **마이크로 피드백**: 모든 버튼은 클릭 시 `:active`에서 `transform: scale(0.97)`의 물리적 눌림 반응을 제공.
2. **스프링 물리 보간**: `TiltCard` 및 드래그 요소는 마우스 좌표 직접 바인딩 대신 `motion/react`의 `useSpring(damping: 22, stiffness: 240)`을 사용해 자연스러운 관성 유지.
3. **`@starting-style` 진입**: 모달, 드롭다운, 토스트 등 동적 렌더링 요소는 CSS `@starting-style`(`starting:`)을 사용해 매끄러운 진입 트랜지션 보장.
4. **`prefers-reduced-motion`**: 모션 감소 요청 시 스크램블, 3D 틸트, 카운트업 애니메이션을 즉시 완료 상태로 렌더링.

---

## 5. 접근성(A11y) 표준

- **키보드 탐색**: `SegmentedTabs`는 `ArrowLeft/Right`, `Home`, `End` 키를 지원하며, `TickerAutocomplete`는 WAI-ARIA Combobox 표준(`role="combobox"`, `role="listbox"`, `aria-activedescendant`)을 준수.
- **포커스 트랩**: `DetailModal`은 열림 시 배경 요소로 포커스 이탈을 차단하고 닫힐 때 원래 트리거로 포커스를 복원.
- **고령층 지원**: 상단 내비게이션 바의 **큰 글씨 모드**(`.a11y-large-text`)를 통해 폰트 크기 및 터치 타깃을 120% 확대 제공.
