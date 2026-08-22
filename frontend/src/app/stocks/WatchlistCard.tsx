"use client";

import { useCallback, useEffect, useState } from "react";
import { Star, X, Plus } from "@phosphor-icons/react";
import { errMsg } from "@/lib/async";
import { getWatchlist, addWatchlist, removeWatchlist } from "@/lib/api";
import { Card, SectionLabel } from "@/components/ui";
import { useToast } from "@/lib/toast";

/** 유저별 관심종목 — 칩 클릭으로 분석 실행, 현재 종목 담기/빼기. 유저 미선택 시 안내만. */
export default function WatchlistCard({
  userUuid,
  currentTicker,
  onPick,
}: {
  userUuid?: string;
  currentTicker: string;
  onPick: (ticker: string) => void;
}) {
  const toast = useToast();
  const [tickers, setTickers] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    if (!userUuid) return;
    getWatchlist(userUuid)
      .then(setTickers)
      .catch(() => setTickers([]));
  }, [userUuid]);

  useEffect(() => {
    load();
  }, [load]);

  if (!userUuid) {
    return (
      <Card className="mb-6">
        <SectionLabel>
          <span className="inline-flex items-center gap-1.5">
            <Star size={14} /> 관심종목
          </span>
        </SectionLabel>
        <p className="mt-2 text-xs text-muted">홈에서 유저를 선택하면 관심종목을 저장할 수 있습니다.</p>
      </Card>
    );
  }

  const mutate = async (fn: () => Promise<string[]>) => {
    setBusy(true);
    try {
      setTickers(await fn());
    } catch (e) {
      toast(`관심종목 갱신 실패: ${errMsg(e)}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const symbol = currentTicker.trim().toUpperCase();
  const alreadyIn = tickers.includes(symbol);

  return (
    <Card className="mb-6">
      <div className="flex items-center justify-between">
        <SectionLabel>
          <span className="inline-flex items-center gap-1.5">
            <Star size={14} /> 관심종목
          </span>
        </SectionLabel>
        <button
          onClick={() => mutate(() => addWatchlist(userUuid, symbol))}
          disabled={busy || !symbol || alreadyIn}
          className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-sm disabled:opacity-40"
          title={alreadyIn ? "이미 관심종목에 있습니다" : `${symbol} 담기`}
        >
          <Plus size={14} />
          {alreadyIn ? "담김" : `${symbol || "현재 종목"} 담기`}
        </button>
      </div>

      {tickers.length === 0 ? (
        <p className="mt-2 text-xs text-muted">아직 관심종목이 없습니다. 분석할 종목을 담아보세요.</p>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {tickers.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 rounded-full border border-line pl-3 pr-1.5 py-1 text-xs text-muted transition hover:border-accent hover:text-accent"
            >
              <button onClick={() => onPick(t)} className="font-mono" title={`${t} 분석`}>
                {t}
              </button>
              <button
                onClick={() => mutate(() => removeWatchlist(userUuid, t))}
                disabled={busy}
                aria-label={`${t} 제거`}
                className="rounded-full p-0.5 text-muted hover:text-negative disabled:opacity-40"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}
