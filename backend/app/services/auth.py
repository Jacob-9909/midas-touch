"""인증 프리미티브 — 비밀번호 해시(bcrypt) + JWT 발급/검증.

플래그 게이트: AUTH_ENABLED=false(기본)면 라우터는 기존처럼 클라이언트가 준 uuid로 동작해
프론트가 로그인을 붙이기 전까지 앱이 깨지지 않는다. AUTH_ENABLED=true면 토큰이 신원의 원천이 되고
남의 uuid를 조회/대화하지 못한다(소유권 강제).

# ponytail: bcrypt 직접(passlib 없이) + PyJWT. HS256 대칭키 1개면 단일 서비스엔 충분.
#           멀티서비스로 키 회전이 필요해지면 그때 비대칭(RS256)+JWKS로. bcrypt 72바이트 초과는 무시(관용).
"""

from __future__ import annotations

import os
import time

import bcrypt
import jwt

_ALGO = "HS256"


def auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").lower() == "true"


def _secret() -> str:
    s = os.getenv("AUTH_SECRET", "")
    if not s:
        # 기본 비밀키로 토큰을 발급하는 사고를 막는다 — 켰으면 반드시 주입해야 한다.
        raise RuntimeError("AUTH_ENABLED=true 인데 AUTH_SECRET 이 비어 있다. 서명키를 설정하라.")
    return s


def _ttl_seconds() -> int:
    return int(float(os.getenv("AUTH_TOKEN_TTL_HOURS", "12")) * 3600)


# ── 비밀번호 ───────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── 토큰 ───────────────────────────────────────────────────
def create_access_token(user_uuid: str) -> str:
    now = int(time.time())
    payload = {"sub": user_uuid, "iat": now, "exp": now + _ttl_seconds()}
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_token(token: str) -> str | None:
    """유효한 토큰이면 sub(uuid), 아니면 None(만료·변조·서명불일치 모두 None)."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None


def _demo() -> None:
    os.environ["AUTH_SECRET"] = "test-secret-not-for-prod"
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)
    assert not verify_password("hunter2", None)
    tok = create_access_token("uuid-abc")
    assert decode_token(tok) == "uuid-abc"
    assert decode_token(tok + "x") is None  # 변조 → None
    assert decode_token("garbage") is None
    # 다른 키로 서명 검증 실패
    os.environ["AUTH_SECRET"] = "another-secret"
    assert decode_token(tok) is None
    print("auth demo ok")


if __name__ == "__main__":
    _demo()
