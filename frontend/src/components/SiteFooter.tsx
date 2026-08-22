"use client";

/** 법적 고지 푸터.
 *
 * 챗 화면은 뷰포트를 꽉 채우는 앱형 레이아웃이라 페이지 스크롤이 생기면 안 되지만,
 * 이 푸터가 항상 main 아래 깔리면 챗에서만큼은 어김없이 스크롤이 생긴다.
 * 그래서 라우트별로 노출 여부를 여기서 결정한다(고지 자체는 챗 입력창 위 안내로 커버).
 */

import { usePathname } from "next/navigation";

/** 푸터를 숨길 앱형 라우트 */
const FULLSCREEN_ROUTES = ["/chat"];

export default function SiteFooter() {
  const pathname = usePathname();
  if (FULLSCREEN_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`))) {
    return null;
  }

  return (
    <footer className="mx-auto w-full max-w-[1200px] px-6 pb-16 pt-20">
      <p className="rounded-[var(--r-md)] border border-line px-4 py-3 text-xs leading-relaxed text-muted">
        <span className="font-semibold text-fg/80">고지</span> · 본 서비스가 제공하는 주가
        전망·세금 계산·자산배분 결과는 <span className="text-fg/80">정보 제공 및 시뮬레이션
        목적이며, 세무 자문이나 투자 자문이 아닙니다.</span> AI 생성 결과에는 오류가 있을 수
        있으므로 실제 신고·투자 결정 전에 세무사·투자권유자문인력 등 전문가의 확인이 필요하며,
        투자 판단의 최종 책임은 이용자 본인에게 있습니다.
      </p>
      <p className="mt-3 text-center text-[11px] text-muted">
        © {new Date().getFullYear()} Midas Touch
      </p>
    </footer>
  );
}
