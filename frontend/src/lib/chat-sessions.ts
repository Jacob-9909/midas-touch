// 대화 세션 메타데이터를 localStorage에 보관한다(사이드바용).
// 실제 대화 내용은 백엔드 체크포인터(Postgres)에 있고, 여기엔 목록 표시용 정보만 둔다.

export interface ChatSession {
  id: string; // = session_id (= thread_id)
  title: string;
  userUuid: string;
  userLabel: string;
  updatedAt: number;
}

const KEY = "midas.chatSessions";

export function loadSessions(): ChatSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as ChatSession[]) : [];
    return list.sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

export function saveSessions(list: ChatSession[]): void {
  localStorage.setItem(KEY, JSON.stringify(list));
}

export function upsertSession(s: ChatSession): ChatSession[] {
  const list = loadSessions().filter((x) => x.id !== s.id);
  list.unshift(s);
  saveSessions(list);
  return list.sort((a, b) => b.updatedAt - a.updatedAt);
}

export function removeSession(id: string): ChatSession[] {
  const list = loadSessions().filter((x) => x.id !== id);
  saveSessions(list);
  return list;
}

export function makeSessionId(userUuid: string): string {
  return `${userUuid}-${Date.now()}`;
}
