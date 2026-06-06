-- ============================================================
-- Midas Touch — Consolidated PostgreSQL Schema (with pgvector)
-- ============================================================
-- DB : midas-touch (PostgreSQL 13+ with pgvector 0.6.0+)
-- 역할 : 정형 데이터 및 의미론적 벡터 RAG 검색용 단일 데이터베이스 스토어
-- ============================================================

-- pgvector 및 한글 검색 보조 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 기존 테이블이 존재할 경우 삭제 (순서 준수)
DROP TABLE IF EXISTS emb_training_triplets CASCADE;
DROP TABLE IF EXISTS emb_synthetic_queries CASCADE;
DROP TABLE IF EXISTS emb_passages CASCADE;
DROP TABLE IF EXISTS news_embeddings CASCADE;
DROP TABLE IF EXISTS strategy_docs CASCADE;
DROP TABLE IF EXISTS macro_indicators CASCADE;
DROP TABLE IF EXISTS persona_embeddings CASCADE;
DROP TABLE IF EXISTS legal_references CASCADE;
DROP TABLE IF EXISTS market_snapshots CASCADE;
DROP TABLE IF EXISTS tax_rules CASCADE;
DROP TABLE IF EXISTS portfolio_items CASCADE;
DROP TABLE IF EXISTS portfolios CASCADE;
DROP TABLE IF EXISTS users CASCADE;


-- ============================================================
-- 1. USERS — 사용자 인적 + 금융 프로필
-- ============================================================
CREATE TABLE users (
    id              UUID                NOT NULL DEFAULT gen_random_uuid(),
    uuid            VARCHAR(100)        NULL,       -- HuggingFace 원본 uuid
    -- 인적 정보
    age             SMALLINT            NULL,
    sex             VARCHAR(10)         NULL,
    marital_status  VARCHAR(50)         NULL,
    education_level VARCHAR(100)        NULL,
    bachelors_field VARCHAR(200)        NULL,
    occupation      VARCHAR(200)        NULL,
    family_type     VARCHAR(100)        NULL,
    housing_type    VARCHAR(100)        NULL,
    district        VARCHAR(100)        NULL,
    -- 페르소나 텍스트 (원문 보존)
    persona                     TEXT NULL,
    professional_persona        TEXT NULL,
    family_persona              TEXT NULL,
    career_goals_and_ambitions  TEXT NULL,
    -- 자산 현황
    total_amount        BIGINT          NULL,
    monthly_income      INT             NULL,
    monthly_investable  INT             NULL,
    specific_items      VARCHAR(500)    NULL,
    has_stock           BOOLEAN         NOT NULL DEFAULT FALSE,
    has_bond            BOOLEAN         NOT NULL DEFAULT FALSE,
    has_deposit         BOOLEAN         NOT NULL DEFAULT FALSE,
    has_real_estate     BOOLEAN         NOT NULL DEFAULT FALSE,
    stock_amount        BIGINT          NOT NULL DEFAULT 0,
    bond_amount         BIGINT          NOT NULL DEFAULT 0,
    deposit_amount      BIGINT          NOT NULL DEFAULT 0,
    real_estate_amount  BIGINT          NOT NULL DEFAULT 0,
    -- 투자 성향
    aggressiveness      SMALLINT        NULL CHECK (aggressiveness BETWEEN 1 AND 10),
    preferred_asset     VARCHAR(200)    NULL,
    financial_literacy  SMALLINT        NULL CHECK (financial_literacy BETWEEN 1 AND 10),
    -- 투자 목표
    target_return_percent       DECIMAL(5,2)    NULL,
    investable_period_months    INT             NULL,
    requires_liquidity          BOOLEAN         NOT NULL DEFAULT FALSE,
    -- 메타
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT PK_users         PRIMARY KEY (id),
    CONSTRAINT UQ_users_uuid    UNIQUE (uuid)
);

CREATE INDEX IX_users_age_aggressiveness ON users (age, aggressiveness);
CREATE INDEX IX_users_total_amount       ON users (total_amount);


-- ============================================================
-- 2. PORTFOLIOS — 포트폴리오 비율 설정
-- ============================================================
CREATE TABLE portfolios (
    id              UUID                NOT NULL DEFAULT gen_random_uuid(),
    user_id         UUID                NOT NULL,
    name            VARCHAR(200)        NULL,
    strategy_name   VARCHAR(100)        NULL,   -- 'All Weather', '60/40' 등
    -- 자산 비율 (합계 = 100)
    stock_ratio         DECIMAL(5,2)    NOT NULL DEFAULT 0,
    bond_ratio          DECIMAL(5,2)    NOT NULL DEFAULT 0,
    deposit_ratio       DECIMAL(5,2)    NOT NULL DEFAULT 0,
    real_estate_ratio   DECIMAL(5,2)    NOT NULL DEFAULT 0,
    gold_ratio          DECIMAL(5,2)    NOT NULL DEFAULT 0,
    cash_ratio          DECIMAL(5,2)    NOT NULL DEFAULT 0,
    -- 상태
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

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
    id              UUID                NOT NULL DEFAULT gen_random_uuid(),
    portfolio_id    UUID                NOT NULL,
    asset_type      VARCHAR(50)         NOT NULL,   -- 'stock', 'bond' 등
    ticker          VARCHAR(30)         NULL,       -- 종목 코드 (e.g., '005930')
    name            VARCHAR(200)        NULL,
    allocation_pct  DECIMAL(5,2)        NOT NULL,
    currency        CHAR(3)             NOT NULL DEFAULT 'KRW',
    note            VARCHAR(500)        NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT PK_portfolio_items          PRIMARY KEY (id),
    CONSTRAINT FK_portfolio_items_portfolio FOREIGN KEY (portfolio_id) REFERENCES portfolios (id) ON DELETE CASCADE
);


-- ============================================================
-- 4. TAX_RULES — 자산 종류별 세율 테이블 (한국 기준)
-- ============================================================
CREATE TABLE tax_rules (
    id              SERIAL          PRIMARY KEY,
    asset_type      VARCHAR(50)     NOT NULL,   -- 'stock_domestic', 'bond' 등
    income_type     VARCHAR(50)     NOT NULL,   -- 'capital_gain', 'dividend' 등
    min_amount      BIGINT          NULL,       -- 적용 하한
    max_amount      BIGINT          NULL,       -- 적용 상한
    tax_rate        DECIMAL(6,4)    NOT NULL,   -- 세율 (0.154 = 15.4%)
    local_tax_rate  DECIMAL(6,4)    NULL,       -- 지방소득세율
    deduction_limit BIGINT          NULL,       -- 공제 한도
    effective_date  DATE            NOT NULL,
    expiry_date     DATE            NULL,       -- NULL = 현행 적용
    description     VARCHAR(500)    NULL,
    legal_basis     VARCHAR(200)    NULL,       -- '소득세법 제14조'

    CONSTRAINT UQ_tax_rules_key UNIQUE (asset_type, income_type, min_amount, max_amount, effective_date)
);

CREATE INDEX IX_tax_rules_asset_income ON tax_rules (asset_type, income_type, effective_date);


-- ============================================================
-- 5. MARKET_SNAPSHOTS — 거시경제 지표 일별 스냅샷
-- ============================================================
CREATE TABLE market_snapshots (
    id              BIGSERIAL       PRIMARY KEY,
    snapshot_date   DATE            NOT NULL,
    data_type       VARCHAR(50)     NOT NULL,   -- 'exchange_rate', 'interest_rate' 등
    sub_key         VARCHAR(30)     NULL,       -- 'USD/KRW', 'KR_CD' 등
    value           DECIMAL(18,6)   NOT NULL,
    unit            VARCHAR(20)     NULL,
    source          VARCHAR(50)     NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT UQ_market_snapshots_key UNIQUE (snapshot_date, data_type, sub_key)
);

CREATE INDEX IX_market_snapshots_date     ON market_snapshots (snapshot_date DESC);
CREATE INDEX IX_market_snapshots_type_key ON market_snapshots (data_type, sub_key, snapshot_date DESC);


-- ============================================================
-- 6. LEGAL_REFERENCES — 자산 관련 법령 메타데이터
-- ============================================================
CREATE TABLE legal_references (
    id              SERIAL          PRIMARY KEY,
    law_name        VARCHAR(200)    NOT NULL,   -- '소득세법'
    article_number  VARCHAR(50)     NULL,       -- '제14조 제3항'
    title           VARCHAR(500)    NULL,
    content         TEXT            NULL,
    asset_category  VARCHAR(100)    NULL,
    effective_date  DATE            NULL,
    last_updated    DATE            NULL,
    source_url      VARCHAR(1000)   NULL,
    supabase_doc_id VARCHAR(100)    NULL        -- 조인용 레코드 ID
);

CREATE INDEX IX_legal_references_category ON legal_references (asset_category);


-- ============================================================
-- 7. NEWS_EMBEDDINGS — 뉴스 원문 + 임베딩 (vector 1024차원)
-- ============================================================
CREATE TABLE news_embeddings (
    id              BIGSERIAL           PRIMARY KEY,
    title           TEXT                NOT NULL,
    content         TEXT                NOT NULL,
    published_at    TIMESTAMPTZ         NOT NULL,
    source          VARCHAR(100)        NOT NULL,
    source_url      TEXT                NULL,
    language        CHAR(2)             NOT NULL DEFAULT 'ko',
    category        VARCHAR(50)         NULL,
    sentiment_score NUMERIC(4,3)        NULL,
    embedding       VECTOR(1024)        NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_news_url UNIQUE (source_url)
);

-- 벡터 유사도 인덱스 (HNSW)
CREATE INDEX idx_news_embedding_hnsw
    ON news_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_news_published_category
    ON news_embeddings (published_at DESC, category);


-- ============================================================
-- 8. STRATEGY_DOCS — 포트폴리오 전략 논문/리포트 임베딩
-- ============================================================
CREATE TABLE strategy_docs (
    id              BIGSERIAL           PRIMARY KEY,
    title           TEXT                NOT NULL,
    author          VARCHAR(200)        NULL,
    published_year  SMALLINT            NULL,
    strategy_type   VARCHAR(100)        NULL,
    chunk_index     INT                 NOT NULL DEFAULT 0,
    chunk_text      TEXT                NOT NULL,
    embedding       VECTOR(1024)        NOT NULL,
    azure_legal_id  INT                 NULL, -- 통합 DB에서는 물리적 외래키 설정 가능
    source_url      TEXT                NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT FK_strategy_docs_legal FOREIGN KEY (azure_legal_id) REFERENCES legal_references (id) ON DELETE SET NULL
);

CREATE INDEX idx_strategy_embedding_hnsw
    ON strategy_docs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_strategy_type
    ON strategy_docs (strategy_type, published_year DESC);


-- ============================================================
-- 9. MACRO_INDICATORS — 거시경제 지표 원본 + 설명 임베딩
-- ============================================================
CREATE TABLE macro_indicators (
    id              BIGSERIAL           PRIMARY KEY,
    indicator_name  VARCHAR(100)        NOT NULL,
    indicator_date  DATE                NOT NULL,
    numeric_value   NUMERIC(18,6)       NOT NULL,
    unit            VARCHAR(20)         NULL,
    analysis_text   TEXT                NULL,
    embedding       VECTOR(1024)        NULL,
    source          VARCHAR(50)         NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_macro_indicator UNIQUE (indicator_name, indicator_date)
);

CREATE INDEX idx_macro_embedding_hnsw
    ON macro_indicators USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

CREATE INDEX idx_macro_name_date
    ON macro_indicators (indicator_name, indicator_date DESC);


-- ============================================================
-- 10. PERSONA_EMBEDDINGS — 사용자 페르소나 텍스트 임베딩
-- ============================================================
CREATE TABLE persona_embeddings (
    id              BIGSERIAL           PRIMARY KEY,
    azure_user_uuid VARCHAR(100)        NOT NULL UNIQUE, -- 물리적 외래키 연결 가능
    persona_text    TEXT                NOT NULL,
    embedding       VECTOR(1024)        NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT FK_persona_embeddings_users FOREIGN KEY (azure_user_uuid) REFERENCES users (uuid) ON DELETE CASCADE
);

CREATE INDEX idx_persona_embedding_hnsw
    ON persona_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ============================================================
-- 11. EMB_PASSAGES — 임베딩 파인튜닝용 금융 문서 단락
-- ============================================================
CREATE TABLE emb_passages (
    passage_id  TEXT            PRIMARY KEY,
    text        TEXT            NOT NULL,
    source      TEXT            NOT NULL,
    metadata    JSONB           NULL,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IX_emb_passages_source ON emb_passages (source);


-- ============================================================
-- 12. EMB_SYNTHETIC_QUERIES — LLM 합성 쿼리
-- ============================================================
CREATE TABLE emb_synthetic_queries (
    query_id        TEXT        PRIMARY KEY,
    passage_id      TEXT        NOT NULL REFERENCES emb_passages (passage_id) ON DELETE CASCADE,
    query_text      TEXT        NOT NULL,
    query_type      TEXT        NOT NULL,   -- keyword/question/vague_intent/comparison/regulatory
    source_passage  TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IX_emb_queries_passage_id ON emb_synthetic_queries (passage_id);
CREATE INDEX IX_emb_queries_type       ON emb_synthetic_queries (query_type);


-- ============================================================
-- 13. EMB_TRAINING_TRIPLETS — (Query, Positive, Negative) 삼중쌍
-- ============================================================
CREATE TABLE emb_training_triplets (
    triplet_id                TEXT            PRIMARY KEY,
    query_id                  TEXT            NOT NULL,
    query_text                TEXT            NOT NULL,
    positive_passage_id       TEXT            NOT NULL,
    positive_text             TEXT            NOT NULL,
    negative_passage_id       TEXT            NOT NULL,
    negative_text             TEXT            NOT NULL,
    query_type                TEXT            NOT NULL,
    negative_similarity_score NUMERIC(8, 6)   NOT NULL,
    positive_similarity_score NUMERIC(8, 6)   NOT NULL,
    margin                    NUMERIC(8, 6)   NOT NULL,
    split                     TEXT            NOT NULL CHECK (split IN ('train', 'eval')),
    created_at                TIMESTAMPTZ     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IX_emb_triplets_split      ON emb_training_triplets (split);
CREATE INDEX IX_emb_triplets_query_type ON emb_training_triplets (query_type, split);


-- ============================================================
-- RAG 검색 유틸리티 PostgreSQL 함수 정의
-- ============================================================

-- 1. 코사인 유사도 기반 뉴스 검색
CREATE OR REPLACE FUNCTION search_news(
    query_embedding VECTOR(1024),
    top_k           INT     DEFAULT 10,
    category_filter VARCHAR DEFAULT NULL,
    days_back       INT     DEFAULT 30
)
RETURNS TABLE (
    id              BIGINT,
    title           TEXT,
    content         TEXT,
    published_at    TIMESTAMPTZ,
    source          VARCHAR,
    category        VARCHAR,
    sentiment_score NUMERIC,
    similarity      FLOAT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        id, title, content, published_at, source,
        category, sentiment_score,
        1 - (embedding <=> query_embedding) AS similarity
    FROM news_embeddings
    WHERE
        (category_filter IS NULL OR category = category_filter)
        AND published_at >= CURRENT_TIMESTAMP - (days_back || ' days')::INTERVAL
    ORDER BY embedding <=> query_embedding
    LIMIT top_k;
$$;


-- 2. 전략 문서 RAG 검색
CREATE OR REPLACE FUNCTION search_strategies(
    query_embedding VECTOR(1024),
    top_k           INT     DEFAULT 5,
    strategy_filter VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id              BIGINT,
    title           TEXT,
    chunk_text      TEXT,
    strategy_type   VARCHAR,
    author          VARCHAR,
    similarity      FLOAT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        id, title, chunk_text, strategy_type, author,
        1 - (embedding <=> query_embedding) AS similarity
    FROM strategy_docs
    WHERE strategy_filter IS NULL OR strategy_type = strategy_filter
    ORDER BY embedding <=> query_embedding
    LIMIT top_k;
$$;


-- 3. 유사 페르소나 사용자 검색
CREATE OR REPLACE FUNCTION search_similar_personas(
    query_embedding VECTOR(1024),
    top_k           INT DEFAULT 5
)
RETURNS TABLE (
    azure_user_uuid VARCHAR,
    persona_text    TEXT,
    similarity      FLOAT
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        azure_user_uuid, persona_text,
        1 - (embedding <=> query_embedding) AS similarity
    FROM persona_embeddings
    ORDER BY embedding <=> query_embedding
    LIMIT top_k;
$$;
