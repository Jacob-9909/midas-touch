"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ShieldChevron,
  UserCircle,
  Moon,
  Sun,
  List,
  X,
} from "@phosphor-icons/react";
import { useSelectedUser } from "@/lib/user-context";
import { useTheme } from "@/lib/theme";

// 단일 여정을 앞세운다: "core" 핵심 여정(내 현황 → 또래 벤치마킹 → 상담 → 종목 확인)을
// 먼저 두고, "engine" 부가·데모(청약·지식그래프·파인튜닝)는 구분선 뒤로 강등해 초점을 준다.
const LINKS = [
  { href: "/", label: "대시보드", group: "core" },
  { href: "/chat", label: "에이전트 챗봇", group: "core" },
  { href: "/stocks", label: "주식분석", group: "core" },
  { href: "/cheongyak", label: "청약", group: "engine" },
  { href: "/graph", label: "지식그래프", group: "engine" },
  { href: "/finetune", label: "파인튜닝셋", group: "engine" },
] as const;

export default function NavBar() {
  const pathname = usePathname();
  const { selected } = useSelectedUser();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-3 z-50 mx-auto mt-2 w-[calc(100%-1.5rem)] max-w-6xl rounded-lg border border-line bg-[var(--ink-1)]/90 backdrop-blur-md shadow-md sm:top-4 sm:mt-3">
      <nav className="flex h-14 items-center gap-1 px-4 sm:px-5">
        <Link
          href="/"
          className="mr-5 flex items-center gap-2.5 font-display text-xl font-normal tracking-tight"
        >
          <ShieldChevron weight="fill" className="text-accent" size={20} />
          <span className="text-gradient-accent font-semibold tracking-wide">Midas Touch</span>
          <span className="hidden font-mono-spec text-[9px] uppercase tracking-widest text-muted border border-line/60 px-1.5 py-0.5 rounded sm:inline-block">
            Console
          </span>
        </Link>

        {/* 데스크톱 링크 — Swiss Hairline Divider & Monospace Active State */}
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l, i) => (
            <span key={l.href} className="flex items-center">
              {i > 0 && LINKS[i - 1].group !== l.group && (
                <span aria-hidden className="mx-2 h-3.5 w-px bg-line/60" />
              )}
              <Link
                href={l.href}
                className={`rounded px-3 py-1 text-xs font-medium transition-all duration-150 ${
                  isActive(l.href)
                    ? "bg-accent/15 text-accent border border-accent/40 font-semibold"
                    : "text-muted hover:text-fg hover:bg-surface"
                } ${l.group === "engine" && !isActive(l.href) ? "opacity-60" : ""}`}
              >
                {l.label}
              </Link>
            </span>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2.5">
          <span className="hidden font-mono-spec text-xs sm:inline">
            {selected ? (
              <span className="flex items-center gap-1.5 whitespace-nowrap rounded border border-line px-2.5 py-1 text-accent">
                <UserCircle weight="fill" size={15} className="shrink-0" />
                {selected.label}
              </span>
            ) : (
              <span className="text-muted/60 text-xs">유저 미선택</span>
            )}
          </span>

          {/* 테마 토글 */}
          <button
            onClick={toggle}
            aria-label="테마 전환"
            className="btn-ghost flex h-8 w-8 items-center justify-center rounded border border-line"
          >
            {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          {/* 모바일 햄버거 */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="메뉴"
            aria-expanded={open}
            className="btn-ghost flex h-8 w-8 items-center justify-center rounded border border-line md:hidden"
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
