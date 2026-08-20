"use client";

import { useEffect, useState } from "react";
import { X, ChatCircleText } from "@phosphor-icons/react";
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

const SHOW_SCORES_KINDS: CheongyakKind[] = ["apt", "remaining"];
const SHOW_SPECIAL_KINDS: CheongyakKind[] = ["apt"];

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
  const [data, setData] = useState<DetailData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 경쟁률·가점·특별공급 실적은 청약홈이 접수 마감 후에만 공개한다. 접수 전/중 공고에서
  // 빈 표가 뜨는 건 오류가 아니라 아직 데이터가 없는 것 — 그대로 밝힌다.
  const pending = item.status === "접수예정" || item.status === "접수중";
  const emptyText = (what: string) =>
    pending
      ? `접수 마감 후 공개되는 정보입니다. (현재 상태: ${item.status})`
      : `이 공고는 ${what} 데이터가 제공되지 않습니다.`;

  // ESC 닫기
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

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

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-t-[var(--r-xl)] border border-line bg-[var(--ink-1)] p-5 [box-shadow:var(--shadow-float)] sm:rounded-[var(--r-xl)] sm:p-6"
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
            onClick={onClose}
            aria-label="닫기"
            className="btn-ghost flex h-8 w-8 shrink-0 items-center justify-center"
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
          <p className="mt-5 text-sm text-[#e2607b]">
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
                                    <span className="text-[#58c8a0]">최저가점 이상 (+{diff})</span>
                                  ) : (
                                    <span className="text-[#e2a05b]">{Math.abs(diff)}점 부족</span>
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
        <div className="mt-6 flex items-center gap-3 border-t border-line pt-4">
          {item.pblanc_url && (
            <a
              href={item.pblanc_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-accent hover:underline"
            >
              청약홈 공고문 보기 →
            </a>
          )}
          <button
            onClick={() => onConsult(item)}
            className="btn-accent ml-auto flex items-center gap-1.5 px-4 py-2 text-sm"
          >
            <ChatCircleText size={15} /> 이 청약 상담받기
          </button>
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
