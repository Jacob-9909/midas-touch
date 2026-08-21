import Link from "next/link";
import { ChatsCircle, Coins, ChartLineUp } from "@phosphor-icons/react/dist/ssr";
import { Reveal } from "@/components/Reveal";
import OGHeroCard from "@/components/bits/OGHeroCard";
import GlareHover from "@/components/bits/GlareHover";

/** 랜딩(`/`)은 헤드라인 여정으로 보내는 관문만 한다.
 *
 * 원래는 거시지표·주식 히트맵·전망 적중률·페르소나 선택표까지 얹힌 대시보드였는데,
 * 전부 청약·자금마련(core)과 무관해서 걷어냈다. 주식 쪽은 `/stocks`, 적중률은
 * `/stocks`의 MemoryStatsCard 에 그대로 살아 있다.
 *
 * 데이터를 부르지 않으므로 클라이언트 컴포넌트일 이유가 없다 — 서버 컴포넌트로 둔다. */

/** MVP 헤드라인 여정(무주택 사회초년생: 청약 상담 → 목표자금 → 자금마련). docs/mvp-scope.md 기준. */
const JOURNEY = [
  {
    icon: ChatsCircle,
    href: "/chat",
    title: "청약 상담",
    body: "내 조건에서 어떤 청약 유형·특별공급이 적용되는지, 세법·청약 조문 근거와 함께 정리해 줍니다.",
  },
  {
    icon: Coins,
    href: "/cheongyak",
    title: "내 가점·목표자금 확인",
    body: "실제 공고의 당첨가점과 내 청약가점(84점 기준)을 나란히 보고, 그 공고의 목표금액을 잡습니다.",
  },
  {
    icon: ChartLineUp,
    href: "/simulator",
    title: "자금마련 타임라인",
    body: "지금 저축 계획으로 목표까지 몇 개월인지, 상품을 바꾸면 얼마나 당겨지는지 그래프로 비교합니다.",
  },
] as const;

export default function HomePage() {
  return (
    <div className="space-y-12">
      {/* 히어로에 붙어 있던 USD/KRW·미국채 지표는 뺐다 — 하드코딩된 고정값이었는데
          "LIVE" 배지 옆에 놓여 있어 실시간 시세처럼 읽혔다(금융 서비스에서 특히 나쁨).
          게다가 청약·자금마련과 무관한 숫자라 걷어내는 게 맞다. */}
      <OGHeroCard
        categoryTag="VOL. 2026 / 청년 자산형성 콘솔"
        title="무주택 사회초년생을 위한 청약·자금마련 AI 콘솔"
        subtitle="흩어진 청약 조건과 자금 계획을 한자리에서 정리합니다. 내 조건에 어떤 청약 유형이 적용되는지 세법·청약 조문 근거와 함께 설명하고, 실제 공고의 당첨가점과 내 가점을 나란히 놓고, 목표금액까지 몇 개월 걸리는지 시뮬레이션합니다. 판단을 대신하지 않고 근거를 정리해 보여주는 정보 제공 서비스이며, 투자·세무 자문이 아닙니다."
        actions={
          <div className="flex items-center gap-3">
            <Link
              href="/chat"
              className="rounded-full border border-accent/40 bg-accent/20 px-4 py-2 text-xs font-mono-spec text-accent hover:bg-accent/30 transition shadow-md"
            >
              청약 상담 시작 →
            </Link>
            <Link
              href="/simulator"
              className="rounded-full border border-line bg-surface/60 px-4 py-2 text-xs font-mono-spec text-fg hover:border-accent/40 transition"
            >
              자금마련 시뮬레이터
            </Link>
          </div>
        }
      />

      <section className="grid gap-px border border-line bg-line/30 sm:grid-cols-3">
        {JOURNEY.map((s, i) => (
          <Reveal key={s.title} index={i} className="h-full">
            {/* 골드 광원이 카드를 사선으로 쓸고 지나간다 — 유리 패널로 읽히게 하는 장치 */}
            <GlareHover
              className="h-full"
              glareColor="#f3e5ab"
              glareOpacity={0.16}
              glareAngle={-40}
              glareSize={220}
              transitionDuration={780}
            >
              <Link
                href={s.href}
                className="block h-full bg-[var(--ink-1)] p-6 transition hover:bg-[color-mix(in_srgb,var(--accent)_4%,var(--ink-1))]"
              >
                <div className="flex items-center justify-between border-b border-line/40 pb-3">
                  <span className="font-mono-spec text-[10px] font-semibold tracking-widest text-accent">
                    STEP 0{i + 1}
                  </span>
                  <span className="text-muted">
                    <s.icon size={18} weight="duotone" />
                  </span>
                </div>
                <h2 className="font-display mt-4 text-xl font-semibold text-fg">{s.title}</h2>
                <p className="mt-2 text-xs leading-relaxed text-muted">{s.body}</p>
              </Link>
            </GlareHover>
          </Reveal>
        ))}
      </section>
    </div>
  );
}
