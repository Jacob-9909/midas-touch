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
        <div className="mx-auto grid max-w-[1200px] items-center gap-12 px-6 py-[80px] sm:py-[96px] lg:grid-cols-[1.25fr_1fr]">
          <div>
            <div className="flex items-center justify-between gap-4">
              <span className="eyebrow">AI 금융 보안 비서 · 금융소비자 보호</span>
              <LandingGuide />
            </div>
            <h1 className="font-display mt-7 text-[clamp(1.45rem,2.9vw,2.65rem)] font-extrabold tracking-tight leading-[1.25] text-fg">
              <span className="block break-keep sm:whitespace-nowrap">피싱·환각·틀린 세법 답변</span>
              <span className="block break-keep sm:whitespace-nowrap mt-1 sm:mt-1.5">
                한 번에 잡는 <span className="grad-text">AI 보안 비서</span>
              </span>
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

            {/* 데모 데이터 고지 — 정직성 원칙 증거. 페르소나·또래·시장 데이터가 합성/공공임을
                UI에서 명시해, 심사위원이 실개인정보로 오해하지 않게 한다. */}
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-line bg-[color-mix(in_srgb,var(--ink-1)_60%,transparent)] px-3.5 py-2.5 max-w-2xl">
              <SealCheck weight="fill" size={15} className="mt-0.5 shrink-0 text-accent" />
              <p className="text-xs leading-relaxed text-muted break-keep">
                <span className="font-semibold text-fg/80">데모 안내</span> · 표시되는 사용자·또래·시장 데이터는
                데모용 <span className="text-fg/80">합성/공공 데이터</span>이며 실제 개인정보가 아닙니다.
                세법·청약 근거는 국세청·공공데이터 등 공개 출처를 사용합니다.
              </p>
            </div>

            {/* 주 CTA — 인디고 그라디언트 pill */}
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link href="/me" className="btn-accent text-sm sm:text-[15px]">
                내 정보 입력하고 시작하기
              </Link>
              <Link
                href={`/chat?prefill=${encodeURIComponent("이 문자 사기야? 엄마 나 사고났어. 경찰서에 있는데 지금 당장 300만원 이체해줘. 전화하지 마세요.")}&autoSend=1`}
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

      {/* ── 4대 금융 안전망 & 심사위원 퀵 검증 통합 섹션 ────────── */}
      <section className="mx-auto max-w-[1200px] px-6 py-16 sm:py-20" data-tour="journey">
        <ProfileNudge className="mb-12" data-tour="nudge" />

        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-line/60 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="eyebrow">CORE CAPABILITIES · 심사위원 퀵 평가</span>
              <span className="font-mono-spec text-[11px] font-bold text-accent px-2 py-0.5 rounded-full border border-accent/30 bg-accent/10">
                3-MIN TOUR
              </span>
            </div>
            <h2 className="font-display mt-2 text-[clamp(1.6rem,2.8vw,2.25rem)] font-bold text-fg break-keep">
              단 한 번의 클릭으로 — 4대 금융 안전망을 검증합니다
            </h2>
            <p className="mt-1 text-xs sm:text-sm text-muted break-keep">
              카드를 클릭하면 실제 의심 사례와 세법 질의가 챗봇에 즉시 입력되거나 해당 검증 페이지로 바로 연결됩니다.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2">
            <Link
              href="/security"
              className="btn-ghost text-xs font-semibold px-3 py-1.5"
            >
              5겹 보안 체험
            </Link>
            <Link
              href="/chat"
              className="btn-accent text-xs font-semibold px-3 py-1.5"
            >
              챗봇 열기 →
            </Link>
          </div>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TiltCard max={4} className="h-full">
            <Link
              href={`/chat?prefill=${encodeURIComponent(
                "이 문자 사기야? 엄마 나 폰 액정 깨져서 수리 맡겼어. 지금 급하게 결제할 게 있는데 이 링크로 들어가서 300만원만 보내줘: http://bit.ly/urgent-pay88. 전화는 안 돼.",
              )}&autoSend=1`}
              className="lift group flex h-full flex-col justify-between rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-5 transition hover:border-accent/40"
            >
              <div>
                <div className="flex items-center justify-between border-b border-line/60 pb-3">
                  <span className="font-mono-spec text-[11px] font-semibold tracking-widest text-gilt">
                    STEP 01
                  </span>
                  <span className="rounded-full border border-gilt/40 bg-gilt/10 px-2.5 py-0.5 font-mono-spec text-[10px] font-bold text-gilt">
                    피싱 방어
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <ShieldWarning size={22} weight="duotone" className="text-gilt shrink-0" />
                  <h3 className="font-display text-lg font-semibold text-fg group-hover:text-accent transition-colors">
                    사기 문자 검증
                  </h3>
                </div>
                <p className="mt-2.5 text-[13px] sm:text-sm leading-relaxed text-muted break-keep">
                  의심 문자를 붙여넣으면 판정 근거와 연령별 대응 요령·공식 신고 번호까지 1초 만에 제시합니다.
                </p>
                <div className="mt-3 rounded-md border border-line/50 bg-[var(--ink-2)]/60 p-2 text-[11px] leading-relaxed text-muted/90">
                  <span className="font-semibold text-fg/80 block mb-0.5">🔍 검증 포인트:</span>
                  10카테고리 스코어링 + 공식 도메인 감쇠 + 112/1332 안내 + 🛡 방어 증명 부착
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-line/50 flex items-center justify-between text-xs font-bold text-accent">
                <span>즉시 검증하기</span>
                <span>→</span>
              </div>
            </Link>
          </TiltCard>

          <TiltCard max={4} className="h-full">
            <Link
              href={`/chat?prefill=${encodeURIComponent(
                "미국 주식(엔비디아) 팔아서 올해 2,000만원 벌었는데 양도소득세 얼마 내야 해? 기본공제랑 세금 계산식 알려줘.",
              )}&autoSend=1`}
              className="lift group flex h-full flex-col justify-between rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-5 transition hover:border-accent/40"
            >
              <div>
                <div className="flex items-center justify-between border-b border-line/60 pb-3">
                  <span className="font-mono-spec text-[11px] font-semibold tracking-widest text-accent">
                    STEP 02
                  </span>
                  <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-0.5 font-mono-spec text-[10px] font-bold text-accent">
                    환각 제로
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <Scroll size={22} weight="duotone" className="text-accent shrink-0" />
                  <h3 className="font-display text-lg font-semibold text-fg group-hover:text-accent transition-colors">
                    세법·근거 계산
                  </h3>
                </div>
                <p className="mt-2.5 text-[13px] sm:text-sm leading-relaxed text-muted break-keep">
                  세금은 LLM이 아니라 코드가 법령 상수로 계산하고, 답변마다 조문 원문 출처를 증명서로 붙입니다.
                </p>
                <div className="mt-3 rounded-md border border-line/50 bg-[var(--ink-2)]/60 p-2 text-[11px] leading-relaxed text-muted/90">
                  <span className="font-semibold text-fg/80 block mb-0.5">🔍 검증 포인트:</span>
                  결정론 250만 공제/22% 산출 + 국세청 해설서 RAG 조문 인용
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-line/50 flex items-center justify-between text-xs font-bold text-accent">
                <span>즉시 계산하기</span>
                <span>→</span>
              </div>
            </Link>
          </TiltCard>

          <TiltCard max={4} className="h-full">
            <Link
              href="/cheongyak"
              className="lift group flex h-full flex-col justify-between rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-5 transition hover:border-accent/40"
            >
              <div>
                <div className="flex items-center justify-between border-b border-line/60 pb-3">
                  <span className="font-mono-spec text-[11px] font-semibold tracking-widest text-positive">
                    STEP 03
                  </span>
                  <span className="rounded-full border border-positive/40 bg-positive/10 px-2.5 py-0.5 font-mono-spec text-[10px] font-bold text-positive">
                    포용 금융
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <Coins size={22} weight="duotone" className="text-positive shrink-0" />
                  <h3 className="font-display text-lg font-semibold text-fg group-hover:text-accent transition-colors">
                    청약·가점 매칭
                  </h3>
                </div>
                <p className="mt-2.5 text-[13px] sm:text-sm leading-relaxed text-muted break-keep">
                  실제 공고의 당첨가점과 내 청약가점(84점 기준)을 나란히 보고, 전국 지도에서 실시간 공고를 찾습니다.
                </p>
                <div className="mt-3 rounded-md border border-line/50 bg-[var(--ink-2)]/60 p-2 text-[11px] leading-relaxed text-muted/90">
                  <span className="font-semibold text-fg/80 block mb-0.5">🔍 검증 포인트:</span>
                  공공데이터 API 실공고 + 가점표 3요소 자동 판정 & 지도 필터
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-line/50 flex items-center justify-between text-xs font-bold text-accent">
                <span>공고 조회하기</span>
                <span>→</span>
              </div>
            </Link>
          </TiltCard>

          <TiltCard max={4} className="h-full">
            <Link
              href="/simulator"
              className="lift group flex h-full flex-col justify-between rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-5 transition hover:border-accent/40"
            >
              <div>
                <div className="flex items-center justify-between border-b border-line/60 pb-3">
                  <span className="font-mono-spec text-[11px] font-semibold tracking-widest text-cyan-400">
                    STEP 04
                  </span>
                  <span className="rounded-full border border-cyan-400/40 bg-cyan-400/10 px-2.5 py-0.5 font-mono-spec text-[10px] font-bold text-cyan-400">
                    자금 설계
                  </span>
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <Calculator size={22} weight="duotone" className="text-cyan-400 shrink-0" />
                  <h3 className="font-display text-lg font-semibold text-fg group-hover:text-accent transition-colors">
                    자금마련 시뮬레이터
                  </h3>
                </div>
                <p className="mt-2.5 text-[13px] sm:text-sm leading-relaxed text-muted break-keep">
                  청년도약계좌 vs 일반적금 금리를 비교해 내 목표자금까지 몇 개월 당겨지는지 브라우저에서 계산합니다.
                </p>
                <div className="mt-3 rounded-md border border-line/50 bg-[var(--ink-2)]/60 p-2 text-[11px] leading-relaxed text-muted/90">
                  <span className="font-semibold text-fg/80 block mb-0.5">🔍 검증 포인트:</span>
                  복리 이자 시각화 + 브라우저 로컬 연산(자산 데이터 미전송)
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-line/50 flex items-center justify-between text-xs font-bold text-accent">
                <span>시뮬레이션 하기</span>
                <span>→</span>
              </div>
            </Link>
          </TiltCard>
        </div>
      </section>

      {/* ── 차별화 기술 해자 요약 섹션 (Why Midas Touch?) ────────── */}
      <section className="border-t border-line bg-[color-mix(in_srgb,var(--ink-1)_60%,transparent)] py-16 sm:py-20">
        <div className="mx-auto max-w-[1200px] px-6">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <span className="eyebrow">TRUST & ARCHITECTURE</span>
            <h2 className="font-display mt-2 text-2xl sm:text-3xl font-bold text-fg break-keep">
              일반 금융 AI 챗봇과 <span className="grad-text">무엇이 다른가요?</span>
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-muted break-keep">
              Midas Touch는 확률적 텍스트 생성에 의존하지 않고, 코드가 보증하는 신뢰 기술을 사용합니다.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-6">
              <div className="font-mono-spec text-xs font-bold text-gilt">01. DETERMINISTIC</div>
              <h3 className="font-display mt-2 text-lg font-bold text-fg">환각 없는 결정론 계산 엔진</h3>
              <p className="mt-2 text-xs sm:text-sm text-muted leading-relaxed break-keep">
                세율과 공제액 계산을 LLM에게 맡기지 않고 순수 Python/TS 코드로 산출하여 숫자 환각을 100% 원천 차단합니다.
              </p>
            </div>
            <div className="rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-6">
              <div className="font-mono-spec text-xs font-bold text-accent">02. 5-LAYER DEFENSE</div>
              <h3 className="font-display mt-2 text-lg font-bold text-fg">모든 답변의 🛡 방어 증명</h3>
              <p className="mt-2 text-xs sm:text-sm text-muted leading-relaxed break-keep">
                도구 화이트리스트, 저온 생성, 국세청 조문 RAG 출처, 외부 경계 검증 상태를 매 답변 말미에 코드로 자동 부착합니다.
              </p>
            </div>
            <div className="rounded-[var(--r-lg)] border border-line bg-[var(--ink-1)] p-6">
              <div className="font-mono-spec text-xs font-bold text-positive">03. PRIVACY BY DESIGN</div>
              <h3 className="font-display mt-2 text-lg font-bold text-fg">민감 금융 데이터 로컬 격리</h3>
              <p className="mt-2 text-xs sm:text-sm text-muted leading-relaxed break-keep">
                청약 가점과 개인 자산 시뮬레이션 데이터를 서버로 전송하지 않고 브라우저 LocalStorage에서만 독립 처리합니다.
              </p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
