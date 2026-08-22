import Link from "next/link";
import { ChatsCircle, Coins, ChartLineUp } from "@phosphor-icons/react/dist/ssr";
import ProfileNudge from "@/components/ProfileNudge";

/** 랜딩(`/`)은 헤드라인 여정으로 보내는 관문만 한다.
 *
 * 원래는 거시지표·주식 히트맵·전망 적중률·페르소나 선택표까지 얹힌 대시보드였는데,
 * 전부 청약·자금마련(core)과 무관해서 걷어냈다. 주식 쪽은 `/stocks`, 적중률은
 * `/stocks`의 MemoryStatsCard 에 그대로 살아 있다.
 *
 * 디자인은 docs/DESIGN-revolut.md 의 두 모드 밴드 구조를 따른다 —
 * 검정 스토리텔링 히어로가 full-bleed 로 깔리고, 그 아래 흰 카탈로그 밴드가 이어진다.
 * 두 밴드는 부드럽게 섞이지 않고 경계에서 그대로 부딪힌다(문서 §Overview).
 * 데이터를 부르지 않으므로 서버 컴포넌트로 둔다. */

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
    <>
      {/* ── 검정 스토리텔링 밴드 (문서 §Overview) ────────────────────
          하드코딩된 USD/KRW·미국채 지표는 뺐다 — "LIVE" 배지 옆에 붙어 있어
          실시간 시세처럼 읽혔고, 청약·자금마련과도 무관한 숫자였다. */}
      <section className="band-dark">
        <div className="mx-auto max-w-[1200px] px-6 py-[104px] sm:py-[120px]">
          <span className="eyebrow">청년 자산형성 콘솔</span>
          <h1 className="font-display mt-8 max-w-[22ch] text-[clamp(2.5rem,6.5vw,4.5rem)]">
            무주택 사회초년생을 위한 청약·자금마련 AI 콘솔
          </h1>
          <p className="mt-8 max-w-[58ch] text-[1.0625rem] leading-[1.56] text-muted">
            흩어진 청약 조건과 자금 계획을 한자리에서 정리합니다. 내 조건에 어떤 청약 유형이
            적용되는지 세법·청약 조문 근거와 함께 설명하고, 실제 공고의 당첨가점과 내 가점을
            나란히 놓고, 목표금액까지 몇 개월 걸리는지 시뮬레이션합니다.
          </p>
          <p className="mt-4 max-w-[58ch] text-sm leading-relaxed text-muted">
            판단을 대신하지 않고 근거를 정리해 보여주는 정보 제공 서비스이며, 투자·세무 자문이 아닙니다.
          </p>

          {/* 문서 §Do's: 검정 밴드 위의 주 CTA는 '흰 pill' — 화면에서 가장 밝은 픽셀이다. */}
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Link href="/me" className="btn-accent">
              내 정보 입력하고 시작하기
            </Link>
            <Link href="/chat" className="btn-ghost">
              청약 상담 먼저 보기
            </Link>
          </div>
        </div>
      </section>

      {/* ── 흰 카탈로그 밴드 ──────────────────────────────────────── */}
      <section className="mx-auto max-w-[1200px] px-6 py-[88px]">
        <ProfileNudge className="mb-12" />

        <h2 className="font-display text-[clamp(1.875rem,3.5vw,2.5rem)] text-fg">
          세 단계면 내 청약 조건이 정리됩니다
        </h2>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {JOURNEY.map((s, i) => (
            <Link
              key={s.title}
              href={s.href}
              className="lift group flex flex-col rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-8"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold tracking-wide text-accent">
                  STEP 0{i + 1}
                </span>
                <span className="text-muted">
                  <s.icon size={22} weight="regular" />
                </span>
              </div>
              <h3 className="font-display mt-6 text-2xl text-fg">{s.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted">{s.body}</p>
              <span className="mt-6 text-sm font-semibold text-fg">시작하기 →</span>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
