import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`glass p-5 ${className}`}>{children}</div>;
}

export function PageTitle({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  // 큰 헤더에 그라디언트 텍스트는 지양(skill 9.A). 위계는 무게·색으로.
  // 골드는 헤드라인 옆 얇은 마커로만 사용.
  return (
    <div className="mb-8 animate-rise">
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="h-7 w-1 shrink-0 rounded-full bg-gradient-to-b from-gold-soft to-gold"
        />
        <h1 className="font-display text-3xl font-semibold leading-tight text-fg sm:text-4xl">
          {title}
        </h1>
      </div>
      {subtitle && (
        <p className="mt-2 max-w-[65ch] pl-4 text-sm leading-relaxed text-muted">
          {subtitle}
        </p>
      )}
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 text-xs font-medium uppercase tracking-[0.18em] text-muted">
      {children}
    </h2>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
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
