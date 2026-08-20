"""Add LangGraph checkpoint tables (backend agent multiturn persistence)

체크포인트 테이블(checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations)을
Alembic이 단일 진실원천으로 관리한다(DESIGN Q3). DDL은 LangGraph PostgresSaver.setup()에
위임하되, '언제 생성되는가'는 이 마이그레이션이 통제한다. 런타임 코드는 setup()을 호출하지 않는다.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13 00:00:00.000000

"""
import os
from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # LangGraph PostgresSaver의 공식 DDL을 그대로 적용(idempotent). 라이브러리 버전 변경 시
    # 새 내부 마이그레이션도 함께 반영되도록 setup()에 위임한다.
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
        checkpointer.setup()


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")
