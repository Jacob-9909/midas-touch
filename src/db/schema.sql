-- ============================================================
-- Midas Touch — Azure SQL Database Schema
-- ============================================================
-- DB : midas-touch (Azure SQL Database Free Tier)
-- 역할 : 정형 데이터 (사용자/포트폴리오/세율/시장지표/법령)
-- ============================================================


-- ============================================================
-- 1. USERS — 사용자 인적 + 금융 프로필
--    generate_finance_data.py 출력을 그대로 수용하는 구조
-- ============================================================
CREATE TABLE users (
    id              UNIQUEIDENTIFIER    NOT NULL DEFAULT NEWSEQUENTIALID(),
    uuid            VARCHAR(100)        NULL,       -- HuggingFace 원본 uuid
    -- 인적 정보
    age             SMALLINT            NULL,
    sex             VARCHAR(10)         NULL,
    marital_status  VARCHAR(50)         NULL,
    education_level VARCHAR(100)        NULL,
    bachelors_field NVARCHAR(200)       NULL,
    occupation      NVARCHAR(200)       NULL,
    family_type     NVARCHAR(100)       NULL,
    housing_type    NVARCHAR(100)       NULL,
    district        NVARCHAR(100)       NULL,
    -- 페르소나 텍스트 (원문 보존, 벡터 검색은 Supabase)
    persona                     NVARCHAR(MAX) NULL,
    professional_persona        NVARCHAR(MAX) NULL,
    family_persona              NVARCHAR(MAX) NULL,
    career_goals_and_ambitions  NVARCHAR(MAX) NULL,
    -- 자산 현황
    total_amount        BIGINT          NULL,
    monthly_income      INT             NULL,
    monthly_investable  INT             NULL,
    specific_items      NVARCHAR(500)   NULL,
    has_stock           BIT             NOT NULL DEFAULT 0,
    has_bond            BIT             NOT NULL DEFAULT 0,
    has_deposit         BIT             NOT NULL DEFAULT 0,
    has_real_estate     BIT             NOT NULL DEFAULT 0,
    -- 투자 성향
    aggressiveness      TINYINT         NULL CHECK (aggressiveness BETWEEN 1 AND 10),
    preferred_asset     NVARCHAR(200)   NULL,
    financial_literacy  TINYINT         NULL CHECK (financial_literacy BETWEEN 1 AND 10),
    -- 투자 목표
    target_return_percent       DECIMAL(5,2)    NULL,
    investable_period_months    INT             NULL,
    requires_liquidity          BIT             NOT NULL DEFAULT 0,
    -- 메타
    created_at  DATETIME2   NOT NULL DEFAULT GETDATE(),
    updated_at  DATETIME2   NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_users         PRIMARY KEY (id),
    CONSTRAINT UQ_users_uuid    UNIQUE (uuid)
);

CREATE INDEX IX_users_age_aggressiveness ON users (age, aggressiveness);
CREATE INDEX IX_users_total_amount       ON users (total_amount);


-- ============================================================
-- 2. PORTFOLIOS — 포트폴리오 비율 설정
--    에이전트가 사용자별로 추천·저장하는 배분 전략
-- ============================================================
CREATE TABLE portfolios (
    id              UNIQUEIDENTIFIER    NOT NULL DEFAULT NEWSEQUENTIALID(),
    user_id         UNIQUEIDENTIFIER    NOT NULL,
    name            NVARCHAR(200)       NULL,
    strategy_name   NVARCHAR(100)       NULL,   -- 'All Weather', '60/40', 'Ray Dalio' 등
    -- 자산 비율 (합계 = 100)
    stock_ratio         DECIMAL(5,2)    NOT NULL DEFAULT 0,
    bond_ratio          DECIMAL(5,2)    NOT NULL DEFAULT 0,
    deposit_ratio       DECIMAL(5,2)    NOT NULL DEFAULT 0,
    real_estate_ratio   DECIMAL(5,2)    NOT NULL DEFAULT 0,
    gold_ratio          DECIMAL(5,2)    NOT NULL DEFAULT 0,
    cash_ratio          DECIMAL(5,2)    NOT NULL DEFAULT 0,
    -- 상태
    is_active   BIT         NOT NULL DEFAULT 1,
    created_at  DATETIME2   NOT NULL DEFAULT GETDATE(),
    updated_at  DATETIME2   NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_portfolios        PRIMARY KEY (id),
    CONSTRAINT FK_portfolios_users  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    -- 비율 합계 검증
    CONSTRAINT CK_portfolio_ratios CHECK (
        stock_ratio + bond_ratio + deposit_ratio +
        real_estate_ratio + gold_ratio + cash_ratio
        BETWEEN 99.9 AND 100.1
    )
);

CREATE INDEX IX_portfolios_user_id ON portfolios (user_id);


-- ============================================================
-- 3. PORTFOLIO_ITEMS — 포트폴리오 내 실제 종목 명세
-- ============================================================
CREATE TABLE portfolio_items (
    id              UNIQUEIDENTIFIER    NOT NULL DEFAULT NEWSEQUENTIALID(),
    portfolio_id    UNIQUEIDENTIFIER    NOT NULL,
    asset_type      VARCHAR(50)         NOT NULL,   -- 'stock', 'bond', 'fund', 'etf', 'deposit', 'real_estate', 'gold'
    ticker          VARCHAR(30)         NULL,       -- 종목 코드 (e.g., '005930', 'KODEX200')
    name            NVARCHAR(200)       NULL,
    allocation_pct  DECIMAL(5,2)        NOT NULL,
    currency        CHAR(3)             NOT NULL DEFAULT 'KRW',
    note            NVARCHAR(500)       NULL,
    created_at      DATETIME2           NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_portfolio_items          PRIMARY KEY (id),
    CONSTRAINT FK_portfolio_items_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios (id) ON DELETE CASCADE
);


-- ============================================================
-- 4. TAX_RULES — 자산 종류별 세율 테이블 (한국 기준)
--    seed_tax_rules.sql에서 초기 데이터 적재
-- ============================================================
CREATE TABLE tax_rules (
    id              INT             NOT NULL IDENTITY(1,1),
    asset_type      VARCHAR(50)     NOT NULL,   -- 'stock_domestic', 'stock_foreign', 'bond', 'deposit', 'fund', 'real_estate'
    income_type     VARCHAR(50)     NOT NULL,   -- 'capital_gain', 'dividend', 'interest', 'rental', 'transfer'
    min_amount      BIGINT          NULL,       -- 적용 하한 (NULL = 없음)
    max_amount      BIGINT          NULL,       -- 적용 상한 (NULL = 없음)
    tax_rate        DECIMAL(6,4)    NOT NULL,   -- 세율 (0.154 = 15.4%)
    local_tax_rate  DECIMAL(6,4)    NULL,       -- 지방소득세율
    deduction_limit BIGINT          NULL,       -- 공제 한도
    effective_date  DATE            NOT NULL,
    expiry_date     DATE            NULL,       -- NULL = 현행 적용
    description     NVARCHAR(500)   NULL,
    legal_basis     NVARCHAR(200)   NULL,       -- '소득세법 제14조 제3항'

    CONSTRAINT PK_tax_rules PRIMARY KEY (id)
);

CREATE INDEX IX_tax_rules_asset_income ON tax_rules (asset_type, income_type, effective_date);


-- ============================================================
-- 5. MARKET_SNAPSHOTS — 거시경제 지표 일별 스냅샷
--    FRED / 한국은행 / 국제원자재 API 수집 데이터
--    32GB 내 관리를 위해 1년치 보존 → 오래된 데이터 월별 집계
-- ============================================================
CREATE TABLE market_snapshots (
    id              BIGINT          NOT NULL IDENTITY(1,1),
    snapshot_date   DATE            NOT NULL,
    data_type       VARCHAR(50)     NOT NULL,   -- 'exchange_rate', 'interest_rate', 'oil_price', 'gold_price', 'silver_price'
    sub_key         VARCHAR(30)     NULL,       -- 'USD/KRW', 'KR_CD', 'WTI', 'BRENT', 'GOLD_USD' 등
    value           DECIMAL(18,6)   NOT NULL,
    unit            VARCHAR(20)     NULL,       -- 'KRW', '%', 'USD/BBL', 'USD/oz'
    source          VARCHAR(50)     NOT NULL,   -- 'FRED', 'BOK', 'EIA', 'LBMA'
    created_at      DATETIME2       NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_market_snapshots     PRIMARY KEY (id),
    CONSTRAINT UQ_market_snapshots_key UNIQUE (snapshot_date, data_type, sub_key)
);

CREATE INDEX IX_market_snapshots_date     ON market_snapshots (snapshot_date DESC);
CREATE INDEX IX_market_snapshots_type_key ON market_snapshots (data_type, sub_key, snapshot_date DESC);


-- ============================================================
-- 6. LEGAL_REFERENCES — 자산 관련 법령 메타데이터
--    조문 원문은 텍스트로 보관, 벡터 검색은 Supabase 위임
-- ============================================================
CREATE TABLE legal_references (
    id              INT             NOT NULL IDENTITY(1,1),
    law_name        NVARCHAR(200)   NOT NULL,   -- '소득세법'
    article_number  NVARCHAR(50)    NULL,       -- '제14조 제3항'
    title           NVARCHAR(500)   NULL,
    content         NVARCHAR(MAX)   NULL,
    asset_category  VARCHAR(100)    NULL,       -- 'stock', 'real_estate', 'fund' 등
    effective_date  DATE            NULL,
    last_updated    DATE            NULL,
    source_url      NVARCHAR(1000)  NULL,
    supabase_doc_id NVARCHAR(100)   NULL,       -- Supabase 벡터 레코드 ID (조인용)

    CONSTRAINT PK_legal_references PRIMARY KEY (id)
);

CREATE INDEX IX_legal_references_category ON legal_references (asset_category);
