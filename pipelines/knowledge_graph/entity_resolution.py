"""
entity_resolution.py
--------------------
Neo4j 지식 그래프의 동적 엔티티 중복 정제(Entity Resolution) 및 병합 스케줄러.

1. 1차 필터링: BAAI/bge-m3 임베딩 모델을 활용하여 유사도가 높은(0.82 이상) 노드 쌍(Candidate Pair) 추출.
2. 2차 검증: LLM(NVIDIA NIM)을 활용해 두 노드가 세무/금융 맥락상 실질적 동의어(Synonym)인지 최종 의미 검증.
3. 3차 병합: Python-driven Cypher 트랜잭션을 실행해 구 노드의 관계를 신 노드로 이식 후 구 노드를 삭제.
4. 백그라운드 스케줄 데몬 기능 포함.
"""

import os
import sys
import time
import logging
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv
import numpy as np

# 프로젝트 루트 경로 추가
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

load_dotenv()

from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from shared.utils.nim_openai import NIMOpenAI

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("entity_resolution")


class EntityRefiner:
    """지식 그래프의 중복 엔티티를 정밀 진단 및 병합 정제하는 클래스."""

    def __init__(self) -> None:
        self._init_connections()

    def _init_connections(self) -> None:
        """Neo4j, 임베딩, LLM 등 필요한 외부 커넥션 초기화."""
        # 1. Neo4j Store 연결
        neo4j_url = os.environ.get("NEO4J_URL")
        neo4j_user = os.environ.get("NEO4J_USERNAME")
        neo4j_password = os.environ.get("NEO4J_PASSWORD")
        
        logger.info("Neo4j 연결 중 (%s)...", neo4j_url)
        self.graph_store = Neo4jPropertyGraphStore(
            username=neo4j_user,
            password=neo4j_password,
            url=neo4j_url,
            database="neo4j",
        )

        # 2. 임베딩 모델 로드 (BAAI/bge-m3)
        logger.info("BAAI/bge-m3 임베딩 모델 로드 중 (CPU)...")
        self.embed_model = HuggingFaceEmbedding(
            model_name="BAAI/bge-m3",
            device="cpu",
        )

        # 3. LLM 설정 (NVIDIA NIM - OpenAI 호환 엔드포인트, 다중 키 로테이션 포함)
        logger.info("NVIDIA NIM LLM 초기화 중...")
        nim_model = os.environ.get("NIM_GENERATION_MODEL")
        if not nim_model:
            raise RuntimeError("NIM_GENERATION_MODEL 환경변수가 설정되어 있지 않습니다.")
        self.llm = NIMOpenAI(
            model=nim_model,
            api_base=NIM_BASE_URL,
            temperature=0.0,
            max_tokens=2048,
        )

    def run_resolution(self, similarity_threshold: float = 0.82) -> int:
        """전체 지식 그래프를 스캔하여 동적 엔티티 병합 세션 수행."""
        logger.info("=== 엔티티 정제 세션 시작 (유사도 임계값: %.2f) ===", similarity_threshold)
        
        # 1. Neo4j의 모든 노드 정보 가져오기
        nodes = self._fetch_all_nodes()
        if len(nodes) < 2:
            logger.info("정제할 만큼 노드가 충분하지 않습니다. (현재 노드 수: %d)", len(nodes))
            return 0

        # 2. 노드 이름들의 임베딩 계산
        logger.info("%d개 노드 이름 임베딩 변환 중...", len(nodes))
        node_names = [n["name"] for n in nodes]
        embeddings = []
        for name in node_names:
            try:
                embeddings.append(self.embed_model.get_text_embedding(name))
            except Exception as exc:
                logger.error("'%s' 임베딩 실패: %s", name, exc)
                embeddings.append([0.0] * 1024) # 덤 벡터
                
        emb_matrix = np.array(embeddings)

        # 3. 코사인 유사도 행렬 계산
        norm = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        # 0 나누기 오류 방지
        norm[norm == 0] = 1.0
        normalized_emb = emb_matrix / norm
        similarity_matrix = np.dot(normalized_emb, normalized_emb.T)

        # 4. 상삼각행렬에서 임계값을 넘는 중복 후보 쌍 검출 (자기 자신 제외)
        pairs_to_check = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                # 동일한 Label을 가진 노드들 사이에서만 비교하여 안전성 확보
                if nodes[i]["label"] == nodes[j]["label"]:
                    score = float(similarity_matrix[i, j])
                    if score >= similarity_threshold:
                        pairs_to_check.append((nodes[i], nodes[j], score))

        logger.info("1차 임베딩 필터링 완료: 중복 의심 후보 %d쌍 검출.", len(pairs_to_check))
        
        # 5. LLM을 통한 2차 최종 판정 및 병합 수행
        merged_count = 0
        merged_names = set() # 세션 내에서 이미 지워진 노드의 이중 처리를 막기 위함

        for node_a, node_b, score in pairs_to_check:
            name_a, name_b = node_a["name"], node_b["name"]
            label = node_a["label"]
            
            # 이미 병합되어 사라진 노드가 포함되어 있으면 패스
            if name_a in merged_names or name_b in merged_names:
                continue

            logger.info("LLM 정밀 검증 중: '%s' ↔ '%s' (유사도 스코어: %.4f, 타입: %s)", name_a, name_b, score, label)
            
            is_dup, preferred_name = self._verify_duplicate_with_llm(name_a, name_b, label)
            
            if is_dup and preferred_name:
                logger.info("⭐ 동의어 판정 성공! 대표 이름: '%s'", preferred_name)
                
                # 병합 타겟 결정
                keep_node = node_a if preferred_name == name_a else node_b
                delete_node = node_b if preferred_name == name_a else node_a
                
                # Neo4j 병합 트랜잭션 수행
                success = self._merge_nodes_neo4j(keep_node, delete_node)
                if success:
                    merged_names.add(delete_node["name"])
                    merged_count += 1
                    logger.info("노드 병합 완료: '%s' ➡️ '%s'로 흡수됨.", delete_node["name"], keep_node["name"])
            else:
                logger.info("독립 개념 판정: 병합을 수행하지 않습니다.")

        logger.info("=== 엔티티 정제 세션 종료: 총 %d개 노드 병합 처리됨 ===", merged_count)
        return merged_count

    def _fetch_all_nodes(self) -> list[dict]:
        """Neo4j DB에서 모든 Entity 노드 정보(이름, 라벨)를 조회."""
        cypher = """
        MATCH (n)
        WHERE labels(n)[0] IS NOT NULL AND n.name IS NOT NULL
        RETURN id(n) AS neo_id, n.name AS name, labels(n)[0] AS label
        """
        try:
            records = self.graph_store.structured_query(cypher)
            nodes = []
            for r in records:
                nodes.append({
                    "neo_id": r.get("neo_id"),
                    "name": r.get("name"),
                    "label": r.get("label"),
                })
            return nodes
        except Exception as exc:
            logger.error("Neo4j 노드 조회 중 오류: %s", exc)
            return []

    def _verify_duplicate_with_llm(self, name_a: str, name_b: str, label: str) -> tuple[bool, str]:
        """LLM을 호출하여 두 노드의 금융/세무적 의미가 완벽히 동일한지 판별."""
        import json
        import re

        prompt = f"""당신은 금융 및 세무 분야의 전문 지식 관리자입니다.
다음 두 단어가 금융/세법 맥락에서 '완벽하게 동일한 의미'를 가지는 동의어인지 분석하십시오.

- 노드 1 이름: {name_a}
- 노드 2 이름: {name_b}
- 지식 도메인 유형: {label}

### 판단 기준:
1. 단순히 어미나 철자 차이(예: 'ISA계좌'와 'ISA'), 또는 동의어 관계(예: '종합저축'과 '종합통장')인 경우 동일 개념(true)으로 간주합니다.
2. 예금금리와 적금금리, 혹은 배당소득과 연금소득처럼 단어가 유사해 보여도 실질적인 세법이나 금융법상 별개 항목인 경우 절대 동일 개념으로 보지 않습니다(false).
3. 동일한 개념이라면, 두 이름 중 한국어 세무 RAG 검색에 가장 명확하고 공식적인 이름 하나를 preferred_name으로 정해주십시오.

반드시 아래 JSON 형식으로만 답하십시오. 설명이나 마크다운 코드펜스(```) 없이 순수 JSON만 출력하십시오:
{{"is_duplicate": true 또는 false, "preferred_name": "대표이름"}}
"""
        try:
            resp = self.llm.complete(prompt)
            resp_text = resp.text if hasattr(resp, "text") else str(resp)
            resp_text = resp_text.strip()
            
            # JSON 파싱 정제
            resp_text = re.sub(r"```(?:json)?\s*", "", resp_text).strip()
            resp_text = resp_text.replace("```", "").strip()
            
            match = re.search(r"\{.*\}", resp_text, re.DOTALL)
            if not match:
                return False, ""
                
            data = json.loads(match.group())
            is_dup = bool(data.get("is_duplicate", False))
            pref_name = str(data.get("preferred_name", "")).strip()
            
            # 대표이름이 반드시 입력된 두 이름 중 하나인지 검증 및 강제 보정
            if is_dup:
                if pref_name not in (name_a, name_b):
                    pref_name = name_a # Fallback
                return True, pref_name
            return False, ""
        except Exception as exc:
            logger.error("LLM 판정 중 실패: %s", exc)
            return False, ""

    def _merge_nodes_neo4j(self, keep_node: dict, delete_node: dict) -> bool:
        """Python-driven 관계 이전 및 구 노드 DETACH DELETE 안전 병합 트랜잭션 수행."""
        name_keep = keep_node["name"]
        name_del = delete_node["name"]
        label = keep_node["label"]

        try:
            # 1. 구 노드(delete_node)에서 나가는 모든 관계(Outgoing Relation)를 찾아 신 노드로 복사
            out_cypher = f"""
            MATCH (del)-[r]->(neighbor)
            WHERE del.name = $name_del AND labels(del)[0] = $label AND labels(neighbor)[0] IS NOT NULL
            RETURN type(r) AS rel_type, properties(r) AS props, neighbor.name AS target_name, labels(neighbor)[0] AS target_label
            """
            out_relations = self.graph_store.structured_query(out_cypher, {"name_del": name_del, "label": label})
            
            for rel in out_relations:
                rel_type = rel["rel_type"]
                target_name = rel["target_name"]
                target_label = rel["target_label"]
                props = rel.get("props") or {}
                
                # 신 노드에 관계선 추가 생성
                create_out_cypher = f"""
                MATCH (keep), (target)
                WHERE keep.name = $name_keep AND labels(keep)[0] = $label 
                  AND target.name = $target_name AND labels(target)[0] = $target_label
                MERGE (keep)-[new_r:{rel_type}]->(target)
                ON CREATE SET new_r = $props
                """
                self.graph_store.structured_query(create_out_cypher, {
                    "name_keep": name_keep,
                    "label": label,
                    "target_name": target_name,
                    "target_label": target_label,
                    "props": props
                })

            # 2. 구 노드로 들어오는 모든 관계(Incoming Relation)를 찾아 신 노드로 복사
            in_cypher = f"""
            MATCH (neighbor)-[r]->(del)
            WHERE del.name = $name_del AND labels(del)[0] = $label AND labels(neighbor)[0] IS NOT NULL
            RETURN type(r) AS rel_type, properties(r) AS props, neighbor.name AS source_name, labels(neighbor)[0] AS source_label
            """
            in_relations = self.graph_store.structured_query(in_cypher, {"name_del": name_del, "label": label})
            
            for rel in in_relations:
                rel_type = rel["rel_type"]
                source_name = rel["source_name"]
                source_label = rel["source_label"]
                props = rel.get("props") or {}
                
                # 신 노드로 향하는 관계선 추가 생성
                create_in_cypher = f"""
                MATCH (source), (keep)
                WHERE source.name = $source_name AND labels(source)[0] = $source_label
                  AND keep.name = $name_keep AND labels(keep)[0] = $label
                MERGE (source)-[new_r:{rel_type}]->(keep)
                ON CREATE SET new_r = $props
                """
                self.graph_store.structured_query(create_in_cypher, {
                    "source_name": source_name,
                    "source_label": source_label,
                    "name_keep": name_keep,
                    "label": label,
                    "props": props
                })

            # 3. 구 노드 안전하게 DETACH DELETE 실행
            delete_cypher = f"""
            MATCH (del)
            WHERE del.name = $name_del AND labels(del)[0] = $label
            DETACH DELETE del
            """
            self.graph_store.structured_query(delete_cypher, {"name_del": name_del, "label": label})
            return True

        except Exception as exc:
            logger.error("노드 '%s' ➡️ '%s' 병합 Cypher 실행 실패: %s", name_del, name_keep, exc)
            return False


async def start_scheduler(interval_hours: float) -> None:
    """지정한 시간 주기마다 백그라운드에서 엔티티 정제를 무한히 자동 가동하는 데몬 루프."""
    interval_seconds = interval_hours * 3600.0
    logger.info("=== Graph Refiner 백그라운드 스케줄러 기동 완료 ===")
    logger.info("가동 주기: %.2f시간마다 (%.0f초)", interval_hours, interval_seconds)
    
    while True:
        try:
            refiner = EntityRefiner()
            refiner.run_resolution()
        except Exception as exc:
            logger.error("스케줄러 작업 실행 실패: %s", exc)
            
        logger.info("%.2f시간 후 다음 정제 세션을 개시합니다. 대기 모드...", interval_hours)
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Midas Touch Neo4j 지식 그래프 엔티티 정제(Resolution) 및 스케줄 데몬")
    parser.add_argument("--run-once", action="store_true", help="정제 로직을 1회 즉시 실행한 후 종료합니다.")
    parser.add_argument("--interval", type=float, default=24.0, help="백그라운드 스케줄러의 구동 주기(시간 기준, 기본: 24시간)")
    args = parser.parse_args()

    if args.run_once:
        logger.info("1회성 즉시 구동 모드 활성화.")
        try:
            refiner = EntityRefiner()
            refiner.run_resolution()
        except Exception as exc:
            logger.exception("정제 작업 도중 심각한 에러 발생: %s", exc)
            sys.exit(1)
    else:
        logger.info("주기적 백그라운드 데몬 모드 활성화.")
        try:
            asyncio.run(start_scheduler(args.interval))
        except (KeyboardInterrupt, SystemExit):
            logger.info("사용자에 의해 스케줄러 데몬이 중단되었습니다.")
        except Exception as exc:
            logger.exception("스케줄러 데몬 작동 중 예외 발생: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    main()
