import Link from "next/link";
import {
  ChatsCircle,
  Coins,
  ChartLineUp,
  ShieldWarning,
  Scroll,
  SealCheck,
} from "@phosphor-icons/react/dist/ssr";
import ProfileNudge from "@/components/ProfileNudge";
import LandingGuide from "@/components/LandingGuide";
import HeroShowcase from "@/components/HeroShowcase";
import TiltCard from "@/components/TiltCard";

/** 3대 AI 피해 차단 배지 — 기획서 태그라인(피싱·환각 세법·허위 조언)의 제품면 증거.
 *  실제 탑재된 기능만 표기한다(과장 금지 원칙). */
const TRUST_BADGES = [
  { icon: ShieldWarning, label: "사기 문자 검증", tone: "text-gilt" },
  { icon: Scroll, label: "근거 조문 첨부", tone: "text-accent" },
  { icon: SealCheck, label: "예측 자가 채점", tone: "text-positive" },
] as const;

/** 랜딩(`/`)은 대시보드 겸 관문 — 콘솔의 정체성을 요약하고 여정으로 보낸다.
 *
 * 원래는 거시지표·주식 히트맵·전망 적중률·페르소나 선택표까지 얹힌 대시보드였는데,
 * 전부 청약·자금마련(core)과 무관해서 걷어냈다. 주식 쪽은 `/stocks`, 적중률은
 * `/stocks`의 MemoryStatsCard 에 그대로 살아 있다.
 *
 * 디자인은 "Bullion Terminal"(globals.css)을 따른다 — 근흑색 콘솔 위에 골드는
 * 목표·달성 신호로만 찍고, 카드는 8px 헤어라인, 숫자·단계 라벨은 모노로.
 * 데이터를 부르지 않으므로 서버 컴포넌트로 둔다(가이드만 클라이언트 경계). */

/** MVP 헤드라인 여정(무주택 사회초년생: 청약 상담 → 목표자금 → 자금마련). docs/mvp-scope.md 기준. */
const JOURNEY = [
  {
    icon: ChatsCircle,
    href: "/chat",
    step: "STEP 01",
    title: "청약 상담",
    body: "내 조건에서 어떤 청약 유형·특별공급이 적용되는지, 세법·청약 조문 근거와 함께 정리해 줍니다.",
  },
  {
    icon: Coins,
    href: "/cheongyak",
    step: "STEP 02",
    title: "내 가점·목표자금 확인",
    body: "실제 공고의 당첨가점과 내 청약가점(84점 기준)을 나란히 보고, 그 공고의 목표금액을 잡습니다.",
  },
  {
    icon: ChartLineUp,
    href: "/simulator",
    step: "STEP 03",
    title: "자금마련 타임라인",
    body: "지금 저축 계획으로 목표까지 몇 개월인지, 상품을 바꾸면 얼마나 당겨지는지 그래프로 비교합니다.",
  },
] as const;

export default function HomePage() {
  return (
    <>
      {/* ── 히어로 ─────────────────────────────────────────────────
          Neon Ledger: 오로라 블롭(인디고+앰버)이 스미는 밴드로 첫 화면의 톤을 만들고,
          헤드라인 키워드는 인디고→골드 그라디언트로 강조한다. CTA는 인디고 pill. */}
      <section
        data-tour="hero"
        className="aurora surface-raised relative overflow-hidden border-b border-line"
      >
        <div className="mx-auto grid max-w-[1200px] items-center gap-14 px-6 py-[88px] sm:py-[104px] lg:grid-cols-[1.15fr_1fr]">
          <div>
            <div className="flex items-center justify-between gap-4">
              <span className="eyebrow">청년 자산형성 콘솔</span>
              <LandingGuide />
            </div>
            <h1 className="font-display mt-10 max-w-[22ch] text-[clamp(2.25rem,5vw,3.75rem)]">
              무주택 사회초년생을 위한
              <br />
              청약·자금마련 <span className="grad-text">AI 콘솔</span>
            </h1>
            <p className="mt-7 max-w-[58ch] leading-[1.6] text-muted">
              흩어진 청약 조건과 자금 계획을 한자리에서 정리합니다. 내 조건에 어떤 청약 유형이
              적용되는지 세법·청약 조문 근거와 함께 설명하고, 실제 공고의 당첨가점과 내 가점을
              나란히 놓고, 목표금액까지 몇 개월 걸리는지 시뮬레이션합니다.
            </p>
            <p className="mt-3 max-w-[58ch] text-xs leading-relaxed text-muted">
              판단을 대신하지 않고 근거를 정리해 보여주는 정보 제공 서비스이며, 투자·세무 자문이 아닙니다.
            </p>

            {/* 주 CTA — 인디고 그라디언트 pill */}
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link href="/me" className="btn-accent">
                내 정보 입력하고 시작하기
              </Link>
              <Link href="/chat" className="btn-ghost">
                청약 상담 먼저 보기
              </Link>
            </div>

            {/* 신뢰 스트립 — "3대 AI 피해 차단" 서사의 제품면 증거(기획서 태그라인 정합) */}
            <div className="mt-7 flex flex-wrap items-center gap-x-2 gap-y-2 text-xs text-muted">
              <span className="font-mono-spec text-[10px] font-semibold uppercase tracking-[0.18em] text-stone">
                AI 피해 차단
              </span>
              {TRUST_BADGES.map((b) => (
                <span
                  key={b.label}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_72%,transparent)] px-3 py-1.5 backdrop-blur-sm"
                >
                  <b.icon weight="fill" size={13} className={b.tone} />
                  {b.label}
                </span>
              ))}
            </div>
          </div>

          {/* 우측 — 서비스를 미리 보여주는 글래스 위젯 클러스터(3D 틸트) */}
          <HeroShowcase />
        </div>
      </section>

      {/* ── 카탈로그 섹션 ────────────────────────────────────────── */}
      <section className="mx-auto max-w-[1200px] px-6 py-[88px]" data-tour="journey">
        <ProfileNudge className="mb-12" data-tour="nudge" />

        <h2 className="font-display text-[clamp(1.75rem,3vw,2.25rem)] text-fg">
          세 단계면 내 청약 조건이 정리됩니다
        </h2>

        <div className="mt-10 grid gap-[1px] overflow-hidden rounded-[var(--r-lg)] border border-line bg-line sm:grid-cols-3">
          {JOURNEY.map((s) => (
            <TiltCard key={s.title} max={4} className="bg-[var(--ink-1)]">
              <Link href={s.href} className="lift group flex h-full flex-col p-6">
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <span className="font-mono-spec text-[10px] font-semibold tracking-widest text-gilt">
                    {s.step}
                  </span>
                  <span className="text-muted">
                    <s.icon size={18} weight="duotone" />
                  </span>
                </div>
                <h3 className="font-display mt-5 text-xl text-fg">{s.title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-muted">{s.body}</p>
                <span className="mt-auto pt-5 text-sm font-semibold text-fg transition-colors group-hover:text-accent">
                  시작하기 →
                </span>
              </Link>
            </TiltCard>
          ))}
        </div>
      </section>
    </>
  );
}
