"""emb_passages 쓰레기 단락 정리 (PostgreSQL + Neo4j Chunk 동시).

주택 PDF의 텍스트 레이어가 깨져 있어 적재 단락의 상당수가 내용 없는 표 구분선(`-----`)이거나
base64 이미지 잔해(`+IV+o9H4hX...` 반복)다. 이런 단락은 RAG 검색에 잡히면 컨텍스트만 오염시키므로
제거한다.

**한글 비율로 자르지 않는다.** 실측 결과 세율표·계산식 단락은 한글 비율이 0.15~0.20로 낮지만
가장 쓸모 있는 내용이다(예: 장기보유특별공제율표, 기준금리 변동표). 대신 아래 두 가지
'내용 없음' 신호만 본다.

  1) 표 구분자/공백을 걷어낸 실질 문자가 20자 미만 → 구분선·빈 표 셀
  2) 한글이 하나도 없고 영숫자·`+/=`만으로 이루어짐 → base64 이미지 잔해

Neo4j `Chunk` 노드는 같은 emb_passages에서 빌드된 것이므로(`c.passage_id`) 동일 기준으로 함께
지운다. Chunk는 MENTIONS 관계만 갖고, 쓰레기 Chunk에는 엔티티가 붙지 않으므로 DETACH DELETE로
안전하다.

사용:
    uv run python -m pipelines.embedding.cleanup_passages          # dry-run (기본)
    uv run python -m pipelines.embedding.cleanup_passages --apply  # 실제 삭제
"""

from __future__ import annotations

import argparse
import re

from dotenv import load_dotenv

load_dotenv()

from shared.database.repositories.connection import db_cursor

_HANGUL = re.compile(r"[가-힣]")
_NOISE_CHARS = set("-|:+=~ \t\r\n_.*#")
_BASE64ISH = re.compile(r"[A-Za-z0-9+/=\s]+\Z")
# ponytail: 임계값 20자는 실측 샘플로 정한 상수. 새 문서를 넣다 오탐이 보이면 여기만 조정.
_MIN_CORE_CHARS = 20


def is_junk(text: str) -> bool:
    """내용이 없는 단락이면 True. (구분선·빈 표·base64 이미지 잔해)"""
    stripped = text.strip()
    core = "".join(ch for ch in stripped if ch not in _NOISE_CHARS)
    if len(core) < _MIN_CORE_CHARS:
        return True
    return not _HANGUL.search(stripped) and bool(_BASE64ISH.match(stripped))


def main() -> None:
    ap = argparse.ArgumentParser(description="emb_passages 쓰레기 단락 정리")
    ap.add_argument("--apply", action="store_true", help="실제 삭제 실행 (미지정 시 dry-run)")
    ap.add_argument("--samples", type=int, default=5, help="출력할 삭제 대상 샘플 수")
    args = ap.parse_args()

    with db_cursor() as (_, cur):
        cur.execute("SELECT passage_id, source, text FROM emb_passages ORDER BY passage_id")
        rows = cur.fetchall()

    junk = [(pid, src, txt) for pid, src, txt in rows if is_junk(txt)]
    junk_ids = [pid for pid, _, _ in junk]

    print(f"emb_passages 전체: {len(rows)}건")
    print(f"삭제 대상(쓰레기): {len(junk)}건 / 남는 단락: {len(rows) - len(junk)}건")
    by_source: dict[str, int] = {}
    for _, src, _ in junk:
        by_source[src] = by_source.get(src, 0) + 1
    for src, cnt in sorted(by_source.items()):
        print(f"  - {src}: {cnt}건 삭제")

    if not junk_ids:
        print("삭제할 단락이 없습니다.")
        return

    # 파인튜닝 파이프라인 제거(2026-08-20) 후 emb_synthetic_queries 는 더 이상 채워지지 않아
    # CASCADE 건수 조회를 뺐다. 테이블·FK 자체는 마이그레이션 이력 보존을 위해 스키마에 남아 있음.
    chunk_ids = _neo4j_junk_chunks(junk_ids)
    print(f"연동 삭제할 Neo4j Chunk: {len(chunk_ids)}건")

    print(f"\n--- 삭제 대상 샘플 {min(args.samples, len(junk))}건 ---")
    for pid, src, txt in junk[: args.samples]:
        print(f"[{pid}] ({src}) len={len(txt)}\n  {txt.strip()[:120]!r}")

    if not args.apply:
        print("\n[dry-run] 실제로 삭제하려면 --apply 를 붙여 다시 실행하십시오.")
        return

    with db_cursor() as (_, cur):
        cur.execute("DELETE FROM emb_passages WHERE passage_id = ANY(%s)", (junk_ids,))
        deleted = cur.rowcount
        cur.execute("SELECT COUNT(*) FROM emb_passages")
        remaining = cur.fetchone()[0]
    print(f"\nemb_passages 삭제 완료: {deleted}건 → 남은 단락 {remaining}건")

    if chunk_ids:
        _neo4j_delete_chunks(chunk_ids)
        print(f"Neo4j Chunk 삭제 완료: {len(chunk_ids)}건")


def _neo4j_junk_chunks(junk_ids: list[str]) -> list[str]:
    """삭제 대상 passage_id에 대응하는 Neo4j Chunk의 내부 id 목록."""
    from shared.database.neo4j_client import get_driver

    cypher = "MATCH (c:Chunk) WHERE c.passage_id IN $ids RETURN c.id AS id"
    with get_driver().session(database="neo4j") as session:
        return [r["id"] for r in session.run(cypher, ids=junk_ids)]


def _neo4j_delete_chunks(chunk_ids: list[str]) -> None:
    from shared.database.neo4j_client import get_driver

    cypher = "MATCH (c:Chunk) WHERE c.id IN $ids DETACH DELETE c"
    with get_driver().session(database="neo4j") as session:
        session.run(cypher, ids=chunk_ids).consume()


if __name__ == "__main__":
    main()
