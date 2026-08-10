"""AI 투자 분석 리포트 생성 (NIM LLM).

wealth_advisor의 ai_analysis(Google Gemini)를 midas의 NIM LLM(agent/llm.py:build_chat_model)으로
교체 이식했다. 백테스트 메트릭에 시장환경(공포탐욕지수·VIX·기업 프로필)을 덧대 한국어 마크다운
리포트를 생성한다. 시장환경 헬퍼는 best-effort(실패해도 리포트는 생성).
"""

from __future__ import annotations

import datetime
import os

from shared.utils.timez import today_kst

from ..agent.llm import build_chat_model


def generate_analysis(
    ticker: str,
    strategy_name: str,
    metrics: dict,
) -> str:
    """NIM LLM으로 한국어 투자 리포트(마크다운)를 생성한다."""
    fng_text = _fetch_fng()
    vix_text = _fetch_vix()
    profile_text = _fetch_profile(ticker)

    result_text = (
        f"총 거래 횟수: {metrics.get('total_trades', 'N/A')}\n"
        f"전략 총 수익률: {metrics.get('total_return', 0):.2%}\n"
        f"매수 후 보유 수익률: {metrics.get('buy_hold_return', 0):.2%}\n"
        f"연간 수익률: {metrics.get('annual_return', 0):.2%}\n"
        f"최대 낙폭: {metrics.get('max_drawdown', 0):.2%}\n"
        f"최종 포트폴리오 가치: {metrics.get('final_value', 0):,.0f}원"
    )

    prompt = f"""너는 주식 리서치 및 트레이딩 전략 분석에 특화된 최고 수준의 금융 전문가다.
아래는 {ticker} 종목에 대한 분석 데이터이다.

{fng_text}
{vix_text}
---
### 기업 정보
{profile_text}

### 전략 백테스트 성과 ({strategy_name})
{result_text}
---

위 데이터를 기반으로 {ticker} 종목에 대한 종합 투자 분석 리포트를 한국어 마크다운으로 작성하라.

포함 항목:
1. **투자 판단 및 근거** (강력매수/매수/보유/매도/강력매도)
2. **시장 환경 및 변동성 분석** (FNG, VIX 해석)
3. **핵심 전략 인사이트 및 추천**
4. **리스크 요인 및 유의사항**
5. **종합 투자 조언**

마크다운 형식: ## 제목, ### 소제목, **볼드**, - 리스트
간결하면서 실질적 가치를 제공하는 전문 리포트로 작성하라."""

    from langchain_core.messages import HumanMessage

    reply = build_chat_model(temperature=0.4).invoke([HumanMessage(content=prompt)])
    content = reply.content
    return content if isinstance(content, str) else str(content)


def _format_similar_patterns(patterns: list[dict] | None) -> str:
    """유사 과거 분석을 프롬프트용 텍스트로. 없으면 빈 문자열."""
    if not patterns:
        return ""
    lines = ["[유사한 과거 분석 사례 — 현재와 비슷한 지표 조건이었을 때]"]
    for p in patterns:
        dec = p.get("decision") or "?"
        sim = p.get("similarity")
        when = (p.get("created_at") or "")[:10]
        tk = p.get("ticker")
        tag = f"[{tk}] " if tk else ""
        outcome = ""
        if p.get("was_correct") is not None:
            ret = p.get("actual_return_pct")
            mark = "적중" if p.get("was_correct") else "빗나감"
            outcome = f" → 결과: {mark}" + (f" ({ret:+.1f}%)" if ret is not None else "")
        summary = (p.get("summary") or "").strip().replace("\n", " ")
        if len(summary) > 80:
            summary = summary[:80] + "…"
        lines.append(f"- {tag}{when} 당시 판단: {dec} (유사도 {sim}){outcome}. {summary}")
    return "\n".join(lines)


def _format_level_accuracy(level_accuracy: dict | None) -> str:
    """자신감 레벨별 과거 실제 적중률을 프롬프트 텍스트로. LLM이 자기 자신감을 보정하도록.

    {"high": {"accuracy": 0.5, "n": 8}, ...} → 사람이 읽는 안내문. 표본 있는 레벨만 노출.
    """
    if not level_accuracy:
        return ""
    lines = ["[당신의 과거 자신감별 실제 적중률 — 이를 감안해 confidence를 현실적으로 보정하라]"]
    for lvl in ("high", "medium", "low"):
        d = level_accuracy.get(lvl)
        if d and d.get("n"):
            lines.append(f"- {lvl} 자신감 예측은 실제 {round(d['accuracy'] * 100)}% 적중 (표본 {d['n']}건)")
    return "\n".join(lines) if len(lines) > 1 else ""


def generate_quick_report(
    ticker: str,
    indicators: dict,
    similar_patterns: list[dict] | None = None,
    level_accuracy: dict | None = None,
    as_of: str | None = None,
) -> dict:
    """Multi-horizon outlook (24h/3d/1w/1m) from technical snapshot.

    QuantDinger fast_analysis style: one LLM call with structured JSON output.
    similar_patterns가 주어지면 '과거 유사 사례'를, level_accuracy가 주어지면 '자신감별 과거 적중률'을
    프롬프트에 컨텍스트로 주입해 LLM이 confidence를 현실적으로 내도록 유도한다.
    as_of("YYYY-MM-DD")를 주면 과거 시점 재현 모드 — 시장 컨텍스트에 '오늘' 값이 새지 않게 한다.
    Returns dict with decision/confidence/outlook/key_reasons/risks.
    Fails gracefully: returns {"error": reason} without raising.
    """
    import json

    # as_of 모드에서 오늘의 FNG·기업프로필(현재가·52주 레인지 포함)을 넣으면 그대로 룩어헤드다.
    # 과거 값을 받을 경로가 없는 둘은 생략하고, 소급조회가 되는 VIX만 해당 시점 종가로 받는다.
    # ponytail: FNG 과거 시계열이 필요하면 alternative.me API로 채워 넣을 수 있다.
    fng_text = "[탐욕공포지수 데이터 없음]" if as_of else _fetch_fng()
    vix_text = _fetch_vix(as_of)
    profile_text = "기업 프로필 데이터 없음 (과거 시점 재현)" if as_of else _fetch_profile(ticker)
    memory_text = _format_similar_patterns(similar_patterns)
    accuracy_text = _format_level_accuracy(level_accuracy)

    rsi = indicators.get("rsi", {})
    macd = indicators.get("macd", {})
    kdj = indicators.get("kdj", {})
    ma = indicators.get("moving_averages", {})
    bb = indicators.get("bollinger", {})
    atr = indicators.get("atr", {})
    lvl = indicators.get("levels", {})
    cp = indicators.get("current_price", 0)
    chg = indicators.get("change_pct", 0)

    ind_block = (
        f"현재가: {cp:,.4f} ({chg:.2%})\n"
        f"RSI(14): {rsi.get('value')} → {rsi.get('signal')}\n"
        f"MACD 히스토그램: {macd.get('histogram')} → {macd.get('signal')}\n"
        f"KDJ: K={kdj.get('k')}, D={kdj.get('d')}, J={kdj.get('j')}\n"
        f"MA 추세: {ma.get('trend')} | SMA20={ma.get('sma20')}, SMA50={ma.get('sma50')}, SMA200={ma.get('sma200')}\n"
        f"볼린저 %B: {bb.get('pct_b')} (상단={bb.get('upper')}, 하단={bb.get('lower')})\n"
        f"ATR 변동성: {atr.get('volatility')} ({atr.get('pct', 0):.2%})\n"
        f"지지선: {lvl.get('support')}, 저항선: {lvl.get('resistance')}"
    )

    memory_block = f"\n{memory_text}\n" if memory_text else ""
    accuracy_block = f"\n{accuracy_text}\n" if accuracy_text else ""

    prompt = f"""당신은 기술적 분석 전문가입니다. {ticker} 종목의 기술적 지표를 분석해 JSON으로 응답하세요.

시장 환경:
{fng_text}
{vix_text}

기업 정보:
{profile_text}

기술적 지표:
{ind_block}
{memory_block}{accuracy_block}
아래 JSON 형식으로만 응답하세요(설명·마크다운 없이 순수 JSON):
{{
  "decision": "BUY" 또는 "SELL" 또는 "HOLD",
  "confidence": "high" 또는 "medium" 또는 "low",
  "summary": "2-3문장 핵심 한국어 요약",
  "outlook": {{
    "24h": {{"trend": "BUY/SELL/HOLD", "strength": "strong/moderate/weak", "note": "한 줄"}},
    "3d":  {{"trend": "BUY/SELL/HOLD", "strength": "strong/moderate/weak", "note": "한 줄"}},
    "1w":  {{"trend": "BUY/SELL/HOLD", "strength": "strong/moderate/weak", "note": "한 줄"}},
    "1m":  {{"trend": "BUY/SELL/HOLD", "strength": "strong/moderate/weak", "note": "한 줄"}}
  }},
  "key_reasons": ["이유1", "이유2", "이유3"],
  "risks": ["리스크1", "리스크2"]
}}"""

    from langchain_core.messages import HumanMessage

    try:
        reply = build_chat_model(temperature=0.2).invoke([HumanMessage(content=prompt)])
        content = reply.content if isinstance(reply.content, str) else str(reply.content)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return {"error": "JSON 파싱 실패", "raw": content[:200]}
    except Exception as exc:
        return {"error": str(exc)}


# ── helper: Fear & Greed index ────────────────────────
def _fetch_fng() -> str:
    try:
        from fear_and_greed import get as get_fng

        d = get_fng()
        return (
            f"[탐욕공포지수] value: {d.value}, description: {d.description}, "
            f"last_update: {d.last_update.date()}"
        )
    except Exception:
        return "[탐욕공포지수 데이터 없음]"


def _fetch_vix(as_of: str | None = None) -> str:
    """VIX 종가. as_of("YYYY-MM-DD")를 주면 그 날짜까지의 마지막 종가만 본다(룩어헤드 차단)."""
    try:
        import yfinance as yf

        vix = yf.Ticker("^VIX")
        anchor = datetime.date.fromisoformat(as_of) if as_of else today_kst()
        # yfinance의 end는 배타적 → anchor 당일 봉까지 포함하려면 +1일. 휴일 대비로 10일치를 받는다.
        hist = vix.history(
            start=(anchor - datetime.timedelta(days=10)).isoformat(),
            end=(anchor + datetime.timedelta(days=1)).isoformat(),
        )
        if not hist.empty:
            val = round(float(hist["Close"].iloc[-1]), 2)
            return f"[VIX 변동성지수] value: {val}"
    except Exception:
        pass
    return "[VIX 데이터 없음]"


def _fetch_profile(ticker: str) -> str:
    fmp_key = os.getenv("FMP_API_KEY", "")
    if not fmp_key:
        return "기업 프로필 데이터 없음 (FMP_API_KEY 미설정)"
    try:
        import requests

        url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={fmp_key}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data and isinstance(data, list):
            p = data[0]
            return (
                f"Beta: {p.get('beta', 'N/A')}\n"
                f"Average Volume: {p.get('averageVolume', 'N/A')}\n"
                f"Market Cap: {p.get('marketCap', 'N/A')}\n"
                f"52-Week Range: {p.get('range', 'N/A')}\n"
                f"Price: {p.get('price', 'N/A')}"
            )
    except Exception:
        pass
    return "기업 프로필 데이터 조회 실패"
