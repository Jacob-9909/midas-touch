"use client";

import { useEffect } from "react";
import Link from "next/link";

// 세그먼트 에러 바운더리 — 렌더 중 예외가 던져지면 이 화면이 폴백으로 뜬다.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // 콘솔 로깅. 여기서 에러 리포팅 서비스로 전달하도록 확장한다.
    console.error(error);
  }, [error]);

  return (
    <div
      role="alert"
      className="glass mx-auto my-24 max-w-md rounded-xl border border-line/60 p-8 text-center shadow-soft"
    >
      <span className="eyebrow">ERROR</span>
      <h1 className="mt-3 font-display text-3xl tracking-tight text-fg">
        문제가 발생했어요
      </h1>
      <p className="mt-3 text-xs leading-relaxed text-muted">
        페이지를 불러오는 동안 예상치 못한 오류가 생겼습니다.
        잠시 후 다시 시도해 주세요.
      </p>
      {error.digest && (
        <p className="mt-2 font-mono-spec text-[10px] uppercase tracking-widest text-muted/70">
          DIGEST · {error.digest}
        </p>
      )}
      <div className="mt-6 flex items-center justify-center gap-3">
        <button
          onClick={reset}
          className="rounded-full border border-accent/40 bg-accent/20 px-4 py-2 font-mono-spec text-xs text-accent shadow-md transition hover:bg-accent/30"
        >
          다시 시도
        </button>
        <Link
          href="/"
          className="rounded-full border border-line bg-surface/60 px-4 py-2 font-mono-spec text-xs text-fg transition hover:border-accent/40"
        >
          홈으로
        </Link>
      </div>
    </div>
  );
}
