-- ============================================================
-- Midas Touch — 한국 자산 세율 초기 데이터 (2024년 기준)
-- ============================================================
-- 출처: 소득세법, 조세특례제한법, 금융투자소득세 관련 법령
-- 실행: Azure SQL Query Editor 또는 sqlcmd
-- ============================================================

-- 기존 데이터 초기화 (재실행 안전)
DELETE FROM tax_rules;

-- ============================================================
-- 1. 국내 주식 (stock_domestic)
-- ============================================================

-- 소액주주 상장주식 양도소득 비과세 (거래세 별도)
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_domestic', 'capital_gain', NULL, 250000000, 0.0000, NULL,
     NULL, '2024-01-01', NULL,
     '소액주주 상장주식 양도 — 비과세 (대주주 요건 미해당)',
     '소득세법 제94조 제1항 제3호');

-- 대주주 상장주식 양도소득세
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_domestic', 'capital_gain', 1, 300000000, 0.2000, 0.0200,
     2500000, '2024-01-01', NULL,
     '대주주 양도소득세 20% (과세표준 3억 이하)',
     '소득세법 제104조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_domestic', 'capital_gain', 300000001, NULL, 0.2500, 0.0250,
     NULL, '2024-01-01', NULL,
     '대주주 양도소득세 25% (과세표준 3억 초과)',
     '소득세법 제104조 제1항');

-- 국내 주식 배당소득세
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_domestic', 'dividend', 1, 20000000, 0.1400, 0.0140,
     NULL, '2024-01-01', NULL,
     '금융소득 2000만원 이하 배당소득세 분리과세 14%+지방세 1.4%',
     '소득세법 제129조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_domestic', 'dividend', 20000001, NULL, 0.4500, 0.0450,
     NULL, '2024-01-01', NULL,
     '금융소득 2000만원 초과 시 종합소득세 합산 (최고세율 45%+지방세 4.5%)',
     '소득세법 제14조 제3항');

-- ============================================================
-- 2. 해외 주식 (stock_foreign)
-- ============================================================

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_foreign', 'capital_gain', 1, NULL, 0.2200, 0.0220,
     2500000, '2024-01-01', NULL,
     '해외주식 양도소득세 22% (기본공제 250만원, 지방세 포함)',
     '소득세법 제118조의2');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('stock_foreign', 'dividend', 1, 20000000, 0.1400, 0.0140,
     NULL, '2024-01-01', NULL,
     '해외주식 배당소득 원천징수세 14% (현지 원천징수 세액공제 가능)',
     '소득세법 제129조');

-- ============================================================
-- 3. 채권 (bond)
-- ============================================================

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('bond', 'interest', 1, 20000000, 0.1540, 0.0000,
     NULL, '2024-01-01', NULL,
     '채권 이자소득세 15.4% (소득세 14% + 지방소득세 1.4%)',
     '소득세법 제16조, 제129조');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('bond', 'capital_gain', 1, NULL, 0.0000, NULL,
     NULL, '2024-01-01', NULL,
     '상장채권 소액주주 양도차익 비과세',
     '소득세법 제94조 제1항 제2호');

-- ============================================================
-- 4. 예금/적금 (deposit)
-- ============================================================

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('deposit', 'interest', 1, 20000000, 0.1540, 0.0000,
     NULL, '2024-01-01', NULL,
     '예금·적금 이자소득세 15.4% (소득세 14% + 지방소득세 1.4%)',
     '소득세법 제16조 제1항 제1호');

-- 비과세종합저축 (만 65세 이상, 장애인 등)
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('deposit', 'interest', 1, 50000000, 0.0000, NULL,
     NULL, '2024-01-01', NULL,
     '비과세종합저축 이자소득 비과세 (5000만원 한도, 65세 이상/장애인)',
     '조세특례제한법 제88조의2');

-- ============================================================
-- 5. 펀드 (fund)
-- ============================================================

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('fund', 'dividend', 1, 20000000, 0.1540, 0.0000,
     NULL, '2024-01-01', NULL,
     '펀드 배당소득(분배금) 15.4% 원천징수',
     '소득세법 제17조 제1항 제5호');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('fund', 'capital_gain', 1, NULL, 0.0000, NULL,
     NULL, '2024-01-01', NULL,
     '국내 공모 주식형 펀드 매매차익 비과세',
     '소득세법 제94조 제1항');

-- ============================================================
-- 6. 부동산 (real_estate)
-- ============================================================

-- 단기 보유 (1년 미만)
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 1, NULL, 0.7000, 0.0700,
     NULL, '2024-01-01', NULL,
     '주택 1년 미만 보유 양도세 70% (조정대상지역 내)',
     '소득세법 제104조 제1항');

-- 1년~2년 보유
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 1, NULL, 0.6000, 0.0600,
     NULL, '2024-01-01', NULL,
     '주택 1년 이상 2년 미만 보유 양도세 60%',
     '소득세법 제104조 제1항');

-- 2년 이상 보유 (일반세율, 누진)
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 1, 14000000, 0.0600, 0.0060,
     2500000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 6% (1400만원 이하)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 14000001, 50000000, 0.1500, 0.0150,
     840000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 15% (1400만원~5000만원)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 50000001, 88000000, 0.2400, 0.0240,
     5940000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 24% (5000만원~8800만원)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 88000001, 150000000, 0.3500, 0.0350,
     15440000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 35% (8800만원~1.5억)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 150000001, 300000000, 0.3800, 0.0380,
     19940000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 38% (1.5억~3억)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 300000001, 500000000, 0.4000, 0.0400,
     25940000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 40% (3억~5억)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 500000001, 1000000000, 0.4200, 0.0420,
     35940000, '2024-01-01', NULL,
     '양도소득세 일반세율 구간 42% (5억~10억)',
     '소득세법 제55조 제1항');

INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'transfer', 1000000001, NULL, 0.4500, 0.0450,
     56940000, '2024-01-01', NULL,
     '양도소득세 최고세율 45% (10억 초과)',
     '소득세법 제55조 제1항');

-- 임대소득세 (주택임대, 연 2000만원 이하 분리과세 선택)
INSERT INTO tax_rules
    (asset_type, income_type, min_amount, max_amount, tax_rate, local_tax_rate,
     deduction_limit, effective_date, expiry_date, description, legal_basis)
VALUES
    ('real_estate', 'rental', 1, 20000000, 0.1400, 0.0140,
     2000000, '2024-01-01', NULL,
     '주택임대소득 2000만원 이하 분리과세 선택 시 14%+지방세 1.4%',
     '소득세법 제64조의2');
