"""emb_passages.embedding 백필 — 문서 단락을 bge-m3로 임베딩해 doc_rag 검색을 가능하게 한다.

임베딩은 백엔드 에이전트와 **같은** 진입점(`tools._embedding`)을 쓴다. 로컬
SentenceTransformer(BAAI/bge-m3, 1024차원)라 API 레이트리밋이 없고 대량 처리가 공짜다.

`embedding IS NULL`인 단락만 처리하므로 재실행하면 이미 된 건 자동으로 건너뛴다.

사용:
    uv run python -m pipelines.embedding.backfill_passage_embeddings
    uv run python -m pipelines.embedding.backfill_passage_embeddings --batch-size 64
"""

from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

load_dotenv()

from backend.app.services.agent.tools._embedding import get_embedding_model
from shared.database.repositories.connection import db_cursor


def main() -> None:
    ap = argparse.ArgumentParser(description="emb_passages 임베딩 백필")
    ap.add_argument("--batch-size", type=int, default=32, help="한 번에 인코딩할 단락 수")
    args = ap.parse_args()

    with db_cursor() as (_, cur):
        cur.execute("SELECT COUNT(*) FROM emb_passages WHERE embedding IS NOT NULL")
        already = cur.fetchone()[0]
        cur.execute("SELECT passage_id, text FROM emb_passages WHERE embedding IS NULL ORDER BY passage_id")
        todo = cur.fetchall()

    print(f"이미 임베딩됨: {already}건 / 이번에 처리할 단락: {len(todo)}건")
    if not todo:
        print("백필할 단락이 없습니다.")
        return

    model = get_embedding_model()
    started = time.time()
    done = 0
    for i in range(0, len(todo), args.batch_size):
        batch = todo[i : i + args.batch_size]
        vectors = model.encode([t for _, t in batch]).tolist()
        # ponytail: 배치마다 커밋 — 중간에 죽어도 재실행하면 남은 것만 이어서 한다.
        with db_cursor() as (_, cur):
            cur.executemany(
                "UPDATE emb_passages SET embedding = %s::vector WHERE passage_id = %s",
                [(vec, pid) for (pid, _), vec in zip(batch, vectors)],
            )
        done += len(batch)
        elapsed = time.time() - started
        print(f"  {done}/{len(todo)} ({done / len(todo):.0%}) · {elapsed:.1f}s 경과", flush=True)

    with db_cursor() as (_, cur):
        cur.execute("SELECT COUNT(*) FROM emb_passages WHERE embedding IS NULL")
        remaining = cur.fetchone()[0]
    print(f"완료: {done}건 임베딩 · {time.time() - started:.1f}s · 남은 NULL {remaining}건")


if __name__ == "__main__":
    main()
