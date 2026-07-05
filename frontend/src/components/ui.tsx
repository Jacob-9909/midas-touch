import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  // soft-skill: 넉넉한 내부 여백으로 호흡감 확보.
  return <div className={`glass p-6 ${className}`}>{children}</div>;
}

export function PageTitle({
  title,
  subtitle,
  eyebrow,
}: {
  title: string;
  subtitle?: string;
  /** 헤딩 위 마이크로 라벨 (soft-skill 아이브로우 태그) */
  eyebrow?: string;
}) {
  // 큰 헤더에 그라디언트 텍스트는 지양(skill 9.A). 위계는 무게·크기로.
  // 골드는 아이브로우 태그/얇은 마커로만 사용.
  return (
    <div className="mb-10 animate-rise">
      {eyebrow && <span className="eyebrow mb-3">{eyebrow}</span>}
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="h-8 w-1 shrink-0 rounded-full bg-gradient-to-b from-accent-soft to-accent"
        />
        <h1 className="font-display text-[2rem] font-semibold leading-[1.1] tracking-tight text-fg sm:text-[2.6rem]">
          {title}
        </h1>
      </div>
      {subtitle && (
        <p className="mt-3 max-w-[60ch] pl-4 text-sm leading-relaxed text-muted">
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
      <span className="text-sm">{label}</span>
    </div>
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
