"use client";

import { useEffect, useRef, useState } from "react";

export function formatKoreanUnit(amount: number): string {
  if (!amount || isNaN(amount) || amount <= 0) return "0원";
  const eok = Math.floor(amount / 100_000_000);
  const man = Math.floor((amount % 100_000_000) / 10_000);
  const won = Math.floor(amount % 10_000);

  const parts: string[] = [];
  if (eok > 0) parts.push(`${eok.toLocaleString("ko-KR")}억`);
  if (man > 0) parts.push(`${man.toLocaleString("ko-KR")}만`);
  if (won > 0 && eok === 0) parts.push(`${won.toLocaleString("ko-KR")}`);

  return parts.join(" ") + "원";
}

/** 큰 원화 숫자 입력.
 *  - 타이핑 중 콤마 자동 포맷 + 커서 위치 완벽 보존
 *  - 백스페이스로 완전히 지우기(빈 문자열) 지원 (0으로 강제 튕김 방지)
 *  - 한글 금액 단위(예: 1억원, 4,000만원) 실시간 표기
 */
export function MoneyInput({
  value,
  onChange,
  className = "",
  placeholder = "0",
  showQuickPills = false,
  max = 100_000_000_000,
}: {
  value: number;
  onChange: (n: number) => void;
  className?: string;
  placeholder?: string;
  showQuickPills?: boolean;
  max?: number;
}) {
  const [displayValue, setDisplayValue] = useState(() =>
    value > 0 ? value.toLocaleString("ko-KR") : value === 0 ? "0" : "",
  );
  const inputRef = useRef<HTMLInputElement>(null);
  const isTypingRef = useRef(false);

  // 외부에서 value가 변경되었을 때 (프리셋, 상위 상태 변경 등)
  useEffect(() => {
    if (isTypingRef.current) return;
    const currentNum = Number(displayValue.replace(/[^0-9]/g, "")) || 0;
    if (value !== currentNum) {
      /* eslint-disable react-hooks/set-state-in-effect -- 외부 value 동기화 */
      setDisplayValue(value > 0 ? value.toLocaleString("ko-KR") : value === 0 ? "0" : "");
      /* eslint-enable react-hooks/set-state-in-effect */
    }
  }, [value, displayValue]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    isTypingRef.current = true;
    const raw = e.target.value;
    const digits = raw.replace(/[^0-9]/g, "");

    if (digits === "") {
      setDisplayValue("");
      onChange(0);
      setTimeout(() => {
        isTypingRef.current = false;
      }, 50);
      return;
    }

    const num = Math.min(Number(digits), max);
    const formatted = num.toLocaleString("ko-KR");

    // 커서 위치 보정: 콤마 추가/삭제 시 커서 튐 방지
    const cursorPos = e.target.selectionStart ?? raw.length;
    const digitsBeforeCursor = raw.slice(0, cursorPos).replace(/[^0-9]/g, "").length;

    setDisplayValue(formatted);
    onChange(num);

    requestAnimationFrame(() => {
      if (!inputRef.current) return;
      let newPos = 0;
      let counted = 0;
      for (let i = 0; i < formatted.length; i++) {
        if (/[0-9]/.test(formatted[i])) {
          counted++;
        }
        if (counted === digitsBeforeCursor) {
          newPos = i + 1;
          break;
        }
      }
      if (digitsBeforeCursor === 0) newPos = 0;
      inputRef.current.setSelectionRange(newPos, newPos);
      isTypingRef.current = false;
    });
  };

  const handleBlur = () => {
    isTypingRef.current = false;
    if (displayValue === "" || displayValue === "0") {
      setDisplayValue("0");
      onChange(0);
    } else {
      const num = Number(displayValue.replace(/[^0-9]/g, "")) || 0;
      setDisplayValue(num.toLocaleString("ko-KR"));
    }
  };

  const addAmount = (amount: number) => {
    const current = Number(displayValue.replace(/[^0-9]/g, "")) || 0;
    const next = Math.min(current + amount, max);
    setDisplayValue(next.toLocaleString("ko-KR"));
    onChange(next);
  };

  const resetAmount = () => {
    setDisplayValue("0");
    onChange(0);
  };

  return (
    <div className="space-y-1.5 w-full">
      <div className="relative flex items-center">
        <input
          ref={inputRef}
          type="text"
          inputMode="numeric"
          value={displayValue}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder={placeholder}
          className={`field w-full font-mono-spec tabular-nums pr-24 ${className}`}
        />
        {value > 0 && (
          <span className="pointer-events-none absolute right-3 font-mono-spec text-xs font-semibold text-accent/90">
            {formatKoreanUnit(value)}
          </span>
        )}
      </div>

      {showQuickPills && (
        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
          <button
            type="button"
            onClick={() => addAmount(10_000_000)}
            className="rounded-lg border border-line bg-surface/60 px-2.5 py-1 font-mono-spec text-[11px] font-medium text-muted hover:border-accent hover:text-accent transition-colors"
          >
            +1천만
          </button>
          <button
            type="button"
            onClick={() => addAmount(50_000_000)}
            className="rounded-lg border border-line bg-surface/60 px-2.5 py-1 font-mono-spec text-[11px] font-medium text-muted hover:border-accent hover:text-accent transition-colors"
          >
            +5천만
          </button>
          <button
            type="button"
            onClick={() => addAmount(100_000_000)}
            className="rounded-lg border border-line bg-surface/60 px-2.5 py-1 font-mono-spec text-[11px] font-medium text-muted hover:border-accent hover:text-accent transition-colors"
          >
            +1억
          </button>
          <button
            type="button"
            onClick={resetAmount}
            className="rounded-lg border border-line/40 px-2 py-1 font-mono-spec text-[11px] text-muted/70 hover:text-negative hover:border-negative/40 transition-colors ml-auto"
          >
            초기화
          </button>
        </div>
      )}
    </div>
  );
}
