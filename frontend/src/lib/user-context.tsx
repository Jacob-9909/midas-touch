"use client";

// 선택된 유저(uuid)를 앱 전역에서 공유한다. localStorage에 영속.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

interface SelectedUser {
  uuid: string;
  label: string;
}

interface UserContextValue {
  selected: SelectedUser | null;
  setSelected: (u: SelectedUser | null) => void;
}

const UserContext = createContext<UserContextValue | undefined>(undefined);
const STORAGE_KEY = "midas.selectedUser";

/** 처음 들어온 사람에게 기본으로 물려주는 페르소나(타겟인 무주택 사회초년생).
 *
 * 이게 없으면 유저를 안 고른 방문자는 /chat 이 "먼저 대화할 유저를 선택하세요"로 막혀서,
 * 헤드라인 기능인 청약 상담에 아예 도달하지 못한다. NavBar의 SAMPLE_USERS[0]과 같은 값이다
 * (그쪽 목록에서 바꾸면 여기도 같이 바꿀 것 — 두 곳뿐이라 상수 공유 대신 주석으로 묶는다). */
const DEFAULT_USER: SelectedUser = {
  uuid: "e7926df30b8f48c09b33684f3075f60f",
  label: "26세 공공행정 · 자산 4,000만",
};

export function UserProvider({ children }: { children: ReactNode }) {
  const [selected, setSelectedState] = useState<SelectedUser | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    // 마운트 1회 localStorage 복원. 서버엔 localStorage 없어 lazy init 불가 → effect가 정답.
    // 저장된 게 없으면(=첫 방문) 기본 페르소나를 넣어 곧장 쓸 수 있게 한다.
    /* eslint-disable react-hooks/set-state-in-effect -- 마운트 시 외부 상태(localStorage) 복원 */
    if (raw) {
      try {
        setSelectedState(JSON.parse(raw));
      } catch {
        setSelectedState(DEFAULT_USER);
      }
    } else {
      setSelectedState(DEFAULT_USER);
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  const setSelected = (u: SelectedUser | null) => {
    setSelectedState(u);
    if (u) localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
    else localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <UserContext.Provider value={{ selected, setSelected }}>
      {children}
    </UserContext.Provider>
  );
}

export function useSelectedUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useSelectedUser must be used within UserProvider");
  return ctx;
}
