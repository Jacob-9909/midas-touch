"use client";

import PixelSwap from "@/components/bits/PixelSwap";

// 호버하면 픽셀이 흩어지며 두 상태가 교체된다:
// "내 질문" → "근거로 채운 답변". 상담 에이전트의 한 문장을 동작으로 보여준다.
function Face({
  tag,
  title,
  body,
  tone,
}: {
  tag: string;
  title: string;
  body: string;
  tone: "ask" | "answer";
}) {
  const bg =
    tone === "ask"
      ? "bg-[var(--ink-2)]"
      : "bg-[color-mix(in_srgb,var(--accent)_10%,var(--ink-1))]";
  return (
    <div className={`flex h-full w-full flex-col justify-between p-6 ${bg}`}>
      <span className="font-mono-spec text-[10px] uppercase tracking-widest text-accent">
        {tag}
      </span>
      <div>
        <h3 className="font-display text-xl font-semibold text-fg">{title}</h3>
        <p className="mt-2 text-xs leading-relaxed text-muted">{body}</p>
      </div>
    </div>
  );
}

export default function PixelSwapCard() {
  return (
    <PixelSwap
      trigger="hover"
      pixelSize={12}
      pattern="center"
      duration={0.5}
      aspectRatio="16 / 9"
      className="cursor-target rounded-lg border border-line"
      firstContent={
        <Face
          tag="Q · 사용자"
          title="지금 내 자산배분 괜찮아?"
          body="또래 대비 현금 비중이 높은지, 세금은 어떻게 되는지 한 번에 묻습니다."
          tone="ask"
        />
      }
      secondContent={
        <Face
          tag="A · 에이전트"
          title="근거로 답합니다"
          body="유사 투자자 벤치마크 · 세법 조항 · 실시간 시장 시그널을 인용해 전략을 제시합니다."
          tone="answer"
        />
      }
    />
  );
}
