"use client";

// 고령층 친화 모드(큰 글씨) 설정. theme.tsx와 같은 패턴 — localStorage 영속 +
// <html> 클래스 토글. 마운트 전에는 layout의 인라인 init 스크립트가 먼저 클래스를 복원해
// 첫 페인트부터 확대된 글씨로 보이게 한다(FOUC 방지).

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

interface A11ySettings {
  largeText: boolean;
}

const STORAGE_KEY = "midas.a11y";
const LARGE_TEXT_CLASS = "a11y-large-text";

interface A11yCtx {
  largeText: boolean;
  toggleLargeText: () => void;
}

const Ctx = createContext<A11yCtx | undefined>(undefined);

function readStored(): A11ySettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { largeText: false };
    const parsed = JSON.parse(raw) as Partial<A11ySettings>;
    return { largeText: parsed.largeText === true };
  } catch {
    return { largeText: false };
  }
}

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [largeText, setLargeText] = useState(false);

  // 마운트 시 localStorage에서 설정을 복원해 <html> 클래스와 상태를 동기화한다.
  useEffect(() => {
    const stored = readStored();
    document.documentElement.classList.toggle(LARGE_TEXT_CLASS, stored.largeText);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 1회 localStorage 복원(SSR엔 storage 없음 → effect가 정답)
    setLargeText(stored.largeText);
  }, []);

  const apply = (v: boolean) => {
    document.documentElement.classList.toggle(LARGE_TEXT_CLASS, v);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ largeText: v } satisfies A11ySettings));
    setLargeText(v);
  };

  return (
    <Ctx.Provider value={{ largeText, toggleLargeText: () => apply(!largeText) }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAccessibility() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAccessibility must be used within AccessibilityProvider");
  return ctx;
}

// FOUC 방지: 하이드레이션 전에 <html>에 큰 글씨 클래스를 즉시 적용하는 인라인 스크립트.
export const a11yInitScript = `(function(){try{var s=JSON.parse(localStorage.getItem('${STORAGE_KEY}')||'{}');if(s&&s.largeText===true){document.documentElement.classList.add('${LARGE_TEXT_CLASS}');}}catch(e){}})();`;
