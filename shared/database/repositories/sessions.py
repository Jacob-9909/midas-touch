"""Sessions 레포지토리 — 대화 세션 메타데이터(chat_sessions 테이블).

이전에는 사이드바 세션 목록을 LangGraph 체크포인트 내부(checkpoints jsonb)를 스캔해
thread마다 get_state()로 역설계했다(N+1). 이제 대화 메타데이터(제목/유저/메시지 수/갱신시각)를
이 앱 전용 테이블에 직접 보관해, 목록 조회를 단일 인덱스 쿼리로 처리한다.

체크포인트(대화 상태 blob)는 여전히 LangGraph가 소유한다. 세션 삭제 시에는 양쪽 모두 지운다
(checkpoints 레포지토리의 delete_checkpoint_thread + 여기의 delete_chat_session).
"""

from .connection import db_cursor

_UPSERT_SQL = """
INSERT INTO chat_sessions (session_id, user_uuid, title, message_count, created_at, updated_at)
VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT (session_id) DO UPDATE SET
    user_uuid     = EXCLUDED.user_uuid,
    message_count = EXCLUDED.message_count,
    -- 제목은 첫 사용자 메시지로 한 번만 정한다(이후 턴에서 덮어쓰지 않음).
    title         = COALESCE(chat_sessions.title, EXCLUDED.title),
    updated_at    = CURRENT_TIMESTAMP;
"""


def upsert_chat_session(
    session_id: str,
    user_uuid: str | None,
    title: str,
    message_count: int,
) -> None:
    """세션 메타데이터를 upsert한다(매 턴 호출). 제목은 최초 1회만 확정된다."""
    with db_cursor() as (_, cursor):
        cursor.execute(_UPSERT_SQL, [session_id, user_uuid, title, message_count])


def list_chat_sessions(user_uuid: str | None = None, limit: int = 50) -> list[dict]:
    """세션 목록을 최근 갱신순으로 반환한다. user_uuid를 주면 해당 유저의 세션만 필터링."""
    where = ""
    params: list = []
    if user_uuid:
        where = "WHERE user_uuid = %s"
        params.append(user_uuid)
    params.append(limit)
    sql = f"""
    SELECT session_id, user_uuid, title, message_count, updated_at
    FROM chat_sessions
    {where}
    ORDER BY updated_at DESC
    LIMIT %s
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]


def delete_chat_session(session_id: str) -> int:
    """세션 메타데이터 행을 삭제한다. 삭제된 행 수 반환."""
    with db_cursor() as (_, cursor):
        cursor.execute("DELETE FROM chat_sessions WHERE session_id = %s", [session_id])
        return cursor.rowcount
