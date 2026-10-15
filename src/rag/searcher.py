# src/rag/searcher.py
from qdrant_client.models import Filter, FieldCondition, MatchValue
from .client import get_qdrant_client, get_embedding_model, close_client, COLLECTION_NAME

def search_guidelines(
    query_text: str,
    setting: str = None,
    subtype: str = None,
    line: str = None,
    source: str = None,
    biomarker_tags: list[str] = None,
    top_k: int = 5
) -> list[dict]:
    client = get_qdrant_client()
    model = get_embedding_model()

    must_conditions = []
    if source:
        must_conditions.append(FieldCondition(key="source", match=MatchValue(value=source)))
    if setting:
        must_conditions.append(FieldCondition(key="setting", match=MatchValue(value=setting)))
    if subtype:
        must_conditions.append(FieldCondition(key="subtype", match=MatchValue(value=subtype)))
    if line:
        must_conditions.append(FieldCondition(key="line", match=MatchValue(value=line)))

    query_filter = Filter(must=must_conditions) if must_conditions else None
    query_vector = model.encode(query_text).tolist()

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k * 2
    )

    scored_results = []
    target_tags = set(biomarker_tags) if biomarker_tags else set()

    for hit in response.points:
        payload = hit.payload
        score = hit.score

        chunk_tags = set(payload.get("biomarker_tags", []))
        overlap = len(target_tags.intersection(chunk_tags))
        adjusted_score = score + (overlap * 0.05)

        scored_results.append({
            "score": adjusted_score,
            "version": payload.get("version", "0000-00"),
            "data": payload
        })

    scored_results.sort(key=lambda x: (x["score"], x["version"]), reverse=True)
    return [item["data"] for item in scored_results[:top_k]]

def close_searcher():
    close_client()