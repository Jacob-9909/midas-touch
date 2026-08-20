"""
pipelines/embedding
-------------------
금융 문서 RAG용 문서 파싱·청킹 유틸리티.
"""

from .document_parser import DocumentParser, Passage

__all__ = [
    "DocumentParser",
    "Passage",
]
