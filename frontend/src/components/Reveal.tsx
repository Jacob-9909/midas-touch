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
      // soft-skill 5.C: 부드러운 blur 페이드-업 (물성감 있는 감속)
      initial={reduce ? false : { opacity: 0, y: 20, filter: "blur(6px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once, amount: 0.2 }}
      transition={{
        duration: 0.7,
        delay: reduce ? 0 : index * 0.07,
        ease: [0.32, 0.72, 0, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
