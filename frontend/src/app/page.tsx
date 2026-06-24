"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MagnifyingGlass, ArrowRight } from "@phosphor-icons/react";
import { apiGet, type MarketSnapshot, type UserSummary } from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { useToast } from "@/lib/toast";
import { Reveal } from "@/components/Reveal";
import {
  Card,
  PageTitle,
  SectionLabel,
  Skeleton,
  fmtKRW,
  fmtKRWShort,
} from "@/components/ui";

export default function HomePage() {
  const { selected, setSelected } = useSelectedUser();
  const router = useRouter();
  const toast = useToast();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [market, setMarket] = useState<MarketSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [u, m] = await Promise.all([
          apiGet<{ users: UserSummary[] }>("/api/v1/users?limit=100"),
          apiGet<{ snapshots: MarketSnapshot[] }>("/api/v1/market/snapshots"),
        ]);
        setUsers(u.users);
        setMarket(m.snapshots);
      } catch (e) {
        toast(
          `백엔드 연결 실패: ${e instanceof Error ? e.message : e}. 서버(:8000) 확인`,
          "error",
        );
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return users;
    return users.filter((u) =>
      [u.occupation, u.district, u.preferred_asset, u.family_type]
        .filter(Boolean)
        .some((f) => String(f).toLowerCase().includes(t)),
    );
  }, [q, users]);

  const pick = (u: UserSummary) => {
    const label = `${u.occupation ?? "유저"} · ${u.age ?? "?"}세`;
    setSelected({ uuid: u.uuid, label });
    toast(`${label} 선택됨`, "success");
  };

  return (
    <div className="space-y-10">
      <PageTitle
        eyebrow="Midas Touch"
        title="자산관리 콘솔"
        subtitle="유저를 선택하면 챗봇·대시보드가 해당 유저 기준으로 동작합니다."
      />

      {/* 시장 지표 */}
      <section className="animate-rise">
        <SectionLabel>최신 시장 지표</SectionLabel>
        {loading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : market.length === 0 ? (
          <p className="text-sm text-muted">시장 데이터가 없습니다.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {market.slice(0, 10).map((m, i) => (
              <Reveal key={i} index={i}>
                <Card className="lift h-full p-4">
                  <div className="text-xs text-muted">
                    {m.data_type}
                    {m.sub_key ? ` · ${m.sub_key}` : ""}
                  </div>
                  <div className="mt-1 font-display text-2xl font-semibold text-fg">
                    {Number(m.value).toLocaleString()}
                    <span className="ml-1 text-xs font-normal text-muted">
                      {m.unit}
                    </span>
                  </div>
                  <div className="mt-1 text-[10px] text-muted/70">
                    {m.snapshot_date}
                  </div>
                </Card>
              </Reveal>
            ))}
          </div>
        )}
      </section>

      {/* 유저 목록 */}
      <section className="animate-rise">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <SectionLabel>유저 선택 ({filtered.length})</SectionLabel>
          <div className="relative w-full sm:w-64">
            <MagnifyingGlass
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="직업, 지역, 선호 검색"
              className="field w-full py-1.5 pl-9 pr-3 text-sm"
            />
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : (
          <div className="glass overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="border-b border-line text-muted">
                  <tr>
                    <th className="px-4 py-3 font-medium">직업 / 나이</th>
                    <th className="px-4 py-3 font-medium">가구 / 지역</th>
                    <th className="px-4 py-3 font-medium">총자산</th>
                    <th className="px-4 py-3 font-medium">공격성</th>
                    <th className="px-4 py-3 font-medium">선호</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => {
                    const isSel = selected?.uuid === u.uuid;
                    return (
                      <tr
                        key={u.uuid}
                        className={`border-t border-line/60 transition ${
                          isSel
                            ? "bg-[color-mix(in_srgb,var(--accent)_8%,transparent)]"
                            : "hover:bg-[color-mix(in_srgb,var(--accent)_5%,transparent)]"
                        }`}
                      >
                        <td className="px-4 py-3">
                          {u.occupation ?? "-"}{" "}
                          <span className="text-muted">/ {u.age ?? "?"}</span>
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {u.family_type ?? "-"} / {u.district ?? "-"}
                        </td>
                        <td className="px-4 py-3" title={fmtKRW(u.total_amount)}>
                          {fmtKRWShort(u.total_amount)}
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {u.aggressiveness ?? "-"}/10
                        </td>
                        <td className="px-4 py-3 text-muted">
                          {u.preferred_asset ?? "-"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-2">
                            <Link
                              href={`/dashboard/${u.uuid}`}
                              className="rounded-md px-2 py-1 text-xs text-muted hover:text-accent"
                            >
                              상세
                            </Link>
                            <button
                              onClick={() => {
                                pick(u);
                                router.push("/chat");
                              }}
                              className={
                                isSel
                                  ? "inline-flex items-center gap-1 rounded-md border border-line px-3 py-1 text-xs text-accent"
                                  : "btn-accent inline-flex items-center gap-1 px-3 py-1 text-xs"
                              }
                            >
                              {isSel ? "선택됨, 대화" : "선택 후 대화"}
                              <ArrowRight weight="bold" size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted">
                        검색 결과가 없습니다.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
