"""Add embedding pipeline dataset tables

Revision ID: a1b2c3d4e5f6
Revises: d93ff1c5811e
Create Date: 2026-05-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d93ff1c5811e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # emb_passages
    op.create_table(
        "emb_passages",
        sa.Column("passage_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("passage_id", name="pk_emb_passages"),
    )
    op.create_index("ix_emb_passages_source", "emb_passages", ["source"])

    # emb_synthetic_queries
    op.create_table(
        "emb_synthetic_queries",
        sa.Column("query_id", sa.Text(), nullable=False),
        sa.Column("passage_id", sa.Text(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_type", sa.Text(), nullable=False),
        sa.Column("source_passage", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("query_id", name="pk_emb_synthetic_queries"),
        sa.ForeignKeyConstraint(
            ["passage_id"],
            ["emb_passages.passage_id"],
            name="fk_emb_queries_passage",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_emb_queries_passage_id", "emb_synthetic_queries", ["passage_id"])
    op.create_index("ix_emb_queries_type", "emb_synthetic_queries", ["query_type"])

    # emb_training_triplets
    op.create_table(
        "emb_training_triplets",
        sa.Column("triplet_id", sa.Text(), nullable=False),
        sa.Column("query_id", sa.Text(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("positive_passage_id", sa.Text(), nullable=False),
        sa.Column("positive_text", sa.Text(), nullable=False),
        sa.Column("negative_passage_id", sa.Text(), nullable=False),
        sa.Column("negative_text", sa.Text(), nullable=False),
        sa.Column("query_type", sa.Text(), nullable=False),
        sa.Column("negative_similarity_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("positive_similarity_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("margin", sa.Numeric(8, 6), nullable=False),
        sa.Column("split", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("triplet_id", name="pk_emb_training_triplets"),
        sa.CheckConstraint("split IN ('train', 'eval')", name="ck_emb_triplets_split"),
    )
    op.create_index("ix_emb_triplets_split", "emb_training_triplets", ["split"])
    op.create_index(
        "ix_emb_triplets_query_type",
        "emb_training_triplets",
        ["query_type", "split"],
    )


def downgrade() -> None:
    op.drop_table("emb_training_triplets")
    op.drop_index("ix_emb_queries_type", table_name="emb_synthetic_queries")
    op.drop_index("ix_emb_queries_passage_id", table_name="emb_synthetic_queries")
    op.drop_table("emb_synthetic_queries")
    op.drop_index("ix_emb_passages_source", table_name="emb_passages")
    op.drop_table("emb_passages")
