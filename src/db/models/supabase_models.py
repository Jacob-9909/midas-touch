"""SQLAlchemy models for Supabase (pgvector / PostgreSQL)."""

from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    BigInteger,
    String,
    Text,
    Numeric,
    DateTime,
    Date,
    text,
)
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

SupabaseBase = declarative_base()


class NewsEmbedding(SupabaseBase):
    __tablename__ = "news_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(100), nullable=False)
    source_url = Column(Text, unique=True, nullable=True)
    language = Column(String(2), nullable=False, server_default=text("'ko'"))
    category = Column(String(50), nullable=True)
    sentiment_score = Column(Numeric(4, 3), nullable=True)
    
    # 1536-dimensional embedding using text-embedding-3-small
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class StrategyDoc(SupabaseBase):
    __tablename__ = "strategy_docs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    author = Column(String(200), nullable=True)
    published_year = Column(SmallInteger, nullable=True)
    strategy_type = Column(String(100), nullable=True)
    chunk_index = Column(Integer, nullable=False, server_default=text("0"))
    chunk_text = Column(Text, nullable=False)
    
    # 1536-dimensional embedding
    embedding = Column(Vector(1536), nullable=False)
    azure_legal_id = Column(Integer, nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class MacroIndicator(SupabaseBase):
    __tablename__ = "macro_indicators"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    indicator_name = Column(String(100), nullable=False)
    indicator_date = Column(Date, nullable=False)
    numeric_value = Column(Numeric(18, 6), nullable=False)
    unit = Column(String(20), nullable=True)
    analysis_text = Column(Text, nullable=True)
    
    # 1536-dimensional embedding
    embedding = Column(Vector(1536), nullable=True)
    source = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )


class PersonaEmbedding(SupabaseBase):
    __tablename__ = "persona_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    azure_user_uuid = Column(String(100), unique=True, nullable=False)
    persona_text = Column(Text, nullable=False)
    
    # 1536-dimensional embedding
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
