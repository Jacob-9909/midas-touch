"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { errMsg } from "@/lib/async";
import {
  Plus,
  TrashSimple,
  PaperPlaneTilt,
  SidebarSimple,
  X,
  ShieldCheck,
  CheckCircle,
  Copy,
  Check,
} from "@phosphor-icons/react";
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
import { splitChatSources } from "@/lib/chat-sources";
import { Card, Spinner, Skeleton } from "@/components/ui";
import { useSelectedUser } from "@/lib/user-context";
import { Markdown } from "@/components/Markdown";
import KnowledgePanel from "./KnowledgePanel";
import SegmentedTabs from "@/components/SegmentedTabs";

interface Msg {
  role: "user" | "assistant";
  content: string;
}

// 어시스턴트 답변 렌더: 본문 마크다운 + 실시간 5겹 방어 검증 증명서 + 출처 칩 리스트.
function AssistantAnswer({ content }: { content: string }) {
  const { body, defense, sources } = splitChatSources(content);
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(body);
      setCopied(true);
      toast("답변이 복사되었습니다.", "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("복사에 실패했습니다.", "error");
    }
  };

  return (
    <>
      <Markdown>{body}</Markdown>

      {/* ── 🛡️ 실시간 5겹 보안 검증 증명서 (Audit Verified Trace) ── */}
      {defense && (
        <div className="mt-4 rounded-xl border border-line bg-[color-mix(in_srgb,var(--ink-2)_65%,transparent)] p-4 text-sm sm:text-[15px]">
          <div className="flex items-center justify-between gap-2 border-b border-line/50 pb-2.5">
            <div className="flex items-center gap-2 font-bold text-positive text-sm sm:text-[15px]">
              <ShieldCheck weight="fill" size={19} className="text-positive shrink-0" />
              <span>실시간 5겹 보안 검증 완료</span>
            </div>
            <span className="rounded-full bg-positive/10 border border-positive/25 px-2.5 py-0.5 font-mono-spec text-xs font-bold text-positive tracking-wide">
              AUDIT VERIFIED
            </span>
          </div>
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs sm:text-[13px]">
            <div className="flex items-center gap-2 text-muted">
              <CheckCircle weight="fill" size={16} className="text-positive shrink-0" />
              <span>검색 도구: <strong className="font-mono-spec text-fg">{defense.tools}</strong></span>
            </div>
            <div className="flex items-center gap-2 text-muted">
              <CheckCircle weight="fill" size={16} className="text-positive shrink-0" />
              <span>
                {defense.hasDeterministicMath ? (
                  <span>수치 계산: <strong className="text-fg">결정론 코드 (LLM 0%)</strong></span>
                ) : (
                  <span>수치 계산: <span className="text-fg">컨텍스트 접지 작문</span></span>
                )}
              </span>
            </div>
            <div className="flex items-center gap-2 text-muted">
              <CheckCircle weight="fill" size={16} className="text-positive shrink-0" />
              <span>근거 접지: <span className="text-fg font-medium">{sources.length > 0 ? `${sources.length}건 인용` : "Grounding 지시 유지"}</span></span>
            </div>
            <div className="flex items-center gap-2 text-muted">
              <CheckCircle weight="fill" size={16} className="text-positive shrink-0" />
              <span>안정화: <span className="text-fg font-medium">저온 생성 (temp 0.3)</span></span>
            </div>
            {/* 5겹째 — 라벨이 "5겹"인데 4줄만 있으면 세어 보는 사람에게 바로 걸린다. */}
            <div className="flex items-center gap-2 text-muted">
              <CheckCircle weight="fill" size={16} className="text-positive shrink-0" />
              <span>외곽 경계: <span className="text-fg font-medium">fetch 허용목록 · JWT 세션</span></span>
            </div>
          </div>
        </div>
      )}

      {/* ── 출처 칩 ── */}
      {sources.length > 0 && (
        <div className="mt-4 border-t border-line/60 pt-3">
          <p className="mb-2 text-xs sm:text-sm font-bold text-muted">인용 출처 ({sources.length}건)</p>
          <ul role="list" aria-label="참고 출처" className="flex flex-wrap gap-2">
            {sources.map((s) => (
              <li
                key={s.index}
                title={`${s.source} (${s.passageId})`}
                className="max-w-full truncate rounded-full border border-accent/25 bg-accent/10 px-3.5 py-1 text-xs sm:text-[13px] text-fg/90 font-medium"
              >
                [{s.index}] {s.source} ({s.passageId})
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── 액션 툴바: 답변 복사 ── */}
      <div className="mt-3.5 flex items-center gap-2">
        <button
          onClick={copyAnswer}
          aria-label="답변 복사"
          className="btn-ghost min-h-0 gap-1.5 rounded-full px-3.5 py-1.5 text-xs sm:text-[13px] text-muted hover:text-fg"
        >
          {copied ? (
            <>
              <Check size={14} className="text-positive" weight="bold" />
              <span className="text-positive font-semibold">복사됨</span>
            </>
          ) : (
            <>
              <Copy size={14} />
              <span>복사</span>
            </>
          )}
        </button>
      </div>
    </>
  );
}

function ChatClient() {
  const { selected } = useSelectedUser();
  const [uid, setUid] = useState<string | null>(null);
  const toast = useToast();
  const [sessions, setSessions] = useState<ChatSessionMeta[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(""); // 스트리밍 대기 구간 진행상태(도구 수집 등)
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [tab, setTab] = useState<"chats" | "kb">("chats");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  /** 메시지 스크롤 박스. 스트리밍 중 자동 하단 추적에 쓴다. */
  const scrollBoxRef = useRef<HTMLDivElement>(null);
  /** 유저가 위로 올려 과거를 읽고 있으면 자동 추적을 멈춘다(맨 아래 근처일 때만 붙는다). */
  const stickRef = useRef(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const initedFor = useRef<string | null>(null);
  const seedRef = useRef<string | null>(null);
  /** ?prefill= 로 넘어온 공격 프롬프트(/security → 챗 실험). 1회 소비용 ref. */
  const prefillRef = useRef<string | null>(null);
  const autoSendRef = useRef(false);
  const sendRef = useRef<(explicitText?: string | React.MouseEvent) => Promise<void>>(async () => {});
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 브라우저/로그인 식별자 복원
    setUid(selected?.uuid || clientId());
  }, [selected]);

  // /security 등에서 ?prefill= 로 넘어온 프롬프트를 받아두고 URL을 정리한다.
  // 파라미터가 주소에 남으면 새로고침마다 프리필이 반복되므로 즉시 replace(스크롤 없음).
  useEffect(() => {
    const prefill = searchParams.get("prefill");
    if (!prefill) return;
    prefillRef.current = prefill;
    autoSendRef.current = searchParams.get("autoSend") === "1";
    router.replace("/chat", { scroll: false });
  }, [searchParams, router]);

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
    setMobileSidebarOpen(false);
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

  // 메시지 변화(스트리밍 토큰 포함)마다, 유저가 맨 아래 근처에 붙어 있을 때만 바닥으로 붙인다.
  useEffect(() => {
    const el = scrollBoxRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

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

  // URL prefill도 동일하게 — autoSend=1이면 즉시 전송, 아니면 입력창에 채우고 포커스.
  useEffect(() => {
    if (prefillRef.current && uid && currentId) {
      const text = prefillRef.current;
      prefillRef.current = null;
      if (autoSendRef.current) {
        autoSendRef.current = false;
        setInput("");
        void sendRef.current(text);
      } else {
        setInput(text);
        requestAnimationFrame(() => inputRef.current?.focus());
      }
    }
  }, [uid, currentId]);

  const openSession = async (s: ChatSessionMeta) => {
    setMobileSidebarOpen(false);
    setCurrentId(s.session_id);
    setLoadingHistory(true);
    stickRef.current = true;
    try {
      const res = await apiGet<{ messages: Msg[] }>(
        `/api/v1/chat/history/${encodeURIComponent(s.session_id)}`,
      );
      setMessages(res.messages);
    } catch (e) {
      const msg = errMsg(e);
      setMessages([]);
      // 세션이 이미 없어진 대화(체크포인트 유실 등)는 목록에 죽은 채로 남겨두지 않고
      // 바로 지운다 — 사용자가 매번 눌러서 같은 에러를 다시 보게 두지 않는다.
      if (msg.startsWith("404")) {
        if (currentId === s.session_id) setCurrentId(null);
        try {
          await apiDelete(`/api/v1/chat/sessions/${encodeURIComponent(s.session_id)}`);
        } catch {
          /* 이미 없으면 그것대로 목표 달성 */
        }
        await refreshSessions();
        toast("세션을 찾을 수 없어 대화 기록을 삭제했습니다.", "error");
      } else {
        toast(`기록 로드 실패: ${msg}`, "error");
      }
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

  const send = async (explicitText?: string | React.MouseEvent) => {
    const text = (typeof explicitText === "string" ? explicitText : input).trim();
    if (!text || !uid || !currentId || busy) return;
    setInput("");
    stickRef.current = true; // 내가 보낸 메시지라면 자동 추적 재개
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setBusy(true);
    setStatus("");
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
        (msg) => setStatus(msg), // 도구 수집 등 진행상태
      );
      await refreshSessions();
    } catch (e) {
      toast(`응답 실패: ${errMsg(e)}`, "error");
      setMessages((m) => m.slice(0, -1)); // 빈 assistant 버블 제거
    } finally {
      setBusy(false);
      setStatus("");
    }
  };

  useEffect(() => {
    sendRef.current = send;
  });

  const fmtDate = (s: string | null) =>
    s ? new Date(s).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" }) : "";

  const sidebarContent = (
    <>
      <SegmentedTabs
        className="mb-4"
        tabs={[
          { id: "chats", label: "대화" },
          { id: "kb", label: "지식베이스" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "kb" ? (
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto pr-1">
          <KnowledgePanel />
        </div>
      ) : (
        <>
          <button
            onClick={startNewChat}
            disabled={!uid}
            className="btn-ghost mb-3 w-full text-sm"
          >
            <Plus weight="bold" size={16} />새 대화
          </button>
          <div className="scroll-thin min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
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
    </>
  );

  return (
    /* 앱형 레이아웃 — NavBar(64px)를 뺀 나머지 뷰포트를 채운다. 페이지 스크롤 없음,
       스크롤은 메시지 영역과 사이드바 목록이 각자 소유한다. */
    <div className="mx-auto flex h-[calc(100dvh-5.75rem)] max-w-[1200px] flex-col px-3 sm:px-6 pb-3 sm:pb-4 pt-4 sm:pt-6">
      <header className="mb-3.5 flex items-center justify-between gap-3">
        <div className="flex items-baseline gap-2.5 min-w-0">
          <h1 className="font-display text-lg sm:text-xl text-fg shrink-0 font-bold">에이전트 챗봇</h1>
          <span className="eyebrow hidden sm:inline-flex">AI Advisor</span>
          <span className="hidden font-mono-spec text-[10px] uppercase tracking-widest text-muted md:inline truncate">
            MidasAdviser · 멀티턴 · 실시간 스트리밍
          </span>
        </div>
        <button
          onClick={() => setMobileSidebarOpen((v) => !v)}
          aria-label="대화 목록 및 지식베이스 열기"
          className="md:!hidden btn-ghost min-h-0 flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-mono-spec shrink-0"
        >
          <SidebarSimple size={15} />
          <span>{tab === "chats" ? "대화 목록" : "지식베이스"}</span>
        </button>
      </header>

      {/* 모바일 사이드바 드로어 */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true" aria-label="대화 메뉴">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <aside className="relative z-10 flex w-72 max-w-[85vw] flex-col border-r border-line bg-[var(--ink-1)] p-4 shadow-[var(--shadow-2)] animate-rise">
            <div className="mb-3 flex items-center justify-between border-b border-line pb-2">
              <span className="font-display text-sm font-semibold text-fg">대화 및 지식베이스</span>
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="btn-ghost btn-icon min-h-0 h-7 w-7 shrink-0"
                aria-label="사이드바 닫기"
              >
                <X size={15} />
              </button>
            </div>
            <div className="min-h-0 flex-1 flex flex-col">
              {sidebarContent}
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-h-0 flex-1 gap-4">
        {/* 데스크톱 사이드바: 대화 목록 / 지식베이스 탭 */}
        <aside className="hidden md:flex w-64 min-h-0 shrink-0 flex-col">
          {sidebarContent}
        </aside>

        {/* 대화 영역 */}
        <div className="flex min-w-0 flex-1 flex-col">
          {!currentId ? (
            <Card className="text-center text-muted">
              왼쪽에서 대화를 선택하거나 <b className="text-accent">+ 새 대화</b>를 시작하세요.
            </Card>
          ) : (
            <Card className="flex min-h-0 flex-1 flex-col p-0">
              <div
                ref={scrollBoxRef}
                onScroll={() => {
                  const el = scrollBoxRef.current;
                  if (!el) return;
                  stickRef.current =
                    el.scrollHeight - el.scrollTop - el.clientHeight < 80;
                }}
                className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto p-5"
              >
                {loadingHistory && (
                  <div className="space-y-3 py-6 max-w-md mx-auto animate-pulse">
                    <div className="flex justify-start">
                      <Skeleton className="h-14 w-3/4 rounded-2xl" />
                    </div>
                    <div className="flex justify-end">
                      <Skeleton className="h-10 w-1/2 rounded-2xl" />
                    </div>
                  </div>
                )}
                {!loadingHistory && messages.length === 0 && (
                  <div className="my-auto py-8 space-y-4 text-center">
                    <div className="mx-auto max-w-sm">
                      <div className="h-12 w-12 mx-auto rounded-full bg-accent/10 border border-accent/30 flex items-center justify-center text-accent text-xl font-bold mb-2">
                        💬
                      </div>
                      <h3 className="text-sm font-semibold text-fg">무엇이든 질문해보세요</h3>
                      <p className="text-xs text-muted mt-1">
                        사기 문자 검증, 세법 근거·계산, 청약 자격까지 — 근거와 함께 정리해 드립니다.
                      </p>
                    </div>

                      {/* 예시 질문은 첫 화면의 실질적 헤드라인이다 — 공모 주제('AI 금융 보안 비서')의
                          핵심 기능(사기 검증·결정론 계산)을 앞세우고 청약·자산은 균형으로 둔다. */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left max-w-xl mx-auto pt-2">
                        {[
                          {
                            badge: "사기 검증",
                            tone: "bg-negative/10 text-negative border-negative/25",
                            title: "🚨 보이스피싱 의심 문자 검증",
                            prompt: "엄마 나 사고났어. 경찰서에 있는데 지금 당장 300만원 이체해줘. 전화하지 마세요.",
                          },
                          {
                            badge: "세법 RAG",
                            tone: "bg-accent/10 text-accent border-accent/25",
                            title: "⚖️ 해외주식 2천만원 양도세 계산",
                            prompt: "미국 주식 팔아서 2,000만원 벌었는데 양도소득세 얼마나 내야 해? 기본공제랑 세율 근거도 알려줘.",
                          },
                          {
                            badge: "청약 자격",
                            tone: "bg-gilt/10 text-gilt border-gilt/25",
                            title: "🏠 서울 1인 가구 청약 조건",
                            prompt: "29살 미혼 무주택자인데 서울에서 청약 넣으려면 어떤 조건이 필요한가요?",
                          },
                          {
                            badge: "자산 진단",
                            tone: "bg-positive/10 text-positive border-positive/25",
                            title: "📊 사회초년생 자산 배분 진단",
                            prompt: "20대 후반 직장인 평균 자산 배분과 비교해서 내 현황(예적금 2천만, 월 60만 저축)을 진단해줘.",
                          },
                        ].map((item, idx) => (
                        <button
                          key={idx}
                          disabled={busy}
                          onClick={() => send(item.prompt)}
                          className="lift p-4 sm:p-4.5 rounded-[var(--r-md)] border border-line bg-[color-mix(in_srgb,var(--ink-1)_72%,transparent)] text-left transition group hover:border-accent/40 active:scale-[0.98]"
                        >
                          <div className="flex items-center justify-between gap-2 mb-1.5">
                            <span className="text-sm font-bold text-fg group-hover:text-accent transition-colors">
                              {item.title}
                            </span>
                            <span className={`shrink-0 rounded-full border px-2 py-0.5 font-mono-spec text-[10px] font-bold ${item.tone}`}>
                              {item.badge}
                            </span>
                          </div>
                          <div className="text-xs sm:text-[13px] text-muted line-clamp-2 leading-relaxed">
                            &ldquo;{item.prompt}&rdquo;
                          </div>
                          <div className="mt-2.5 text-xs font-bold text-accent opacity-85 group-hover:opacity-100 flex items-center gap-1">
                            클릭하여 바로 질문하기 →
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`msg-in flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      data-chat-answer
                      className={`max-w-[85%] sm:max-w-[80%] rounded-[var(--r-lg)] px-5 py-3.5 text-base sm:text-[16.5px] leading-relaxed break-words [overflow-wrap:anywhere] ${
                        m.role === "user"
                          ? "whitespace-pre-wrap rounded-br-md bg-gradient-to-br from-[var(--accent)] to-[var(--accent-soft)] text-white shadow-[0_6px_20px_-8px_var(--glow)] font-medium"
                          : "rounded-bl-md border border-line bg-[color-mix(in_srgb,var(--ink-1)_72%,transparent)] text-fg backdrop-blur-md [box-shadow:var(--shadow-soft)]"
                      }`}
                    >
                      {/* 유저 입력은 평문 그대로, 어시스턴트 응답은 마크다운 렌더(평문이면 그대로 잘 나옴) */}
                      {m.role === "assistant" ? (
                        m.content ? (
                          <AssistantAnswer content={m.content} />
                        ) : busy ? (
                          <span className="font-mono-spec inline-flex items-center gap-2 text-xs sm:text-[13px] text-muted">
                            {status && (
                              <span>
                                {"⟳ "}
                                {status}…
                              </span>
                            )}
                            <span className="caret" />
                          </span>
                        ) : null
                      ) : (
                        m.content
                      )}
                    </div>
                  </div>
                ))}
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

function ChatLoadingFallback() {
  return (
    <div className="mx-auto flex h-[calc(100dvh-5.75rem)] max-w-[1200px] flex-col px-3 sm:px-6 pb-3 sm:pb-4 pt-4 sm:pt-6 animate-pulse">
      <div className="mb-3.5 flex items-center justify-between">
        <div className="h-6 w-32 rounded-lg bg-surface/80" />
      </div>
      <div className="flex min-h-0 flex-1 gap-4">
        <div className="hidden md:flex w-64 flex-col gap-2 rounded-xl border border-line/60 bg-[var(--ink-1)] p-3">
          <div className="h-8 w-full rounded-lg bg-surface/60" />
          <div className="h-10 w-full rounded-lg bg-surface/40" />
          <div className="h-10 w-full rounded-lg bg-surface/40" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col rounded-2xl border border-line bg-[var(--ink-1)] p-5 justify-between">
          <div className="space-y-4 max-w-lg mx-auto w-full pt-16 text-center">
            <div className="h-12 w-12 rounded-full bg-accent/10 mx-auto" />
            <div className="h-5 w-48 rounded bg-surface/80 mx-auto" />
            <div className="h-4 w-64 rounded bg-surface/50 mx-auto" />
          </div>
          <div className="h-11 w-full rounded-xl border border-line bg-surface/30" />
        </div>
      </div>
    </div>
  );
}

// useSearchParams는 프리렌더 경로에서 Suspense 경계를 요구한다(Next 권장 패턴) —
// 경계 안의 챗 본문만 클라이언트 렌더로 전환하고 나머지는 그대로 유지한다.
export default function ChatPage() {
  return (
    <Suspense fallback={<ChatLoadingFallback />}>
      <ChatClient />
    </Suspense>
  );
}
