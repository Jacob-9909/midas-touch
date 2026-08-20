"use client";

import { useEffect, useMemo, useState } from "react";
import { errMsg } from "@/lib/async";
import { useRouter } from "next/navigation";
import {
  Buildings,
  MapPin,
  CalendarBlank,
  ChatCircleText,
  MagnifyingGlassPlus,
} from "@phosphor-icons/react";
import {
  apiGet,
  listCheongyak,
  type CheongyakKind,
  type CheongyakSummary,
  type UserDetail,
} from "@/lib/api";
import { useSelectedUser } from "@/lib/user-context";
import { seedChat } from "@/lib/chat-seed";
import {
  DEPENDENTS_NOTE,
  MAX_SCORE,
  SCORE_SOURCE_NOTE,
  totalCheongyakScore,
} from "@/lib/cheongyak-score";
import OGHeroCard from "@/components/bits/OGHeroCard";
import LiveSyncBadge from "@/components/bits/LiveSyncBadge";
import PopularCard from "@/components/bits/PopularCard";
import SpecularMetricCard from "@/components/bits/SpecularMetricCard";
import { Card, PageTitle, Skeleton } from "@/components/ui";
import { useToast } from "@/lib/toast";
import DetailModal, { SHOW_SCORES_KINDS } from "./DetailModal";
import KoreaMap from "./KoreaMap";
import { PROVINCES, matchProvince } from "./korea-geo";

const TABS: { kind: CheongyakKind; label: string }[] = [
  { kind: "apt", label: "APT" },
  { kind: "officetel", label: "오피스텔" },
  { kind: "remaining", label: "무순위/잔여" },
  { kind: "opt", label: "임의공급" },
  { kind: "public-rent", label: "공공임대" },
];

// 상태 필터 (백엔드 status 값과 일치). "전체"는 미필터.
const STATUS_FILTERS = ["전체", "접수중", "접수예정", "마감"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

const STATUS_TONE: Record<string, string> = {
  접수중: "text-[#58c8a0] border-[#58c8a0]/40 bg-[#58c8a0]/10",
  접수예정: "text-accent border-accent/40 bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]",
  마감: "text-muted border-line bg-[var(--ink-2)]/40",
  일정미정: "text-muted border-line bg-[var(--ink-2)]/40",
};

function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? STATUS_TONE["일정미정"];
  const isLive = status === "접수중";
  return (
    <span
      className={`shrink-0 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold flex items-center gap-1.5 ${tone}`}
    >
      {isLive && (
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#58c8a0] opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-[#58c8a0]" />
        </span>
      )}
      {status || "-"}
    </span>
  );
}

function CheongyakCard({
  item,
  onConsult,
  onDetail,
}: {
  item: CheongyakSummary;
  onConsult: (item: CheongyakSummary) => void;
  onDetail: (item: CheongyakSummary) => void;
}) {
  const isHot = item.status === "접수중" || item.total_supply > 300;

  return (
    <SpecularMetricCard glowColor={isHot ? "gold" : "cyan"}>
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            {isHot && (
              <span className="inline-block rounded-full border border-orange-500/40 bg-orange-500/10 px-2 py-0.5 font-mono-spec text-[9px] font-bold text-orange-400">
                🔥 POPULAR HOT
              </span>
            )}
            <button
              onClick={() => onDetail(item)}
              className="block text-left font-display text-base font-bold leading-snug text-fg transition hover:text-accent"
            >
              {item.house_nm || "(이름 없음)"}
            </button>
          </div>
          <StatusBadge status={item.status} />
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted font-mono-spec">
          {item.region && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={13} /> {item.region}
            </span>
          )}
          {item.house_secd_nm && (
            <span className="inline-flex items-center gap-1">
              <Buildings size={13} /> {item.house_secd_nm}
            </span>
          )}
          {item.total_supply > 0 && <span className="text-accent font-semibold">총 {item.total_supply.toLocaleString()}세대</span>}
        </div>
        {item.address && <p className="text-xs text-fg/80">{item.address}</p>}
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted font-mono-spec">
          <span className="inline-flex items-center gap-1">
            <CalendarBlank size={13} /> 모집공고 {item.announcement_date || "-"}
          </span>
          <span>접수 {item.reception_start || "-"} ~ {item.reception_end || "-"}</span>
          {item.winner_date && <span>당첨발표 {item.winner_date}</span>}
        </div>
        <div className="mt-2 flex items-center gap-3 pt-2 border-t border-line/40">
          <button
            onClick={() => onDetail(item)}
            className="flex items-center gap-1 text-xs text-muted hover:text-fg font-mono-spec transition"
          >
            <MagnifyingGlassPlus size={14} /> 상세보기
          </button>
          <button
            onClick={() => onConsult(item)}
            className="ml-auto flex items-center gap-1 rounded-full border border-accent/40 bg-accent/15 px-3 py-1 text-xs font-mono-spec text-accent hover:bg-accent/25 transition"
          >
            <ChatCircleText size={14} /> 상담받기
          </button>
        </div>
      </div>
    </SpecularMetricCard>
  );
}

// 내 청약 가점 계산기 상태. 여러 공고 상세를 오가며 비교해야 하므로 localStorage에 영속해
// 매번 다시 입력하지 않게 한다.
const SCORE_STORAGE_KEY = "midas.cheongyak.myScore.v1";

interface ScoreState {
  homelessYears: number;
  dependents: number;
  subscriptionYears: number;
  under30Unmarried: boolean;
}

const DEFAULT_SCORE_STATE: ScoreState = {
  homelessYears: 3,
  dependents: 0,
  subscriptionYears: 5,
  under30Unmarried: false,
};

function MyScoreCard({
  state,
  onChange,
  applicable,
}: {
  state: ScoreState;
  onChange: (s: ScoreState) => void;
  /** 청약가점제(84점제)는 APT·무순위 일반공급에만 적용됨 — 다른 탭에서는 계산기 대신 안내만. */
  applicable: boolean;
}) {
  const score = totalCheongyakScore(state);
  const inputClass =
    "w-full rounded-xl border border-line bg-[var(--ink-2)]/50 px-3 py-2 text-sm text-fg outline-none focus:border-accent font-mono-spec tabular-nums";

  if (!applicable) {
    return (
      <Card className="text-xs text-muted">
        이 유형에는 청약가점제(84점 만점)가 적용되지 않습니다 — APT·무순위 일반공급에서만 가점제를 씁니다.
      </Card>
    );
  }

  return (
    <Card className="flex flex-col gap-3">
      <label className="flex items-center gap-2 text-xs text-muted">
        <input
          type="checkbox"
          className="h-3.5 w-3.5 accent-[var(--accent)]"
          checked={state.under30Unmarried}
          onChange={(e) => onChange({ ...state, under30Unmarried: e.target.checked })}
        />
        만 30세 미만이면서 미혼
        <span className="text-[10px] text-muted/70">
          (무주택기간은 만 30세부터 계산 — 30세 이전 혼인 시 혼인신고일부터. 해당하면 무주택기간 0점)
        </span>
      </label>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
      <div className="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted">무주택기간(년)</span>
          <input
            type="number"
            min={0}
            max={30}
            step={0.5}
            disabled={state.under30Unmarried}
            className={`${inputClass} disabled:opacity-40`}
            value={state.under30Unmarried ? 0 : state.homelessYears}
            onChange={(e) => onChange({ ...state, homelessYears: Number(e.target.value) })}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted">부양가족수(명, 본인 제외)</span>
          <input
            type="number"
            min={0}
            max={10}
            step={1}
            className={inputClass}
            value={state.dependents}
            onChange={(e) => onChange({ ...state, dependents: Number(e.target.value) })}
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs text-muted">청약통장 가입기간(년)</span>
          <input
            type="number"
            min={0}
            max={30}
            step={0.5}
            className={inputClass}
            value={state.subscriptionYears}
            onChange={(e) => onChange({ ...state, subscriptionYears: Number(e.target.value) })}
          />
        </label>
      </div>
      <div className="shrink-0 rounded-xl border border-accent/30 bg-accent/10 px-4 py-2.5 text-center font-mono-spec">
        <div className="text-[10px] uppercase tracking-wider text-accent/80">내 청약 가점</div>
        <div className="font-mono-spec text-2xl font-bold tabular-nums text-accent">
          {score}
          <span className="text-sm text-muted">/{MAX_SCORE}</span>
        </div>
      </div>
      </div>
      <p className="text-[10px] leading-relaxed text-muted/70">{DEPENDENTS_NOTE}</p>
      <p className="text-[10px] text-muted/70">{SCORE_SOURCE_NOTE}</p>
    </Card>
  );
}

export default function CheongyakPage() {
  const toast = useToast();
  const router = useRouter();
  const { selected } = useSelectedUser();
  const [kind, setKind] = useState<CheongyakKind>("apt");
  const [items, setItems] = useState<CheongyakSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [district, setDistrict] = useState<string | null>(null);
  const [onlyMyRegion, setOnlyMyRegion] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("전체");
  const [mapRegion, setMapRegion] = useState<string | null>(null);
  const [detailItem, setDetailItem] = useState<CheongyakSummary | null>(null);
  const [scoreState, setScoreState] = useState<ScoreState>(DEFAULT_SCORE_STATE);

  // 마운트 1회 localStorage 복원(서버엔 localStorage 없어 lazy init 불가 → effect가 정답).
  useEffect(() => {
    const raw = localStorage.getItem(SCORE_STORAGE_KEY);
    if (raw) {
      try {
        // 예전 버전 localStorage엔 under30Unmarried 필드가 없을 수 있어 기본값과 병합.
        /* eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 저장된 가점 입력 복원 */
        setScoreState({ ...DEFAULT_SCORE_STATE, ...JSON.parse(raw) });
      } catch {
        /* 무시 — 기본값 유지 */
      }
    }
  }, []);

  const updateScoreState = (s: ScoreState) => {
    setScoreState(s);
    localStorage.setItem(SCORE_STORAGE_KEY, JSON.stringify(s));
  };
  const myScore = totalCheongyakScore(scoreState);

  // 선택 유저의 거주 지역(개인화).
  useEffect(() => {
    if (!selected) {
      /* eslint-disable react-hooks/set-state-in-effect -- 유저 해제 시 지역 개인화 상태 초기화 */
      setDistrict(null);
      setOnlyMyRegion(false);
      /* eslint-enable react-hooks/set-state-in-effect */
      return;
    }
    let alive = true;
    apiGet<UserDetail>(`/api/v1/users/${selected.uuid}`)
      .then((d) => {
        if (!alive) return;
        const dist = (d.profile?.district as string) || null;
        setDistrict(dist);
      })
      .catch(() => alive && setDistrict(null));
    return () => {
      alive = false;
    };
  }, [selected]);

  useEffect(() => {
    let alive = true;
    /* eslint-disable react-hooks/set-state-in-effect -- kind 변경 시 로딩 리셋 후 재요청 */
    setItems(null);
    setError(null);
    setMapRegion(null);
    /* eslint-enable react-hooks/set-state-in-effect */
    listCheongyak(kind, 120, 120)
      .then((data) => alive && setItems(data))
      .catch((e) => {
        if (!alive) return;
        const msg = errMsg(e);
        setError(msg);
        toast(`청약 조회 실패: ${msg}`, "error");
      });
    return () => {
      alive = false;
    };
  }, [kind, toast]);

  // 상태별 개수(필터 칩 배지용) — 지역 필터와 무관하게 전체 기준.
  const statusCounts = useMemo(() => {
    const c: Record<string, number> = {};
    (items ?? []).forEach((it) => {
      c[it.status] = (c[it.status] ?? 0) + 1;
    });
    return c;
  }, [items]);

  // 상태 필터만 적용한 목록 — 지도 카운트와 최종 view 의 공통 기준.
  const statusFiltered = useMemo(() => {
    if (!items) return null;
    return statusFilter === "전체" ? items : items.filter((it) => it.status === statusFilter);
  }, [items, statusFilter]);

  // 시도별 공고 수 (지도 채움 농도용).
  const regionCounts = useMemo(() => {
    const c: Record<string, number> = {};
    PROVINCES.forEach((p) => {
      c[p.short] = (statusFiltered ?? []).filter((it) => matchProvince(it, p)).length;
    });
    return c;
  }, [statusFiltered]);

  // 지도 선택 → district 매칭 우선 정렬 + (옵션) 내 지역만 필터.
  // 2순위는 '결과 공개' 여부 — 경쟁률·가점은 접수 마감 후에만 API로 내려오므로, 상세가 빈 채로
  // 열리는 접수예정 공고를 목록 맨 위에 두지 않는다. (상태 칩으로 언제든 접수예정만 볼 수 있다)
  const view = useMemo(() => {
    if (!statusFiltered) return null;
    const key = (district || "").replace(/특별시|광역시|특별자치시|특별자치도|도$/g, "").trim();
    const matches = (it: CheongyakSummary) =>
      key.length >= 2 && (it.region?.includes(key) || it.address?.includes(key));
    const hasResults = (it: CheongyakSummary) => it.status === "마감";
    let list = statusFiltered;
    const prov = PROVINCES.find((p) => p.short === mapRegion);
    if (prov) list = list.filter((it) => matchProvince(it, prov));
    if (onlyMyRegion && key) list = list.filter(matches);
    return [...list].sort(
      (a, b) =>
        Number(matches(b)) - Number(matches(a)) ||
        Number(hasResults(b)) - Number(hasResults(a)),
    );
  }, [statusFiltered, district, onlyMyRegion, mapRegion]);

  const consult = (item: CheongyakSummary) => {
    const text =
      `[청약 상담] ${item.house_nm} (${item.region || "지역미상"}, ${item.house_secd_nm || "유형미상"})\n` +
      `총 ${item.total_supply}세대 · 접수 ${item.reception_start || "-"}~${item.reception_end || "-"} · 상태 ${item.status}.\n` +
      `내 자격·자금 상황에서 이 청약이 적합한지, 준비할 점은 무엇인지 알려줘.`;
    if (!selected) toast("먼저 홈에서 유저를 선택하면 맞춤 상담이 됩니다.", "info");
    seedChat(router, text);
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 space-y-6">
      <OGHeroCard
        categoryTag="REAL ESTATE & SUBSCRIPTION"
        title="전국 청약 분양정보 큐레이션"
        subtitle="한국부동산원 청약홈 실시간 공공 데이터로 주택, 오피스텔, 잔여세대 분양 정보를 탐색하고 AI 가점 분석을 받으세요."
        badgeContent={<LiveSyncBadge state="live" label="CHEONGYAK-HOME LIVE" latencyMs={10} />}
        metrics={[
          { label: "실시간 분양 공고", value: items ? `${items.length}건` : "조회중" },
          { label: "접수 중 단지", value: items ? `${statusCounts["접수중"] ?? 0}개` : "-" },
        ]}
      />

      <MyScoreCard state={scoreState} onChange={updateScoreState} applicable={SHOW_SCORES_KINDS.includes(kind)} />

      <div className="flex flex-wrap items-center gap-2 font-mono-spec text-xs bg-[#090d16]/80 p-1.5 rounded-full border border-line-50">
        {TABS.map((t) => (
          <button
            key={t.kind}
            onClick={() => setKind(t.kind)}
            className={`rounded-full px-4 py-1.5 text-xs font-semibold transition-all duration-200 ${
              kind === t.kind
                ? "bg-accent/20 text-accent border border-accent/40 shadow-[0_0_12px_rgba(212,175,96,0.18)]"
                : "text-muted hover:text-fg border border-transparent"
            }`}
          >
            {t.label}
          </button>
        ))}
        {district && (
          <button
            onClick={() => setOnlyMyRegion((v) => !v)}
            className={`ml-auto inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs transition ${
              onlyMyRegion
                ? "border-accent/40 bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] text-accent"
                : "border-line text-muted hover:text-fg"
            }`}
            title={`${district} 매칭 공고만`}
          >
            <MapPin size={13} /> 내 지역만 ({district})
          </button>
        )}
      </div>

      {/* 상태 필터: 접수중 / 접수예정 / 마감 */}
      {items && items.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          {STATUS_FILTERS.map((s) => {
            const count = s === "전체" ? items.length : statusCounts[s] ?? 0;
            const active = statusFilter === s;
            return (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition ${
                  active
                    ? "border-accent/50 bg-[color-mix(in_srgb,var(--accent)_14%,transparent)] text-accent"
                    : "border-line text-muted hover:text-fg"
                }`}
              >
                {s}
                <span className={active ? "text-accent/80" : "text-muted/70"}>{count}</span>
              </button>
            );
          })}
          <span className="w-full text-xs text-muted sm:w-auto sm:pl-1">
            경쟁률·가점은 접수 마감 후 공개되어, 결과가 있는 공고를 먼저 보여줍니다.
          </span>
        </div>
      )}

      {/* 지역 지도: 클릭하면 해당 시도로 필터 + 포커싱 */}
      {items && items.length > 0 && (
        <Card className="mb-5 flex flex-col items-center gap-5 lg:flex-row lg:items-start">
          <KoreaMap counts={regionCounts} selected={mapRegion} onSelect={setMapRegion} />
          <div className="min-w-0 flex-1 text-sm">
            {mapRegion ? (
              <>
                <div className="flex items-center gap-2">
                  <span className="font-display text-lg font-semibold text-accent">{mapRegion}</span>
                  <span className="text-muted">공고 {regionCounts[mapRegion] ?? 0}건</span>
                  <button
                    onClick={() => setMapRegion(null)}
                    className="ml-auto rounded-full border border-line px-3 py-1 text-xs text-muted transition hover:text-fg"
                  >
                    전체 보기 ✕
                  </button>
                </div>
                <p className="mt-2 text-xs text-muted">
                  다른 시도를 누르면 이동, 같은 곳을 다시 누르거나 지도 바깥을 누르면 전체로 돌아갑니다.
                </p>
              </>
            ) : (
              <>
                <p className="font-display text-base text-fg">지역으로 좁혀보기</p>
                <p className="mt-2 text-xs leading-relaxed text-muted">
                  지도에서 시도를 누르면 해당 지역 공고만 보이고 지도도 그 지역으로 확대됩니다. 색이
                  진할수록 공고가 많은 지역입니다.
                </p>
              </>
            )}
            <div className="mt-4 flex flex-wrap gap-1.5">
              {PROVINCES.filter((p) => (regionCounts[p.short] ?? 0) > 0).map((p) => (
                <button
                  key={p.code}
                  onClick={() => setMapRegion(p.short === mapRegion ? null : p.short)}
                  className={`rounded-full border px-2.5 py-0.5 text-xs transition ${
                    p.short === mapRegion
                      ? "border-accent/50 bg-[color-mix(in_srgb,var(--accent)_14%,transparent)] text-accent"
                      : "border-line text-muted hover:text-fg"
                  }`}
                >
                  {p.short} {regionCounts[p.short]}
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}

      {error && (
        <Card className="border-[#e2607b]/40">
          <p className="text-sm text-[#e2607b]">조회 실패: {error}</p>
          <p className="mt-1 text-xs text-muted">
            CHEONGYAK_API_KEY 가 설정되지 않았으면 .env 에 공공데이터포털 키를 넣어주세요.
          </p>
        </Card>
      )}

      {!view && !error && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      )}

      {view && view.length === 0 && (
        <p className="text-sm text-muted">
          {mapRegion
            ? `'${mapRegion}' 지역에 조건에 맞는 공고가 없습니다.`
            : statusFilter !== "전체"
            ? `'${statusFilter}' 상태의 공고가 없습니다.`
            : onlyMyRegion
              ? "내 지역 매칭 공고가 없습니다."
              : "해당 기간에 공고가 없습니다."}
        </p>
      )}

      {view && view.length > 0 && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
          {view.map((item) => (
            <CheongyakCard
              key={`${item.house_manage_no}-${item.pblanc_no}`}
              item={item}
              onConsult={consult}
              onDetail={setDetailItem}
            />
          ))}
        </div>
      )}

      {detailItem && (
        <DetailModal
          item={detailItem}
          kind={kind}
          myScore={myScore}
          onClose={() => setDetailItem(null)}
          onConsult={(it) => {
            setDetailItem(null);
            consult(it);
          }}
        />
      )}
    </main>
  );
}
