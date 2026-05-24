-- ============================================================
-- Midas Touch — Supabase (pgvector) Schema
-- ============================================================
-- DB : midas_touch (Supabase Free Tier, ap-northeast-2)
-- 역할 : 벡터 검색 / RAG (뉴스, 전략 논문, 거시경제 분석 캐시)
-- 실행 : Supabase SQL Editor 또는 psql
-- ============================================================

-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 한국어 키워드 검색 보조


-- ============================================================
-- 1. NEWS_EMBEDDINGS — 뉴스 원문 + 임베딩
--    수집 대상: NewsAPI, 네이버 뉴스, Yahoo Finance RSS
-- ============================================================
CREATE TABLE IF NOT EXISTS news_embeddings (
    id              BIGSERIAL           PRIMARY KEY,
    -- 원문 메타
    title           TEXT                NOT NULL,
    content         TEXT                NOT NULL,
    published_at    TIMESTAMPTZ         NOT NULL,
    source          VARCHAR(100)        NOT NULL,       -- 'newsapi', 'naver', 'yahoo_finance'
    source_url      TEXT                NULL,
    language        CHAR(2)             NOT NULL DEFAULT 'ko',  -- 'ko' | 'en'
    -- 분류
    category        VARCHAR(50)         NULL,   -- 'exchange_rate', 'interest_rate', 'oil', 'gold', 'politics', 'disaster'
    sentiment_score NUMERIC(4,3)        NULL,   -- -1.0 ~ 1.0 (LLM 감성 분석)
    -- 벡터 (text-embedding-3-small: 1536차원)
    embedding       VECTOR(1536)        NOT NULL,
    -- 메타
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_news_url UNIQUE (source_url)
);

-- 벡터 유사도 인덱스 (HNSW — 검색 속도 최적화)
CREATE INDEX IF NOT EXISTS idx_news_embedding_hnsw
    ON news_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 날짜 + 카테고리 인덱스
CREATE INDEX IF NOT EXISTS idx_news_published_category
    ON news_embeddings (published_at DESC, category);


-- ============================================================
-- 2. STRATEGY_DOCS — 포트폴리오 전략 논문/리포트 임베딩
--    All Weather, Ray Dalio, 60/40, Risk Parity, Factor 전략 등
-- ============================================================
CREATE TABLE IF NOT EXISTS strategy_docs (
    id              BIGSERIAL           PRIMARY KEY,
    title           TEXT                NOT NULL,
    author          VARCHAR(200)        NULL,
    published_year  SMALLINT            NULL,
    strategy_type   VARCHAR(100)        NULL,   -- 'all_weather', '60_40', 'risk_parity', 'factor', 'momentum'
    -- 청크 정보 (긴 문서는 분할 적재)
    chunk_index     INT                 NOT NULL DEFAULT 0,
    chunk_text      TEXT                NOT NULL,
    -- 벡터
    embedding       VECTOR(1536)        NOT NULL,
    -- Azure SQL legal_references와의 연결 고리
    azure_legal_id  INT                 NULL,
    source_url      TEXT                NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_embedding_hnsw
    ON strategy_docs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_strategy_type
    ON strategy_docs (strategy_type, published_year DESC);


-- ============================================================
-- 3. MACRO_INDICATORS — 거시경제 지표 원본 + 설명 임베딩
--    시계열 수치는 Azure SQL market_snapshots에 저장
--    여기선 지표 해석/분석 텍스트의 벡터 검색용
-- ============================================================
CREATE TABLE IF NOT EXISTS macro_indicators (
    id              BIGSERIAL           PRIMARY KEY,
    indicator_name  VARCHAR(100)        NOT NULL,   -- 'USD/KRW', 'KR_BASE_RATE', 'WTI'
    indicator_date  DATE                NOT NULL,
    numeric_value   NUMERIC(18,6)       NOT NULL,
    unit            VARCHAR(20)         NULL,       -- 'KRW', '%', 'USD/BBL'
    -- LLM이 생성한 이 수치의 거시경제 해설 + 임베딩
    analysis_text   TEXT                NULL,
    embedding       VECTOR(1536)        NULL,       -- analysis_text의 임베딩
    source          VARCHAR(50)         NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_macro_indicator UNIQUE (indicator_name, indicator_date)
);

CREATE INDEX IF NOT EXISTS idx_macro_embedding_hnsw
    ON macro_indicators USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_macro_name_date
    ON macro_indicators (indicator_name, indicator_date DESC);


-- ============================================================
-- 4. PERSONA_EMBEDDINGS — 사용자 페르소나 텍스트 임베딩
--    Azure SQL users.uuid와 연결 — 유사 사용자 검색용
-- ============================================================
CREATE TABLE IF NOT EXISTS persona_embeddings (
    id              BIGSERIAL           PRIMARY KEY,
    azure_user_uuid VARCHAR(100)        NOT NULL UNIQUE,  -- users.uuid FK (논리적)
    persona_text    TEXT                NOT NULL,         -- 합성된 페르소나 요약
    embedding       VECTOR(1536)        NOT NULL,
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_persona_embedding_hnsw
    ON persona_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- ============================================================
-- 유틸 함수: 코사인 유사도 기반 뉴스 검색 (TOP-K)
-- ============================================================
CREATE OR REPLACE FUNCTION search_news(
    query_embedding VECTOR(1536),
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
        AND published_at >= NOW() - (days_back || ' days')::INTERVAL
    ORDER BY embedding <=> query_embedding
    LIMIT top_k;
$$;


-- ============================================================
-- 유틸 함수: 전략 문서 RAG 검색
-- ============================================================
CREATE OR REPLACE FUNCTION search_strategies(
    query_embedding VECTOR(1536),
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


-- ============================================================
-- 유틸 함수: 유사 페르소나 사용자 검색
-- ============================================================
CREATE OR REPLACE FUNCTION search_similar_personas(
    query_embedding VECTOR(1536),
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
