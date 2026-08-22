"""멀티턴 채팅 API — LangGraph 에이전트 라우터.

session_id(thread_id)별로 대화 상태가 체크포인터에 보존되어 멀티턴으로 이어진다.
비즈니스 로직(프로필 404·첫 턴 판정·프로필 주입·세션 기록)은 ChatService가 담당하고,
이 라우터는 얇은 HTTP 어댑터로만 남는다. 세션 목록은 chat_sessions 테이블에서 직접 조회한다
(과거처럼 체크포인트를 thread마다 스캔하지 않는다).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.api.auth import current_uuid, resolve_user_uuid
from backend.app.services.agent.graph import get_agent
from backend.app.services.chat_service import ChatService
from shared.database.repositories.checkpoints import delete_checkpoint_thread
from shared.database.repositories.sessions import delete_chat_session, list_chat_sessions

router = APIRouter(prefix="/api/v1", tags=["agent"])


@lru_cache(maxsize=1)
def _service() -> ChatService:
    """ChatService를 첫 요청 시 1회 생성(에이전트/체크포인터 지연 초기화)."""
    return ChatService()


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    # 로그인이 없으므로 이건 신원이 아니라 "이 브라우저"를 가리키는 익명 키다.
    # 세션 묶기에만 쓰고, 프로필 조회 키로는 더 이상 쓰지 않는다.
    user_uuid: str = Field(min_length=1, max_length=100)
    # 사용자가 화면(/me)에 직접 입력한 청약 조건 요약. 첫 턴 시스템 프롬프트에만 합치고
    # 저장하지 않는다. 없으면 프로필 없이 일반 상담으로 동작한다.
    profile: str | None = Field(default=None, max_length=4000)


class ChatResponse(BaseModel):
    session_id: str
    reply: str


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, auth_uuid: str | None = Depends(current_uuid)) -> ChatResponse:
    uid = resolve_user_uuid(auth_uuid, req.user_uuid)
    try:
        reply = _service().run(req.session_id, req.message, uid, req.profile)
        return ChatResponse(session_id=req.session_id, reply=reply)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"대화 처리 중 오류가 발생했습니다: {exc}")


@router.post("/chat/stream")
def chat_stream(req: ChatRequest, auth_uuid: str | None = Depends(current_uuid)) -> StreamingResponse:
    """멀티턴 채팅을 SSE로 스트리밍한다(synthesize 노드의 최종 답변 토큰만 흘린다)."""
    uid = resolve_user_uuid(auth_uuid, req.user_uuid)
    stream = _service().stream(req.session_id, req.message, uid, req.profile)
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/sessions")
def chat_sessions(user_uuid: str | None = None, limit: int = 50) -> dict:
    """대화 세션 목록을 최근 갱신순으로 반환한다(chat_sessions 테이블 단일 쿼리).

    user_uuid를 주면 해당 유저의 세션만 필터링한다.
    """
    out: list[dict] = []
    for row in list_chat_sessions(user_uuid=user_uuid, limit=limit):
        updated_at = row.get("updated_at")
        out.append(
            {
                "session_id": row["session_id"],
                "user_uuid": row.get("user_uuid"),
                "title": row.get("title") or "새 대화",
                "message_count": row.get("message_count") or 0,
                "updated_at": updated_at.isoformat() if updated_at is not None else None,
            }
        )
    return {"sessions": out}


@router.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    """세션의 대화 기록(체크포인트)과 메타데이터(chat_sessions)를 함께 삭제한다."""
    deleted = delete_checkpoint_thread(session_id)
    delete_chat_session(session_id)
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
