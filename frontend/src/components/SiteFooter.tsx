"use client";

/** 법적 고지 푸터.
 *
 * 챗 화면은 뷰포트를 꽉 채우는 앱형 레이아웃이라 페이지 스크롤이 생기면 안 되지만,
 * 이 푸터가 항상 main 아래 깔리면 챗에서만큼은 어김없이 스크롤이 생긴다.
 * 그래서 라우트별로 노출 여부를 여기서 결정한다(고지 자체는 챗 입력창 위 안내로 커버).
 */

import Link from "next/link";
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
      <div className="mt-4 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted">
        <Link href="/" className="hover:text-fg transition-colors">홈</Link>
        <Link href="/chat" className="hover:text-fg transition-colors">챗봇</Link>
        <Link href="/security" className="hover:text-fg transition-colors">보안 비서</Link>
        <Link href="/cheongyak" className="hover:text-fg transition-colors">청약 공고</Link>
        <Link href="/simulator" className="hover:text-fg transition-colors">자금 시뮬레이터</Link>
        <Link href="/me" className="hover:text-fg transition-colors">내 정보</Link>
        <Link href="/tax-rates" className="hover:text-fg transition-colors">세율 인입</Link>
        <Link href="/graph" className="hover:text-fg transition-colors">지식그래프</Link>
        <Link href="/stocks" className="hover:text-fg transition-colors">주식 분석</Link>
        <span className="text-line">|</span>
        <Link href="/login" className="text-accent font-semibold hover:underline">체험 계정 로그인</Link>
      </div>
      <p className="mt-3 text-center text-[11px] text-muted">
        © {new Date().getFullYear()} Midas Touch · 2026 금융 AI Challenge 출품작
      </p>
    </footer>
  );
}
