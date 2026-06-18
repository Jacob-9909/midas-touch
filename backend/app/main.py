"""
main.py
-------
FastAPI 기반 실시간 Midas Touch 금융 자산 관리 및 GraphRAG 질의 웹 API 서비스 엔트리포인트.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.database.connector import get_connection
from backend.app.api.chat import router as chat_router
from backend.app.api.users import router as users_router
from backend.app.api.finetune import router as finetune_router
from backend.app.api.graph import router as graph_router
from backend.app.api.query import router as query_router

app = FastAPI(
    title="Midas Touch API Server",
    description="금융 특화 임베딩 및 Neo4j GraphRAG 기반 자산관리 조언 서비스 API",
    version="1.0.0",
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
