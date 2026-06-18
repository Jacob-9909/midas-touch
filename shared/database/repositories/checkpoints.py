"""Checkpoints 레포지토리 — LangGraph 체크포인트 테이블 직접 조회/삭제.

NOTE: 대화 세션 메타데이터(제목/유저/갱신시각)는 sessions 레포지토리(chat_sessions 테이블)가
별도로 보관한다. 여기서는 체크포인트(대화 상태 blob)의 물리적 삭제만 책임진다.
"""

from .connection import db_cursor


def list_checkpoint_threads(limit: int = 50) -> list[dict]:
    """LangGraph 체크포인터에 존재하는 세션(thread_id) 목록을 최근순으로 반환한다.

    각 체크포인트 jsonb의 'ts'(ISO 타임스탬프) 최댓값으로 최근 활동 시각을 추정한다.
    """
    sql = """
    SELECT thread_id, MAX(checkpoint->>'ts') AS last_ts
    FROM checkpoints
    GROUP BY thread_id
    ORDER BY last_ts DESC NULLS LAST
    LIMIT %s
    """
    with db_cursor() as (_, cursor):
        cursor.execute(sql, [limit])
        return [{"thread_id": r[0], "last_ts": r[1]} for r in cursor.fetchall()]


def delete_checkpoint_thread(thread_id: str) -> int:
    """특정 세션(thread_id)의 체크포인트 데이터를 모두 삭제한다. 삭제된 checkpoints 행 수 반환."""
    with db_cursor() as (_, cursor):
        cursor.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", [thread_id])
        cursor.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", [thread_id])
        cursor.execute("DELETE FROM checkpoints WHERE thread_id = %s", [thread_id])
        return cursor.rowcount
