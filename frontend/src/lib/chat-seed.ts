// 분석 페이지(주식/청약 등) → 챗 상담으로 컨텍스트를 넘기는 공용 브리지.
// 긴 URL 대신 sessionStorage 핸드오프: 페이지에서 seed를 심고 /chat으로 이동하면
// 챗 페이지가 마운트 시 읽어 입력창에 프리필한다(자동전송 아님 — 유저가 검토 후 전송).

import type { useRouter } from "next/navigation";

const SEED_KEY = "midas.chatSeed";

type AppRouter = ReturnType<typeof useRouter>;

/** 상담 요약문을 심고 챗으로 이동한다. */
export function seedChat(router: AppRouter, text: string): void {
  try {
    sessionStorage.setItem(SEED_KEY, text);
  } catch {
    /* sessionStorage 불가 환경은 무시(이동만) */
  }
  router.push("/chat");
}

/** 챗 페이지에서 1회 소비. 읽은 즉시 제거한다. */
export function consumeChatSeed(): string | null {
  try {
    const v = sessionStorage.getItem(SEED_KEY);
    if (v) sessionStorage.removeItem(SEED_KEY);
    return v;
  } catch {
    return null;
  }
}
