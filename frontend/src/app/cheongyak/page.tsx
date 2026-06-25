"use client";

import { useEffect, useMemo, useState } from "react";
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
import { Card, PageTitle, Skeleton } from "@/components/ui";
import { useToast } from "@/lib/toast";
import DetailModal from "./DetailModal";

const TABS: { kind: CheongyakKind; label: string }[] = [
  { kind: "apt", label: "APT" },
  { kind: "officetel", label: "오피스텔" },
  { kind: "remaining", label: "무순위/잔여" },
  { kind: "opt", label: "임의공급" },
  { kind: "public-rent", label: "공공임대" },
];

const STATUS_TONE: Record<string, string> = {
  접수중: "text-[#58c8a0] border-[#58c8a0]/40 bg-[#58c8a0]/10",
  접수예정: "text-accent border-accent/40 bg-[color-mix(in_srgb,var(--accent)_12%,transparent)]",
  마감: "text-muted border-line bg-[var(--ink-2)]/40",
  일정미정: "text-muted border-line bg-[var(--ink-2)]/40",
};

function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONE[status] ?? STATUS_TONE["일정미정"];
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>
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
  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <button
          onClick={() => onDetail(item)}
          className="text-left font-display text-base font-semibold leading-snug text-fg transition hover:text-accent"
        >
          {item.house_nm || "(이름 없음)"}
        </button>
        <StatusBadge status={item.status} />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
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
        {item.total_supply > 0 && <span>총 {item.total_supply.toLocaleString()}세대</span>}
      </div>
      {item.address && <p className="text-sm text-fg/80">{item.address}</p>}
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1">
          <CalendarBlank size={13} /> 모집공고 {item.announcement_date || "-"}
        </span>
        <span>접수 {item.reception_start || "-"} ~ {item.reception_end || "-"}</span>
        {item.winner_date && <span>당첨발표 {item.winner_date}</span>}
      </div>
      <div className="mt-1 flex items-center gap-3">
        <button
          onClick={() => onDetail(item)}
          className="inline-flex items-center gap-1 text-xs text-accent transition hover:underline"
          title="주택형·경쟁률·가점 상세 보기"
        >
          <MagnifyingGlassPlus size={13} /> 상세 보기
        </button>
        {item.pblanc_url && (
          <a
            href={item.pblanc_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted transition hover:text-accent"
          >
            공고문 →
          </a>
        )}
        <button
          onClick={() => onConsult(item)}
          className="inline-flex items-center gap-1 text-xs text-muted transition hover:text-accent"
          title="이 청약을 챗 상담으로 넘기기"
        >
          <ChatCircleText size={13} /> 상담받기
        </button>
      </div>
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
  const [detailItem, setDetailItem] = useState<CheongyakSummary | null>(null);

  // 선택 유저의 거주 지역(개인화).
  useEffect(() => {
    if (!selected) {
      setDistrict(null);
      setOnlyMyRegion(false);
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
    setItems(null);
    setError(null);
    listCheongyak(kind)
      .then((data) => alive && setItems(data))
      .catch((e) => {
        if (!alive) return;
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        toast(`청약 조회 실패: ${msg}`, "error");
      });
    return () => {
      alive = false;
    };
  }, [kind, toast]);

  // district 매칭 우선 정렬 + (옵션) 내 지역만 필터.
  const view = useMemo(() => {
    if (!items) return null;
    const key = (district || "").replace(/특별시|광역시|특별자치시|특별자치도|도$/g, "").trim();
    const matches = (it: CheongyakSummary) =>
      key.length >= 2 && (it.region?.includes(key) || it.address?.includes(key));
    let list = items;
    if (onlyMyRegion && key) list = items.filter(matches);
    return [...list].sort((a, b) => Number(matches(b)) - Number(matches(a)));
  }, [items, district, onlyMyRegion]);

  const consult = (item: CheongyakSummary) => {
    const text =
      `[청약 상담] ${item.house_nm} (${item.region || "지역미상"}, ${item.house_secd_nm || "유형미상"})\n` +
      `총 ${item.total_supply}세대 · 접수 ${item.reception_start || "-"}~${item.reception_end || "-"} · 상태 ${item.status}.\n` +
      `내 자격·자금 상황에서 이 청약이 적합한지, 준비할 점은 무엇인지 알려줘.`;
    if (!selected) toast("먼저 홈에서 유저를 선택하면 맞춤 상담이 됩니다.", "info");
    seedChat(router, text);
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <PageTitle
        eyebrow="청약홈"
        title="청약 분양정보"
        subtitle="공공데이터포털 청약홈 API로 최근·예정 분양 공고를 조회합니다."
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.kind}
            onClick={() => setKind(t.kind)}
            className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
              kind === t.kind
                ? "bg-[color-mix(in_srgb,var(--accent)_13%,transparent)] text-accent"
                : "text-muted hover:bg-[color-mix(in_srgb,var(--accent)_6%,transparent)] hover:text-fg"
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

      {error && (
        <Card className="border-[#e2607b]/40">
          <p className="text-sm text-[#e2607b]">조회 실패: {error}</p>
          <p className="mt-1 text-xs text-muted">
            CHEONGYAK_API_KEY 가 설정되지 않았으면 .env 에 공공데이터포털 키를 넣어주세요.
          </p>
        </Card>
      )}

      {!view && !error && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      )}

      {view && view.length === 0 && (
        <p className="text-sm text-muted">
          {onlyMyRegion ? "내 지역 매칭 공고가 없습니다." : "해당 기간에 공고가 없습니다."}
        </p>
      )}

      {view && view.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
