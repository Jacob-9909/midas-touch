"use client";

/** 랜딩(`/`)용 스포트라이트 가이드.
 *
 * 첫 방문자에게 "이 콘솔을 어떤 순서로 쓰는지"를 번호 매겨 짚어준다.
 * 재시작 버튼도 함께 렌더한다 — 서버 컴포넌트인 page.tsx 에서 상태 없이 쓰려면
 * 투어와 버튼이 한 클라이언트 경계 안에 있어야 하므로 별도 컴포넌트로 뒀다.
 *
 * 화면 구조가 바뀌면 STEPS 의 target(data-tour)도 같이 고쳐야 한다.
 */

import { useState } from "react";
import { Compass } from "@phosphor-icons/react/dist/ssr";
import GuideTour, { type TourStep } from "@/components/GuideTour";

const STEPS: TourStep[] = [
  {
    target: "hero",
    title: "여기가 출발점입니다",
    body: "이 콘솔은 무주택 사회초년생의 청약 조건 정리와 자금 계획만 다룹니다. 판단을 대신하지 않고 세법·청약 조문 근거와 함께 보여주는 정보 제공 도구입니다.",
  },
  {
    target: "nudge",
    title: "먼저 내 정보부터",
    body: "청약가점과 자금 상황을 입력해 두면 공고 목록·챗봇·시뮬레이터가 전부 그 기준으로 계산됩니다. 입력값은 이 브라우저에만 저장됩니다.",
  },
  {
    target: "journey",
    title: "세 단계 여정을 따라가세요",
    body: "① 챗봇으로 내 청약 유형 확인 → ② 실제 공고의 당첨가점과 내 가점 비교 → ③ 목표금액까지 몇 개월 걸리는지 시뮬레이션. 어느 카드든 눌러 시작할 수 있습니다.",
  },
];

export default function LandingGuide() {
  const [open, setOpen] = useState<boolean | undefined>(undefined);

  return (
    <>
      <GuideTour
        steps={STEPS}
        storageKey="midas.tour.home.v1"
        open={open}
        onClose={() => setOpen(undefined)}
      />
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-[var(--r-pill)] border border-accent/50 bg-accent/12 px-4 py-2 text-xs font-semibold text-accent transition-colors duration-150 hover:border-accent hover:bg-accent/20"
      >
        <Compass size={15} weight="bold" />
        사용 가이드
        <span aria-hidden className="font-mono-spec text-[10px] font-semibold tracking-widest opacity-70">
          3 STEPS
        </span>
      </button>
    </>
  );
}
