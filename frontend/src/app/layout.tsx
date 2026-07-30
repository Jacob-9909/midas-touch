import type { Metadata } from "next";
import { Geist, Geist_Mono, Cormorant_Garamond } from "next/font/google";
import "./globals.css";
import { UserProvider } from "@/lib/user-context";
import { ThemeProvider, themeInitScript } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";
import NavBar from "@/components/NavBar";
import AmbientBackground from "@/components/AmbientBackground";
import ClickSpark from "@/components/bits/ClickSpark";

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
              <ClickSpark sparkRadius={18} sparkCount={9} duration={480}>
                <NavBar />
                <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
                  {children}
                </main>
              </ClickSpark>
            </UserProvider>
          </ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
