"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "dark" | "light";
const STORAGE_KEY = "midas.theme";

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
}

const Ctx = createContext<ThemeCtx | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  // 마운트 시 <html>의 실제 클래스(인라인 스크립트가 적용해둔 값)와 동기화
  useEffect(() => {
    const current = document.documentElement.classList.contains("light")
      ? "light"
      : "dark";
    setTheme(current);
  }, []);

  const apply = (t: Theme) => {
    const root = document.documentElement;
    root.classList.remove("dark", "light");
    root.classList.add(t);
    localStorage.setItem(STORAGE_KEY, t);
    setTheme(t);
  };

  return (
    <Ctx.Provider
      value={{ theme, toggle: () => apply(theme === "dark" ? "light" : "dark") }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

// FOUC 방지: 하이드레이션 전에 <html>에 테마 클래스를 즉시 적용하는 인라인 스크립트.
export const themeInitScript = `(function(){try{var t=localStorage.getItem('${STORAGE_KEY}')||'dark';document.documentElement.classList.add(t);}catch(e){document.documentElement.classList.add('dark');}})();`;
