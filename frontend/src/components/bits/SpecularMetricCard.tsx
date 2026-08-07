"use client";

import { useRef, useState, MouseEvent, ReactNode } from "react";

interface SpecularMetricCardProps {
  children: ReactNode;
  glowColor?: "gold" | "emerald" | "rose" | "cyan";
  className?: string;
}

export default function SpecularMetricCard({
  children,
  glowColor = "gold",
  className = "",
}: SpecularMetricCardProps) {
  const divRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const colors = {
    gold: "rgba(212, 175, 96, 0.22)",
    emerald: "rgba(16, 185, 129, 0.22)",
    rose: "rgba(244, 63, 94, 0.22)",
    cyan: "rgba(6, 182, 212, 0.22)",
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!divRef.current) return;
    const rect = divRef.current.getBoundingClientRect();
    setPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={divRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setOpacity(1)}
      onMouseLeave={() => setOpacity(0)}
      className={`group relative overflow-hidden rounded-2xl border border-line-50/80 bg-surface/50 p-5 backdrop-blur-md transition-all duration-300 hover:border-accent/50 hover:shadow-[0_8px_30px_rgba(0,0,0,0.25)] ${className}`}
    >
      {/* Specular Light Cone */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300"
        style={{
          opacity,
          background: `radial-gradient(450px circle at ${pos.x}px ${pos.y}px, ${colors[glowColor]}, transparent 50%)`,
        }}
      />
      {/* Dynamic Specular Border Glow Highlight */}
      <div
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity duration-300 group-hover:opacity-100 border border-accent/30"
        style={{
          maskImage: `radial-gradient(180px circle at ${pos.x}px ${pos.y}px, black, transparent)`,
          WebkitMaskImage: `radial-gradient(180px circle at ${pos.x}px ${pos.y}px, black, transparent)`,
        }}
      />
      <div className="relative z-10">{children}</div>
    </div>
  );
}
