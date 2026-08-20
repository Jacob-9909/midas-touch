"use client";

import { useRouter } from "next/navigation";
import ScrollExpand from "@/components/bits/ScrollExpand";
import RotatingText from "@/components/bits/RotatingText";
import SpecularButton from "@/components/bits/SpecularButton";

// 스크롤로 프레임이 풀스크린까지 확장되는 시네마틱 인트로.
// useWindowScroll=false → 자기 영역 안에서만 스크롤을 소비하므로
// 데이터 콘솔 본문을 통째로 가로채지 않는다(높이 고정형 히어로).
const KEYWORDS = ["자산배분", "세법 근거", "또래 벤치마크", "시장 시그널", "지식그래프"];

export default function HeroIntro() {
  const router = useRouter();

  return (
    <section className="relative h-[82vh] w-full overflow-hidden rounded-lg border border-line">
      <ScrollExpand
        src="/hero/molten.svg"
        mediaType="image"
        alt="Midas Touch molten gold hero"
        title="MIDAS TOUCH"
        scrollHint="스크롤하여 콘솔로 진입 ↓"
        startWidth={38}
        startHeight={54}
        startRadius={20}
        endRadius={12}
        mediaZoom={1.4}
        scrollDistance={1.15}
        holdDistance={0.3}
        overlayScrim={0.55}
      >
        {/* 프레임이 다 열린 뒤 떠오르는 오버레이 — 회전 키워드 + CTA */}
        <div className="flex flex-col items-center gap-6 px-6">
          <div className="flex items-center gap-2 font-display text-2xl font-semibold text-white sm:text-4xl">
            <span className="text-white/80">나와 닮은 투자자의</span>
            <RotatingText
              texts={KEYWORDS}
              rotationInterval={2200}
              staggerDuration={0.02}
              splitBy="characters"
              mainClassName="rounded-md bg-accent/90 px-3 py-1 text-[#04060a]"
              elementLevelClassName="font-bold"
            />
          </div>
          <p className="max-w-xl text-center text-sm leading-relaxed text-white/70">
            유사 투자자의 포트폴리오를 벤치마크로 대조하고, 세법·시장·지식그래프를
            근거로 맞춤형 전략을 제시하는 AI 어시스턴트 콘솔.
          </p>
          <div className="cursor-target flex items-center gap-4">
            <SpecularButton
              size="md"
              tint="#d4af37"
              tintOpacity={0.9}
              lineColor="#e8c86b"
              baseColor="#1a1608"
              textColor="#f8f2df"
              onClick={() => router.push("/chat")}
            >
              에이전트 상담 시작 →
            </SpecularButton>
            <SpecularButton
              size="md"
              tint="#7c8598"
              tintOpacity={0.5}
              lineColor="#aab3c4"
              baseColor="#0d1320"
              textColor="#e7ecf5"
              onClick={() => router.push("/stocks")}
            >
              주식분석 랩
            </SpecularButton>
          </div>
        </div>
      </ScrollExpand>
    </section>
  );
}
