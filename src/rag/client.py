# src/rag/client.py
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

def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(path=str(DB_PATH))
    return _client

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-m3")
    return _model

def get_reranker() -> CrossEncoder:
    """질의와 권고를 한 쌍씩 읽어 맞는 정도를 매기는 재정렬 모델 (PROJECT.md §6)."""
    global _reranker
    if _reranker is None:
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