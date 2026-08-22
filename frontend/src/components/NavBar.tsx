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
    // 문서 §Components: 네비는 캔버스에 밀착된 평평한 바다. 유리·굴절·그림자를 걷어내고
    // 아래쪽 1px 헤어라인으로만 본문과 나눈다(full-bleed).
    <header className="sticky top-0 z-50 border-b border-line bg-[var(--ink)]">
      <nav className="mx-auto flex h-16 max-w-[1200px] items-center gap-1 px-6">
        <Link
          href="/"
          className="mr-5 flex shrink-0 items-center gap-2.5 whitespace-nowrap font-display text-xl font-normal tracking-tight"
        >
          {/* 브랜드 스탬프 — 문서 §Colors에서 어센트는 '드물게 찍는 도장'이다.
              발광·흐르는 하이라이트는 걷어내고 글리프에만 골드를 남긴다. */}
          <ShieldChevron weight="fill" className="text-accent" size={20} />
          <span className="font-semibold tracking-tight">Midas Touch</span>
          <span className="hidden font-mono-spec text-[9px] uppercase tracking-widest text-muted border border-line/60 px-1.5 py-0.5 rounded sm:inline-block">
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
        <div className="border-t border-line px-4 py-2 md:hidden bg-[var(--ink-1)]">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`block rounded px-3 py-2 text-xs font-medium transition-colors ${
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
