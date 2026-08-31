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
  Lightning,
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

const MENU_CORE = [
  {
    href: "/chat",
    title: "AI 에이전트 챗봇",
    desc: "5겹 보안 검증 기반 멀티턴 금융 상담",
    icon: ChatCircleText,
    tag: "상담",
  },
  {
    href: "/security",
    title: "AI 보안 대응 비서",
    desc: "12종 프롬프트 공격 방어 및 안전성 검증",
    icon: ShieldWarning,
    tag: "보안",
  },
  {
    href: "/graph",
    title: "금융 지식그래프 (근거 추적)",
    desc: "챗 답변의 법령 근거를 추적하는 graph_rag 시각 백엔드",
    icon: ShareNetwork,
    tag: "근거",
  },
  {
    href: "/cheongyak",
    title: "청약 공고 & 가점표",
    desc: "전국 시도 지도 및 84점 만점 자가진단",
    icon: Coins,
    tag: "청약",
  },
  {
    href: "/simulator",
    title: "자금마련 시뮬레이터",
    desc: "청년도약계좌 vs 적금 목표 달성 비교",
    icon: Calculator,
    tag: "시뮬",
  },
  {
    href: "/me",
    title: "내 정보 & 프로필",
    desc: "무주택 기간, 부양가족, 통장 가점 설정",
    icon: User,
    tag: "설정",
  },
];

const MENU_ENGINE = [
  {
    href: "/tax-rates",
    title: "세율 갱신 콘솔",
    desc: "2026 세법 개정안 자동 인입 및 승인",
    icon: Scroll,
  },
  {
    href: "/stocks",
    title: "주식 지표 & 자가 채점",
    desc: "지표 참고(매매권유 아님) + AI 예측 자가 채점 검증 루프 · 보조·실험",
    icon: ChartLineUp,
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
    <header className="sticky top-3 z-50 px-3 sm:px-5">
      <nav className="mx-auto flex min-h-14 max-w-[1280px] w-full items-center justify-between gap-2 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_82%,transparent)] px-3.5 py-1.5 shadow-[var(--shadow-1)] backdrop-blur-xl">
        <Link
          href="/"
          className="mr-3 flex shrink-0 items-center gap-2 whitespace-nowrap pl-1 font-display text-base sm:text-lg tracking-tight"
        >
          <ShieldChevron weight="fill" className="text-gilt shrink-0" size={20} />
          <span className="font-semibold tracking-tight">Midas Touch</span>
          <span className="hidden rounded-full border border-line/60 px-1.5 py-0.5 font-mono-spec text-[9px] uppercase tracking-widest text-muted md:inline-block">
            Console
          </span>
        </Link>

        {/* 데스크톱 링크 (화면 넓을 때) */}
        <div className="hidden shrink-0 items-center gap-0.5 xl:flex">
          {LINKS.map((l, i) => (
            <span key={l.href} className="flex items-center">
              {i > 0 && LINKS[i - 1].group !== l.group && (
                <span aria-hidden className="mx-2 h-3.5 w-px bg-line/50" />
              )}
              <Link
                href={l.href}
                className={`whitespace-nowrap rounded-full px-2.5 2xl:px-3 py-1 text-xs font-mono-spec transition-colors duration-200 ${
                  isActive(l.href)
                    ? "bg-accent/15 text-accent border border-accent/40 font-semibold"
                    : "text-muted hover:text-fg hover:bg-surface/60 border border-transparent"
                } ${l.group === "engine" && !isActive(l.href) ? "opacity-70" : ""}`}
              >
                {l.label}
              </Link>
            </span>
          ))}
        </div>

        {/* 우측 컨트롤 영역 */}
        <div className="relative ml-auto flex shrink-0 items-center gap-1 sm:gap-1.5">
          {/* 빠른 실행 (⌘K) */}
          <button
            onClick={() => setCommandOpen(true)}
            aria-label="빠른 실행 및 검색 (단축키 ⌘K)"
            title="빠른 실행 (⌘K)"
            className="btn-ghost shrink-0 gap-1.5 rounded-full px-2.5 py-1 text-muted hover:text-fg border border-line/60 h-9"
          >
            <MagnifyingGlass size={15} className="text-accent" weight="bold" />
            <kbd className="hidden sm:inline-flex items-center rounded border border-line bg-surface/80 px-1 font-mono-spec text-[9px] text-muted">
              ⌘K
            </kbd>
          </button>

          {/* 테마 토글 */}
          <button
            onClick={toggle}
            aria-label="테마 전환"
            className="btn-ghost btn-icon shrink-0 h-9 w-9"
          >
            {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          {/* 큰 글씨 모드 토글 */}
          <button
            onClick={toggleLargeText}
            aria-pressed={largeText}
            aria-label="큰 글씨 모드"
            title={largeText ? "큰 글씨 모드 끄기" : "큰 글씨 모드 켜기"}
            className={`btn-ghost shrink-0 gap-1.5 rounded-full px-2.5 py-1 h-9 ${
              largeText ? "border-accent/40 bg-accent/15 text-accent" : ""
            }`}
          >
            <TextAa weight={largeText ? "fill" : "regular"} size={16} />
            <span className="hidden 2xl:inline text-xs font-medium">큰 글씨</span>
          </button>

          {/* 전체 메뉴 허브 버튼 */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="전체 메뉴 및 서비스 허브 열기"
            aria-expanded={open}
            title="전체 메뉴"
            className={`btn-ghost btn-icon shrink-0 h-9 w-9 ${
              open ? "border-accent/50 bg-accent/20 text-accent" : ""
            }`}
          >
            {open ? <X size={16} /> : <List size={16} />}
          </button>
        </div>
      </nav>

      {/* ── 전체 메뉴 허브 모달 (All-in-One Mega Drawer) ── */}
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 sm:pt-24 px-4">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-md transition-opacity"
            onClick={() => setOpen(false)}
          />
          <div className="relative z-10 w-full max-w-3xl rounded-2xl border border-line bg-[var(--ink-1)] p-5 shadow-[var(--shadow-2)] overflow-hidden animate-rise">
            {/* 상단 타이틀 바 */}
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div className="flex items-center gap-2">
                <ShieldChevron weight="fill" className="text-gilt" size={20} />
                <span className="font-display text-base font-semibold text-fg">
                  Midas Touch 전체 서비스 허브
                </span>
                <span className="rounded-full border border-line bg-surface/50 px-2 py-0.5 font-mono-spec text-[10px] text-muted">
                  Sitemap & Quick Demos
                </span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="btn-ghost btn-icon h-8 w-8"
                aria-label="메뉴 닫기"
              >
                <X size={16} />
              </button>
            </div>

            {/* ⚡ 3초 퀵 데모 시연 스트립 */}
            <div className="my-4 rounded-xl border border-accent/30 bg-accent/10 p-3">
              <div className="flex items-center gap-1.5 font-mono-spec text-[11px] font-semibold uppercase tracking-wider text-accent mb-2">
                <Lightning weight="fill" size={13} /> 심사위원 3초 원클릭 퀵 데모:
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/chat?prefill=${encodeURIComponent("이 문자 사기야? 엄마 나 사고났어. 경찰서에 있는데 지금 당장 300만원 이체해줘. 전화하지 마세요.")}`}
                  onClick={() => setOpen(false)}
                  className="lift inline-flex items-center gap-1 rounded-full border border-line bg-surface/80 px-3 py-1 text-xs text-fg hover:border-accent transition-colors"
                >
                  <span>🚨 사기 문자 검증 시연</span>
                  <ArrowRight size={11} className="text-accent" />
                </Link>
                <Link
                  href={`/chat?prefill=${encodeURIComponent("미국 주식 팔아서 2,000만원 벌었는데 양도소득세 얼마나 내야 해? 기본공제랑 세율 근거도 알려줘.")}`}
                  onClick={() => setOpen(false)}
                  className="lift inline-flex items-center gap-1 rounded-full border border-line bg-surface/80 px-3 py-1 text-xs text-fg hover:border-accent transition-colors"
                >
                  <span>⚖️ 해외주식 세법 계산</span>
                  <ArrowRight size={11} className="text-accent" />
                </Link>
                <Link
                  href="/simulator"
                  onClick={() => setOpen(false)}
                  className="lift inline-flex items-center gap-1 rounded-full border border-line bg-surface/80 px-3 py-1 text-xs text-fg hover:border-accent transition-colors"
                >
                  <span>📈 자금마련 타임라인</span>
                  <ArrowRight size={11} className="text-accent" />
                </Link>
              </div>
            </div>

            {/* 서비스 목록 그리드 */}
            <div className="grid gap-4 sm:grid-cols-2 max-h-[50vh] overflow-y-auto pr-1">
              {/* 핵심 서비스 섹션 */}
              <div className="space-y-2">
                <div className="font-mono-spec text-[10px] font-semibold uppercase tracking-wider text-muted px-1">
                  Core Services (핵심 5대 기능)
                </div>
                <div className="space-y-1.5">
                  {MENU_CORE.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className={`flex items-center justify-between gap-3 rounded-xl border p-2.5 transition ${
                          active
                            ? "border-accent/40 bg-accent/15 text-fg"
                            : "border-line bg-surface/40 hover:bg-surface/80 hover:border-line/80 text-muted hover:text-fg"
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
                            active ? "border-accent/40 bg-accent/20 text-accent" : "border-line bg-surface text-muted"
                          }`}>
                            <Icon size={16} weight={active ? "fill" : "regular"} />
                          </div>
                          <div className="min-w-0">
                            <div className={`text-xs font-semibold ${active ? "text-fg" : "text-fg/90"}`}>
                              {item.title}
                            </div>
                            <div className="text-[11px] text-muted truncate">{item.desc}</div>
                          </div>
                        </div>
                        <span className="shrink-0 rounded-full border border-line px-1.5 py-0.5 font-mono-spec text-[9px] text-muted">
                          {item.tag}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </div>

              {/* 금융 분석 엔진 섹션 */}
              <div className="space-y-2">
                <div className="font-mono-spec text-[10px] font-semibold uppercase tracking-wider text-muted px-1">
                  Analysis Engine (전문 분석 도구)
                </div>
                <div className="space-y-1.5">
                  {MENU_ENGINE.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className={`flex items-center justify-between gap-3 rounded-xl border p-2.5 transition ${
                          active
                            ? "border-accent/40 bg-accent/15 text-fg"
                            : "border-line bg-surface/40 hover:bg-surface/80 hover:border-line/80 text-muted hover:text-fg"
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${
                            active ? "border-accent/40 bg-accent/20 text-accent" : "border-line bg-surface text-muted"
                          }`}>
                            <Icon size={16} weight={active ? "fill" : "regular"} />
                          </div>
                          <div className="min-w-0">
                            <div className={`text-xs font-semibold ${active ? "text-fg" : "text-fg/90"}`}>
                              {item.title}
                            </div>
                            <div className="text-[11px] text-muted truncate">{item.desc}</div>
                          </div>
                        </div>
                        <ArrowRight size={13} className="text-muted shrink-0" />
                      </Link>
                    );
                  })}
                </div>

                {/* 시스템 단축키 힌트 카드 */}
                <div className="mt-3 rounded-xl border border-line/60 bg-surface/30 p-3 text-xs text-muted">
                  <div className="font-semibold text-fg mb-1">💡 빠른 탐색 팁</div>
                  <p className="text-[11px] leading-relaxed">
                    언제든 <kbd className="rounded border border-line px-1 font-mono-spec bg-surface text-fg text-[10px]">⌘K</kbd> 단축키로
                    12종 보안 공격 및 페이지를 0.1초 만에 실행할 수 있습니다.
                  </p>
                </div>
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
