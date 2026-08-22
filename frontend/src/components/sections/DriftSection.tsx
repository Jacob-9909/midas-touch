"use client";

import DriftWall from "@/components/bits/DriftWall";

// 배경에서 타일이 원근을 타고 흘러가는 앰비언트 월.
// 실물 이미지 대신 테마 그라디언트 타일을 여러 장 반복해 질감을 만든다.
const TILES = [
  { image: "/hero/wall-1.svg", title: "GOLD" },
  { image: "/hero/wall-2.svg", title: "BOND" },
  { image: "/hero/wall-3.svg", title: "FX" },
  { image: "/hero/wall-4.svg", title: "EQUITY" },
  { image: "/hero/wall-2.svg", title: "RATE" },
  { image: "/hero/wall-1.svg", title: "OIL" },
  { image: "/hero/wall-3.svg", title: "CRYPTO" },
  { image: "/hero/wall-4.svg", title: "INDEX" },
];

export default function DriftSection() {
  return (
    <div className="relative h-[420px] w-full overflow-hidden rounded-lg border border-line">
      <DriftWall
        items={TILES}
        columns={4}
        tileHeight={220}
        speed={22}
        tilt={16}
        turn={-14}
        overlayColor="rgba(4,6,10,0.35)"
        pauseOnHover
      />
    </div>
  );
}
