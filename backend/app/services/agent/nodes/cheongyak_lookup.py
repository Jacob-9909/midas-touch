"""cheongyak_lookup 도구 노드 — 대화로 최근 청약 공고를 요약한다.

공공데이터 청약홈 API(fetch_recent_apt)에서 최근 APT 공고 상위 N건을 끌어와 tool_context에 넣는다.
CHEONGYAK_API_KEY 미설정(RuntimeError)이나 외부 API 실패는 잡아 안내 문구로 흡수해 그래프를 보호한다.

상세 목록/지역 필터는 웹 `/api/v1/cheongyak`가 담당하고, 이 노드는 대화 맥락용 요약만 제공한다.
"""

from __future__ import annotations

from ..state import AgentState

_TOP_N = 6


def cheongyak_lookup_node(state: AgentState) -> dict:
    try:
        from backend.app.services.cheongyak import fetch_recent_apt

        rows = fetch_recent_apt(days_back=30, days_forward=60)
    except RuntimeError as exc:  # 키 미설정
        return {"tool_context": [f"[cheongyak_lookup 미수행] {exc}"]}
    except Exception as exc:  # noqa: BLE001
        return {"tool_context": [f"[cheongyak_lookup 실패] 공공데이터 API 호출 실패: {exc}"]}

    if not rows:
        return {"tool_context": ["[cheongyak_lookup] 최근 기간에 조회된 APT 청약 공고가 없습니다."]}

    lines: list[str] = []
    for r in rows[:_TOP_N]:
        lines.append(
            f"- {r.get('house_nm', '?')} ({r.get('region', '지역미상')}) · "
            f"{r.get('status', '')} · 접수 {r.get('reception_start', '-')}~{r.get('reception_end', '-')} · "
            f"총 {r.get('total_supply', 0)}세대"
        )
    body = "\n".join(lines)
    return {"tool_context": [f"[cheongyak_lookup·최근 APT 청약 상위 {len(lines)}건]\n{body}"]}
