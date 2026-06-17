"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  apiDelete,
  apiGet,
  streamChat,
  type ChatSessionMeta,
} from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { useToast } from "@/lib/toast";
import { Card, PageTitle } from "@/components/ui";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const { selected, setSelected } = useSelectedUser();
  const toast = useToast();
  const [sessions, setSessions] = useState<ChatSessionMeta[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const initedFor = useRef<string | null>(null);

  const refreshSessions = useCallback(async () => {
    try {
      const qs = selected ? `?user_uuid=${encodeURIComponent(selected.uuid)}` : "";
      const res = await apiGet<{ sessions: ChatSessionMeta[] }>(
        `/api/v1/chat/sessions${qs}`,
      );
      setSessions(res.sessions);
    } catch {
      /* 사이드바 로드 실패는 조용히 무시 */
    }
  }, [selected]);

  const startNewChat = useCallback(() => {
    if (!selected) return;
    setCurrentId(`${selected.uuid}-${Date.now()}`);
    setMessages([]);
  }, [selected]);

  // 선택 유저가 바뀌면 세션 목록 갱신 + 새 대화 준비 (유저당 1회)
  useEffect(() => {
    if (!selected) return;
    void refreshSessions();
    if (initedFor.current !== selected.uuid) {
      initedFor.current = selected.uuid;
      startNewChat();
    }
  }, [selected, refreshSessions, startNewChat]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const openSession = async (s: ChatSessionMeta) => {
    setCurrentId(s.session_id);
    if (s.user_uuid && s.user_uuid !== selected?.uuid) {
      setSelected({ uuid: s.user_uuid, label: `유저 ${s.user_uuid.slice(0, 6)}` });
      initedFor.current = s.user_uuid; // 새 대화 자동생성 방지
    }
    setLoadingHistory(true);
    try {
      const res = await apiGet<{ messages: Msg[] }>(
        `/api/v1/chat/history/${encodeURIComponent(s.session_id)}`,
      );
      setMessages(res.messages);
    } catch (e) {
      toast(`기록 로드 실패: ${e instanceof Error ? e.message : e}`, "error");
      setMessages([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await apiDelete(`/api/v1/chat/sessions/${encodeURIComponent(id)}`);
      if (currentId === id) {
        setCurrentId(null);
        setMessages([]);
      }
      await refreshSessions();
      toast("대화를 삭제했습니다.", "success");
    } catch (e) {
      toast(`삭제 실패: ${e instanceof Error ? e.message : e}`, "error");
    }
  };

  const send = async () => {
    if (!input.trim() || !selected || !currentId || busy) return;
    const text = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setBusy(true);
    try {
      await streamChat(
        { session_id: currentId, user_uuid: selected.uuid, message: text },
        (tok) =>
          setMessages((m) => {
            const next = [...m];
            next[next.length - 1] = {
              role: "assistant",
              content: next[next.length - 1].content + tok,
            };
            return next;
          }),
      );
      await refreshSessions();
    } catch (e) {
      toast(`응답 실패: ${e instanceof Error ? e.message : e}`, "error");
      setMessages((m) => m.slice(0, -1)); // 빈 assistant 버블 제거
    } finally {
      setBusy(false);
    }
  };

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" }) : "";

  return (
    <div>
      <PageTitle title="에이전트 챗봇" subtitle="MidasAdviser · 멀티턴 · 실시간 스트리밍" />
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
              const active = s.session_id === currentId;
              return (
                <div
                  key={s.session_id}
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
                      {fmtDate(s.updated_at)} · {s.message_count}개 메시지
                    </div>
                  </button>
                  <button
                    onClick={() => deleteSession(s.session_id)}
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
              왼쪽에서 대화를 선택하거나 <b className="text-gold">+ 새 대화</b>를 시작하세요.
            </Card>
          ) : (
            <Card className="flex h-[60vh] flex-col p-0">
              <div className="scroll-thin flex-1 space-y-4 overflow-auto p-5">
                {loadingHistory && (
                  <p className="text-center text-sm text-muted">기록 불러오는 중…</p>
                )}
                {!loadingHistory && messages.length === 0 && (
                  <p className="mt-10 text-center text-sm text-muted">
                    예: &ldquo;나와 비슷한 투자자들의 자산 배분을 벤치마크로 보여줘&rdquo;
                  </p>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                        m.role === "user"
                          ? "bg-[color-mix(in_srgb,var(--gold)_18%,transparent)] text-fg"
                          : "border border-line bg-[var(--ink-2)] text-fg"
                      }`}
                    >
                      {m.content || (busy ? "▍" : "")}
                    </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
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
