"use client";

import DepthCarousel from "@/components/bits/DepthCarousel";

// 투자 성향 페르소나를 3D 깊이 캐러셀로 훑어본다.
// 이미지는 테마에 맞춘 골드/네이비 그라디언트 타일(로컬 asset).
const PERSONAS = [
  { image: "/hero/persona-1.svg", alt: "안정형 투자자" },
  { image: "/hero/persona-2.svg", alt: "균형형 투자자" },
  { image: "/hero/persona-3.svg", alt: "성장형 투자자" },
  { image: "/hero/persona-4.svg", alt: "공격형 투자자" },
  { image: "/hero/persona-5.svg", alt: "인컴형 투자자" },
];

export default function PersonaCarousel() {
  return (
    <DepthCarousel
      items={PERSONAS}
      cardWidth={280}
      cardHeight={360}
      tint="#04060a"
      tilt={20}
      autoplay
      autoplayDelay={3600}
      className="cursor-target"
    />
  );
}
