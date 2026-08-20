import type { Metadata } from "next";
import { Geist, Geist_Mono, Cormorant_Garamond } from "next/font/google";
import "./globals.css";
import { UserProvider } from "@/lib/user-context";
import { ThemeProvider, themeInitScript } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";
import NavBar from "@/components/NavBar";
import AmbientBackground from "@/components/AmbientBackground";
import ClickSpark from "@/components/bits/ClickSpark";
import TargetCursor from "@/components/bits/TargetCursor";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const display = Cormorant_Garamond({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Midas Touch · AI 자산관리 & 투자 에디토리얼 콘솔",
  description: "금융 에이전트, 파인튜닝셋, 지식그래프 통합 웹 콘솔",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className="dark h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} ${display.variable} min-h-full`}>
        <ThemeProvider>
          <ToastProvider>
            <UserProvider>
              {/* 전역 골드 앰비언트 — 앱 전체에서 유일한 WebGL 캔버스 */}
              <AmbientBackground />
              {/* 코너 브래킷 커서 — .cursor-target 요소에 스냅. 데스크톱 전용(내부에서 터치 무시) */}
              <TargetCursor
                targetSelector=".cursor-target"
                cursorColor="#d4af37"
                cursorColorOnTarget="#e8c86b"
                hideDefaultCursor={false}
              />
              <ClickSpark sparkRadius={18} sparkCount={9} duration={480}>
                <NavBar />
                <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
                  {children}
                </main>
                {/* 법적 고지 — 세무사법(조세 자문 독점)·자본시장법(무등록 투자자문) 대비.
                    페이지마다 복붙하지 않고 레이아웃에서 한 번만 깔아 모든 화면에 동일하게 노출한다. */}
                <footer className="mx-auto max-w-6xl px-4 pb-10 sm:px-6">
                  <p className="rounded-xl border border-line/60 bg-[var(--ink-1)]/60 px-4 py-3 text-[11px] leading-relaxed text-muted">
                    <span className="font-semibold text-fg/80">고지</span> · 본 서비스가 제공하는 주가
                    전망·세금 계산·자산배분 결과는 <span className="text-fg/80">정보 제공 및 시뮬레이션
                    목적이며, 세무 자문이나 투자 자문이 아닙니다.</span> AI 생성 결과에는 오류가 있을 수
                    있으므로 실제 신고·투자 결정 전에 세무사·투자권유자문인력 등 전문가의 확인이 필요하며,
                    투자 판단의 최종 책임은 이용자 본인에게 있습니다.
                  </p>
                </footer>
              </ClickSpark>
            </UserProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
