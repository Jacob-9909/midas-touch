"""
reingest_pdf.py
---------------
손상된 텍스트 레이어 PDF를 DocumentParser(비전 폴백 포함)로 재파싱하여
emb_passages 테이블에 재적재하는 일회성/재사용 유틸.

사용:
    python -m scripts.reingest_pdf data/raw_documents/주택과세금_2025.pdf
"""

import sys
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

from src.embedding_pipeline.config import DEFAULT_CONFIG
from src.embedding_pipeline.document_parser import DocumentParser
from src.db.connector import bulk_upsert_emb_passages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("reingest_pdf")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.reingest_pdf <pdf_path>")
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
