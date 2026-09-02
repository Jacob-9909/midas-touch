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
  // 인증 켜짐이면 토큰 확인 전까지 자식(페이지)을 그리지 않는다. 그리지 않으면 홈 화면의
  // GuideTour(가이드 스포트라이트)가 먼저 열려버려, /login으로 밀려나기 전 화면을 어둡게
  // 덮는 게 잠깐 보였다 사라지는 문제가 있었다 — 자식 자체를 감춰 원천 차단한다.
  const [checking, setChecking] = useState(AUTH_ENABLED);
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
  // 원래 가려던 주소를 ?next= 로 넘긴다. 안 넘기면 README 퀵투어의 딥링크
  // (/chat?prefill=... 같은)가 로그인 리다이렉트에서 통째로 버려진다.
  // useSearchParams 대신 window.location 을 쓰는 건 이 코드가 이미 effect 안이라
  // 브라우저에서만 돌고, 훅을 쓰면 Suspense 경계를 따로 둘러야 하기 때문이다.
  useEffect(() => {
    // 토큰(localStorage)은 브라우저에서만 읽을 수 있어 effect가 정답 — 렌더 중엔 알 수 없다.
    if (!AUTH_ENABLED || pathname === "/login") {
      /* eslint-disable-next-line react-hooks/set-state-in-effect */
      setChecking(false);
      return;
    }
    if (!getToken()) {
      const here = window.location.pathname + window.location.search;
      router.replace(`/login?next=${encodeURIComponent(here)}`);
      return; // 리다이렉트가 끝날 때까지 자식을 계속 숨긴 채로 둔다.
    }
    setChecking(false);
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
      {checking ? null : children}
    </UserContext.Provider>
  );
}

export function useSelectedUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useSelectedUser must be used within UserProvider");
  return ctx;
}
