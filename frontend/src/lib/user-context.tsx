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

export function UserProvider({ children }: { children: ReactNode }) {
  const [selected, setSelectedState] = useState<SelectedUser | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        setSelectedState(JSON.parse(raw));
      } catch {
        /* ignore */
      }
    }
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
