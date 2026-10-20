# src/rag/indexer.py
import uuid
from qdrant_client.models import (Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, FilterSelector,
                                  HasIdCondition)
from .client import get_qdrant_client, get_embedding_model, close_client, COLLECTION_NAME


def _clear_search_cache():
    """색인이 바뀌면 검색 결과 기억(searcher의 캐시)을 비운다. 같은 프로세스에서 색인 후 검색할 때 옛 결과가 나오지 않게."""
    from .searcher import clear_search_cache
    clear_search_cache()


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


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
            point_id = _point_id(item["chunk_id"])
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


def replace_doc_type(doc_type: str, chunks: list[dict], batch_size: int = 32) -> dict:
    """doc_type 점을 chunks로 바꿔 끼운다: 새 청크를 먼저 넣고(같은 chunk_id는 덮어씀), 새 목록에 없는 옛 점만 지운다.
    delete_by_doc_type → index_chunks 순서는 넣다가 실패하면(모델 내려받기 실패 등) 그 종류의 점이 0개로 남는다.
    이 순서는 넣다가 실패하면 지우기까지 가지 않으므로 옛 점이 남아 검색이 계속된다 (D 안건 C1, 2026-10-20).
    → {"indexed": 넣은 수, "removed": 지운 옛 점 수}"""
    if doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type은 {DOC_TYPES} 중 하나여야 합니다: {doc_type!r}")
    if not chunks:
        # 빈 목록이면 그 종류를 전부 지우게 된다. 실수(파일을 못 읽음 등)일 때가 많아 막고, 정말 지우려면 delete_by_doc_type
        raise ValueError("넣을 청크가 없습니다. 전부 지우려면 delete_by_doc_type을 부르세요.")
    wrong = [c.get("chunk_id") for c in chunks if c.get("doc_type") != doc_type]
    if wrong:
        raise ValueError(f"doc_type이 {doc_type!r}이 아닌 청크: {wrong[:5]}")
    index_chunks(chunks, batch_size=batch_size)
    client = get_qdrant_client()
    flt = Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))],
                 must_not=[HasIdCondition(has_id=[_point_id(c["chunk_id"]) for c in chunks])])
    removed = client.count(collection_name=COLLECTION_NAME, count_filter=flt).count
    if removed:
        client.delete(collection_name=COLLECTION_NAME, points_selector=FilterSelector(filter=flt))
    _clear_search_cache()
    print(f"[RAG] doc_type={doc_type} 교체 완료: {len(chunks)}개 넣음, 옛 점 {removed}개 지움.")
    return {"indexed": len(chunks), "removed": removed}


def delete_guideline_chunks():
    """지침 청크만 지운다 (delete_by_doc_type("guideline")과 같다)."""
    delete_by_doc_type("guideline")


def close_indexer():
    close_client()