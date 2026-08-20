"""
src/embedding_pipeline
----------------------
금융 문서 RAG용 문서 파싱·청킹 유틸리티.
"""

from .config import DEFAULT_CONFIG, PipelineConfig
from .document_parser import DocumentParser, Passage

__all__ = [
    "DEFAULT_CONFIG",
    "DocumentParser",
    "Passage",
    "PipelineConfig",
]
