"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { errMsg } from "@/lib/async";
import Link from "next/link";
import { Plus, TrashSimple, ArrowRight, PaperPlaneTilt } from "@phosphor-icons/react";
import {
  apiDelete,
  apiGet,
  streamChat,
  type ChatSessionMeta,
} from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { useToast } from "@/lib/toast";
import { consumeChatSeed } from "@/lib/chat-seed";
import { Card, PageTitle, Spinner } from "@/components/ui";
import { Markdown } from "@/components/Markdown";
import KnowledgePanel from "./KnowledgePanel";

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
  const [tab, setTab] = useState<"chats" | "kb">("chats");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initedFor = useRef<string | null>(null);
  const seedRef = useRef<string | null>(null);

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
    /* eslint-disable react-hooks/set-state-in-effect -- 유저 변경 시 세션 목록 동기화 + 새 대화 준비(외부 동기) */
    void refreshSessions();
    if (initedFor.current !== selected.uuid) {
      initedFor.current = selected.uuid;
      startNewChat();
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [selected, refreshSessions, startNewChat]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // 분석 페이지에서 넘어온 상담 seed를 1회 소비(마운트 시).
  useEffect(() => {
    seedRef.current = consumeChatSeed();
  }, []);

  // 챗 준비(유저 선택 + 세션 생성)되면 seed를 입력창에 프리필 + 포커스.
  useEffect(() => {
    if (seedRef.current && selected && currentId) {
      setInput(seedRef.current);
      seedRef.current = null;
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [selected, currentId]);

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
      toast(`기록 로드 실패: ${errMsg(e)}`, "error");
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
      toast(`삭제 실패: ${errMsg(e)}`, "error");
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
      toast(`응답 실패: ${errMsg(e)}`, "error");
      setMessages((m) => m.slice(0, -1)); // 빈 assistant 버블 제거
    } finally {
      setBusy(false);
    }
  };

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" }) : "";

  return (
    <div>
      <PageTitle eyebrow="AI Advisor" title="에이전트 챗봇" subtitle="MidasAdviser · 멀티턴 · 실시간 스트리밍" />
      <div className="flex gap-4">
        {/* 좌측 사이드바: 대화 목록 / 지식베이스 탭 */}
        <aside className="w-64 shrink-0">
          <div className="mb-3 flex gap-1 rounded-lg border border-line p-1">
            {(["chats", "kb"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition ${
                  tab === t
                    ? "bg-[color-mix(in_srgb,var(--accent)_14%,transparent)] text-accent"
                    : "text-muted hover:text-fg"
                }`}
              >
                {t === "chats" ? "대화" : "지식베이스"}
              </button>
            ))}
          </div>

          {tab === "kb" ? (
            <KnowledgePanel />
          ) : (
            <>
              <button
                onClick={startNewChat}
                disabled={!selected}
                className="btn-accent mb-3 flex w-full items-center justify-center gap-1.5 px-3 py-2 text-sm"
              >
                <Plus weight="bold" size={16} />새 대화
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
                          ? "bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]"
                          : "hover:bg-[color-mix(in_srgb,var(--accent)_6%,transparent)]"
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
                        className="flex h-6 w-6 items-center justify-center rounded-md text-muted opacity-0 transition hover:text-negative group-hover:opacity-100"
                        aria-label="대화 삭제"
                        title="삭제"
                      >
                        <TrashSimple size={15} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </aside>

        {/* 대화 영역 */}
        <div className="min-w-0 flex-1">
          {!selected ? (
            <Card className="text-center">
              <p className="text-fg">먼저 대화할 유저를 선택하세요.</p>
              <Link
                href="/"
                className="btn-accent mt-3 inline-flex items-center gap-1.5 px-4 py-2 text-sm"
              >
                유저 선택하러 가기
                <ArrowRight weight="bold" size={15} />
              </Link>
            </Card>
          ) : !currentId ? (
            <Card className="text-center text-muted">
              왼쪽에서 대화를 선택하거나 <b className="text-accent">+ 새 대화</b>를 시작하세요.
            </Card>
          ) : (
            <Card className="flex h-[60vh] flex-col p-0">
              <div className="scroll-thin flex-1 space-y-4 overflow-auto p-5">
                {loadingHistory && (
                  <p className="text-center text-sm text-muted">기록 불러오는 중…</p>
                )}
                {!loadingHistory && messages.length === 0 && (
                  <div className="my-auto py-8 space-y-4 text-center">
                    <div className="mx-auto max-w-sm">
                      <div className="h-12 w-12 mx-auto rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center text-accent text-xl font-bold mb-2">
                        💬
                      </div>
                      <h3 className="text-sm font-semibold text-fg">무엇이든 질문해보세요</h3>
                      <p className="text-xs text-muted mt-1">
                        유저 자산 정보, 마크로 금융 지표, 청약 자격, 개별 주식 분석을 종합하여 맞춤형 인사이트를 제공합니다.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left max-w-lg mx-auto pt-2">
                      {[
                        { title: "📊 포트폴리오 자산배분", prompt: "나와 비슷한 투자자들의 자산 배분과 내 포트폴리오 리스크를 분석해줘" },
                        { title: "💵 금리 인상 파급 효과", prompt: "미국 10년물 국채 금리 변화가 내 주식 포트폴리오에 미치는 영향은?" },
                        { title: "🏢 공모주 청약 자격 체크", prompt: "올해 하반기 주요 공모주 청약 일정과 내 진단 등급 자격을 확인해줘" },
                        { title: "⚡ NVDA & TSLA 지표 분석", prompt: "엔비디아(NVDA)와 테슬라(TSLA)의 기술적 지표 및 중단기 전망을 분석해줘" },
                      ].map((item, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            setInput(item.prompt);
                            requestAnimationFrame(() => inputRef.current?.focus());
                          }}
                          className="p-3 border border-line/60 bg-[#090d16] hover:border-accent hover:bg-accent/10 rounded-lg text-left transition group"
                        >
                          <div className="text-xs font-semibold text-accent group-hover:text-accent-soft">{item.title}</div>
                          <div className="text-[11px] text-muted truncate mt-0.5">&ldquo;{item.prompt}&rdquo;</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-[var(--r-lg)] px-4 py-3 text-sm leading-relaxed [box-shadow:var(--shadow-soft)] ${
                        m.role === "user"
                          ? "whitespace-pre-wrap rounded-br-md bg-[color-mix(in_srgb,var(--accent)_16%,transparent)] text-fg"
                          : "rounded-bl-md border border-line bg-[var(--ink-2)] text-fg"
                      }`}
                    >
                      {/* 유저 입력은 평문 그대로, 어시스턴트 응답은 마크다운 렌더(평문이면 그대로 잘 나옴) */}
                      {m.role === "assistant" ? (
                        m.content ? (
                          <Markdown>{m.content}</Markdown>
                        ) : busy ? (
                          <span className="caret" />
                        ) : null
                      ) : (
                        m.content
                      )}
                    </div>
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              <div className="flex gap-2 border-t border-line p-3">
                <input
                  ref={inputRef}
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
                  aria-label="전송"
                  className="btn-accent flex items-center gap-1.5 px-5 py-2.5 text-sm disabled:opacity-40"
                >
                  {busy ? <Spinner className="h-3.5 w-3.5" /> : <PaperPlaneTilt weight="fill" size={15} />}
                  {busy ? "응답 중…" : "전송"}
                </button>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
