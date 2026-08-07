import type { ReactNode } from "react";
import BlurText from "@/components/bits/BlurText";
import DecryptedText from "@/components/bits/DecryptedText";
import CountUp from "@/components/bits/CountUp";

export function Card({
  children,
  className = "",
  variant = "editorial",
}: {
  children: ReactNode;
  className?: string;
  variant?: "editorial" | "glass" | "subtle" | "interactive";
}) {
  const variantStyles = {
    editorial: "glass border-line-50 shadow-soft",
    glass: "glass border-line/60 shadow-md",
    subtle: "bg-surface/30 border border-line/40 rounded-xl",
    interactive: "glass border-line-50 lift cursor-pointer",
  };
  return <div className={`${variantStyles[variant]} p-5 sm:p-6 ${className}`}>{children}</div>;
}

export function PageTitle({
  title,
  subtitle,
  eyebrow,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: string;
}) {
  return (
    <div className="mb-10 animate-rise space-y-3">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <div className="flex items-baseline gap-4">
        <span
          aria-hidden
          className="h-7 w-0.5 shrink-0 bg-accent shadow-[0_0_12px_var(--accent)]"
        />
        {/* 제목은 단어 단위 블러 인. 모든 페이지의 첫인상이라 여기만 모션을 크게 준다. */}
        <BlurText
          as="h1"
          text={title}
          animateBy="words"
          delay={90}
          className="font-display text-[2.2rem] font-normal leading-[1.05] tracking-tight text-fg sm:text-[3.1rem]"
        />
      </div>
      {subtitle && (
        <p className="max-w-[64ch] pl-5 text-xs leading-relaxed text-muted font-sans border-l border-line/40">
          {subtitle}
        </p>
      )}
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 font-mono-spec text-[10px] font-semibold uppercase tracking-[0.25em] text-accent flex items-center gap-2">
      <span className="h-1.5 w-1.5 rounded-full bg-accent shadow-[0_0_6px_var(--accent)]" />
      {children}
    </h2>
  );
}

export function StatusBadge({
  label,
  tone = "gold",
}: {
  label: string;
  tone?: "positive" | "negative" | "gold" | "neutral";
}) {
  const toneClasses = {
    positive: "status-indicator-positive",
    negative: "status-indicator-negative",
    gold: "status-indicator-gold",
    neutral: "text-muted bg-surface/50 border-line/40",
  };
  return <span className={`status-indicator ${toneClasses[tone]}`}>{label}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** 회전 스피너. 크기·색은 className으로 (예: "h-4 w-4 text-accent"). border-current를 쓴다. */
export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="로딩 중"
      className={`inline-block shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

/** 로딩 중 영역 표시 — 스피너 + "로딩중입니다…" 라벨(스켈레톤 대신 진행감을 준다). */
export function LoadingBlock({
  label = "로딩중입니다…",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-3 py-12 text-muted ${className}`}
    >
      <Spinner className="h-7 w-7 text-accent" />
      {/* 데이터 피드가 복호화되는 듯한 스크램블 — 대기 시간을 "처리 중"으로 읽히게 만든다.
          sequential이라 글자가 왼쪽부터 순서대로 확정된다. */}
      <DecryptedText
        text={label}
        animateOn="view"
        sequential
        speed={38}
        className="text-sm text-muted"
        encryptedClassName="text-sm text-accent/70"
        parentClassName="font-mono-spec"
      />
    </div>
  );
}

/**
 * 스크롤 진입 시 0에서 목표값까지 올라가는 수치.
 * 금융 콘솔에서 체감이 가장 큰 모션이라 지표·금액 전반에 쓴다.
 * 표시 형식은 호출부가 prefix/suffix로 정한다 (예: suffix="원", suffix="%").
 */
export function AnimatedNumber({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  separator = ",",
  duration = 1.4,
  className = "",
}: {
  value: number | null | undefined;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  separator?: string;
  duration?: number;
  className?: string;
}) {
  if (value == null) return <span className={className}>-</span>;
  return (
    <span className={className}>
      {prefix}
      <CountUp
        to={decimals > 0 ? Number(value.toFixed(decimals)) : Math.round(value)}
        duration={duration}
        separator={separator}
      />
      {suffix}
    </span>
  );
}

/**
 * 큰 금액을 억/만으로 축약해 애니메이션한다 (fmtKRWShort의 모션 버전).
 * 단위는 고정 텍스트로 두고 숫자만 카운트업해야 단위가 흔들리지 않는다.
 */
export function AnimatedKRWShort({
  value,
  className = "",
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value == null) return <span className={className}>-</span>;
  if (value >= 1e8) {
    const scaled = value / 1e8;
    // 1.2억처럼 소수 한 자리까지만. 딱 떨어지면 정수로.
    const decimals = value % 1e8 === 0 ? 0 : 1;
    return <AnimatedNumber value={scaled} decimals={decimals} suffix="억" className={className} />;
  }
  if (value >= 1e4) {
    return <AnimatedNumber value={Math.round(value / 1e4)} suffix="만" className={className} />;
  }
  return <AnimatedNumber value={value} className={className} />;
}

export function fmtKRW(n: number | null | undefined): string {
  if (n == null) return "-";
  return new Intl.NumberFormat("ko-KR").format(n) + "원";
}

/** 큰 금액을 억/만 단위 한글로 축약 (예: 120000000 → 1.2억) */
export function fmtKRWShort(n: number | null | undefined): string {
  if (n == null) return "-";
  if (n >= 1e8) return `${(n / 1e8).toFixed(n % 1e8 === 0 ? 0 : 1)}억`;
  if (n >= 1e4) return `${Math.round(n / 1e4).toLocaleString()}만`;
  return n.toLocaleString();
}
