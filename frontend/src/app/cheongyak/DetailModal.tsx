"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { X, ChatCircleText, ChartLineUp } from "@phosphor-icons/react";
import {
  getCheongyakHousingTypes,
  getCheongyakCompetition,
  getCheongyakScores,
  getCheongyakSpecialSupply,
  type CheongyakKind,
  type CheongyakSummary,
  type CheongyakHousingType,
  type CheongyakCompetition,
  type CheongyakScore,
  type CheongyakSpecialSupply,
} from "@/lib/api";
import { Skeleton } from "@/components/ui";
import {
  DEFAULT_PROFILE,
  FIRST_PRIORITY_SOURCE_NOTE,
  SIDO,
  areaTierOf,
  firstPriorityChecks,
  loadProfile,
  parseExclusiveArea,
  type MyProfile,
  type Sido,
} from "@/lib/my-profile";
import { AREA_LABELS } from "@/lib/simulate";

interface DetailModalProps {
  item: CheongyakSummary;
  kind: CheongyakKind;
  /** 청약 가점 계산기(page.tsx)에서 계산한 내 점수. 당첨 가점 테이블과 나란히 비교해서 보여준다. */
  myScore: number;
  onClose: () => void;
  onConsult: (item: CheongyakSummary) => void;
}

interface DetailData {
  housingTypes: CheongyakHousingType[];
  competition: CheongyakCompetition[];
  scores: CheongyakScore[];
  special: CheongyakSpecialSupply[];
}

// 청약가점제(84점 만점)는 APT·무순위 일반공급에만 적용된다 — page.tsx의 가점 계산기도 이 기준을 쓴다.
export const SHOW_SCORES_KINDS: CheongyakKind[] = ["apt", "remaining"];
const SHOW_SPECIAL_KINDS: CheongyakKind[] = ["apt"];

/** 이 공고에 실제로 적용되는 1순위 요건으로 다시 대조한다.
 *
 * /me 의 판정은 사용자가 적어 둔 "관심 지역·면적" 기준이라, 실제로 보고 있는 공고와
 * 다를 수 있다(서울 85㎡ 기준으로 충족이어도 그 공고가 102㎡면 예치금이 두 배다).
 * 주택형마다 면적이 달라 예치금 기준이 갈리므로 면적 구간별로 나눠 보여준다. */
function ListingEligibility({
  profile,
  sido,
  housingTypes,
}: {
  profile: MyProfile;
  sido: Sido | null;
  housingTypes: CheongyakHousingType[];
}) {
  if (!sido) return null;

  // 공고에 들어있는 전용면적 구간들(중복 제거). 파싱 실패한 주택형은 건너뛴다.
  const tiers = [
    ...new Set(
      housingTypes
        .map((h) => parseExclusiveArea(h.house_ty))
        .filter((a): a is number => a !== null)
        .map(areaTierOf),
    ),
  ];
  if (tiers.length === 0) return null;

  // 면적과 무관한 항목(통장 기간·무주택·규제지역 요건)은 첫 구간 기준으로 한 번만 보여준다.
  const base = firstPriorityChecks(profile, { sido, area: tiers[0] });
  const shared = base.filter((c) => c.label !== "예치금");
  const depositRows = tiers.map((area) => ({
    area,
    check: firstPriorityChecks(profile, { sido, area }).find((c) => c.label === "예치금")!,
  }));
  // 예치금은 면적 구간마다 기준이 달라 "일부만 충족"이 정상적인 상태다.
  // 헤더가 "충족"이라고 말하면서 아래에 ✕ 가 보이면 모순이므로, 구간별로 정확히 말한다.
  const sharedUnmet = shared.filter((c) => !c.ok);
  const okTiers = depositRows.filter((r) => r.check.ok).map((r) => r.area);
  const ngTiers = depositRows.filter((r) => !r.check.ok).map((r) => r.area);
  const allOk = sharedUnmet.length === 0 && ngTiers.length === 0;
  const noneOk = sharedUnmet.length > 0 || okTiers.length === 0;

  const headline = (() => {
    if (allOk) return `내 정보 기준으로 이 공고(${sido})의 1순위 요건을 충족합니다`;
    if (sharedUnmet.length > 0)
      return `${sharedUnmet.map((c) => c.label).join(", ")} 미달 — 이 공고는 1순위 요건을 채우지 못합니다`;
    if (okTiers.length === 0)
      return `예치금이 모든 주택형 기준에 미달합니다 (${ngTiers.map((a) => AREA_LABELS[a]).join(", ")})`;
    return (
      `${okTiers.map((a) => AREA_LABELS[a]).join(", ")}는 요건 충족, ` +
      `${ngTiers.map((a) => AREA_LABELS[a]).join(", ")}는 예치금 미달`
    );
  })();

  return (
    <Section title="이 공고 기준 1순위 요건">
      <div
        className={`mb-3 rounded-xl border px-3 py-2 text-xs ${
          allOk
            ? "border-positive/30 bg-positive/10 text-positive"
            : noneOk
              ? "border-warning/30 bg-warning/10 text-warning"
              : "border-line bg-[var(--ink-2)]/50 text-fg"
        }`}
      >
        {headline}
      </div>

      <ul className="space-y-2">
        {shared.map((c) => (
          <li key={c.label} className="flex gap-2 text-xs">
            <span className={c.ok ? "text-positive" : "text-warning"}>{c.ok ? "✓" : "✕"}</span>
            <span className="min-w-0">
              <span className="text-fg">{c.label}</span>
              {c.regulatedOnly && <span className="ml-1 text-[10px] text-muted/70">(규제지역)</span>}
              <span className="block font-mono-spec tabular-nums text-[11px] leading-relaxed text-muted">
                {c.detail}
              </span>
            </span>
          </li>
        ))}
        {depositRows.map(({ area, check }) => (
          <li key={area} className="flex gap-2 text-xs">
            <span className={check.ok ? "text-positive" : "text-warning"}>
              {check.ok ? "✓" : "✕"}
            </span>
            <span className="min-w-0">
              <span className="text-fg">예치금</span>{" "}
              <span className="text-[10px] text-muted/70">· {AREA_LABELS[area]}</span>
              <span className="block font-mono-spec tabular-nums text-[11px] leading-relaxed text-muted">
                {check.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-[10px] leading-relaxed text-muted/70">
        규제지역 여부는 공공데이터에 없어 「내 정보」에 체크한 값(
        {profile.regulatedArea ? "규제지역" : "비규제지역"})으로 계산했습니다. 공고문에서 확인하세요.
        {" "}
        {FIRST_PRIORITY_SOURCE_NOTE}
      </p>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5">
      <h4 className="mb-2 text-sm font-semibold text-fg">{title}</h4>
      {children}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <p className="text-xs text-muted">{text}</p>;
}

// 표에 찍히는 숫자는 전부 이 클래스로 통일 — tabular-nums라 자릿수가 흔들리지 않고 읽기 편하다.
const NUM_CLASS = "font-mono-spec tabular-nums";

/** 1000단위 콤마. 원본이 빈 문자열/undefined면 표시할 값이 없다는 뜻으로 null. */
function fmtNum(n: number | string | undefined): string | null {
  const v = typeof n === "string" ? Number(n) : n;
  if (v === undefined || v === null || Number.isNaN(v)) return null;
  return v.toLocaleString("ko-KR");
}

export default function DetailModal({ item, kind, myScore, onClose, onConsult }: DetailModalProps) {
  const [profile, setProfile] = useState<MyProfile>(DEFAULT_PROFILE);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 마운트 시 저장된 내 정보 복원
    setProfile(loadProfile());
  }, []);
  // 공고의 region 은 이미 시/도 단축명("서울","경기")이라 그대로 매칭된다.
  const listingSido = (SIDO as readonly string[]).includes(item.region)
    ? (item.region as Sido)
    : null;
  const [data, setData] = useState<DetailData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 경쟁률·가점·특별공급 실적은 청약홈이 접수 마감 후에만 공개한다. 접수 전/중 공고에서
  // 빈 표가 뜨는 건 오류가 아니라 아직 데이터가 없는 것 — 그대로 밝힌다.
  const pending = item.status === "접수예정" || item.status === "접수중";
  const emptyText = (what: string) =>
    pending
      ? `접수 마감 후 공개되는 정보입니다. (현재 상태: ${item.status})`
      : `이 공고는 ${what} 데이터가 제공되지 않습니다.`;

  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const prevFocusRef = useRef<HTMLElement | null>(null);

  // 포커스 트랩 및 ESC 닫기
  useEffect(() => {
    prevFocusRef.current = document.activeElement as HTMLElement | null;
    closeBtnRef.current?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab") {
        if (!dialogRef.current) return;
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prevFocusRef.current?.focus();
    };
  }, [onClose]);

  // 열려 있는 동안 배경 스크롤 잠금 — 뒤쪽 페이지가 함께 굴러가면 포커스가 이탈한다.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- kind/item 변경 시 로딩 리셋 후 재요청 */
    setData(null);
    setError(null);

    const wantScores = SHOW_SCORES_KINDS.includes(kind);
    const wantSpecial = SHOW_SPECIAL_KINDS.includes(kind);

    // 각 상세는 독립적으로 실패해도 나머지는 표시(allSettled).
    Promise.allSettled([
      getCheongyakHousingTypes(item.house_manage_no, item.pblanc_no),
      getCheongyakCompetition(item.house_manage_no, item.pblanc_no, kind),
      wantScores
        ? getCheongyakScores(item.house_manage_no, item.pblanc_no)
        : Promise.resolve([] as CheongyakScore[]),
      wantSpecial
        ? getCheongyakSpecialSupply(item.house_manage_no, item.pblanc_no)
        : Promise.resolve([] as CheongyakSpecialSupply[]),
    ])
      .then(([ht, cp, sc, sp]) => {
        if (!alive) return;
        const allFailed = [ht, cp, sc, sp].every((r) => r.status === "rejected");
        if (allFailed) {
          const first = [ht, cp, sc, sp].find((r) => r.status === "rejected");
          setError(first && first.status === "rejected" ? String(first.reason) : "상세 조회 실패");
          return;
        }
        setData({
          housingTypes: ht.status === "fulfilled" ? ht.value : [],
          competition: cp.status === "fulfilled" ? cp.value : [],
          scores: sc.status === "fulfilled" ? sc.value : [],
          special: sp.status === "fulfilled" ? sp.value : [],
        });
      });
    return () => {
      alive = false;
    };
  }, [item, kind]);

  // 자금마련 시뮬레이터로 넘길 목표금액. lttot_top_amount는 만원 단위라 원 단위로 환산하고,
  // 주택형이 여러 개면 가장 비싼 쪽(최악의 경우) 기준으로 보수적으로 잡는다.
  const simulatorTarget = Math.max(
    0,
    ...(data?.housingTypes.map((h) => Number(h.lttot_top_amount) || 0) ?? [0]),
  ) * 10_000;
  const simulatorHref = simulatorTarget > 0 ? `/simulator?target=${simulatorTarget}` : "/simulator";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={item.house_nm || "청약 공고 상세"}
      className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-4"
      onClick={onClose}
    >
      {/* 딤 — 모달보다 짧게 페이드 인 (200ms ease-out) */}
      <div className="absolute inset-0 bg-black/50 transition-opacity duration-200 ease-out starting:opacity-0" />
      <div
        ref={dialogRef}
        /* 패널 진입 — 모달은 트리거에 고정되지 않으므로 origin은 center가 맞다.
           모바일 bottom-sheet는 아래에서(starting:translate-y-full), 데스크톱은 제자리 scale-in. */
        className="relative max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-t-[var(--r-xl)] border border-line bg-[var(--ink-1)] p-5 [box-shadow:var(--shadow-float)] transition-[opacity,transform] duration-[240ms] ease-[var(--ease-soft)] starting:translate-y-full starting:opacity-100 sm:rounded-[var(--r-xl)] sm:p-6 sm:starting:translate-y-0 sm:starting:scale-[0.96] sm:starting:opacity-0"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="break-words font-display text-lg font-semibold leading-snug text-fg">
              {item.house_nm || "(이름 없음)"}
            </h3>
            <p className="mt-0.5 text-xs text-muted">
              {[item.region, item.house_secd_nm, item.status].filter(Boolean).join(" · ")}
            </p>
          </div>
          <button
            ref={closeBtnRef}
            onClick={onClose}
            aria-label="닫기"
            className="btn-ghost btn-icon shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {item.address && <p className="mt-2 text-sm text-fg/80">{item.address}</p>}

        {/* 일정 요약 */}
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
          <Meta label="모집공고" value={item.announcement_date} />
          <Meta label="접수시작" value={item.reception_start} />
          <Meta label="접수마감" value={item.reception_end} />
          <Meta label="특별공급" value={item.special_start} />
          <Meta label="당첨발표" value={item.winner_date} />
          <Meta label="입주예정" value={item.move_in_month} />
        </div>

        {/* 본문 */}
        {error && (
          <p className="mt-5 text-sm text-negative">
            상세 조회 실패: {error}
            <br />
            <span className="text-xs text-muted">
              청약 접수 전 공고는 경쟁률·가점 데이터가 아직 없을 수 있습니다.
            </span>
          </p>
        )}

        {!data && !error && (
          <div className="mt-5 flex flex-col gap-3">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        )}

        {data && (
          <>
            {SHOW_SCORES_KINDS.includes(kind) && (
              <ListingEligibility
                profile={profile}
                sido={listingSido}
                housingTypes={data.housingTypes}
              />
            )}

            <Section title="주택형별 공급">
              {data.housingTypes.length === 0 ? (
                <EmptyHint text="주택형 정보가 없습니다." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-line text-muted">
                        <th className="py-2 pr-3 text-left font-medium">주택형</th>
                        <th className="py-2 pr-3 text-right font-medium">공급면적</th>
                        <th className="py-2 pr-3 text-right font-medium">일반</th>
                        <th className="py-2 pr-3 text-right font-medium">특별</th>
                        <th className="py-2 text-right font-medium">분양가(최고)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.housingTypes.map((h, i) => (
                        <tr key={i} className="border-b border-line/50">
                          <td className="py-1.5 pr-3 font-medium">{h.house_ty || "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{h.supply_area || "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(h.general_count) ?? "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(h.special_count) ?? "-"}</td>
                          <td className={`py-1.5 text-right ${NUM_CLASS}`}>
                            {fmtNum(h.lttot_top_amount) ? `${fmtNum(h.lttot_top_amount)}만원` : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            <Section title="경쟁률">
              {data.competition.length === 0 ? (
                <EmptyHint text={emptyText("경쟁률")} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-line text-muted">
                        <th className="py-2 pr-3 text-left font-medium">주택형</th>
                        {data.competition.some((c) => c.region_name) && (
                          <th className="py-2 pr-3 text-left font-medium">지역</th>
                        )}
                        <th className="py-2 pr-3 text-right font-medium">공급</th>
                        <th className="py-2 pr-3 text-right font-medium">접수</th>
                        <th className="py-2 text-right font-medium">경쟁률</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.competition.map((c, i) => (
                        <tr key={i} className="border-b border-line/50">
                          <td className="py-1.5 pr-3 font-medium">{c.house_ty || "-"}</td>
                          {data.competition.some((x) => x.region_name) && (
                            <td className="py-1.5 pr-3">{c.region_name || "-"}</td>
                          )}
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(c.supply_count) ?? "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(c.applicants) ?? c.applicants}</td>
                          <td className={`py-1.5 text-right font-medium text-accent ${NUM_CLASS}`}>
                            {fmtNum(c.competition_rate) ?? c.competition_rate}:1
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            {SHOW_SCORES_KINDS.includes(kind) && (
              <Section title="당첨 가점 (최저/평균/최고)">
                {data.scores.length === 0 ? (
                  <EmptyHint text={emptyText("당첨 가점")} />
                ) : (
                  <>
                    <p className="mb-2 text-[11px] text-muted">
                      내 청약 가점(계산기에서 입력한 값 기준) <span className="font-semibold text-accent">{myScore}점</span>과
                      비교합니다. 과거 최저 당첨가점이며 이번 회차 결과를 보장하지 않습니다.
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-line text-muted">
                            <th className="py-2 pr-3 text-left font-medium">주택형</th>
                            <th className="py-2 pr-3 text-right font-medium">최저</th>
                            <th className="py-2 pr-3 text-right font-medium">평균</th>
                            <th className="py-2 pr-3 text-right font-medium">최고</th>
                            <th className="py-2 text-right font-medium">내 점수 대비</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.scores.map((s, i) => {
                            const min = Number(s.min_score);
                            const hasMin = s.min_score !== "" && s.min_score != null && !Number.isNaN(min);
                            const diff = hasMin ? myScore - min : null;
                            return (
                              <tr key={i} className="border-b border-line/50">
                                <td className="py-1.5 pr-3 font-medium">{s.house_ty || "-"}</td>
                                <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(s.min_score) ?? "-"}</td>
                                <td className={`py-1.5 pr-3 text-right font-medium ${NUM_CLASS}`}>{fmtNum(s.avg_score) ?? "-"}</td>
                                <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(s.max_score) ?? "-"}</td>
                                <td className={`py-1.5 text-right ${NUM_CLASS}`}>
                                  {diff === null ? (
                                    "-"
                                  ) : diff >= 0 ? (
                                    <span className="text-positive">최저가점 이상 (+{diff})</span>
                                  ) : (
                                    <span className="text-warning">{Math.abs(diff)}점 부족</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </Section>
            )}

            {SHOW_SPECIAL_KINDS.includes(kind) && (
              <Section title="특별공급 신청현황">
                {data.special.length === 0 ? (
                  <EmptyHint text={emptyText("특별공급 신청현황")} />
                ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-line text-muted">
                        <th className="py-2 pr-3 text-left font-medium">주택형</th>
                        <th className="py-2 pr-3 text-right font-medium">다자녀</th>
                        <th className="py-2 pr-3 text-right font-medium">신혼</th>
                        <th className="py-2 pr-3 text-right font-medium">생애최초</th>
                        <th className="py-2 text-right font-medium">노부모</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.special.map((s, i) => (
                        <tr key={i} className="border-b border-line/50">
                          <td className="py-1.5 pr-3 font-medium">{s.house_ty || "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(s.multi_child) ?? "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(s.newlywed) ?? "-"}</td>
                          <td className={`py-1.5 pr-3 text-right ${NUM_CLASS}`}>{fmtNum(s.first_life) ?? "-"}</td>
                          <td className={`py-1.5 text-right ${NUM_CLASS}`}>{fmtNum(s.elderly_parent) ?? "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                )}
              </Section>
            )}
          </>
        )}

        {/* 액션 */}
        <div className="mt-6 flex flex-col sm:flex-row sm:items-center gap-2.5 sm:gap-3 border-t border-line pt-4">
          {item.pblanc_url && (
            <a
              href={item.pblanc_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs sm:text-sm text-accent hover:underline py-1"
            >
              청약홈 공고문 보기 →
            </a>
          )}
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 sm:ml-auto w-full sm:w-auto">
            <Link
              href={simulatorHref}
              className="flex items-center justify-center gap-1.5 rounded-full border border-line px-3.5 py-2 text-xs sm:text-sm text-muted transition hover:border-accent hover:text-accent"
            >
              <ChartLineUp size={15} /> 이 청약으로 자금계획 세우기
            </Link>
            <button
              onClick={() => onConsult(item)}
              className="btn-accent flex items-center justify-center gap-1.5 px-4 py-2 text-xs sm:text-sm"
            >
              <ChatCircleText size={15} /> 이 청약 상담받기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div className="rounded-lg border border-line bg-[var(--ink-2)]/40 px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-0.5 font-medium text-fg">{value || "-"}</div>
    </div>
  );
}
