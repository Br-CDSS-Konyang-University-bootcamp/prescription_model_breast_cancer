# src/rag/indexer.py
import uuid
from qdrant_client.models import Distance, VectorParams, PointStruct
from .client import get_qdrant_client, get_embedding_model, close_client, COLLECTION_NAME


def init_collection(force_recreate: bool = False):
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in collections and force_recreate:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"[RAG] 기존 컬렉션 '{COLLECTION_NAME}' 초기화 완료.")

    if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"[RAG] 새 컬렉션 '{COLLECTION_NAME}' 생성 완료.")


def index_chunks(chunks: list[dict], batch_size: int = 32):
    client = get_qdrant_client()
    model = get_embedding_model()

    init_collection(force_recreate=False)
    total = len(chunks)
    print(f"[RAG Indexer] 총 {total}개 청크 색인 시작 (배치 크기: {batch_size})")

    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        texts = [item.get("text", "") for item in batch]
        vectors = model.encode(texts, show_progress_bar=False).tolist()

        points = []
        for item, vector in zip(batch, vectors):
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=item
                )
            )
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"[RAG Indexer] {total}개 청크 색인 완료.")


def close_indexer():
    close_client()