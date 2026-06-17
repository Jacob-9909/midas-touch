"""지식그래프 빌드/탐색 라우터.

- 빌드: `pipelines/knowledge_graph/builder.py`를 비동기 작업으로 실행(증분 적재).
- 스냅샷: Neo4j에서 노드/엣지를 끌어와 포스그래프 렌더용 JSON으로 변환.
GraphRAG 질의(근거 서브그래프 포함)는 main.py의 `/api/v1/query`가 담당한다.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services.jobs import job_manager

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


class BuildRequest(BaseModel):
    limit: int = 40  # 이번 실행에서 처리할 미처리 단락 수 (-1이면 전체)


@router.post("/build/jobs")
async def start_build_job(req: BuildRequest) -> dict:
    """지식그래프 증분 빌드 파이프라인을 비동기로 시작한다."""
    cmd = [
        "uv", "run", "python", "-m", "pipelines.knowledge_graph.builder",
        "--limit", str(req.limit),
    ]
    job = job_manager.start("graph_build", cmd)
    return {"job_id": job.job_id}


@router.get("/build/jobs")
def list_build_jobs() -> dict:
    return {"jobs": [j.to_dict(log_tail=5) for j in job_manager.list("graph_build")]}


@router.get("/build/jobs/{job_id}")
def get_build_job(job_id: str) -> dict:
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
    return job.to_dict()


@router.get("/snapshot")
def graph_snapshot(limit: int = 100) -> dict:
    """Neo4j에서 (n)-[r]-(m) 관계를 끌어와 포스그래프용 nodes/links로 변환한다."""
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"neo4j 드라이버를 찾을 수 없습니다: {exc}")

    url = os.environ.get("NEO4J_URL")
    user = os.environ.get("NEO4J_USERNAME")
    password = os.environ.get("NEO4J_PASSWORD")
    if not url:
        raise HTTPException(status_code=500, detail="NEO4J_URL 환경변수가 설정되지 않았습니다.")

    cypher = """
    MATCH (n)-[r]-(m)
    RETURN n.name AS source, labels(n)[0] AS s_label,
           type(r) AS rel,
           m.name AS target, labels(m)[0] AS t_label
    LIMIT $limit
    """
    nodes: dict[str, dict] = {}
    links: list[dict] = []
    try:
        driver = GraphDatabase.driver(url, auth=(user, password))
        with driver.session(database="neo4j") as session:
            for rec in session.run(cypher, limit=limit):
                src, tgt = rec["source"], rec["target"]
                if src is None or tgt is None:
                    continue
                nodes.setdefault(src, {"id": src, "group": rec["s_label"] or "Entity"})
                nodes.setdefault(tgt, {"id": tgt, "group": rec["t_label"] or "Entity"})
                links.append({"source": src, "target": tgt, "rel": rec["rel"]})
        driver.close()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Neo4j 조회 실패: {exc}")

    return {"nodes": list(nodes.values()), "links": links}
