import type { Metadata } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider, themeInitScript } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";
import NavBar from "@/components/NavBar";
import AmbientBackground from "@/components/AmbientBackground";
import ClickSpark from "@/components/bits/ClickSpark";

// 문서 §Typography: 본문·버튼·캡션은 Inter 400/600. 디스플레이도 Aeonik Pro 대체로
// Inter 를 쓰되(문서가 지정한 대체 경로) 500 weight + 음수 자간으로 조인다.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
// 숫자 정렬용 모노는 유지한다 — 금액·가점·개월수가 표에서 자릿수를 맞춰야 한다.
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Midas Touch · 청약·자금마련 AI 콘솔",
  description:
    "무주택 사회초년생을 위한 청약 상담·청약가점 계산·자금마련 타임라인 시뮬레이터. GraphRAG 근거 기반 정보 제공 서비스(투자·세무 자문 아님).",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className="light h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${inter.variable} ${geistMono.variable} min-h-full`}>
        <ThemeProvider>
          <ToastProvider>
              {/* 전역 골드 앰비언트 — 앱 전체에서 유일한 WebGL 캔버스 */}
              <AmbientBackground />
              <ClickSpark sparkRadius={18} sparkCount={9} duration={480}>
                <NavBar />
                {/* 컨테이너는 각 페이지가 소유한다 — 랜딩의 검정 히어로 밴드가 전체폭으로 깔려야 하기 때문. */}
                <main>
                  {children}
                </main>
                {/* 법적 고지 — 세무사법(조세 자문 독점)·자본시장법(무등록 투자자문) 대비.
                    페이지마다 복붙하지 않고 레이아웃에서 한 번만 깔아 모든 화면에 동일하게 노출한다. */}
                <footer className="mx-auto max-w-[1200px] px-6 pb-16 pt-20">
                  <p className="rounded-xl border border-line/60 bg-[var(--ink-1)]/60 px-4 py-3 text-[11px] leading-relaxed text-muted">
                    <span className="font-semibold text-fg/80">고지</span> · 본 서비스가 제공하는 주가
                    전망·세금 계산·자산배분 결과는 <span className="text-fg/80">정보 제공 및 시뮬레이션
                    목적이며, 세무 자문이나 투자 자문이 아닙니다.</span> AI 생성 결과에는 오류가 있을 수
                    있으므로 실제 신고·투자 결정 전에 세무사·투자권유자문인력 등 전문가의 확인이 필요하며,
                    투자 판단의 최종 책임은 이용자 본인에게 있습니다.
                  </p>
                </footer>
              </ClickSpark>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
