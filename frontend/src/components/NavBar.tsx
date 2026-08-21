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
import ShinyText from "@/components/bits/ShinyText";
import GlassSurface from "@/components/bits/GlassSurface";
import LiveSyncBadge from "@/components/bits/LiveSyncBadge";

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
    <header className="sticky top-3 z-50 mx-auto mt-2 w-[calc(100%-1.5rem)] max-w-6xl sm:top-4 sm:mt-3">
      {/* 뒤의 골드 앰비언트가 유리를 통과해 굴절된다.
          SVG 필터 미지원 브라우저에서는 컴포넌트 내부 폴백(backdrop-filter)으로 내려간다. */}
      <GlassSurface
        width="100%"
        height="auto"
        borderRadius={10}
        blur={14}
        backgroundOpacity={0.55}
        saturation={1.4}
        distortionScale={-140}
        displace={1.2}
        className="border border-line shadow-md"
      >
      <nav className="flex h-14 items-center gap-1 px-4 sm:px-5">
        <Link
          href="/"
          className="mr-5 flex shrink-0 items-center gap-2.5 whitespace-nowrap font-display text-xl font-normal tracking-tight"
        >
          <ShieldChevron
            weight="fill"
            className="text-accent drop-shadow-[0_0_8px_var(--accent)]"
            size={20}
          />
          {/* 정적 그라디언트 대신 금이 흐르는 하이라이트. 브랜드명이 곧 Midas라 여기가 제자리다. */}
          <ShinyText
            text="Midas Touch"
            speed={4}
            delay={2.5}
            className="font-semibold tracking-wide"
          />
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
                    ? "bg-accent/15 text-accent border border-accent/40 font-semibold shadow-[0_0_12px_rgba(212,175,96,0.18)]"
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
          {/* 최근 디자인 라이브 상태 뱃지 */}
          <div className="hidden sm:block">
            <LiveSyncBadge state="live" label="FIN-STREAM" latencyMs={12} lastUpdated="방금 전" />
          </div>
          {/* 페르소나 퀵 스위처는 제거했다 — 남의 프로필을 뒤집어쓰는 구조라
              자기 청약 자격을 볼 수 없었다. 이제 사용자가 /me 에 직접 입력한다. */}
          {/* 테마 토글 */}
          <button
            onClick={toggle}
            aria-label="테마 전환"
            className="btn-ghost flex h-8 w-8 shrink-0 items-center justify-center rounded border border-line"
          >
            {theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}
          </button>

          {/* 모바일 햄버거 */}
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="메뉴"
            aria-expanded={open}
            className="btn-ghost flex h-8 w-8 shrink-0 items-center justify-center rounded border border-line md:hidden"
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
      </GlassSurface>
    </header>
  );
}
