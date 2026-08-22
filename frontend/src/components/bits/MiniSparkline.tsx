"use client";

interface MiniSparklineProps {
  data: number[];
  color?: "positive" | "negative" | "accent";
  width?: number;
  height?: number;
  className?: string;
}

export default function MiniSparkline({
  data,
  color = "positive",
  width = 80,
  height = 24,
  className = "",
}: MiniSparklineProps) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((val, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const colorHex = {
    positive: "var(--positive)",
    negative: "var(--negative)",
    accent: "var(--accent)",
  }[color];

  return (
    <svg
      width={width}
      height={height}
      className={`overflow-visible ${className}`}
      aria-hidden="true"
    >
      <polyline
        fill="none"
        stroke={colorHex}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}
