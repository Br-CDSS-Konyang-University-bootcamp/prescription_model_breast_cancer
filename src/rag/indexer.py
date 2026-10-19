# src/rag/indexer.py
import uuid
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, FilterSelector
from .client import get_qdrant_client, get_embedding_model, close_client, COLLECTION_NAME


def init_collection(force_recreate: bool = False):
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    # 주의: 컬렉션을 지우면 D의 급여 청크도 사라진다. 지침만 다시 넣을 때는 delete_guideline_chunks()를 쓴다.
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
            # chunk_id로 고정 ID(uuid5)를 만들어, 같은 청크를 다시 넣으면 덮어쓴다
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, item["chunk_id"]))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=item
                )
            )
        client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"[RAG Indexer] {total}개 청크 색인 완료.")


def delete_guideline_chunks():
    """doc_type=guideline인 점만 지운다. 지침을 다시 색인할 때 옛 청크가 남지 않게 하고, D의 급여 청크는 남긴다."""
    client = get_qdrant_client()
    if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
        return
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value="guideline"))])
        ),
    )
    print(f"[RAG] '{COLLECTION_NAME}'에서 지침 청크(doc_type=guideline) 삭제 완료.")


def close_indexer():
    close_client()