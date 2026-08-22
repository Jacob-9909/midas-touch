"""Consolidated SQLAlchemy ORM models for Midas Touch (PostgreSQL + pgvector)."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

PostgresBase = declarative_base()


class User(PostgresBase):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    uuid = Column(String(100), unique=True, nullable=True)
    # 인증(로그인) — 기존 데모 유저(비번 없음) 호환 위해 nullable. 비번 설정된 유저만 로그인 가능.
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)

    # Personal Info
    age = Column(SmallInteger, nullable=True)
    sex = Column(String(10), nullable=True)
    marital_status = Column(String(50), nullable=True)
    education_level = Column(String(100), nullable=True)
    bachelors_field = Column(String(200), nullable=True)
    occupation = Column(String(200), nullable=True)
    family_type = Column(String(100), nullable=True)
    housing_type = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    
    # Personas
    persona = Column(Text, nullable=True)
    professional_persona = Column(Text, nullable=True)
    family_persona = Column(Text, nullable=True)
    career_goals_and_ambitions = Column(Text, nullable=True)
    
    # Assets Info
    total_amount = Column(BigInteger, nullable=True)
    monthly_income = Column(Integer, nullable=True)
    monthly_investable = Column(Integer, nullable=True)
    specific_items = Column(String(500), nullable=True)
    
    # Asset flags
    has_stock = Column(Boolean, nullable=False, server_default=text("false"))
    has_bond = Column(Boolean, nullable=False, server_default=text("false"))
    has_deposit = Column(Boolean, nullable=False, server_default=text("false"))
    has_real_estate = Column(Boolean, nullable=False, server_default=text("false"))
    
    # Asset amounts
    stock_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    bond_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    deposit_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    real_estate_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    
    # Investment Propensity
    aggressiveness = Column(SmallInteger, nullable=True)
    preferred_asset = Column(String(200), nullable=True)
    financial_literacy = Column(SmallInteger, nullable=True)
    
    # Goals
    target_return_percent = Column(Numeric(5, 2), nullable=True)
    investable_period_months = Column(Integer, nullable=True)
    requires_liquidity = Column(Boolean, nullable=False, server_default=text("false"))
    
    # Meta
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    persona_embedding = relationship("PersonaEmbedding", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Portfolio(PostgresBase):
    __tablename__ = "portfolios"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(200), nullable=True)
    strategy_name = Column(String(100), nullable=True)
    
    # Ratios (sum = 100)
    stock_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    bond_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    deposit_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    real_estate_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    gold_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    cash_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="portfolios")
    items = relationship("PortfolioItem", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioItem(PostgresBase):
    __tablename__ = "portfolio_items"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type = Column(String(50), nullable=False)
    ticker = Column(String(30), nullable=True)
    name = Column(String(200), nullable=True)
    allocation_pct = Column(Numeric(5, 2), nullable=False)
    currency = Column(String(3), nullable=False, server_default=text("'KRW'"))
    note = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    portfolio = relationship("Portfolio", back_populates="items")


class TaxRule(PostgresBase):
    __tablename__ = "tax_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_type = Column(String(50), nullable=False)
    income_type = Column(String(50), nullable=False)
    min_amount = Column(BigInteger, nullable=True)
    max_amount = Column(BigInteger, nullable=True)
    tax_rate = Column(Numeric(6, 4), nullable=False)
    local_tax_rate = Column(Numeric(6, 4), nullable=True)
    deduction_limit = Column(BigInteger, nullable=True)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    description = Column(String(500), nullable=True)
    legal_basis = Column(String(200), nullable=True)


class MarketSnapshot(PostgresBase):
    __tablename__ = "market_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    data_type = Column(String(50), nullable=False)
    sub_key = Column(String(30), nullable=True)
    value = Column(Numeric(18, 6), nullable=False)
    unit = Column(String(20), nullable=True)
    source = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class LegalReference(PostgresBase):
    __tablename__ = "legal_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    law_name = Column(String(200), nullable=False)
    article_number = Column(String(50), nullable=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    asset_category = Column(String(100), nullable=True)
    effective_date = Column(Date, nullable=True)
    last_updated = Column(Date, nullable=True)
    source_url = Column(String(1000), nullable=True)
    supabase_doc_id = Column(String(100), nullable=True)

    strategy_docs = relationship("StrategyDoc", back_populates="legal_reference")


class NewsEmbedding(PostgresBase):
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
    
    # 1024-dimensional embedding
    embedding = Column(Vector(1024), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class StrategyDoc(PostgresBase):
    __tablename__ = "strategy_docs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    author = Column(String(200), nullable=True)
    published_year = Column(SmallInteger, nullable=True)
    strategy_type = Column(String(100), nullable=True)
    chunk_index = Column(Integer, nullable=False, server_default=text("0"))
    chunk_text = Column(Text, nullable=False)
    
    # 1024-dimensional embedding
    embedding = Column(Vector(1024), nullable=False)
    azure_legal_id = Column(
        Integer,
        ForeignKey("legal_references.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_url = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    legal_reference = relationship("LegalReference", back_populates="strategy_docs")


class MacroIndicator(PostgresBase):
    __tablename__ = "macro_indicators"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    indicator_name = Column(String(100), nullable=False)
    indicator_date = Column(Date, nullable=False)
    numeric_value = Column(Numeric(18, 6), nullable=False)
    unit = Column(String(20), nullable=True)
    analysis_text = Column(Text, nullable=True)
    
    # 1024-dimensional embedding
    embedding = Column(Vector(1024), nullable=True)
    source = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class PersonaEmbedding(PostgresBase):
    __tablename__ = "persona_embeddings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    azure_user_uuid = Column(
        String(100),
        ForeignKey("users.uuid", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    persona_text = Column(Text, nullable=False)
    
    # 1024-dimensional embedding
    embedding = Column(Vector(1024), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user = relationship("User", back_populates="persona_embedding")


class ChatSession(PostgresBase):
    """대화 세션 메타데이터(웹 콘솔 사이드바용).

    대화 상태 자체는 LangGraph 체크포인트 테이블이 보관한다. 이 테이블은 제목·유저·메시지 수·
    갱신시각만 들고 있어, 세션 목록을 체크포인트 스캔 없이 단일 쿼리로 조회하게 한다.
    session_id == LangGraph thread_id.
    """

    __tablename__ = "chat_sessions"

    session_id = Column(String(200), primary_key=True)
    user_uuid = Column(String(100), nullable=True, index=True)
    title = Column(String(200), nullable=True)
    message_count = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
