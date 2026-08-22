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
import { clientId, loadProfile, profileSummary } from "@/lib/my-profile";
import { totalCheongyakScore } from "@/lib/cheongyak-score";
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
  // 로그인이 없으므로 세션은 이 브라우저의 익명 id 로 묶고, "누구인가"는
  // /me 에 직접 입력한 내 정보를 첫 턴에 요약해 보내는 것으로 대신한다.
  const [uid, setUid] = useState<string | null>(null);
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

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 브라우저 식별자 복원
    setUid(clientId());
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      const qs = uid ? `?user_uuid=${encodeURIComponent(uid)}` : "";
      const res = await apiGet<{ sessions: ChatSessionMeta[] }>(
        `/api/v1/chat/sessions${qs}`,
      );
      setSessions(res.sessions);
    } catch {
      /* 사이드바 로드 실패는 조용히 무시 */
    }
  }, [uid]);

  const startNewChat = useCallback(() => {
    if (!uid) return;
    setCurrentId(`${uid}-${Date.now()}`);
    setMessages([]);
  }, [uid]);

  useEffect(() => {
    if (!uid) return;
    /* eslint-disable react-hooks/set-state-in-effect -- 식별자 준비 시 세션 목록 동기화 + 새 대화 준비(외부 동기) */
    void refreshSessions();
    if (initedFor.current !== uid) {
      initedFor.current = uid;
      startNewChat();
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [uid, refreshSessions, startNewChat]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // 분석 페이지에서 넘어온 상담 seed를 1회 소비(마운트 시).
  useEffect(() => {
    seedRef.current = consumeChatSeed();
  }, []);

  // 챗 준비(유저 선택 + 세션 생성)되면 seed를 입력창에 프리필 + 포커스.
  useEffect(() => {
    if (seedRef.current && uid && currentId) {
      setInput(seedRef.current);
      seedRef.current = null;
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [uid, currentId]);

  const openSession = async (s: ChatSessionMeta) => {
    setCurrentId(s.session_id);
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
    if (!input.trim() || !uid || !currentId || busy) return;
    const text = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setBusy(true);
    try {
      await streamChat(
        {
          session_id: currentId,
          user_uuid: uid,
          message: text,
          // /me 에 입력해 둔 내 정보를 요약해 동봉한다. 백엔드는 첫 턴에만 시스템 프롬프트로
          // 합치고 저장하지 않는다 — 원시 입력값(자산 금액 등)은 보내지 않는다.
          profile: (() => {
            const me = loadProfile();
            return profileSummary(me, totalCheongyakScore(me));
          })(),
        },
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
    <div className="mx-auto max-w-[1200px] px-6 py-[72px]">
      <PageTitle eyebrow="AI Advisor" title="에이전트 챗봇" subtitle="MidasAdviser · 멀티턴 · 실시간 스트리밍" />
      <div className="flex gap-4">
        {/* 좌측 사이드바: 대화 목록 / 지식베이스 탭 */}
        <aside className="w-64 shrink-0">
          {/* 사이드바 탭 (Swiss Sleek Pill Segmented Control) */}
          <div className="mb-4 flex gap-1 rounded-full border border-line bg-[var(--ink-2)] p-1">
            {(["chats", "kb"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 rounded-full px-3 py-1.5 text-xs font-mono-spec transition-all duration-200 ${
                  tab === t
                    ? "bg-accent/20 text-accent border border-accent/40 font-semibold shadow-[0_0_10px_rgba(212,175,96,0.16)]"
                    : "text-muted hover:text-fg border border-transparent"
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
                disabled={!uid}
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
          {!currentId ? (
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
                        청약 자격·가점, 세법 조문, 자금마련 계획을 근거와 함께 정리해 드립니다.
                      </p>
                    </div>

                    {/* 예시 질문은 첫 화면의 실질적 헤드라인이다 — 헤드라인(주택청약·자금마련)을 앞에 두고
                        주식은 맨 뒤 하나만 남긴다. 이전엔 4개 중 3개가 주식이었고 "공모주 청약"은
                        주택청약과 아예 다른 것(IPO)이라 타겟에게 오해를 줬다. */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left max-w-lg mx-auto pt-2">
                      {[
                        { title: "🏠 내 조건에 맞는 청약", prompt: "29살 미혼 무주택인데 서울에서 청약 넣으려면 어떤 조건이 필요한가요?" },
                        { title: "🎯 특별공급 자격 확인", prompt: "사회초년생이 노려볼 만한 특별공급 유형과 각각의 자격 요건을 근거 조문과 함께 정리해줘" },
                        { title: "💰 청약 자금 마련", prompt: "청약 예치금과 계약금까지 생각하면 얼마가 필요하고, 어떤 저축상품을 쓰면 언제쯤 모을 수 있어?" },
                        { title: "📊 내 자산 진단", prompt: "나와 비슷한 조건인 사람들의 자산 배분과 비교해서 내 현황을 진단해줘" },
                      ].map((item, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            setInput(item.prompt);
                            requestAnimationFrame(() => inputRef.current?.focus());
                          }}
                          className="p-4 border border-line bg-[var(--ink-1)] hover:border-fg rounded-[var(--r-md)] text-left transition group"
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
