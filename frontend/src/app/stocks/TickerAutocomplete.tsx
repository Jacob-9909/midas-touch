"use client";

import { useEffect, useRef, useState } from "react";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { searchTickers, type TickerSearchItem } from "@/lib/api";

interface TickerAutocompleteProps {
  value: string;
  onChange: (v: string) => void;
  /** 종목 확정(Enter 또는 항목 선택). 선택된 심볼을 넘긴다. */
  onSubmit: (symbol: string) => void;
}

/** 야후 파이낸스 티커 검색 자동완성 입력. 디바운스 250ms, 키보드 탐색 지원. */
export default function TickerAutocomplete({ value, onChange, onSubmit }: TickerAutocompleteProps) {
  const [results, setResults] = useState<TickerSearchItem[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const boxRef = useRef<HTMLDivElement>(null);
  const skipNextSearch = useRef(false);

  // 디바운스 검색.
  useEffect(() => {
    if (skipNextSearch.current) {
      skipNextSearch.current = false;
      return;
    }
    const q = value.trim();
    if (q.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    let alive = true;
    const t = setTimeout(() => {
      searchTickers(q)
        .then((r) => {
          if (!alive) return;
          setResults(r);
          setOpen(r.length > 0);
          setActive(-1);
        })
        .catch(() => alive && setResults([]));
    }, 250);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [value]);

  // 외부 클릭 닫기.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, []);

  const pick = (item: TickerSearchItem) => {
    skipNextSearch.current = true; // 선택 직후 재검색 막기
    onChange(item.symbol);
    setOpen(false);
    setResults([]);
    onSubmit(item.symbol);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open || results.length === 0) {
      if (e.key === "Enter") onSubmit(value);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (active >= 0 && active < results.length) pick(results[active]);
      else onSubmit(value);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} className="relative flex flex-1 flex-col gap-1.5">
      <span className="text-xs text-muted">티커 / 종목명 검색</span>
      <div className="relative">
        <MagnifyingGlass
          size={15}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
        />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="예: AAPL, 삼성전자, Tesla, 7203.T"
          className="w-full rounded-xl border border-line bg-[var(--ink-2)]/50 py-2 pl-9 pr-3 text-sm text-fg outline-none focus:border-accent"
          autoComplete="off"
        />
      </div>

      {open && results.length > 0 && (
        <ul className="absolute top-full z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-line bg-[var(--ink-1)] py-1 [box-shadow:var(--shadow-float)]">
          {results.map((r, i) => (
            <li key={`${r.symbol}-${i}`}>
              <button
                onMouseEnter={() => setActive(i)}
                onClick={() => pick(r)}
                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors ${
                  i === active ? "bg-[color-mix(in_srgb,var(--accent)_10%,transparent)]" : ""
                }`}
              >
                <span className="flex min-w-0 flex-col">
                  <span className="truncate text-fg">{r.name || r.symbol}</span>
                  {r.exchange && <span className="truncate text-xs text-muted">{r.exchange}</span>}
                </span>
                <span className="shrink-0 font-mono text-xs text-accent">{r.symbol}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
