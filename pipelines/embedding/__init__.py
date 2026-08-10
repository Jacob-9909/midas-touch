"""
src/embedding_pipeline
----------------------
금융 문서 RAG용 임베딩 파인튜닝 데이터셋 생성 및 모델 학습 파이프라인.
"""

from .config import DEFAULT_CONFIG, PipelineConfig
from .dataset_builder import Triplet, TripletAssembler
from .document_parser import DocumentParser, Passage
from .hard_negative_miner import HardNegativeMiner, MiningResult
from .pipeline import EmbeddingDatasetPipeline
from .query_synthesizer import QuerySynthesizer, SyntheticQuery

__all__ = [
    "DEFAULT_CONFIG",
    "DocumentParser",
    "EmbeddingDatasetPipeline",
    "HardNegativeMiner",
    "MiningResult",
    "Passage",
    "PipelineConfig",
    "QuerySynthesizer",
    "SyntheticQuery",
    "Triplet",
    "TripletAssembler",
]
