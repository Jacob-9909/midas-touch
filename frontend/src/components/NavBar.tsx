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
import ShinyText from "@/components/bits/ShinyText";
import ElectricBorder from "@/components/bits/ElectricBorder";
import GlassSurface from "@/components/bits/GlassSurface";
import LiveSyncBadge from "@/components/bits/LiveSyncBadge";

// 헤드라인은 청약(챗봇 상담 + 목록조회 + 자금마련 시뮬레이터)이라 "core"로 앞세우고,
// 나머지(대시보드·주식분석·지식그래프)는 부가 기능이라 "engine"으로 구분선 뒤에 강등한다.
const LINKS = [
  { href: "/chat", label: "에이전트 챗봇", group: "core" },
  { href: "/cheongyak", label: "청약", group: "core" },
  { href: "/simulator", label: "자금마련 시뮬레이터", group: "core" },
  { href: "/", label: "대시보드", group: "engine" },
  { href: "/stocks", label: "주식분석", group: "engine" },
  { href: "/graph", label: "지식그래프", group: "engine" },
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

        {/* 페르소나 라벨 길이가 가변이라, 줄어드는 쪽은 항상 이 그룹이어야 한다.
            (min-w-0 없이는 flex가 로고·링크까지 압축해 글자가 두 줄로 깨진다) */}
        <div className="relative ml-auto flex min-w-0 items-center gap-2.5">
          {/* 최근 디자인 라이브 상태 뱃지 */}
          <div className="hidden sm:block">
            <LiveSyncBadge state="live" label="FIN-STREAM" latencyMs={12} lastUpdated="방금 전" />
          </div>
          {/* 페르소나 유저 퀵 스위처 */}
          {/* truncate가 실제로 걸리려면 축소 사슬 전체에 min-w-0이 있어야 한다.
              하나라도 빠지면 콘텐츠 폭이 하한이 되어 우측 아이콘 버튼이 잘려 나간다. */}
          <div className="relative min-w-0">
            <button
              onClick={() => setUserDropdownOpen((v) => !v)}
              className="flex min-w-0 max-w-full items-center gap-1.5 whitespace-nowrap rounded-full border border-line/60 px-3 py-1 text-xs text-accent hover:border-accent/60 transition bg-surface/40 font-mono-spec shadow-sm"
            >
              <UserCircle weight="fill" size={15} className="shrink-0" />
              <span className="min-w-0 max-w-[150px] truncate font-medium">
                {selected ? selected.label : "유저 선택"}
              </span>
              <span className="ml-0.5 shrink-0 text-[10px] text-muted">▼</span>
            </button>

            {userDropdownOpen && (
              <div
                onMouseLeave={() => setUserDropdownOpen(false)}
                className="absolute right-0 mt-2 w-64 rounded-lg border border-line/80 bg-[#0c1220] p-1.5 shadow-2xl z-50 animate-rise font-mono-spec text-xs space-y-1"
              >
                <div className="px-2 py-1 text-[10px] uppercase font-bold text-accent tracking-wider border-b border-line/40">
                  ★ 페르소나 유저 전환 (Persona Switcher)
                </div>
                {SAMPLE_USERS.map((u) => {
                  const isCurrent = selected?.uuid === u.uuid;
                  const row = (
                    <button
                      onClick={() => {
                        setSelected({ uuid: u.uuid, label: u.label });
                        setUserDropdownOpen(false);
                      }}
                      className={`w-full text-left p-2 rounded-md transition flex flex-col ${
                        isCurrent
                          ? "bg-accent/20 text-accent font-semibold"
                          : "hover:bg-surface/80 text-fg"
                      }`}
                    >
                      <span className="truncate">{u.label}</span>
                      <span className="text-[10px] text-muted font-normal">{u.district}</span>
                    </button>
                  );

                  // 지금 보고 있는 페르소나에만 전류 테두리를 준다. 장식이 아니라 상태 표시이고,
                  // 드롭다운이 열렸을 때만 마운트되므로 rAF 루프도 그때만 돈다.
                  return isCurrent ? (
                    <ElectricBorder key={u.uuid} borderRadius={6} speed={0.8} chaos={0.1}>
                      {row}
                    </ElectricBorder>
                  ) : (
                    <div key={u.uuid}>{row}</div>
                  );
                })}
              </div>
            )}
          </div>

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
