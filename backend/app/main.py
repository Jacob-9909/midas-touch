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
from shared.database.connector import get_connection
from backend.app.api.chat import router as chat_router
from backend.app.api.users import router as users_router
from backend.app.api.finetune import router as finetune_router
from backend.app.api.graph import router as graph_router
from backend.app.api.query import router as query_router
from backend.app.api.stocks import router as stocks_router
from backend.app.api.cheongyak import router as cheongyak_router
from backend.app.api.research import router as research_router

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
        except Exception as exc:  # noqa: BLE001 - 검증 실패가 서버를 죽이면 안 됨
            _log.warning("analysis validation failed: %s", exc)
        await asyncio.sleep(interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명 동안 분석 검증 백그라운드 태스크를 띄우고, 종료 시 정리한다."""
    task = asyncio.create_task(_validation_loop())
    try:
        yield
    finally:
        task.cancel()
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
app.include_router(chat_router)
# 웹 콘솔 라우터 (유저/대시보드, 파인튜닝, 지식그래프, GraphRAG 단발 질의)
app.include_router(users_router)
app.include_router(finetune_router)
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
