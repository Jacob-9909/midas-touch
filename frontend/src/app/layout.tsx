import type { Metadata } from "next";
import { Inter, Geist_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import "pretendard/dist/web/variable/pretendardvariable.css";
import { ThemeProvider, themeInitScript } from "@/lib/theme";
import { AccessibilityProvider, a11yInitScript } from "@/lib/accessibility";
import { ToastProvider } from "@/lib/toast";
import NavBar from "@/components/NavBar";
import SiteFooter from "@/components/SiteFooter";
import { UserProvider } from "@/lib/user-context";

// 본문·버튼·캡션은 Inter 400/600. 디스플레이는 Space Grotesk — 기하학적 그로테스크로
// 랜딩 헤드라인의 톤을 끌어올린다(Neon Ledger §Typography).
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
const spaceGrotesk = Space_Grotesk({
  variable: "--font-space",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});
// 숫자 정렬용 모노는 유지한다 — 금액·가점·개월수가 표에서 자릿수를 맞춰야 한다.
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Midas Touch · AI 금융 보안 비서",
  description:
    "피싱·환각·틀린 세법 답변을 한 번에 잡는 AI 금융 보안 비서. 사기 문자 검증·연령별 행동 요령, 법령 근거 기반 결정론 세금 계산, 청약·자산 상담을 하나의 대화로. 정보 제공 서비스(투자·세무 자문 아님).",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className="light h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <script dangerouslySetInnerHTML={{ __html: a11yInitScript }} />
      </head>
      <body className={`${inter.variable} ${spaceGrotesk.variable} ${geistMono.variable} min-h-full`}>
        <ThemeProvider>
          <AccessibilityProvider>
            <ToastProvider>
              <UserProvider>
                <NavBar />
                {/* 컨테이너는 각 페이지가 소유한다 — 히어로 밴드가 전체폭으로 깔려야 하기 때문. */}
                <main>
                  {children}
                </main>
                {/* 법적 고지 — 세무사법(조세 자문 독점)·자본시장법(무등록 투자자문) 대비.
                    페이지마다 복붙하지 않고 레이아웃에서 한 번만 깔아 모든 화면에 동일하게 노출한다.
                    챗 같은 앱형 레이아웃에서는 SiteFooter 가 스스로 숨어 페이지 스크롤을 만들지 않는다. */}
                <SiteFooter />
              </UserProvider>
            </ToastProvider>
          </AccessibilityProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
