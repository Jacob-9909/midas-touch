"use client";

// 선택된 유저(uuid)를 앱 전역에서 공유한다. localStorage에 영속.
// AUTH_ENABLED(NEXT_PUBLIC_AUTH_ENABLED=true)면 로그인으로 신원을 정하고, 토큰 없으면 /login으로 보낸다.
// 끄면 기존 페르소나 스위처(데모)로 동작 — 하위호환.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";

import { apiLogin, clearToken, getToken } from "./api";

const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

interface SelectedUser {
  uuid: string;
  label: string;
}

interface UserContextValue {
  selected: SelectedUser | null;
  setSelected: (u: SelectedUser | null) => void;
  authEnabled: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const UserContext = createContext<UserContextValue | undefined>(undefined);
const STORAGE_KEY = "midas.selectedUser";

export function UserProvider({ children }: { children: ReactNode }) {
  const [selected, setSelectedState] = useState<SelectedUser | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        // 마운트 1회 localStorage 복원. 서버엔 localStorage 없어 lazy init 불가 → effect가 정답.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSelectedState(JSON.parse(raw));
      } catch {
        /* ignore */
      }
    }
  }, []);

  // 인증 가드: 켜져 있고 토큰이 없으면 로그인 페이지로 밀어낸다.
  useEffect(() => {
    if (!AUTH_ENABLED) return;
    if (!getToken() && pathname !== "/login") router.replace("/login");
  }, [pathname, router]);

  const setSelected = (u: SelectedUser | null) => {
    setSelectedState(u);
    if (u) localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
    else localStorage.removeItem(STORAGE_KEY);
  };

  const login = async (email: string, password: string) => {
    const r = await apiLogin(email, password); // 토큰은 apiLogin이 localStorage에 저장
    setSelected({ uuid: r.user_uuid, label: email });
  };

  const logout = () => {
    clearToken();
    setSelected(null);
    if (AUTH_ENABLED) router.replace("/login");
  };

  return (
    <UserContext.Provider
      value={{ selected, setSelected, authEnabled: AUTH_ENABLED, login, logout }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useSelectedUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useSelectedUser must be used within UserProvider");
  return ctx;
}
