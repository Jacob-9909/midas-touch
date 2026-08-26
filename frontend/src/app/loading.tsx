import { Skeleton } from "@/components/ui";

// 라우트 세그먼트 로딩 폴백 — 페이지 골격을 스켈레톤으로 먼저 보여준다.
export default function Loading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="로딩 중"
      className="animate-rise space-y-6 py-8"
    >
      {/* 제목 자리 */}
      <div className="space-y-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-9 w-72 max-w-full" />
      </div>
      {/* 본문 카드 자리 */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-36 rounded-xl" />
        <Skeleton className="h-36 rounded-xl" />
      </div>
      <Skeleton className="h-52 rounded-xl" />
    </div>
  );
}
