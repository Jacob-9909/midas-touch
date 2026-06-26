"""Neo4j 접근 단일 진입점.

이전엔 raw `GraphDatabase.driver`가 api/graph.py에 인라인돼 요청마다 드라이버를 새로 열고
닫았다. 여기로 모아 **프로세스 1회 생성 드라이버를 재사용**한다(연결/세션 비용 절감).

NOTE: 에이전트 GraphRAG 검색은 LlamaIndex의 Neo4jPropertyGraphStore(다른 추상화)를 쓰므로
별도 경로다(tools/graph_rag.py). 본 모듈은 raw Cypher 조회(그래프 스냅샷 등)를 담당한다.
"""

from __future__ import annotations

import os
import threading
from typing import Any

_driver: Any | None = None
_driver_lock = threading.Lock()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} 환경변수가 설정되어 있지 않습니다.")
    return value


def get_driver():
    """프로세스 수명 동안 유지되는 Neo4j 드라이버를 1회 생성해 반환한다(지연 초기화·스레드 안전)."""
    global _driver
    if _driver is None:
        with _driver_lock:
            if _driver is None:
                from neo4j import GraphDatabase

                url = _require_env("NEO4J_URL")
                user = os.environ.get("NEO4J_USERNAME")
                password = os.environ.get("NEO4J_PASSWORD")
                _driver = GraphDatabase.driver(url, auth=(user, password))
    return _driver


def fetch_graph_snapshot(limit: int = 200) -> dict:
    """엔티티 간 의미관계를 끌어와 포스그래프 렌더용 nodes/links로 변환한다.

    - 노드 group: 구조 라벨(`__Entity__`/`__Node__`/`Chunk`)을 걸러낸 **도메인 라벨**
      (예: TAXRULE, ASSETCLASS)을 쓴다. labels()[0]은 항상 `__Entity__`라 타입이 뭉개졌다.
    - 관계: 명명된 엔티티 사이의 **방향성** 관계만(무방향 중복·`MENTIONS`(Chunk→Entity) 제외).
    - 상세정보: 노드 속성(source/file_type/description 등 임베딩 외 스칼라)을 함께 내려준다.
    """
    cypher = """
    MATCH (n)-[r]->(m)
    WHERE n.name IS NOT NULL AND m.name IS NOT NULL AND type(r) <> 'MENTIONS'
    RETURN n.name AS source,
           [l IN labels(n) WHERE NOT l STARTS WITH '__' AND l <> 'Chunk'][0] AS s_label,
           type(r) AS rel,
           m.name AS target,
           [l IN labels(m) WHERE NOT l STARTS WITH '__' AND l <> 'Chunk'][0] AS t_label,
           properties(n) AS s_props,
           properties(m) AS t_props
    LIMIT $limit
    """
    _DROP = {"embedding", "name", "id"}

    def _detail(props: dict) -> dict:
        return {
            k: v
            for k, v in (props or {}).items()
            if k not in _DROP and not isinstance(v, list) and v is not None
        }

    nodes: dict[str, dict] = {}
    links: list[dict] = []
    driver = get_driver()
    with driver.session(database="neo4j") as session:
        for rec in session.run(cypher, limit=limit):
            src, tgt = rec["source"], rec["target"]
            if src is None or tgt is None:
                continue
            nodes.setdefault(
                src,
                {"id": src, "group": rec["s_label"] or "Entity", "props": _detail(rec["s_props"])},
            )
            nodes.setdefault(
                tgt,
                {"id": tgt, "group": rec["t_label"] or "Entity", "props": _detail(rec["t_props"])},
            )
            links.append({"source": src, "target": tgt, "rel": rec["rel"]})
    return {"nodes": list(nodes.values()), "links": links}
