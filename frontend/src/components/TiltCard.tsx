"use client";

import { useRef, type ReactNode } from "react";

/**
 * 마우스를 따라 기우는 3D 카드 — Neon Ledger §Motion.
 * transform 만 쓰므로 레이아웃 스래싱이 없고, reduced-motion 에선 즉시 비활성.
 */
export default function TiltCard({
  children,
  className = "",
  max = 7,
}: {
  children: ReactNode;
  className?: string;
  /** 최대 기울기(도). */
  max?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const glareRef = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    el.style.transform = `perspective(900px) rotateY(${(px - 0.5) * max * 2}deg) rotateX(${(0.5 - py) * max * 2}deg) translateZ(0)`;
    if (glareRef.current) {
      glareRef.current.style.opacity = "1";
      glareRef.current.style.background = `radial-gradient(420px circle at ${px * 100}% ${py * 100}%, var(--specular), transparent 65%)`;
    }
  };

  const onLeave = () => {
    const el = ref.current;
    if (el) el.style.transform = "";
    if (glareRef.current) glareRef.current.style.opacity = "0";
  };

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      className={`relative transition-transform duration-300 ease-[var(--ease-out)] will-change-transform ${className}`}
    >
      {/* 커서 따라다니는 스페큘러 광택 */}
      <div
        ref={glareRef}
        aria-hidden
        className="pointer-events-none absolute inset-0 z-10 rounded-[inherit] opacity-0 transition-opacity duration-300"
      />
      {children}
    </div>
  );
}
