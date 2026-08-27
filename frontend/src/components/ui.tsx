import type { ComponentPropsWithoutRef, ReactNode } from "react";
import DecryptedText from "@/components/bits/DecryptedText";
import CountUp from "@/components/bits/CountUp";

export function Card({
  children,
  className = "",
  variant = "editorial",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  variant?: "editorial" | "glass" | "subtle" | "interactive";
  // 나머지 div 속성은 그대로 통과시킨다(가이드 투어의 data-tour 앵커 등).
} & Omit<ComponentPropsWithoutRef<"div">, "className" | "children">) {
  const variantStyles = {
    editorial: "glass border-line-50 shadow-soft",
    glass: "glass border-line/60",
    subtle: "bg-surface/30 border border-line/40 rounded-xl",
    interactive: "glass border-line-50 lift cursor-pointer",
  };
  return (
    <div className={`${variantStyles[variant]} p-5 sm:p-6 ${className}`} {...rest}>
      {children}
    </div>
  );
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
    // 문서 §Typography: 디스플레이는 weight 500 · lineHeight 1.0 · 큰 음수 자간.
    // 골드 세로바와 발광은 뺐다 — 어센트는 도장처럼 드물게만 찍는다.
    <div className="mb-12 space-y-5">
      {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      <h1 className="font-display max-w-3xl text-[clamp(2.25rem,5.5vw,3.75rem)] text-fg break-keep">
        {title}
      </h1>
      {subtitle && (
        <p className="max-w-3xl text-[1.0625rem] leading-[1.56] text-muted break-keep">{subtitle}</p>
      )}
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 font-mono-spec text-[10px] font-semibold uppercase tracking-[0.25em] text-accent flex items-center gap-2">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
      {children}
    </h2>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

/** 회전 스피너. 크기·색은 className으로 (예: "h-4 w-4 text-accent"). border-current를 쓴다.
 *  700ms — 실제 로딩 시간이 같아도 빨리 도는 스피너가 더 빨리 로드된 '느낌'을 준다. */
export function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="로딩 중"
      className={`inline-block shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent [animation-duration:700ms] ${className}`}
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
