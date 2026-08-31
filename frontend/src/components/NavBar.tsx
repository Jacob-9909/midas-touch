"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import {
  ShieldChevron,
  Moon,
  Sun,
  List,
  X,
  TextAa,
  MagnifyingGlass,
  ChatCircleText,
  ShieldWarning,
  Coins,
  Calculator,
  User,
  ChartLineUp,
  ShareNetwork,
  Scroll,
  ArrowRight,
} from "@phosphor-icons/react";
import { useTheme } from "@/lib/theme";
import { useAccessibility } from "@/lib/accessibility";
import CommandPalette from "./CommandPalette";

// 코어 여정은 사기검증(챗·보안) → 세법·근거(그래프) → 청약·자금(청약·시뮬·내정보).
// 그래프는 챗 graph_rag 근거의 시각 백엔드라 부가가 아니라 코어로 앞세운다.
// 나머지(세율·주식)는 부가 기능이라 "engine"으로 구분선 뒤에 배치하고, 보조·실험인 주식을 맨 뒤에 둔다.
const LINKS = [
  { href: "/chat", label: "챗봇", group: "core" },
  { href: "/security", label: "보안", group: "core" },
  { href: "/graph", label: "그래프", group: "core" },
  { href: "/cheongyak", label: "청약", group: "core" },
  { href: "/simulator", label: "시뮬레이터", group: "core" },
  { href: "/me", label: "내 정보", group: "core" },
  { href: "/tax-rates", label: "세율", group: "engine" },
  { href: "/stocks", label: "주식", group: "engine" },
] as const;

const MENU_GROUPS = [
  {
    category: "핵심 금융 안전망",
    categoryEn: "CORE SERVICES",
    items: [
      {
        href: "/chat",
        title: "AI 에이전트 챗봇",
        desc: "사기 검증 · 세법 결정론 계산 · 🛡 방어 증명",
        icon: ChatCircleText,
        badge: "상담",
        tone: "text-accent border-accent/40 bg-accent/10",
      },
      {
        href: "/security",
        title: "AI 보안 & 사기 검증",
        desc: "12종 프롬프트 공격 방어 및 피싱 문자 즉시 판정",
        icon: ShieldWarning,
        badge: "보안",
        tone: "text-gilt border-gilt/40 bg-gilt/10",
      },
      {
        href: "/cheongyak",
        title: "청약 공고 & 가점표",
        desc: "전국 실시간 분양 지도 및 84점 만점 자가진단",
        icon: Coins,
        badge: "청약",
        tone: "text-positive border-positive/40 bg-positive/10",
      },
      {
        href: "/simulator",
        title: "자금마련 시뮬레이터",
        desc: "청년도약계좌 vs 일반적금 복리 목표 달성 비교",
        icon: Calculator,
        badge: "시뮬",
        tone: "text-cyan-400 border-cyan-400/40 bg-cyan-400/10",
      },
      {
        href: "/me",
        title: "내 프로필 & 자산 설정",
        desc: "무주택 기간, 부양가족, 청약통장 기준 저장 (로컬 격리)",
        icon: User,
        badge: "설정",
        tone: "text-fg/80 border-line bg-surface/50",
      },
    ],
  },
  {
    category: "지식그래프 & 전문 분석 엔진",
    categoryEn: "KNOWLEDGE & ENGINE",
    items: [
      {
        href: "/graph",
        title: "금융 지식그래프 (GraphRAG)",
        desc: "챗봇 답변의 법령 조문 출처를 시각화하는 지식망",
        icon: ShareNetwork,
        badge: "근거",
        tone: "text-indigo-400 border-indigo-400/40 bg-indigo-400/10",
      },
      {
        href: "/tax-rates",
        title: "세율 갱신 콘솔",
        desc: "최신 세법 개정안 자동 인입 및 법령 조문 조회",
        icon: Scroll,
        badge: "세법",
        tone: "text-amber-400 border-amber-400/40 bg-amber-400/10",
      },
      {
        href: "/stocks",
        title: "주식 지표 & 자가 채점 루프",
        desc: "보조 지표 참고 + AI 예측 실현 수익률 사후 채점 공개",
        icon: ChartLineUp,
        badge: "실험",
        tone: "text-emerald-400 border-emerald-400/40 bg-emerald-400/10",
      },
    ],
  },
];

export default function NavBar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const { largeText, toggleLargeText } = useAccessibility();
  const [open, setOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandOpen((prev) => !prev);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-2.5 z-50 px-3 sm:px-5 mb-2 sm:mb-3">
      <nav className="mx-auto flex min-h-[54px] max-w-[1280px] w-full items-center justify-between gap-2.5 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_90%,transparent)] px-3.5 sm:px-4 py-1.5 shadow-sm shadow-black/5 dark:shadow-md dark:shadow-black/50 backdrop-blur-xl transition-all">
        {/* 좌측 브랜드 로고 */}
        <Link
          href="/"
          className="group mr-2 flex shrink-0 items-center gap-2.5 whitespace-nowrap pl-0.5 font-display transition-transform duration-150 active:scale-95"
        >
          <div className="flex h-7.5 w-7.5 shrink-0 items-center justify-center rounded-xl border border-accent/35 bg-accent/10 text-accent group-hover:border-accent group-hover:bg-accent/15 transition-colors">
            <ShieldChevron weight="fill" size={18} />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[15px] sm:text-[16px] font-extrabold tracking-tight text-fg group-hover:text-accent transition-colors">
              Midas Touch
            </span>
            <span className="hidden items-center gap-1 rounded-full border border-positive/30 bg-positive/10 px-2 py-0.5 font-mono-spec text-[10px] font-bold text-positive md:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-positive animate-pulse" />
              AI GUARD
            </span>
          </div>
        </Link>

        {/* 데스크톱 메뉴 링크 (중앙) */}
        <div className="hidden shrink-0 items-center gap-1 xl:flex">
          {LINKS.map((l, i) => (
            <span key={l.href} className="flex items-center">
              {i > 0 && LINKS[i - 1].group !== l.group && (
                <span aria-hidden className="mx-2 h-4 w-px bg-line/70" />
              )}
              <Link
                href={l.href}
                className={`whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-semibold transition-all duration-150 ${
                  isActive(l.href)
                    ? "!bg-accent !text-white !border-accent shadow-sm font-bold"
                    : "text-muted hover:text-fg hover:bg-surface/80 border border-transparent"
                } ${l.group === "engine" && !isActive(l.href) ? "opacity-75" : ""}`}
              >
                {l.label}
              </Link>
            </span>
          ))}
        </div>

        {/* 우측 컨트롤 영역 */}
        <div className="relative ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          {/* 빠른 실행 검색바 (⌘K) */}
          <button
            onClick={() => setCommandOpen(true)}
            aria-label="빠른 실행 및 검색 (단축키 ⌘K)"
            title="빠른 검색 (⌘K)"
            className="flex items-center gap-2 rounded-full border border-line bg-surface/60 hover:bg-surface hover:border-accent/40 px-3 py-1.5 text-xs text-muted hover:text-fg transition-all h-[38px]"
          >
            <MagnifyingGlass size={15} className="text-accent" weight="bold" />
            <span className="hidden sm:inline font-medium text-muted">검색</span>
            <kbd className="inline-flex items-center rounded border border-line bg-surface px-1.5 py-0.5 font-mono-spec text-[10px] font-bold text-muted">
              ⌘K
            </kbd>
          </button>

          {/* 테마 토글 */}
          <button
            onClick={toggle}
            aria-label="테마 전환"
            className="btn-ghost btn-icon shrink-0 h-[38px] w-[38px] rounded-full border border-line/70 hover:border-line hover:bg-surface/80"
          >
            {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          {/* 큰 글씨 모드 토글 */}
          <button
            onClick={toggleLargeText}
            aria-pressed={largeText}
            aria-label="큰 글씨 모드"
            title={largeText ? "큰 글씨 모드 끄기" : "큰 글씨 모드 켜기"}
            className={`btn-ghost shrink-0 gap-1.5 rounded-full px-3 py-1.5 h-[38px] border border-line/70 hover:border-line hover:bg-surface/80 ${
              largeText ? "!border-accent/50 !bg-accent/15 !text-accent font-bold" : ""
            }`}
          >
            <TextAa weight={largeText ? "fill" : "regular"} size={16} />
            <span className="hidden 2xl:inline text-xs font-semibold">큰 글씨</span>
          </button>

          {/* 전체 메뉴 햄버거 버튼 */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="전체 메뉴 열기"
            aria-expanded={open}
            title="전체 메뉴"
            className={`btn-ghost btn-icon shrink-0 h-[38px] w-[38px] rounded-full border transition-all ${
              open
                ? "!border-accent !bg-accent/20 !text-accent"
                : "border-line/70 hover:border-line hover:bg-surface/80 text-fg"
            }`}
          >
            {open ? <X size={18} /> : <List size={18} />}
          </button>
        </div>
      </nav>

      {/* ── 전체 메뉴 허브 모달 (고가독성 모던 메가 드로어) ── */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-20 px-4 pb-6 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black/65 backdrop-blur-md transition-opacity"
            onClick={() => setOpen(false)}
          />
          <div className="relative z-10 w-full max-w-4xl rounded-2xl border border-line bg-[var(--ink-1)] p-6 sm:p-7 shadow-[var(--shadow-2)] overflow-hidden animate-rise">
            {/* 상단 타이틀 바 */}
            <div className="flex items-center justify-between border-b border-line pb-4">
              <div className="flex items-center gap-2.5">
                <ShieldChevron weight="fill" className="text-accent" size={22} />
                <div>
                  <span className="font-display text-lg font-bold text-fg block leading-tight">
                    Midas Touch 전체 서비스
                  </span>
                  <span className="font-mono-spec text-xs text-muted">
                    신뢰 가능한 4대 금융 안전망 & 분석 엔진
                  </span>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="btn-ghost btn-icon h-9 w-9 rounded-full border border-line/60 hover:border-line text-muted hover:text-fg"
                aria-label="메뉴 닫기"
              >
                <X size={18} />
              </button>
            </div>

            {/* 2단 카테고리 그리드 */}
            <div className="mt-6 grid gap-6 md:grid-cols-2">
              {MENU_GROUPS.map((group) => (
                <div key={group.category} className="space-y-3">
                  <div className="flex items-center justify-between px-1">
                    <span className="font-display text-sm font-bold text-fg">
                      {group.category}
                    </span>
                    <span className="font-mono-spec text-[10px] font-semibold tracking-wider text-accent">
                      {group.categoryEn}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {group.items.map((item) => {
                      const Icon = item.icon;
                      const active = isActive(item.href);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setOpen(false)}
                          className={`group flex items-center justify-between gap-3.5 rounded-xl border p-3.5 transition-all duration-150 ${
                            active
                              ? "border-accent/50 bg-accent/15 text-fg shadow-sm"
                              : "border-line bg-[var(--ink-2)]/60 hover:bg-[var(--ink-2)] hover:border-accent/40 text-fg"
                          }`}
                        >
                          <div className="flex items-center gap-3.5 min-w-0">
                            <div
                              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition-colors ${
                                active
                                  ? "border-accent/50 bg-accent text-white"
                                  : "border-line bg-surface text-fg/80 group-hover:border-accent/40 group-hover:text-accent"
                              }`}
                            >
                              <Icon size={20} weight={active ? "fill" : "duotone"} />
                            </div>
                            <div className="min-w-0">
                              <div className="text-[14px] font-bold text-fg group-hover:text-accent transition-colors">
                                {item.title}
                              </div>
                              <div className="text-xs text-muted/90 leading-snug mt-0.5 line-clamp-1">
                                {item.desc}
                              </div>
                            </div>
                          </div>

                          <div className="shrink-0 flex items-center gap-2">
                            <span
                              className={`rounded-full border px-2 py-0.5 font-mono-spec text-[10px] font-bold ${item.tone}`}
                            >
                              {item.badge}
                            </span>
                            <ArrowRight
                              size={14}
                              className="text-muted group-hover:text-accent group-hover:translate-x-0.5 transition-transform shrink-0"
                            />
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            {/* 하단 퀵 액션 & 단축키 바 */}
            <div className="mt-6 pt-4 border-t border-line/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-muted">
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-fg/80">단축키 안내:</span>
                <span>어디서나</span>
                <kbd className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono-spec text-[10px] font-bold text-fg">
                  ⌘K
                </kbd>
                <span>를 누르면 빠른 검색창이 열립니다.</span>
              </div>
              <div className="flex items-center gap-3">
                <Link
                  href="/security"
                  onClick={() => setOpen(false)}
                  className="text-accent hover:underline font-semibold"
                >
                  🛡️ 5겹 보안 검증장 바로가기 →
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 글로벌 커맨드 팔레트 */}
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} />
    </header>
  );
}
