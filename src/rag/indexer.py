# src/rag/indexer.py
import uuid
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, FilterSelector
from .client import get_qdrant_client, get_embedding_model, close_client, COLLECTION_NAME


def _clear_search_cache():
    """색인이 바뀌면 검색 결과 기억(searcher의 캐시)을 비운다. 같은 프로세스에서 색인 후 검색할 때 옛 결과가 나오지 않게."""
    from .searcher import clear_search_cache
    clear_search_cache()


def init_collection(force_recreate: bool = False):
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]

    # 주의: 컬렉션을 지우면 D의 급여 청크도 사라진다. 지침만 다시 넣을 때는 delete_guideline_chunks()를 쓴다.
    if COLLECTION_NAME in collections and force_recreate:
        client.delete_collection(collection_name=COLLECTION_NAME)
        print(f"[RAG] 기존 컬렉션 '{COLLECTION_NAME}' 초기화 완료.")
        _clear_search_cache()

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

    _clear_search_cache()
    print(f"[RAG Indexer] {total}개 청크 색인 완료.")


DOC_TYPES = ("guideline", "reimbursement")  # schemas/chunk.json의 doc_type


def delete_by_doc_type(doc_type: str):
    """doc_type이 같은 점만 지운다. 지침(C)과 급여(D)는 한 컬렉션을 같이 쓰므로,
    한쪽을 다시 색인할 때 다른 쪽 점은 남겨야 한다. D는 delete_by_doc_type("reimbursement")를 부른다."""
    if doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type은 {DOC_TYPES} 중 하나여야 합니다: {doc_type!r}")
    client = get_qdrant_client()
    if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
        return
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=FilterSelector(
            filter=Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))])
        ),
    )
    _clear_search_cache()
    print(f"[RAG] '{COLLECTION_NAME}'에서 doc_type={doc_type} 청크 삭제 완료.")


def delete_guideline_chunks():
    """지침 청크만 지운다 (delete_by_doc_type("guideline")과 같다)."""
    delete_by_doc_type("guideline")


def close_indexer():
    close_client()