import { ReactNode } from "react";

interface SpecularMetricCardProps {
  children: ReactNode;
  /** 이전 버전의 마우스 추적 광원 색. 디자인 문서(docs/DESIGN-revolut.md §Elevation)가
   * 카드 글로우를 금지하므로 더는 시각 효과에 쓰이지 않는다 — 호출부 호환만 위해 남긴다. */
  glowColor?: "gold" | "emerald" | "rose" | "cyan";
  className?: string;
}

/** 지표 카드 — 문서 규격(20px 카드 + 헤어라인 + 그림자 없음).
 * 깊이는 표면 명도 차이로만 만들고, 반응은 테두리 색으로만 낸다. */
export default function SpecularMetricCard({
  children,
  className = "",
}: SpecularMetricCardProps) {
  return (
    <div
      className={`group relative rounded-[var(--r-lg)] border border-line-50/80 bg-[var(--ink-1)] p-5 transition-colors duration-200 hover:border-accent/50 ${className}`}
    >
      {children}
    </div>
  );
}
