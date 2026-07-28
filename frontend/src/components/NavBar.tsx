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
  { href: "/finetune", label: "AI지식·학습", group: "engine" },
] as const;

const SAMPLE_USERS = [
  { uuid: "5c1f632516b34e56a89b3672e11456cc", label: "44세 연구원 · 자산 1.2억", district: "경기-용인시" },
  { uuid: "319b99b4172b48ab98ebaa7dba449ac6", label: "63세 제조원 · 자산 1.2억", district: "경북-구미시" },
  { uuid: "19ebbdd30b6c4aabbdc2424dfee02b1a", label: "40세 조리사 · 자산 7,000만", district: "서울-서대문구" },
  { uuid: "c1df90a15fe34fc4929e4e9318026512", label: "43세 회계원 · 자산 7,500만", district: "세종-세종시" },
  { uuid: "1fa921721df6420aaa9aad5b42591563", label: "44세 개발자 · 자산 3.5억", district: "경기-김포시" },
];

export default function NavBar() {
  const pathname = usePathname();
  const { selected, setSelected } = useSelectedUser();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

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

        <div className="ml-auto flex items-center gap-2.5 relative">
          {/* 페르소나 유저 퀵 스위처 */}
          <div className="relative">
            <button
              onClick={() => setUserDropdownOpen((v) => !v)}
              className="flex items-center gap-1.5 whitespace-nowrap rounded border border-line px-2.5 py-1 text-xs text-accent hover:border-accent/60 transition bg-surface/40 font-mono-spec"
            >
              <UserCircle weight="fill" size={15} className="shrink-0" />
              <span className="font-medium truncate max-w-[150px]">
                {selected ? selected.label : "유저 선택"}
              </span>
              <span className="text-[10px] text-muted ml-0.5">▼</span>
            </button>

            {userDropdownOpen && (
              <div
                onMouseLeave={() => setUserDropdownOpen(false)}
                className="absolute right-0 mt-2 w-64 rounded-lg border border-line/80 bg-[#0c1220] p-1.5 shadow-2xl z-50 animate-rise font-mono-spec text-xs space-y-1"
              >
                <div className="px-2 py-1 text-[10px] uppercase font-bold text-accent tracking-wider border-b border-line/40">
                  ★ 페르소나 유저 전환 (Persona Switcher)
                </div>
                {SAMPLE_USERS.map((u) => (
                  <button
                    key={u.uuid}
                    onClick={() => {
                      setSelected({ uuid: u.uuid, label: u.label });
                      setUserDropdownOpen(false);
                    }}
                    className={`w-full text-left p-2 rounded-md transition flex flex-col ${
                      selected?.uuid === u.uuid
                        ? "bg-accent/20 border border-accent/40 text-accent font-semibold"
                        : "hover:bg-surface/80 text-fg"
                    }`}
                  >
                    <span className="truncate">{u.label}</span>
                    <span className="text-[10px] text-muted font-normal">{u.district}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

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
