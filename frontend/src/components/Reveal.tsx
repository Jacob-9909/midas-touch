"use client";

// 스크롤 진입 시 페이드·상승 (skill 5.C). prefers-reduced-motion 시 즉시 표시.
// window scroll 리스너 금지(skill 5.D) → motion whileInView 사용.

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

interface RevealProps {
  children: ReactNode;
  className?: string;
  /** 스태거 순번 (0,1,2…), 60ms 간격으로 지연 */
  index?: number;
  /** 한 번만 재생할지 여부 */
  once?: boolean;
}

export function Reveal({
  children,
  className = "",
  index = 0,
  once = true,
}: RevealProps) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once, amount: 0.2 }}
      transition={{
        duration: 0.5,
        delay: reduce ? 0 : index * 0.06,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
