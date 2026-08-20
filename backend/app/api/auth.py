"""인증 라우터 + FastAPI 의존성.

- POST /api/v1/auth/login  → email/password 검증 후 JWT 발급.
- current_uuid 의존성: 보호 라우트가 '토큰이 말하는 신원(uuid)'을 얻는 통로.
- resolve_user_uuid / enforce_owner: AUTH_ENABLED 여부에 따라 소유권을 강제하거나(켬)
  기존처럼 클라이언트 uuid를 그대로 쓴다(끔, 하위호환).
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.auth import (
    auth_enabled,
    create_access_token,
    decode_token,
    verify_password,
)
from shared.database.repositories.users import get_user_by_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_uuid: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest) -> LoginResponse:
    user = get_user_by_email(req.email.strip().lower())
    # 존재하지 않는 계정과 틀린 비번을 구분하지 않는다(계정 열거 방지).
    if not user or not verify_password(req.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    uuid = user.get("uuid")
    if not uuid:
        raise HTTPException(status_code=401, detail="계정에 uuid가 없습니다.")
    return LoginResponse(access_token=create_access_token(uuid), user_uuid=uuid)


# ── 의존성 / 헬퍼 ──────────────────────────────────────────
def current_uuid(authorization: str | None = Header(default=None)) -> str | None:
    """Authorization: Bearer <jwt> → uuid. AUTH_ENABLED=false면 항상 None(하위호환)."""
    if not auth_enabled():
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return decode_token(authorization[7:].strip())


def resolve_user_uuid(auth_uuid: str | None, requested: str) -> str:
    """대화/조회에 쓸 실제 uuid. 켬: 토큰이 원천(없으면 401). 끔: 요청값."""
    if auth_enabled():
        if not auth_uuid:
            raise HTTPException(status_code=401, detail="인증이 필요합니다.")
        return auth_uuid
    return requested


def enforce_owner(auth_uuid: str | None, requested: str) -> None:
    """켬 상태에서 '남의 uuid' 접근을 차단. 끔이면 통과."""
    if not auth_enabled():
        return
    if not auth_uuid:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    if auth_uuid != requested:
        raise HTTPException(status_code=403, detail="본인 데이터만 조회할 수 있습니다.")
