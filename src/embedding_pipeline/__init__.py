"""
src/embedding_pipeline
----------------------
금융 문서 RAG용 임베딩 파인튜닝 데이터셋 생성 및 모델 학습 파이프라인.
"""

from .config import PipelineConfig, DEFAULT_CONFIG
from .pipeline import EmbeddingDatasetPipeline
from .document_parser import DocumentParser, Passage
from .query_synthesizer import QuerySynthesizer, SyntheticQuery
from .hard_negative_miner import HardNegativeMiner, MiningResult
from .dataset_builder import TripletAssembler, Triplet

__all__ = [
    "PipelineConfig",
    "DEFAULT_CONFIG",
    "EmbeddingDatasetPipeline",
    "DocumentParser",
    "Passage",
    "QuerySynthesizer",
    "SyntheticQuery",
    "HardNegativeMiner",
    "MiningResult",
    "TripletAssembler",
    "Triplet",
]
