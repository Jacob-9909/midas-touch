"""reingest.py

손상된 텍스트 레이어 PDF를 DocumentParser(비전 폴백 포함)로 재파싱하여
emb_passages 테이블에 재적재하는 일회성/재사용 유틸리티.

사용:
    python -m pipelines.embedding.reingest <pdf_path>
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load env variables
load_dotenv(str(Path(__file__).resolve().parent.parent.parent / ".env"))

from pipelines.embedding.config import DEFAULT_CONFIG
from pipelines.embedding.document_parser import DocumentParser
from shared.database.connector import bulk_upsert_emb_passages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("reingest_pdf")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m pipelines.embedding.reingest <pdf_path>")
        raise SystemExit(1)

    path = Path(sys.argv[1])
    parser = DocumentParser(DEFAULT_CONFIG)
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


if __name__ == "__main__":
    main()
