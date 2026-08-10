"""Add chat_sessions table (대화 세션 메타데이터)

대화 상태(메시지)는 LangGraph 체크포인트 테이블이 보관하지만, 사이드바 세션 목록을 위한
메타데이터(제목/유저/메시지 수/갱신시각)는 이 앱 전용 테이블에 둔다. 이전에는 체크포인트
jsonb를 thread마다 스캔(N+1)해 역설계했다.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-18 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column("user_uuid", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "message_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_chat_sessions"),
    )
    op.create_index("ix_chat_sessions_user_uuid", "chat_sessions", ["user_uuid"])
    op.create_index("ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_updated_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_uuid", table_name="chat_sessions")
    op.drop_table("chat_sessions")
