"""
main.py
-------
FastAPI 기반 실시간 Midas Touch 금융 자산 관리 및 GraphRAG 질의 웹 API 서비스 엔트리포인트.
"""

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.auth import router as auth_router
from backend.app.api.chat import router as chat_router
from backend.app.api.cheongyak import router as cheongyak_router
from backend.app.api.graph import router as graph_router
from backend.app.api.query import router as query_router
from backend.app.api.research import router as research_router
from backend.app.api.stocks import router as stocks_router
from backend.app.api.users import router as users_router
from shared.database.connector import get_connection

# uvicorn은 자기 로거만 설정해서, 앱 로거의 INFO가 root(기본 WARNING)에서 잘린다.
# 캐시 예열·일일 적재 로그를 기동 화면에서 바로 보려면 root 레벨을 열어줘야 한다.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

_log = logging.getLogger("midas.validation")


def _run_validation() -> dict:
    """분석 메모리 검증 1회 실행(블로킹 — yfinance/psycopg2). 스레드에서 호출한다.

    주 결정(decision, 7일 고정구간)과 다중 시간축(24h/3d/1w/1m)을 함께 채점한다.
    """
    from backend.app.services.trading.analysis_memory import get_analysis_memory

    mem = get_analysis_memory()
    return {"decision": mem.validate_recent(), "horizons": mem.validate_horizons()}


async def _validation_loop() -> None:
    """주기적으로 미검증 분석을 채점해 학습 루프(캘리브레이션·유사 가산점)를 살린다.

    ANALYSIS_VALIDATION_ENABLED=false면 비활성. 간격은 ANALYSIS_VALIDATION_INTERVAL_HOURS(기본 12h),
    부팅 직후 지연은 ANALYSIS_VALIDATION_START_DELAY_SECONDS(기본 60s). 실패해도 루프는 지속.
    """
    if os.getenv("ANALYSIS_VALIDATION_ENABLED", "true").lower() != "true":
        _log.info("analysis validation disabled (ANALYSIS_VALIDATION_ENABLED=false)")
        return
    interval_s = float(os.getenv("ANALYSIS_VALIDATION_INTERVAL_HOURS", "12")) * 3600
    delay_s = float(os.getenv("ANALYSIS_VALIDATION_START_DELAY_SECONDS", "60"))
    await asyncio.sleep(delay_s)  # 부팅 직후 폭주 방지
    while True:
        try:
            stats = await asyncio.to_thread(_run_validation)
            _log.info("analysis validation: %s", stats)
        except Exception as exc:
            _log.warning("analysis validation failed: %s", exc)
        await asyncio.sleep(interval_s)


def _run_market_ingest() -> dict:
    """거시지표 일일 적재 1회 실행(블로킹 — yfinance/FRED/ECOS/psycopg2). 스레드에서 호출한다.

    최근 MARKET_INGEST_LOOKBACK_DAYS일(기본 7)만 수집한다. upsert 키가
    (snapshot_date, data_type, sub_key)라 겹치는 날짜를 다시 넣어도 행이 늘지 않고,
    값이 같으면 내용도 그대로다. 휴장일·지연 정정 때문에 하루가 아니라 일주일을 겹쳐 받는다.
    """
    from datetime import timedelta

    from pipelines.data_ingestion.fetch_market_data import MarketDataPipeline
    from shared.database.connector import bulk_upsert_market_snapshots
    from shared.utils.timez import now_kst

    end = now_kst()
    start = end - timedelta(days=int(os.getenv("MARKET_INGEST_LOOKBACK_DAYS", "7")))
    rows = MarketDataPipeline().fetch_all(
        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    )
    return {"fetched": len(rows), "saved": bulk_upsert_market_snapshots(rows) if rows else 0}


async def _market_ingest_loop() -> None:
    """거시지표(환율·금리·유가 등)를 매일 한 번 DB에 적재한다.

    MARKET_INGEST_ENABLED=false면 비활성. 간격은 MARKET_INGEST_INTERVAL_HOURS(기본 24h).
    마지막 적재가 간격 이내면 건너뛴다 — dev 서버가 --reload로 자주 재시작해도
    외부 API를 반복해서 때리지 않는다. 실패해도 루프는 지속.
    """
    if os.getenv("MARKET_INGEST_ENABLED", "true").lower() != "true":
        _log.info("market ingest disabled (MARKET_INGEST_ENABLED=false)")
        return
    interval_s = float(os.getenv("MARKET_INGEST_INTERVAL_HOURS", "24")) * 3600
    await asyncio.sleep(float(os.getenv("MARKET_INGEST_START_DELAY_SECONDS", "30")))

    while True:
        try:
            if await asyncio.to_thread(_ingest_due, interval_s):
                _log.info("market ingest: %s", await asyncio.to_thread(_run_market_ingest))
            else:
                _log.info("market ingest skipped (최근 적재 이력이 간격 이내)")
        except Exception as exc:
            _log.warning("market ingest failed: %s", exc)
        await asyncio.sleep(interval_s)


def _ingest_due(interval_s: float) -> bool:
    """마지막 적재로부터 interval_s가 지났는지. 이력이 없으면 실행한다."""
    from datetime import datetime

    from shared.database.connector import get_last_ingest_time

    last = get_last_ingest_time()
    if last is None:
        return True
    return (datetime.now(tz=last.tzinfo) - last).total_seconds() >= interval_s


async def _warm_caches() -> None:
    """부팅 직후 거시지표·히트맵 캐시를 미리 채운다.

    두 엔드포인트 모두 '요청이 들어온 뒤에야' 백그라운드 갱신을 시작해서, 서버를 갓 띄우면
    첫 방문자는 하드코딩 기본값(sample_initial)을 본다. 미리 데워두면 첫 화면부터 라이브 값이다.
    """
    from backend.app.api.stocks import _do_update_heatmap
    from backend.app.api.users import _update_macro_cache
    from backend.app.services.agent.tools._embedding import get_embedding_model
    from backend.app.services.agent.tools.graph_rag import _get_retriever_bundle

    # 첫 GraphRAG 요청이 콜드 비용을 전부 뒤집어쓰면 데모가 멈춘 것처럼 보인다(실측 콜드 ~8분,
    # 웜 11초). 무거운 쪽은 bge-m3 로드가 아니라 PropertyGraphIndex.from_existing이다.
    # ponytail: 비용을 부팅 시점으로 옮기기만 한다. from_existing 자체를 빠르게 하려면
    # 리트리버를 직접 Cypher로 짜야 하는데 그건 별개 작업이다.
    # 병렬 워밍: 예전엔 순차라 가벼운 macro/heatmap이 무거운 graph-retriever(콜드 ~8분) 뒤에 줄서서,
    # 부팅 후 몇 분간 시장지표가 옛 기본값으로 보였다. gather로 동시에 데워 시장지표는 즉시 신선해진다.
    async def _warm(name: str, fn) -> None:
        try:
            await asyncio.to_thread(fn)
            _log.info("cache warmed: %s", name)
        except Exception as exc:
            _log.warning("cache warm failed (%s): %s", name, exc)

    await asyncio.gather(
        _warm("embedding", get_embedding_model),
        _warm("graph-retriever", _get_retriever_bundle),
        _warm("macro", _update_macro_cache),
        _warm("heatmap", _do_update_heatmap),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명 동안 백그라운드 태스크(캐시 예열·분석 검증·거시지표 적재)를 띄우고, 종료 시 정리한다.

    캐시 예열은 프로세스별 인메모리라 워커마다 돌아야 한다. 반면 분석검증·거시적재는 DB 쓰기/외부적재라
    워커마다 돌면 중복 실행된다 → RUN_BACKGROUND_JOBS(기본 true) 뒤로 게이트한다. 웹 워커를 N개로
    늘릴 땐 웹 tier는 false로 두고 전용 워커/크론 1개만 true로 돌린다.
    # ponytail: env 플래그 = 운영자가 정확히 세팅해야 하는 게 천장. 진짜 스케줄러(Celery beat/k8s CronJob)로
    #           옮기면 이 규약이 코드로 강제된다. 그 전까지는 플래그로 충분.
    """
    tasks = [asyncio.create_task(_warm_caches())]
    if os.getenv("RUN_BACKGROUND_JOBS", "true").lower() == "true":
        tasks.append(asyncio.create_task(_validation_loop()))
        tasks.append(asyncio.create_task(_market_ingest_loop()))
    else:
        _log.info("background jobs disabled (RUN_BACKGROUND_JOBS=false) — 검증/적재는 전용 워커가 담당")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="Midas Touch API Server",
    description="금융 특화 임베딩 및 Neo4j GraphRAG 기반 자산관리 조언 서비스 API",
    version="1.0.0",
    lifespan=lifespan,
)

# 웹 콘솔(Next.js dev) → API 호출 허용. 운영 시 도메인을 좁힐 것.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ALLOW_ORIGINS", "http://localhost:3000"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 멀티턴 에이전트 라우터 (LangGraph 기반 /api/v1/chat)
app.include_router(auth_router)
app.include_router(chat_router)
# 웹 콘솔 라우터 (유저/대시보드, 지식그래프·문서 인입, GraphRAG 단발 질의)
app.include_router(users_router)
app.include_router(graph_router)
app.include_router(query_router)
# 라이브 기능 라우터 (wealth_advisor 이식: 주식 백테스트/분석, 청약 조회, 시장 리서치)
app.include_router(stocks_router)
app.include_router(cheongyak_router)
app.include_router(research_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Midas Touch API Server"}


@app.get("/health")
def health_check():
    # 간단한 PostgreSQL 연결 헬스체크
    try:
        conn = get_connection()
        conn.close()
        db_status = "healthy"
    except Exception as exc:
        db_status = f"unhealthy ({exc})"

    return {
        "status": "healthy",
        "database": db_status,
        "neo4j": os.environ.get("NEO4J_URL", "unset"),
    }
