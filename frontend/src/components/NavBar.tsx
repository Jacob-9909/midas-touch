"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Sparkle,
  UserCircle,
  Moon,
  Sun,
  List,
  X,
} from "@phosphor-icons/react";
import { useSelectedUser } from "@/lib/user-context";
import { useTheme } from "@/lib/theme";

const LINKS = [
  { href: "/", label: "대시보드" },
  { href: "/chat", label: "에이전트 챗봇" },
  { href: "/finetune", label: "파인튜닝셋" },
  { href: "/graph", label: "지식그래프" },
];

export default function NavBar() {
  const pathname = usePathname();
  const { selected } = useSelectedUser();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-[var(--ink)]/70 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-6xl items-center gap-1 px-4 sm:px-6">
        <Link
          href="/"
          className="mr-3 flex items-center gap-2 font-display text-lg font-semibold"
        >
          <Sparkle weight="fill" className="text-gold" size={20} />
          <span className="text-gradient-gold">Midas Touch</span>
        </Link>

        {/* 데스크톱 링크 (단일 라인 유지) */}
        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-lg px-3 py-1.5 text-sm transition ${
                isActive(l.href)
                  ? "bg-[color-mix(in_srgb,var(--gold)_14%,transparent)] text-gold"
                  : "text-muted hover:text-fg"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-sm sm:inline">
            {selected ? (
              <span className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-gold">
                <UserCircle weight="fill" size={16} />
                {selected.label}
              </span>
            ) : (
              <span className="text-muted">유저 미선택</span>
            )}
          </span>

          {/* 테마 토글 */}
          <button
            onClick={toggle}
            aria-label="테마 전환"
            className="btn-ghost flex h-9 w-9 items-center justify-center"
          >
            {theme === "dark" ? <Moon size={18} /> : <Sun size={18} />}
          </button>

          {/* 모바일 햄버거 */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="메뉴"
            aria-expanded={open}
            className="btn-ghost flex h-9 w-9 items-center justify-center md:hidden"
          >
            {open ? <X size={18} /> : <List size={18} />}
          </button>
        </div>
      </nav>

      {/* 모바일 메뉴 */}
      {open && (
        <div className="border-t border-line px-4 py-2 md:hidden">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`block rounded-lg px-3 py-2 text-sm ${
                isActive(l.href) ? "text-gold" : "text-muted"
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
