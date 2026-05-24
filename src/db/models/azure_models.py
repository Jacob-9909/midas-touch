"""SQLAlchemy models for Azure SQL Database (Midas Touch)."""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    BigInteger,
    String,
    Unicode,
    UnicodeText,
    Numeric,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    text,
)
from sqlalchemy.orm import declarative_base, relationship

AzureBase = declarative_base()


class User(AzureBase):
    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        server_default=text("NEWSEQUENTIALID()"),
    )
    uuid = Column(String(100), unique=True, nullable=True)
    
    # Personal Info
    age = Column(SmallInteger, nullable=True)
    sex = Column(Unicode(10), nullable=True)
    marital_status = Column(Unicode(50), nullable=True)
    education_level = Column(Unicode(100), nullable=True)
    bachelors_field = Column(Unicode(200), nullable=True)
    occupation = Column(Unicode(200), nullable=True)
    family_type = Column(Unicode(100), nullable=True)
    housing_type = Column(Unicode(100), nullable=True)
    district = Column(Unicode(100), nullable=True)
    
    # Personas
    persona = Column(UnicodeText, nullable=True)
    professional_persona = Column(UnicodeText, nullable=True)
    family_persona = Column(UnicodeText, nullable=True)
    career_goals_and_ambitions = Column(UnicodeText, nullable=True)
    
    # Assets Info
    total_amount = Column(BigInteger, nullable=True)
    monthly_income = Column(Integer, nullable=True)
    monthly_investable = Column(Integer, nullable=True)
    specific_items = Column(Unicode(500), nullable=True)
    
    # Asset type flags (deprecated, kept for compatibility)
    has_stock = Column(Boolean, nullable=False, server_default=text("0"))
    has_bond = Column(Boolean, nullable=False, server_default=text("0"))
    has_deposit = Column(Boolean, nullable=False, server_default=text("0"))
    has_real_estate = Column(Boolean, nullable=False, server_default=text("0"))
    
    # Asset type actual amounts
    stock_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    bond_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    deposit_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    real_estate_amount = Column(BigInteger, nullable=False, server_default=text("0"))
    
    # Investment Propensity
    aggressiveness = Column(SmallInteger, nullable=True)
    preferred_asset = Column(Unicode(200), nullable=True)
    financial_literacy = Column(SmallInteger, nullable=True)
    
    # Goals
    target_return_percent = Column(Numeric(5, 2), nullable=True)
    investable_period_months = Column(Integer, nullable=True)
    requires_liquidity = Column(Boolean, nullable=False, server_default=text("0"))
    
    # Meta
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("GETDATE()"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("GETDATE()"),
    )

    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")


class Portfolio(AzureBase):
    __tablename__ = "portfolios"

    id = Column(
        String(36),
        primary_key=True,
        server_default=text("NEWSEQUENTIALID()"),
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(Unicode(200), nullable=True)
    strategy_name = Column(Unicode(100), nullable=True)
    
    # Ratios (sum = 100)
    stock_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    bond_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    deposit_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    real_estate_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    gold_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    cash_ratio = Column(Numeric(5, 2), nullable=False, server_default=text("0"))
    
    is_active = Column(Boolean, nullable=False, server_default=text("1"))
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("GETDATE()"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("GETDATE()"),
    )

    user = relationship("User", back_populates="portfolios")
    items = relationship("PortfolioItem", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioItem(AzureBase):
    __tablename__ = "portfolio_items"

    id = Column(
        String(36),
        primary_key=True,
        server_default=text("NEWSEQUENTIALID()"),
    )
    portfolio_id = Column(
        String(36),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type = Column(String(50), nullable=False)
    ticker = Column(String(30), nullable=True)
    name = Column(Unicode(200), nullable=True)
    allocation_pct = Column(Numeric(5, 2), nullable=False)
    currency = Column(String(3), nullable=False, server_default=text("'KRW'"))
    note = Column(Unicode(500), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("GETDATE()"),
    )

    portfolio = relationship("Portfolio", back_populates="items")


class TaxRule(AzureBase):
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
    description = Column(Unicode(500), nullable=True)
    legal_basis = Column(Unicode(200), nullable=True)


class MarketSnapshot(AzureBase):
    __tablename__ = "market_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, nullable=False)
    data_type = Column(String(50), nullable=False)
    sub_key = Column(String(30), nullable=True)
    value = Column(Numeric(18, 6), nullable=False)
    unit = Column(String(20), nullable=True)
    source = Column(String(50), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("GETDATE()"),
    )


class LegalReference(AzureBase):
    __tablename__ = "legal_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    law_name = Column(Unicode(200), nullable=False)
    article_number = Column(Unicode(50), nullable=True)
    title = Column(Unicode(500), nullable=True)
    content = Column(UnicodeText, nullable=True)
    asset_category = Column(String(100), nullable=True)
    effective_date = Column(Date, nullable=True)
    last_updated = Column(Date, nullable=True)
    source_url = Column(Unicode(1000), nullable=True)
    supabase_doc_id = Column(Unicode(100), nullable=True)
