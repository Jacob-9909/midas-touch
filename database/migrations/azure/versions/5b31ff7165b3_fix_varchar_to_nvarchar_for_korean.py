"""fix varchar to nvarchar for korean columns

Revision ID: 5b31ff7165b3
Revises: bac9ddead618
Create Date: 2026-05-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '5b31ff7165b3'
down_revision: Union[str, Sequence[str], None] = 'bac9ddead618'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'sex',
                    existing_type=sa.String(10),
                    type_=sa.Unicode(10),
                    existing_nullable=True)
    op.alter_column('users', 'marital_status',
                    existing_type=sa.String(50),
                    type_=sa.Unicode(50),
                    existing_nullable=True)
    op.alter_column('users', 'education_level',
                    existing_type=sa.String(100),
                    type_=sa.Unicode(100),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'education_level',
                    existing_type=sa.Unicode(100),
                    type_=sa.String(100),
                    existing_nullable=True)
    op.alter_column('users', 'marital_status',
                    existing_type=sa.Unicode(50),
                    type_=sa.String(50),
                    existing_nullable=True)
    op.alter_column('users', 'sex',
                    existing_type=sa.Unicode(10),
                    type_=sa.String(10),
                    existing_nullable=True)
