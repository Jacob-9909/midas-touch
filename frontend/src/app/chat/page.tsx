"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { Card, PageTitle } from "@/components/ui";
import {
  loadSessions,
  upsertSession,
  removeSession,
  makeSessionId,
  type ChatSession,
} from "@/lib/chat-sessions";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const { selected, setSelected } = useSelectedUser();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const initRef = useRef(false);

  // 최초 진입: 세션 목록 로드 후, 선택 유저의 최근 세션을 열거나 새 대화 시작
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    const list = loadSessions();
    setSessions(list);
    if (selected) {
      const latest = list.find((s) => s.userUuid === selected.uuid);
      if (latest) void openSession(latest);
      else startNewChat();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const startNewChat = () => {
    if (!selected) return;
    const id = makeSessionId(selected.uuid);
    const s: ChatSession = {
      id,
      title: "새 대화",
      userUuid: selected.uuid,
      userLabel: selected.label,
      updatedAt: Date.now(),
    };
    setSessions(upsertSession(s));
    setCurrentId(id);
    setMessages([]);
    setError(null);
  };

  const openSession = async (s: ChatSession) => {
    setCurrentId(s.id);
    setSelected({ uuid: s.userUuid, label: s.userLabel });
    setError(null);
    setLoadingHistory(true);
    try {
      const res = await apiGet<{ messages: Msg[] }>(
        `/api/v1/chat/history/${encodeURIComponent(s.id)}`,
      );
      setMessages(res.messages);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const deleteSession = (id: string) => {
    const list = removeSession(id);
    setSessions(list);
    if (currentId === id) {
      setCurrentId(null);
      setMessages([]);
    }
  };

  const send = async () => {
    if (!input.trim() || !selected || !currentId || busy) return;
    const text = input.trim();
    const isFirst = messages.length === 0;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    setError(null);
    try {
      const res = await apiPost<{ reply: string }>("/api/v1/chat", {
        session_id: currentId,
        user_uuid: selected.uuid,
        message: text,
      });
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
      // 세션 메타 갱신 (첫 메시지면 제목으로 사용)
      const cur = sessions.find((s) => s.id === currentId);
      setSessions(
        upsertSession({
          id: currentId,
          title: isFirst ? text.slice(0, 30) : (cur?.title ?? text.slice(0, 30)),
          userUuid: selected.uuid,
          userLabel: selected.label,
          updatedAt: Date.now(),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageTitle title="에이전트 챗봇" subtitle="MidasAdviser · 멀티턴 · 세션 기록" />
      <div className="flex gap-4">
        {/* 세션 사이드바 */}
        <aside className="w-60 shrink-0">
          <button
            onClick={startNewChat}
            disabled={!selected}
            className="btn-gold mb-3 w-full px-3 py-2 text-sm"
          >
            + 새 대화
          </button>
          <div className="space-y-1">
            {sessions.length === 0 && (
              <p className="px-2 text-xs text-muted">대화 기록이 없습니다.</p>
            )}
            {sessions.map((s) => {
              const active = s.id === currentId;
              return (
                <div
                  key={s.id}
                  className={`group flex items-center gap-1 rounded-lg px-2 py-2 text-sm transition ${
                    active
                      ? "bg-[color-mix(in_srgb,var(--gold)_12%,transparent)]"
                      : "hover:bg-[color-mix(in_srgb,var(--gold)_6%,transparent)]"
                  }`}
                >
                  <button
                    onClick={() => openSession(s)}
                    className="min-w-0 flex-1 text-left"
                  >
                    <div className="truncate text-fg">{s.title}</div>
                    <div className="truncate text-[10px] text-muted">
                      {s.userLabel}
                    </div>
                  </button>
                  <button
                    onClick={() => deleteSession(s.id)}
                    className="text-muted opacity-0 transition hover:text-negative group-hover:opacity-100"
                    title="삭제"
                  >
                    ✕
                  </button>
                </div>
              );
            })}
          </div>
        </aside>

        {/* 대화 영역 */}
        <div className="min-w-0 flex-1">
          {!selected ? (
            <Card className="text-center">
              <p className="text-fg">먼저 대화할 유저를 선택하세요.</p>
              <Link href="/" className="btn-gold mt-3 inline-block px-4 py-2 text-sm">
                유저 선택하러 가기 →
              </Link>
            </Card>
          ) : !currentId ? (
            <Card className="text-center text-muted">
              왼쪽에서 대화를 선택하거나 <b className="text-gold">+ 새 대화</b>를
              시작하세요.
            </Card>
          ) : (
            <Card className="flex h-[60vh] flex-col p-0">
              <div className="scroll-thin flex-1 space-y-4 overflow-auto p-5">
                {loadingHistory && (
                  <p className="text-center text-sm text-muted">
                    기록 불러오는 중…
                  </p>
                )}
                {!loadingHistory && messages.length === 0 && (
                  <p className="mt-10 text-center text-sm text-muted">
                    예: &ldquo;나와 비슷한 투자자들의 자산 배분을 벤치마크로
                    보여줘&rdquo;
                  </p>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`flex ${
                      m.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                        m.role === "user"
                          ? "bg-[color-mix(in_srgb,var(--gold)_18%,transparent)] text-fg"
                          : "border border-line bg-[var(--ink-2)] text-fg"
                      }`}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
                {busy && (
                  <div className="flex justify-start">
                    <div className="rounded-2xl border border-line bg-[var(--ink-2)] px-4 py-2.5 text-sm text-muted">
                      답변 생성 중…
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>
              {error && (
                <p className="px-5 pb-2 text-xs text-negative">오류: {error}</p>
              )}
              <div className="flex gap-2 border-t border-line p-3">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  placeholder="메시지를 입력하세요…"
                  className="field flex-1 px-4 py-2.5 text-sm"
                />
                <button
                  onClick={send}
                  disabled={busy || !input.trim()}
                  className="btn-gold px-5 py-2.5 text-sm disabled:opacity-40"
                >
                  전송
                </button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
