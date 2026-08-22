"""ChatService — 멀티턴 채팅 비즈니스 로직.

HTTP 핸들러(api/chat.py)에 흩어져 복붙돼 있던 로직(프로필 404, 첫 턴 판정, 프로필 주입,
state 조립, 세션 메타데이터 upsert)을 한곳으로 모은다. 비스트리밍/스트리밍 엔드포인트가
동일한 준비 로직을 공유하게 해 드리프트를 막는다.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import HTTPException

from backend.app.services.agent.graph import get_agent
from shared.database.repositories.sessions import upsert_chat_session

_TITLE_MAX = 40

# 그래프 노드 → 사람이 읽는 진행상태 라벨. 도구 수집 구간(오래 걸림)에 "지금 뭐 하는지"를 흘리는 용도.
_NODE_LABELS = {
    "intent": "질문 의도 분석",
    "persona_rag": "또래 투자자 데이터 조회",
    "graph_rag": "세법 지식그래프 탐색",
    "doc_rag": "세법 문서 검색",
    "tax_and_market_lookup": "세율·시장지표 조회",
    "product_research": "금융상품 금리 검색",
    "news_research": "금리 동향 웹검색",
    "nts_law_research": "국세청 해석 조회",
    "stock_backtest": "백테스트 실행",
    "stock_quick": "주식 기술지표 분석",
    "cheongyak_lookup": "청약 공고 조회",
    "synthesize": "답변 작성",
}


class ChatService:
    """멀티턴 채팅 실행기. 엔드포인트당 1회 생성하거나 모듈 싱글톤으로 재사용한다."""

    def __init__(self) -> None:
        self._agent = get_agent()

    # -- 공용 준비 ---------------------------------------------------------

    def _prepare_inputs(
        self, session_id: str, message: str, user_uuid: str, profile: str | None = None
    ) -> tuple[dict, dict]:
        """(state_in, config)를 만든다. 첫 턴이면 프로필 요약을 함께 주입한다.

        프로필은 클라이언트가 보낸 요약 문자열을 그대로 쓴다 — 사용자가 /me 에 직접 입력한
        청약 조건이라 서버가 다시 조회할 원본이 없다(로그인·회원DB 없음). 없으면 프로필
        없이 진행한다: 일반적인 청약 정보 상담은 그래도 성립한다.
        """
        config = {"configurable": {"thread_id": session_id}}

        existing = self._agent.get_state(config)
        is_first_turn = not existing.values.get("messages")

        state_in: dict = {
            "messages": [{"role": "user", "content": message}],
            "user_uuid": user_uuid,
        }
        if is_first_turn and profile:
            # 프로필은 state.profile_summary로 주입 → synthesize 노드가 system prompt에 합친다.
            # (가짜 user 메시지로 넣지 않으므로 대화 히스토리가 깨끗하게 유지됨.)
            state_in["profile_summary"] = profile

        return state_in, config

    def _record_session(self, session_id: str, message: str, user_uuid: str, config: dict) -> None:
        """턴 종료 후 세션 메타데이터를 upsert한다(제목은 최초 1회만 확정)."""
        try:
            state = self._agent.get_state(config)
            messages = state.values.get("messages", []) if state and state.values else []
            message_count = len(messages)
        except Exception:
            message_count = 0

        upsert_chat_session(
            session_id=session_id,
            user_uuid=user_uuid,
            title=message[:_TITLE_MAX],
            message_count=message_count,
        )

    # -- 실행 --------------------------------------------------------------

    def run(self, session_id: str, message: str, user_uuid: str, profile: str | None = None) -> str:
        """비스트리밍 1회 응답. 최종 답변 텍스트를 반환한다."""
        state_in, config = self._prepare_inputs(session_id, message, user_uuid, profile)
        try:
            result = self._agent.invoke(state_in, config)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        self._record_session(session_id, message, user_uuid, config)
        return result["messages"][-1].content

    def stream(
        self, session_id: str, message: str, user_uuid: str, profile: str | None = None
    ) -> Iterator[str]:
        """SSE 토큰 스트림 제너레이터. synthesize 노드의 최종 답변 토큰만 흘린다.

        이벤트: {"type":"status","message":...}(도구 수집 진행) · {"type":"token","content":...}(답변 토큰)
        반복 후 {"type":"done"}. 도구 구간(웹검색·yfinance·그래프)은 오래 걸리는데 예전엔 synthesize 토큰만
        흘려 그 구간이 '조용한 대기'였다. updates 모드를 함께 구독해 각 단계를 status로 흘린다.
        체크포인터 영속화/세션 기록은 스트림 종료 시 처리한다.
        """
        state_in, config = self._prepare_inputs(session_id, message, user_uuid, profile)

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            announced_synth = False
            for mode, payload in self._agent.stream(
                state_in, config, stream_mode=["updates", "messages"]
            ):
                if mode == "updates":
                    # 노드가 끝날 때마다 진행상태. intent 완료 시엔 '무엇을 수집하는지'까지 알린다.
                    for node, update in (payload or {}).items():
                        if node == "synthesize":
                            continue
                        if node == "intent":
                            route = (update or {}).get("route") or []
                            tools = ", ".join(_NODE_LABELS.get(t, t) for t in route)
                            yield _sse({"type": "status", "message": f"수집 중: {tools}" if tools else "답변 준비 중"})
                        elif node in _NODE_LABELS:
                            yield _sse({"type": "status", "message": f"{_NODE_LABELS[node]} 완료"})
                    continue

                # mode == "messages": synthesize 노드의 최종 답변 토큰만 전달(intent 분류기 LLM은 제외)
                chunk, metadata = payload
                if metadata.get("langgraph_node") != "synthesize":
                    continue
                if not announced_synth:
                    announced_synth = True
                    yield _sse({"type": "status", "message": "답변 작성 중"})
                content = getattr(chunk, "content", None)
                if content:
                    yield _sse({"type": "token", "content": content})

            self._record_session(session_id, message, user_uuid, config)
            yield _sse({"type": "done"})
        except Exception as exc:
            yield _sse({"type": "error", "detail": str(exc)})
