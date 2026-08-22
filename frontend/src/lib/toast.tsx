"use client";

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import {
  CheckCircle,
  XCircle,
  Info,
  type IconProps,
} from "@phosphor-icons/react";

type ToastKind = "success" | "error" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastCtx {
  toast: (message: string, kind?: ToastKind) => void;
}

const Ctx = createContext<ToastCtx | undefined>(undefined);

const ICONS: Record<ToastKind, ComponentType<IconProps>> = {
  success: CheckCircle,
  error: XCircle,
  info: Info,
};
const ACCENT: Record<ToastKind, string> = {
  success: "text-positive",
  error: "text-negative",
  info: "text-accent",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, 4000);
  }, []);

  return (
    <Ctx.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed top-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col items-center gap-2.5 w-auto max-w-[92vw]">
        {toasts.map((t) => {
          const Icon = ICONS[t.kind];
          return (
            <div
              key={t.id}
              className="toast-enter pointer-events-auto flex items-center gap-3 px-5 py-3 text-xs sm:text-sm font-mono-spec bg-[var(--ink-2)] border border-line text-fg rounded-[var(--r-md)] transition-all duration-300 animate-rise border-l-4 border-l-accent"
            >
              <Icon
                weight="fill"
                size={20}
                className={`shrink-0 ${ACCENT[t.kind]}`}
              />
              <span className="font-bold text-fg tracking-tight">{t.message}</span>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx.toast;
}
