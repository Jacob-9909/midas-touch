"use client";

/** 아직 내 정보를 한 번도 저장하지 않은 사람에게 "여기부터"를 알려주는 줄.
 *
 * 저장 전에는 화면에 기본값이 보이고 있을 뿐인데, 그걸 자기 값으로 오해하면
 * 가점도 1순위 판정도 남의 숫자를 보게 된다. 그래서 조용히 두지 않고 명시한다.
 * 한 번이라도 저장했으면 사라진다. */

import { useEffect, useState } from "react";
import Link from "next/link";
import { hasSavedProfile } from "@/lib/my-profile";

export default function ProfileNudge({
  className = "",
  ...rest
}: { className?: string } & React.ComponentPropsWithoutRef<"a">) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 저장 이력(localStorage) 확인
    setShow(!hasSavedProfile());
  }, []);

  if (!show) return null;

  return (
    <Link
      href="/me"
      className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--r-md)] border border-accent/40 bg-accent/10 px-4 py-3 text-sm transition hover:bg-accent/15 ${className}`}
      {...rest}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-[var(--ink)]">
        1
      </span>
      <span className="font-semibold text-accent">내 정보를 먼저 입력하세요</span>
      <span className="min-w-0 text-xs text-muted">
        지금 보이는 가점·자격 판정은 예시 기본값입니다. 무주택기간·부양가족수·청약통장 정보를 넣으면 내 기준으로 바뀝니다.
      </span>
      <span className="ml-auto shrink-0 text-accent">→</span>
    </Link>
  );
}
