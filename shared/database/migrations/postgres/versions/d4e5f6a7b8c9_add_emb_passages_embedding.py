"""Add emb_passages.embedding for document RAG

문서 단락(emb_passages)을 챗봇이 pgvector로 직접 검색할 수 있게 1024차원 bge-m3 임베딩 컬럼을
추가한다. 차원·인덱스 구성은 persona_embeddings와 동일하게 맞춘다(같은 모델·같은 코사인 거리).

백필 전에는 NULL이므로 인덱스는 partial(WHERE embedding IS NOT NULL)로 만든다
(macro_indicators와 동일 패턴).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-08 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE emb_passages ADD COLUMN IF NOT EXISTS embedding vector(1024)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_emb_passages_embedding_hnsw
            ON emb_passages USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_emb_passages_embedding_hnsw")
    op.execute("ALTER TABLE emb_passages DROP COLUMN IF EXISTS embedding")
