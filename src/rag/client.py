# src/rag/client.py
import os
from pathlib import Path
from qdrant_client import QdrantClient
from sentence_transformers import CrossEncoder, SentenceTransformer

# data/qdrant_db 절대 경로 설정
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "qdrant_db"
COLLECTION_NAME = "breast_cancer_guidelines"

# 단일 Qdrant 로컬 클라이언트 및 임베딩 모델 인스턴스
_client = None
_model = None
_reranker = None
RERANKER_NAME = "BAAI/bge-reranker-v2-m3"  # 처음 쓸 때 약 2GB를 내려받는다


def _set_cpu_threads():
    """PyTorch CPU 스레드를 실제 코어 수(논리 코어의 절반)로 맞춘다. 기본값은 논리 코어 전부라,
    하이퍼스레딩 PC에서는 스레드끼리 기다려 오히려 느리다 (2026-10-20 측정: 12개 3.7초, 6개 2.8초).
    환경 변수 RAG_TORCH_THREADS로 바꿀 수 있다."""
    import torch
    threads = int(os.environ.get("RAG_TORCH_THREADS") or max(1, (os.cpu_count() or 2) // 2))
    if torch.get_num_threads() != threads:
        torch.set_num_threads(threads)

def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=str(DB_PATH))
    return _client

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _set_cpu_threads()
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model

def get_reranker() -> CrossEncoder:
    """질의와 권고를 한 쌍씩 읽어 맞는 정도를 매기는 재정렬 모델 (PROJECT.md §6)."""
    global _reranker
    if _reranker is None:
        _set_cpu_threads()
        _reranker = CrossEncoder(RERANKER_NAME)
    return _reranker

def close_client():
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None