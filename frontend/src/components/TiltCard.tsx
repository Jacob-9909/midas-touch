"use client";

import { useRef, type ReactNode } from "react";
import { motion, useMotionValue, useSpring, useReducedMotion } from "motion/react";

/**
 * 마우스를 따라 기우는 3D 카드 — Neon Ledger §Motion.
 * useSpring 으로 물성감 있는 감속/복원을 구현하며, reduced-motion 에선 즉시 비활성.
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
  const reduce = useReducedMotion();
  const glareRef = useRef<HTMLDivElement>(null);

  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);

  const rotateX = useSpring(rawX, { stiffness: 240, damping: 22 });
  const rotateY = useSpring(rawY, { stiffness: 240, damping: 22 });

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    rawY.set((px - 0.5) * max * 2);
    rawX.set((0.5 - py) * max * 2);

    if (glareRef.current) {
      glareRef.current.style.opacity = "1";
      glareRef.current.style.background = `radial-gradient(420px circle at ${px * 100}% ${py * 100}%, var(--specular), transparent 65%)`;
    }
  };

  const onLeave = () => {
    rawX.set(0);
    rawY.set(0);
    if (glareRef.current) glareRef.current.style.opacity = "0";
  };

  if (reduce) {
    return <div className={`relative ${className}`}>{children}</div>;
  }

  return (
    <motion.div
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
      }}
      className={`relative will-change-transform ${className}`}
    >
      {/* 커서 따라다니는 스페큘러 광택 */}
      <div
        ref={glareRef}
        aria-hidden
        className="pointer-events-none absolute inset-0 z-10 rounded-[inherit] opacity-0 transition-opacity duration-300"
      />
      {children}
    </motion.div>
  );
}
