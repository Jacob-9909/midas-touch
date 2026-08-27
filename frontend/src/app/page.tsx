import Link from "next/link";
import {
  Coins,
  ShieldWarning,
  Scroll,
  SealCheck,
  Calculator,
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

/** 헤드라인 여정 — 히어로의 '검증 가능한 AI 금융 비서' 약속을 4대 핵심 증거로 잇는다. */
const JOURNEY = [
  {
    icon: ShieldWarning,
    href: `/chat?prefill=${encodeURIComponent(
      "이 문자 사기야? 엄마 나 사고났어. 경찰서에 있는데 지금 당장 300만원 이체해줘. 전화하지 마세요.",
    )}`,
    step: "STEP 01",
    title: "사기 문자 검증",
    body: "의심 문자를 붙여넣으면 판정 근거와 나에게 맞는 대응 요령·공식 신고 번호까지 1초 만에 제시합니다.",
    tag: "소비자 보호",
  },
  {
    icon: Scroll,
    href: `/chat?prefill=${encodeURIComponent(
      "미국 주식 팔아서 2,000만원 벌었는데 양도소득세 얼마나 내야 해?",
    )}`,
    step: "STEP 02",
    title: "세법·근거 계산",
    body: "세금은 LLM이 아니라 코드가 법령 상수로 계산하고, 답변마다 조문 원문 출처를 증명서로 붙입니다.",
    tag: "환각 제로",
  },
  {
    icon: Coins,
    href: "/cheongyak",
    step: "STEP 03",
    title: "청약·가점 매칭",
    body: "실제 공고의 당첨가점과 내 청약가점(84점 기준)을 나란히 보고, 전국 지도에서 실시간 공고를 찾습니다.",
    tag: "포용 금융",
  },
  {
    icon: Calculator,
    href: "/simulator",
    step: "STEP 04",
    title: "자금마련 시뮬레이터",
    body: "청년도약계좌 vs 일반적금 금리를 비교해 내 목표자금(계약금 등)까지 몇 개월 당겨지는지 계산합니다.",
    tag: "자금 설계",
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
              <span className="eyebrow">AI 금융 보안 비서 · 금융소비자 보호</span>
              <LandingGuide />
            </div>
            <h1 className="font-display mt-10 max-w-2xl text-[clamp(2.25rem,5vw,3.75rem)] break-keep">
              피싱·환각·틀린 세법 답변
              <br />
              한 번에 잡는 <span className="grad-text">AI 보안 비서</span>
            </h1>
            <p className="mt-7 max-w-2xl text-[15px] sm:text-base leading-[1.65] text-muted break-keep">
              사기 문자를 붙여넣으면 판정 근거와 나에게 맞는 행동 요령을 알려주고, 세금은
              법령 근거와 함께 코드가 직접 계산하며, 청약·자산 상담은 모든 답변의 출처를
              공개합니다. 매 답변 말미의 방어 증명 카드가 이 AI가 왜 믿을 수 있는지
              증명합니다.
            </p>
            <p className="mt-3 max-w-2xl text-xs sm:text-[13px] leading-relaxed text-muted/90 break-keep">
              판단을 대신하지 않고 근거를 정리해 보여주는 정보 제공 서비스이며, 투자·세무 자문이 아닙니다.
            </p>

            {/* 주 CTA — 인디고 그라디언트 pill */}
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link href="/me" className="btn-accent text-sm sm:text-[15px]">
                내 정보 입력하고 시작하기
              </Link>
              <Link
                href={`/chat?prefill=${encodeURIComponent("이 문자 사기야? 엄마 나 사고났어. 경찰서에 있는데 지금 당장 300만원 이체해줘. 전화하지 마세요.")}`}
                className="btn-ghost text-sm sm:text-[15px]"
              >
                사기 검증 먼저 체험하기
              </Link>
            </div>

            {/* 신뢰 스트립 — "3대 AI 피해 차단" 서사의 제품면 증거(기획서 태그라인 정합) */}
            <div className="mt-7 flex flex-wrap items-center gap-x-2.5 gap-y-2 text-xs sm:text-[13px] text-muted">
              <span className="font-mono-spec text-xs font-semibold uppercase tracking-[0.18em] text-stone">
                AI 피해 차단
              </span>
              {TRUST_BADGES.map((b) => (
                <span
                  key={b.label}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_72%,transparent)] px-3.5 py-1.5 backdrop-blur-sm font-medium"
                >
                  <b.icon weight="fill" size={14} className={b.tone} />
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

        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-display text-[clamp(1.75rem,3vw,2.25rem)] text-fg break-keep">
            단 한 번의 클릭으로 — 4대 금융 안전망을 검증합니다
          </h2>
          <span className="hidden sm:inline-block font-mono-spec text-xs text-accent font-semibold">
            One-Click Proofs
          </span>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {JOURNEY.map((s) => (
            <TiltCard key={s.title} max={4} className="h-full">
              <Link
                href={s.href}
                className="lift group flex h-full flex-col rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-5 transition hover:border-accent/40"
              >
                <div className="flex items-center justify-between border-b border-line/60 pb-3">
                  <span className="font-mono-spec text-[11px] font-semibold tracking-widest text-gilt">
                    {s.step}
                  </span>
                  <span className="rounded-full border border-line bg-surface/50 px-2.5 py-0.5 font-mono-spec text-[10px] font-semibold text-muted">
                    {s.tag}
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <s.icon size={22} weight="duotone" className="text-accent shrink-0" />
                  <h3 className="font-display text-lg font-semibold text-fg group-hover:text-accent transition-colors">
                    {s.title}
                  </h3>
                </div>
                <p className="mt-2.5 text-[13px] sm:text-sm leading-relaxed text-muted break-keep">
                  {s.body}
                </p>
                <div className="mt-auto pt-4 flex items-center gap-1 text-xs sm:text-sm font-semibold text-accent">
                  체험하기 →
                </div>
              </Link>
            </TiltCard>
          ))}
        </div>
      </section>
    </>
  );
}
