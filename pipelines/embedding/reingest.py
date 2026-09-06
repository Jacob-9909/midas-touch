"""reingest.py

문서를 DocumentParser로 파싱하여 emb_passages 테이블에 재적재하고 bge-m3 임베딩을 즉시 계산하는 유틸리티.

사용:
    python -m pipelines.embedding.reingest <file_path>
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load env variables
load_dotenv(str(Path(__file__).resolve().parent.parent.parent / ".env"))

from backend.app.services.agent.tools._embedding import get_embedding_model
from pipelines.embedding.document_parser import DocumentParser
from shared.database.connector import bulk_upsert_emb_passages
from shared.database.repositories.connection import db_cursor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("reingest_doc")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m pipelines.embedding.reingest <file_path>")
        raise SystemExit(1)

    path = Path(sys.argv[1])
    parser = DocumentParser()
    passages = parser.parse_file(path)

    if not passages:
        logger.error("파싱된 단락이 없습니다: %s", path)
        raise SystemExit(1)

    rows = [
        {"passage_id": p.passage_id, "text": p.text, "source": p.source, "metadata": p.metadata}
        for p in passages
    ]
    count = bulk_upsert_emb_passages(rows)
    logger.info("emb_passages 재적재 완료: %d단락 (source=%s)", count, passages[0].source)

    logger.info("신규 단락 bge-m3 임베딩 연산 시작...")
    model = get_embedding_model()
    vectors = model.encode([p.text for p in passages]).tolist()
    with db_cursor() as (_, cur):
        cur.executemany(
            "UPDATE emb_passages SET embedding = %s::vector WHERE passage_id = %s",
            [(vec, p.passage_id) for p, vec in zip(passages, vectors)],
        )
    logger.info("신규 단락 %d건 임베딩 적재 완료", len(passages))


if __name__ == "__main__":
    main()
