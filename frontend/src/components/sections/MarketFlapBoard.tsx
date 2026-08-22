"use client";

import SplitFlapText from "@/components/bits/SplitFlapText";

interface MarketFlapBoardProps {
  // 상위(page)에서 실제 시장 스냅샷으로 만든 라벨 목록.
  // 공항 안내판식 split-flap 이 지수/환율/금리를 번갈아 뒤집으며 표시한다.
  words: string[];
}

// 증시를 반영하는 split-flap 보드. 값 자체를 flap 문자로 흘려
// "정보가 방금 갱신됐다"는 감각을 물리적 동작으로 전달한다.
export default function MarketFlapBoard({ words }: MarketFlapBoardProps) {
  const safe = words.length ? words : ["MARKET SYNC", "SIGNAL LIVE"];

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-line bg-[var(--ink-1)] p-6">
      <div className="flex items-center gap-2 font-mono-spec text-[10px] uppercase tracking-widest text-accent">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent shadow-[0_0_8px_var(--accent)]" />
        LIVE MARKET BOARD
      </div>
      <SplitFlapText
        words={safe}
        charset="alphanumeric"
        fontSize={40}
        gap={5}
        tileColor="#0d1320"
        textColor="#e8c86b"
        tileRadius={6}
        flipsPerChar={9}
        cycleDelay={2600}
        padTo={16}
      />
    </div>
  );
}
