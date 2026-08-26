"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ShieldChevron,
  Moon,
  Sun,
  List,
  X,
} from "@phosphor-icons/react";
import { useTheme } from "@/lib/theme";

// 헤드라인은 청약(상담 + 목록조회 + 시뮬레이터 + 내 정보)이라 "core"로 앞세우고,
// 나머지(주식분석·지식그래프)는 부가 기능이라 "engine"으로 구분선 뒤에 강등한다.
const LINKS = [
  { href: "/chat", label: "에이전트 챗봇", group: "core" },
  { href: "/cheongyak", label: "청약", group: "core" },
  { href: "/simulator", label: "자금마련 시뮬레이터", group: "core" },
  { href: "/me", label: "내 정보", group: "core" },
  // "/" 는 대시보드가 아니라 랜딩이 됐고(거시지표·히트맵·페르소나표 제거),
  // 좌측 Midas Touch 로고가 이미 "/" 로 가므로 중복 항목을 뺐다.
  { href: "/stocks", label: "주식분석", group: "engine" },
  { href: "/graph", label: "지식그래프", group: "engine" },
] as const;


export default function NavBar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    // Neon Ledger §Components: 네비는 캔버스에서 한 단 떠 있는 글래스 필.
    // 상단에 떠 있고 좌우 여백을 두며 blur+헤어라인+부유 섀도로 본문과 나눈다.
    <header className="sticky top-3 z-50 px-3 sm:px-5">
      <nav className="mx-auto flex h-14 max-w-[1200px] items-center gap-1 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_78%,transparent)] px-3 shadow-[var(--shadow-1)] backdrop-blur-xl">
        <Link
          href="/"
          className="mr-4 flex shrink-0 items-center gap-2.5 whitespace-nowrap pl-2 font-display text-lg tracking-tight"
        >
          {/* 브랜드 스탬프 — 골드 글리프는 Midas 도장으로 유지 */}
          <ShieldChevron weight="fill" className="text-gilt" size={20} />
          <span className="font-semibold tracking-tight">Midas Touch</span>
          <span className="hidden rounded-full border border-line/60 px-1.5 py-0.5 font-mono-spec text-[9px] uppercase tracking-widest text-muted sm:inline-block">
            Console
          </span>
        </Link>

        {/* 데스크톱 링크 — Swiss Hairline Divider & Sleek Pill Navigation */}
        <div className="hidden shrink-0 items-center gap-1 md:flex">
          {LINKS.map((l, i) => (
            <span key={l.href} className="flex items-center">
              {i > 0 && LINKS[i - 1].group !== l.group && (
                <span aria-hidden className="mx-2.5 h-3.5 w-px bg-line/50" />
              )}
              <Link
                href={l.href}
                className={`whitespace-nowrap rounded-full px-3.5 py-1 text-xs font-mono-spec transition-all duration-200 ${
                  isActive(l.href)
                    ? "bg-accent/15 text-accent border border-accent/40 font-semibold"
                    : "text-muted hover:text-fg hover:bg-surface/60 border border-transparent"
                } ${l.group === "engine" && !isActive(l.href) ? "opacity-60" : ""}`}
              >
                {l.label}
              </Link>
            </span>
          ))}
        </div>

        {/* 줄어드는 쪽은 항상 이 그룹이어야 한다
            (min-w-0 없이는 flex가 로고·링크까지 압축해 글자가 두 줄로 깨진다) */}
        <div className="relative ml-auto flex min-w-0 items-center gap-2.5">
          {/* 테마 토글 */}
          <button
            onClick={toggle}
            aria-label="테마 전환"
            className="btn-ghost btn-icon shrink-0"
          >
            {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          {/* 모바일 햄버거 */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="메뉴"
            aria-expanded={open}
            className="btn-ghost btn-icon shrink-0 md:hidden"
          >
            {open ? <X size={16} /> : <List size={16} />}
          </button>
        </div>
      </nav>

      {/* 모바일 메뉴 */}
      {open && (
        <div className="mx-auto mt-2 max-w-[1200px] rounded-2xl border border-line bg-[color-mix(in_srgb,var(--ink-1)_92%,transparent)] px-3 py-2 shadow-[var(--shadow-2)] backdrop-blur-xl md:hidden">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`block rounded-full px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive(l.href)
                  ? "bg-accent/15 text-accent font-semibold"
                  : "text-muted hover:text-fg"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}
