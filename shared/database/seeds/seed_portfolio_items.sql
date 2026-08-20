-- ============================================================
-- Midas Touch — 포트폴리오 종목 명세(portfolio_items) 시드
-- ============================================================
-- portfolios 의 자산군 비중(stock/bond/deposit/real_estate/gold/cash)을
-- 유저의 투자성향(users.aggressiveness)에 맞는 실제 종목으로 쪼개 넣는다.
--   · 안정(1~4) → 대형주·배당주·인덱스 위주
--   · 중립(5~6) → 대형주 + 해외 대표주 소량
--   · 공격(7~8) → 반도체·플랫폼 + 해외 기술주 비중 확대
-- ticker 는 야후 파이낸스 심볼(국내는 .KS)이라 대시보드 → /stocks 백테스트가 바로 붙는다.
--
-- ponytail: 종목 배분은 성향 티어 × 자산군 비중만 본다. users.specific_items 의
--   자유서술(예: "정기예금, 청약저축")까지 파싱하지 않는다 — 500명 데모용으로 과하다.
--   개인화가 더 필요해지면 그때 specific_items 매칭 규칙을 catalog 에 추가.
--
-- 실행: docker exec -i midas-postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
--         -f - < shared/database/seeds/seed_portfolio_items.sql
-- ============================================================

SET client_encoding = 'UTF8';

-- 기존 데이터 초기화 (재실행 안전)
DELETE FROM portfolio_items;

-- 카탈로그: (자산군, 성향티어, 버킷 내 배분비율, 표시유형, 티커, 종목명, 통화, 메모)
--   tier '*' = 성향 무관 공통. 같은 (bucket, tier)의 share 합은 정확히 1.0.
WITH catalog(bucket, tier, share, asset_type, ticker, nm, cur, note) AS (VALUES
    -- ── 주식 · 안정형 ──────────────────────────────────
    ('stock', '안정', 0.5, '국내주식', '005930.KS', '삼성전자',        'KRW', '시총 1위 대표주 — 변동성 대비 안정적인 코어 보유'),
    ('stock', '안정', 0.3, '국내주식', '069500.KS', 'KODEX 200',       'KRW', '코스피200 인덱스 ETF — 개별종목 위험 분산'),
    ('stock', '안정', 0.2, '국내주식', '033780.KS', 'KT&G',            'KRW', '경기방어 고배당주 — 현금흐름 보강'),
    -- ── 주식 · 중립형 ──────────────────────────────────
    ('stock', '중립', 0.4, '국내주식', '005930.KS', '삼성전자',        'KRW', '포트폴리오 코어 — 실적 안정성 우선'),
    ('stock', '중립', 0.3, '국내주식', '000660.KS', 'SK하이닉스',      'KRW', '메모리 업사이클 참여 — 성장 축'),
    ('stock', '중립', 0.2, '국내주식', '069500.KS', 'KODEX 200',       'KRW', '인덱스로 잔여 국내 익스포저 커버'),
    ('stock', '중립', 0.1, '해외주식', 'AAPL',      '애플',            'USD', '달러 자산 소량 편입 — 원화 편중 완화'),
    -- ── 주식 · 공격형 ──────────────────────────────────
    ('stock', '공격', 0.3, '국내주식', '000660.KS', 'SK하이닉스',      'KRW', 'AI 메모리 수요 직접 수혜 — 성장 코어'),
    ('stock', '공격', 0.2, '국내주식', '005930.KS', '삼성전자',        'KRW', '변동성 완충용 대형주'),
    ('stock', '공격', 0.2, '국내주식', '035420.KS', 'NAVER',           'KRW', '국내 플랫폼·AI 서비스 익스포저'),
    ('stock', '공격', 0.2, '해외주식', 'NVDA',      '엔비디아',        'USD', 'AI 인프라 핵심 — 고성장·고변동'),
    ('stock', '공격', 0.1, '해외주식', 'QQQ',       'Invesco QQQ',     'USD', '나스닥100 ETF — 해외 성장주 분산'),
    -- ── 채권 ───────────────────────────────────────────
    ('bond',  '*',    0.6, '채권',     '148070.KS', 'KOSEF 국고채10년', 'KRW', '국고채 장기물 — 금리 하락기 자본이득 기대'),
    ('bond',  '*',    0.4, '채권',     '273130.KS', 'KODEX 종합채권액티브', 'KRW', 'AA- 이상 종합채권 — 이자수익 중심'),
    -- ── 예금 ───────────────────────────────────────────
    ('deposit', '*',  0.7, '예금',     NULL,        '정기예금(12개월)', 'KRW', '원금보장 — 비상자금 및 만기 매칭'),
    ('deposit', '*',  0.3, '예금',     NULL,        '적립식 적금',      'KRW', '월 저축 여력을 자동 이체로 적립'),
    -- ── 부동산 ─────────────────────────────────────────
    ('real_estate', '*', 1.0, '부동산', NULL,       '보유 부동산·전세보증금', 'KRW', '거주·임대 목적 실물자산 — 유동성 낮음'),
    -- ── 금 ─────────────────────────────────────────────
    ('gold', '*',     1.0, '금',       '411060.KS', 'ACE KRX금현물',   'KRW', '인플레이션·달러 헤지'),
    -- ── 현금 ───────────────────────────────────────────
    ('cash', '*',     1.0, '현금',     NULL,        '수시입출금·CMA',  'KRW', '즉시 인출 가능한 대기자금')
)
INSERT INTO portfolio_items (portfolio_id, asset_type, ticker, name, allocation_pct, currency, note)
SELECT
    p.id,
    c.asset_type,
    c.ticker,
    c.nm,
    ROUND(b.ratio * c.share, 2),
    c.cur,
    c.note
FROM portfolios p
JOIN users u ON u.id = p.user_id
CROSS JOIN LATERAL (VALUES
    ('stock',       p.stock_ratio),
    ('bond',        p.bond_ratio),
    ('deposit',     p.deposit_ratio),
    ('real_estate', p.real_estate_ratio),
    ('gold',        p.gold_ratio),
    ('cash',        p.cash_ratio)
) AS b(bucket, ratio)
JOIN catalog c
  ON c.bucket = b.bucket
 AND c.tier IN ('*', CASE
                       WHEN COALESCE(u.aggressiveness, 5) <= 4 THEN '안정'
                       WHEN COALESCE(u.aggressiveness, 5) <= 6 THEN '중립'
                       ELSE '공격'
                     END)
WHERE b.ratio > 0
  AND ROUND(b.ratio * c.share, 2) >= 0.01;   -- 반올림 후 0%가 되는 잔부는 버린다

-- 검수: 종목 합계가 포트폴리오 비중 합(100%)과 일치하는지 확인
SELECT
    COUNT(*)                                   AS portfolios,
    SUM((s.item_sum BETWEEN 99.9 AND 100.1)::int) AS ok_100pct,
    MIN(s.item_cnt)                            AS min_items,
    MAX(s.item_cnt)                            AS max_items
FROM (
    SELECT portfolio_id, SUM(allocation_pct) AS item_sum, COUNT(*) AS item_cnt
    FROM portfolio_items GROUP BY portfolio_id
) s;
