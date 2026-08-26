"use client";

import { useRef } from "react";
import { FileText, SealCheck } from "@phosphor-icons/react";
import { AnimatedNumber, Card } from "@/components/ui";
import MiniSparkline from "@/components/bits/MiniSparkline";
import TiltCard from "@/components/TiltCard";

/** 히어로 우측 글래스 위젯 클러스터 — 서비스 흐름(가점→근거→목표자금)을
 *  정지 이미지가 아니라 "살아있는 콘솔"로 미리 보여준다. 실데이터 없이 동작. */

const SPARK = [38, 42, 40, 47, 52, 50, 58, 63, 61, 70, 76];

export default function HeroShowcase() {
  const ringRef = useRef<SVGCircleElement>(null);

  // SVG 진행 링 — r=54, 둘레 ≈ 339.3. 74/84 ≈ 88%.
  const CIRC = 2 * Math.PI * 54;
  const pct = 74 / 84;

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
                  ref={ringRef}
                  cx="64"
                  cy="64"
                  r="54"
                  fill="none"
                  stroke="url(#ringGrad)"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={CIRC}
                  strokeDashoffset={CIRC * (1 - pct)}
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
                <li>무주택 기간 <b className="text-fg">7년</b> · +32점</li>
                <li>부양가족 <b className="text-fg">2명</b> · +15점</li>
                <li>청약통장 <b className="text-fg">24개월</b> · +17점</li>
              </ul>
            </div>
          </div>
        </Card>

        {/* 하단 행 — 근거 칩 + 목표자금 스파크라인 */}
        <div className="mt-3 grid grid-cols-5 gap-3">
          <Card variant="subtle" className="col-span-2 animate-rise p-4 [animation-delay:120ms]">
            <p className="flex items-center gap-1.5 font-mono-spec text-[10px] uppercase tracking-widest text-gilt">
              <FileText weight="fill" size={12} /> 근거
            </p>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              조문 <b className="text-fg">3건</b> 첨부
              <br />
              해석례 <b className="text-fg">2건</b> 인용
            </p>
          </Card>
          <Card variant="subtle" className="col-span-3 animate-rise p-4 [animation-delay:240ms]">
            <p className="font-mono-spec text-[10px] uppercase tracking-widest text-muted">
              목표 자금 추이
            </p>
            <div className="mt-2 flex items-end justify-between gap-2">
              <p className="font-display text-xl text-fg">
                <AnimatedNumber value={76} suffix="%" />
              </p>
              <MiniSparkline data={SPARK} color="accent" width={110} height={30} />
            </div>
          </Card>
        </div>
      </TiltCard>

      {/* 부유 배지 — 카드 밖에 떠 있는 '라이브' 신호 */}
      <div
        className="float-slow absolute -right-4 -top-4 flex items-center gap-1.5 rounded-full border border-line bg-[color-mix(in_srgb,var(--ink-1)_85%,transparent)] px-3 py-1.5 text-[11px] font-semibold text-fg shadow-[var(--shadow-1)] backdrop-blur-md"
        data-tour="hero-badge"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-positive" />
        실시간 공고 연동
      </div>
    </div>
  );
}
