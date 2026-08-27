"""tax_and_market_lookup 도구 — 세법/시장 지표 직접 조회.

페르소나 검색(persona_rag)이나 그래프 탐색(graph_rag) 없이, 구조화된 세법 규칙과 최신
거시경제 지표 '수치'만 필요할 때 쓰는 경량 도구. 중복 호출을 막기 위해 별도로 분리한다.
"""

from __future__ import annotations

from langchain_core.tools import tool

from shared.database.connector import get_all_tax_rules, get_latest_market_snapshots

# LLM이 한글 자산명을 넘겨도 0건이 되지 않게 DB 코드로 접어준다.
_ASSET_ALIASES: dict[str, list[str]] = {
    "주식": ["stock_domestic", "stock_foreign"],
    "국내주식": ["stock_domestic"],
    "국내 주식": ["stock_domestic"],
    "해외주식": ["stock_foreign"],
    "해외 주식": ["stock_foreign"],
    "미국주식": ["stock_foreign"],
    "미국 주식": ["stock_foreign"],
    "채권": ["bond"],
    "예금": ["deposit"],
    "예적금": ["deposit"],
    "적금": ["deposit"],
    "펀드": ["fund"],
    "부동산": ["real_estate"],
    "주택": ["real_estate"],
    "아파트": ["real_estate"],
}


@tool
def tax_and_market_lookup(
    asset_types: list[str] | None = None, include_market: bool = True
) -> str:
    """한국 세법 규칙(세율·공제 한도·근거 법령)과 최신 거시경제 지표(환율·금리·자산 인덱스 등)를
    데이터베이스에서 직접 조회한다. 특정 자산의 절세 조건이나 현재 시장 수치만 필요할 때 사용하라.

    Args:
        asset_types: 세법 규칙을 필터링할 자산 코드 목록. DB에 저장된 영문 코드만 매칭되므로
            반드시 다음 값 중에서 고를 것 — 'stock_domestic'(국내주식), 'stock_foreign'(해외주식),
            'bond'(채권), 'deposit'(예적금), 'fund'(펀드), 'real_estate'(부동산).
            예: 국내외 주식 절세 질문이면 ['stock_domestic', 'stock_foreign'].
            한글('주식', '채권' 등)을 넘겨도 자동 매핑된다. 비거나 생략 시 전체 반환.
        include_market: False면 거시경제 지표 섹션을 생략한다(자산 한정 세법 질문의 컨텍스트 절감).
    """
    tax_rules = get_all_tax_rules()
    if asset_types:
        # 원문과 별칭 코드를 모두 허용 — 한글로 넘어와도 0건이 되지 않는다.
        wanted: set[str] = set()
        for a in asset_types:
            stripped = a.strip()
            wanted.add(stripped)
            if stripped in _ASSET_ALIASES:
                wanted.update(_ASSET_ALIASES[stripped])
        tax_rules = [r for r in tax_rules if r.get("asset_type") in wanted]

    lines: list[str] = ["### 세법 규칙"]
    if not tax_rules:
        lines.append(" - 해당 조건의 세법 데이터가 없습니다.")
    else:
        for r in tax_rules:
            rate = float(r.get("tax_rate") or 0) * 100
            local = float(r.get("local_tax_rate") or 0) * 100
            deduction = f"{r.get('deduction_limit'):,}원" if r.get("deduction_limit") else "없음"
            lines.append(
                f" - {r.get('asset_type')}({r.get('income_type')}): 세율 {rate:.2f}% "
                f"(지방세 {local:.2f}%), 공제한도 {deduction} | {r.get('description')} ({r.get('legal_basis')})"
            )

    if include_market:
        lines.append("\n### 최신 시장 지표")
        snapshots = get_latest_market_snapshots()
        if not snapshots:
            lines.append(" - 연동된 시장 지표가 없습니다.")
        else:
            for ms in snapshots:
                lines.append(
                    f" - [{ms.get('data_type')}] {ms.get('sub_key')}: "
                    f"{float(ms.get('value') or 0):,.2f} {ms.get('unit', '')} (기준일: {ms.get('snapshot_date')})"
                )

    return "\n".join(lines)
