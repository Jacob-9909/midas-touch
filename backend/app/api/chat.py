"""멀티턴 채팅 API — LangGraph 에이전트 라우터.

session_id(thread_id)별로 대화 상태가 체크포인터에 보존되어 멀티턴으로 이어진다.
user_uuid는 필수(Q5): 존재하지 않는 사용자면 404. 첫 턴에 Users DB 프로필을 끌어와
프로필 컨텍스트를 대화 앞에 1회 주입한다.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.services.agent.graph import get_agent
from shared.database.connector import (
    delete_checkpoint_thread,
    get_user_by_uuid,
    list_checkpoint_threads,
)

router = APIRouter(prefix="/api/v1", tags=["agent"])


class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_uuid: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


def _build_profile_context(profile: dict) -> str:
    """첫 턴에 대화 앞단에 주입할 사용자 프로필 요약."""
    return (
        "[의뢰인 프로필 — 이 사용자에 맞춰 모든 조언을 개인화하십시오]\n"
        f"- 나이/성별/직업: {profile.get('age')}세 / {profile.get('sex')} / {profile.get('occupation')}\n"
        f"- 가족/주거: {profile.get('family_type')} / {profile.get('housing_type')} ({profile.get('district')})\n"
        f"- 자산 총액: {profile.get('total_amount'):,}원 (월 소득 {profile.get('monthly_income'):,}원 / "
        f"월 가용 투자액 {profile.get('monthly_investable'):,}원)\n"
        f"- 자산 배분: 주식 {profile.get('stock_amount'):,} / 채권 {profile.get('bond_amount'):,} / "
        f"예적금 {profile.get('deposit_amount'):,} / 부동산 {profile.get('real_estate_amount'):,}\n"
        f"- 투자 성향(1-10): 공격성 {profile.get('aggressiveness')} / 금융이해도 {profile.get('financial_literacy')}\n"
        f"- 선호 자산/종목: {profile.get('preferred_asset')} | {profile.get('specific_items')}\n"
        f"- 목표 수익률/기간: {profile.get('target_return_percent')}% / {profile.get('investable_period_months')}개월"
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    profile = get_user_by_uuid(req.user_uuid)
    if not profile:
        raise HTTPException(status_code=404, detail=f"사용자를 찾을 수 없습니다: {req.user_uuid}")

    agent = get_agent()
    config = {"configurable": {"thread_id": req.session_id}}

    # 첫 턴 여부 판단 (체크포인터에 누적 메시지가 없으면 첫 턴)
    existing = agent.get_state(config)
    is_first_turn = not existing.values.get("messages")

    # 프로필은 state.profile_summary로 주입 → dynamic_prompt 미들웨어가 system prompt에 합친다.
    # (가짜 user 메시지로 넣지 않으므로 대화 히스토리가 깨끗하게 유지됨.)
    state_in: dict = {
        "messages": [{"role": "user", "content": req.message}],
        "user_uuid": req.user_uuid,
    }
    if is_first_turn:
        state_in["profile_summary"] = _build_profile_context(profile)

    try:
        result = agent.invoke(state_in, config)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))

    reply = result["messages"][-1].content
    return ChatResponse(session_id=req.session_id, reply=reply)


@router.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """멀티턴 채팅을 SSE로 스트리밍한다(synthesize 노드의 최종 답변 토큰만 흘린다).

    이벤트: {"type":"token","content":...} 반복 후 {"type":"done"}.
    체크포인터 영속화는 비스트리밍 /chat과 동일하게 자동 처리된다.
    """
    profile = get_user_by_uuid(req.user_uuid)
    if not profile:
        raise HTTPException(status_code=404, detail=f"사용자를 찾을 수 없습니다: {req.user_uuid}")

    agent = get_agent()
    config = {"configurable": {"thread_id": req.session_id}}
    existing = agent.get_state(config)
    is_first_turn = not existing.values.get("messages")

    state_in: dict = {
        "messages": [{"role": "user", "content": req.message}],
        "user_uuid": req.user_uuid,
    }
    if is_first_turn:
        state_in["profile_summary"] = _build_profile_context(profile)

    def event_stream():
        try:
            for chunk, metadata in agent.stream(
                state_in, config, stream_mode="messages"
            ):
                # synthesize 노드가 생성하는 최종 답변 토큰만 전달(intent 분류기 LLM은 제외)
                if metadata.get("langgraph_node") != "synthesize":
                    continue
                content = getattr(chunk, "content", None)
                if content:
                    yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/sessions")
def chat_sessions(user_uuid: str | None = None, limit: int = 50) -> dict:
    """체크포인터에 저장된 대화 세션 목록을 최근순으로 반환한다(서버 기반 사이드바).

    user_uuid를 주면 해당 유저의 세션만 필터링한다. 각 세션의 첫 사용자 메시지를 제목으로 쓴다.
    """
    agent = get_agent()
    out: list[dict] = []
    for row in list_checkpoint_threads(limit=limit):
        thread_id = row["thread_id"]
        config = {"configurable": {"thread_id": thread_id}}
        try:
            state = agent.get_state(config)
        except Exception:  # noqa: BLE001
            continue
        values = state.values if state else {}
        messages = values.get("messages", []) or []
        if not messages:
            continue

        sess_user = values.get("user_uuid")
        if user_uuid and sess_user != user_uuid:
            continue

        title = "새 대화"
        human_count = 0
        for m in messages:
            if getattr(m, "type", None) == "human":
                human_count += 1
                if human_count == 1 and getattr(m, "content", None):
                    title = str(m.content)[:40]

        out.append(
            {
                "session_id": thread_id,
                "user_uuid": sess_user,
                "title": title,
                "message_count": len(messages),
                "updated_at": row["last_ts"],
            }
        )
    return {"sessions": out}


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    """세션의 대화 기록(체크포인트)을 삭제한다."""
    deleted = delete_checkpoint_thread(session_id)
    return {"session_id": session_id, "deleted_checkpoints": deleted}


@router.get("/chat/history/{session_id}")
def chat_history(session_id: str) -> dict:
    """체크포인터에 저장된 세션의 대화 이력(사람이 읽는 메시지)을 복원해 반환한다.

    LangGraph state.values["messages"]에서 Human/AI 메시지만 추려 role/content로 직렬화.
    존재하지 않는 세션이면 빈 목록을 반환한다.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": session_id}}
    state = agent.get_state(config)
    messages = state.values.get("messages", []) if state and state.values else []

    out: list[dict] = []
    for m in messages:
        role = getattr(m, "type", None)
        content = getattr(m, "content", None)
        if not content:
            continue
        if role == "human":
            out.append({"role": "user", "content": content})
        elif role == "ai":
            out.append({"role": "assistant", "content": content})
    return {"session_id": session_id, "messages": out}
