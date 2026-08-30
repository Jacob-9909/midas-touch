"use client";

import { useEffect, useState } from "react";
import { FileText, SealCheck, ShieldWarning } from "@phosphor-icons/react";
import { AnimatedNumber, Card } from "@/components/ui";
import MiniSparkline from "@/components/bits/MiniSparkline";
import TiltCard from "@/components/TiltCard";

/** 히어로 우측 글래스 위젯 클러스터 — 서비스 흐름(가점→근거→목표자금)을
 *  정지 이미지가 아니라 "살아있는 콘솔"로 미리 보여준다. 실데이터 없이 동작. */

const SPARK = [38, 42, 40, 47, 52, 50, 58, 63, 61, 70, 76];

export default function HeroShowcase() {
  // SVG 진행 링 — r=54, 둘레 ≈ 339.3. 74/84 ≈ 88%.
  const CIRC = 2 * Math.PI * 54;
  const pct = 74 / 84;
  const DRAWN_OFFSET = CIRC * (1 - pct);

  // 링 드로잉 — 빈 링(오프셋 = 둘레)에서 목표치까지 한 번 그려진다.
  // 첫 로드의 레어 순간이라 delight 예산이 허용되는 구간.
  const [offset, setOffset] = useState<number | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const raf = requestAnimationFrame(() => setOffset(DRAWN_OFFSET));
    return () => cancelAnimationFrame(raf);
  }, [DRAWN_OFFSET]);

  const dashoffset = offset ?? CIRC;

  return (
    <div className="relative mx-auto w-full max-w-[420px] select-none" aria-hidden>
      <TiltCard max={6}>
        {/* 메인 카드 — 청약가점 게이지 */}
        <Card variant="glass" className="animate-rise overflow-hidden">
          <div className="flex items-center gap-5">
            <div className="relative h-[128px] w-[128px] shrink-0">
              <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
                <circle cx="64" cy="64" r="54" fill="none" stroke="var(--line)" strokeWidth="10" />
                <circle
                  cx="64"
                  cy="64"
                  r="54"
                  fill="none"
                  stroke="url(#ringGrad)"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={CIRC}
                  strokeDashoffset={dashoffset}
                  style={{ transition: "stroke-dashoffset 1.4s var(--ease-soft)" }}
                />
                <defs>
                  <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="var(--accent)" />
                    <stop offset="100%" stopColor="var(--gilt)" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-display text-3xl text-fg">
                  <AnimatedNumber value={74} duration={1.6} />
                </span>
                <span className="font-mono-spec text-[10px] tracking-widest text-muted">/ 84점</span>
              </div>
            </div>
            <div className="min-w-0 space-y-2">
              <p className="flex items-center gap-1.5 font-mono-spec text-[10px] font-semibold uppercase tracking-widest text-accent">
                <SealCheck weight="fill" size={13} /> 내 청약가점
              </p>
              <ul className="space-y-1 text-xs text-muted">
                {/* 별표1 실제 배점과 합계가 맞아야 한다 — 이 서비스는 '정확성'을 파는데
                    히어로 예시가 틀리면 그 자리에서 신뢰를 잃는다. 32+25+17 = 74. */}
                <li>무주택 기간 <b className="text-fg">15년</b> · +32점</li>
                <li>부양가족 <b className="text-fg">4명</b> · +25점</li>
                <li>청약통장 <b className="text-fg">15년</b> · +17점</li>
              </ul>
            </div>
          </div>
        </Card>

        {/* 하단 행 — 근거 칩 + 목표자금 스파크라인 */}
        <div className="mt-3 grid grid-cols-5 gap-2.5">
          <Card variant="subtle" className="col-span-2 animate-rise p-3.5 [animation-delay:120ms]">
            <p className="flex items-center gap-1.5 font-mono-spec text-[10px] uppercase tracking-widest text-gilt">
              <FileText weight="fill" size={12} /> 근거
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              조문 <b className="text-fg">3건</b> 첨부
              <br />
              해석례 <b className="text-fg">2건</b> 인용
            </p>
          </Card>
          <Card variant="subtle" className="col-span-3 animate-rise p-3.5 [animation-delay:240ms]">
            <p className="font-mono-spec text-[10px] uppercase tracking-widest text-muted">
              목표 자금 추이
            </p>
            <div className="mt-2 flex items-end justify-between gap-1.5">
              <p className="font-display text-xl text-fg">
                <AnimatedNumber value={76} suffix="%" />
              </p>
              <MiniSparkline data={SPARK} color="accent" width={92} height={28} />
            </div>
          </Card>
        </div>
      </TiltCard>

      {/* 부유 배지 — 카드 밖에 떠 있는 '라이브' 신호 */}
      <div
        className="float-slow absolute -right-2 -top-3 sm:-right-3 sm:-top-3 flex items-center gap-1.5 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_85%,transparent)] px-3 py-1.5 text-[11px] font-semibold text-fg shadow-[var(--shadow-1)] backdrop-blur-md whitespace-nowrap z-20"
        data-tour="hero-badge"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-positive" />
        실시간 공고 연동
      </div>
      {/* 부유 배지 2 — 사기 검증 탑재 신호(좌하단, 위상차 애니메이션) */}
      <div
        className="float-slow absolute -bottom-3 -left-2 sm:-bottom-3 sm:-left-3 flex items-center gap-1.5 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_85%,transparent)] px-3 py-1.5 text-[11px] font-semibold text-fg shadow-[var(--shadow-1)] backdrop-blur-md [animation-delay:1.6s] whitespace-nowrap z-20"
      >
        <ShieldWarning weight="fill" size={13} className="text-gilt" />
        사기 문자 검증 탑재
      </div>
    </div>
  );
}
