"""Initial schema

Revision ID: bac9ddead618
Revises: 
Create Date: 2026-05-24 16:36:34.902023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

# revision identifiers, used by Alembic.
revision: str = 'bac9ddead618'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('stock_amount', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('bond_amount', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('deposit_amount', sa.BigInteger(), server_default=sa.text('0'), nullable=False))
    op.add_column('users', sa.Column('real_estate_amount', sa.BigInteger(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'real_estate_amount')
    op.drop_column('users', 'deposit_amount')
    op.drop_column('users', 'bond_amount')
    op.drop_column('users', 'stock_amount')
