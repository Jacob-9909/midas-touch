"use client";

/** 번호 매긴 스포트라이트 가이드.
 *
 * 처음 들어온 사람은 "내 정보부터 채워야 한다"는 걸 알 방법이 없다. 화면을 어둡게 덮고
 * 해당 영역만 뚫어 보여주면서 무엇을 넣어야 하는지 순서대로 설명한다.
 *
 * ponytail: driver.js 같은 투어 라이브러리를 넣지 않고 직접 만들었다. 구멍은 타겟 크기의
 * 빈 div 에 아주 큰 box-shadow 를 줘서 파낸다(clip-path 없이 되고, 모서리 둥글림도 공짜).
 *
 * 타겟은 data-tour 속성으로 잡는다 — 클래스명은 스타일 바꾸다 깨지기 쉽다.
 */

import { useCallback, useEffect, useState } from "react";

export interface TourStep {
  /** data-tour 속성값. 못 찾으면 그 단계는 건너뛴다. */
  target: string;
  title: string;
  body: string;
}

interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}

const PAD = 8;
const GAP = 12;
const CARD_W = 320;

export default function GuideTour({
  steps,
  storageKey,
  open,
  onClose,
}: {
  steps: TourStep[];
  /** 이 키가 localStorage 에 있으면 자동 실행하지 않는다. */
  storageKey: string;
  /** 외부에서 "가이드 다시 보기"로 열 때. undefined 면 첫 방문 여부로 스스로 판단. */
  open?: boolean;
  onClose?: () => void;
}) {
  const [idx, setIdx] = useState<number | null>(null);
  const [rect, setRect] = useState<Rect | null>(null);

  // 첫 방문이면 자동 시작. 외부에서 open 을 주면 그쪽이 우선.
  useEffect(() => {
    if (open === undefined) {
      /* eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 방문 이력(localStorage) 확인 */
      if (!localStorage.getItem(storageKey)) setIdx(0);
      return;
    }
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- 부모가 제어하는 열림 상태 반영 */
    setIdx(open ? 0 : null);
  }, [open, storageKey]);

  const measure = useCallback(() => {
    if (idx === null) return;
    const el = document.querySelector<HTMLElement>(`[data-tour="${steps[idx].target}"]`);
    if (!el) {
      setRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
  }, [idx, steps]);

  // 단계가 바뀌면 타겟을 화면 안으로 넣고 위치를 잰다.
  useEffect(() => {
    if (idx === null) return;
    const el = document.querySelector<HTMLElement>(`[data-tour="${steps[idx].target}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = setTimeout(measure, 420); // 스크롤이 멎은 뒤에 재야 정확하다
    return () => clearTimeout(t);
  }, [idx, steps, measure]);

  useEffect(() => {
    if (idx === null) return;
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [idx, measure]);

  const finish = useCallback(() => {
    localStorage.setItem(storageKey, "1");
    setIdx(null);
    onClose?.();
  }, [storageKey, onClose]);

  // Esc 로 종료, 화살표로 이동
  useEffect(() => {
    if (idx === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
      if (e.key === "ArrowRight") setIdx((i) => (i === null ? i : Math.min(steps.length - 1, i + 1)));
      if (e.key === "ArrowLeft") setIdx((i) => (i === null ? i : Math.max(0, i - 1)));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [idx, steps.length, finish]);

  if (idx === null) return null;
  const step = steps[idx];
  const last = idx === steps.length - 1;

  // 타겟 아래에 카드를 두되, 아래가 좁으면 위로 뒤집는다.
  const below = rect ? rect.top + rect.height + GAP : 0;
  const placeAbove = rect ? below + 190 > window.innerHeight : false;
  const cardTop = rect
    ? placeAbove
      ? Math.max(GAP, rect.top - GAP - 176)
      : below
    : window.innerHeight / 2 - 88;
  const cardLeft = rect
    ? Math.min(Math.max(GAP, rect.left), Math.max(GAP, window.innerWidth - CARD_W - GAP))
    : window.innerWidth / 2 - CARD_W / 2;

  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true" aria-label="사용 가이드">
      {/* 구멍: 타겟만 남기고 나머지를 덮는다. 타겟을 클릭할 수 있게 pointer-events 는 끈다. */}
      {rect ? (
        <div
          className="pointer-events-none absolute rounded-xl ring-2 ring-accent transition-all duration-300"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(3,6,14,0.78)",
          }}
        />
      ) : (
        <div className="absolute inset-0 bg-[rgba(3,6,14,0.78)]" />
      )}

      {/* 빈 곳을 누르면 종료 */}
      <button
        aria-label="가이드 닫기"
        onClick={finish}
        className="absolute inset-0 cursor-default"
        tabIndex={-1}
      />

      <div
        className="absolute w-[320px] rounded-2xl border border-accent/40 bg-[var(--ink-1)] p-4 shadow-2xl"
        style={{ top: cardTop, left: cardLeft }}
      >
        <div className="mb-2 flex items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-[#0b0f19]">
            {idx + 1}
          </span>
          <h3 className="font-display text-sm font-semibold text-fg">{step.title}</h3>
          <span className="ml-auto font-mono-spec text-[10px] tabular-nums text-muted">
            {idx + 1}/{steps.length}
          </span>
        </div>

        <p className="mb-3 text-xs leading-relaxed text-muted">{step.body}</p>

        <div className="flex items-center gap-2">
          <button
            onClick={finish}
            className="text-[11px] text-muted transition hover:text-fg"
          >
            건너뛰기
          </button>
          <div className="ml-auto flex gap-2">
            {idx > 0 && (
              <button
                onClick={() => setIdx(idx - 1)}
                className="rounded-lg border border-line px-3 py-1.5 text-xs text-muted transition hover:border-accent hover:text-accent"
              >
                이전
              </button>
            )}
            <button
              onClick={() => (last ? finish() : setIdx(idx + 1))}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-[#0b0f19] transition hover:opacity-90"
            >
              {last ? "시작하기" : "다음"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
