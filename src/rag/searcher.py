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

    # 1. doc_type 하드 필터: 지침(guideline) 데이터만 검색 (D 파트 급여 데이터와 분리)
    must_conditions.append(FieldCondition(key="doc_type", match=MatchValue(value="guideline")))

    if source and source.lower() != "unknown":
        must_conditions.append(FieldCondition(key="source", match=MatchValue(value=source)))

    # 2. 하드 필터 유연화: 요청값과 일치하거나, 청크의 값이 "any"인 경우 모두 통과
    if setting and setting.lower() != "unknown":
        must_conditions.append(
            Filter(
                should=[
                    FieldCondition(key="setting", match=MatchValue(value=setting)),
                    FieldCondition(key="setting", match=MatchValue(value="any"))
                ]
            )
        )

    if subtype and subtype.lower() != "unknown":
        must_conditions.append(
            Filter(
                should=[
                    FieldCondition(key="subtype", match=MatchValue(value=subtype)),
                    FieldCondition(key="subtype", match=MatchValue(value="any"))
                ]
            )
        )

    # 쿼리 벡터 변환
    query_vector = model.encode(query_text).tolist()
    query_filter = Filter(must=must_conditions) if must_conditions else None

    # Qdrant 검색 실행 (가점 부여를 위해 top_k보다 여유 있게 검색)
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k * 3
    )

    scored_results = []
    target_tags = set(biomarker_tags) if biomarker_tags else set()

    for hit in response.points:
        payload = hit.payload
        score = hit.score

        # 3. line(치료 차수)을 하드 필터에서 소프트 조건(가점)으로 변경
        if line and line.lower() != "unknown":
            chunk_lines = payload.get("line", [])
            if isinstance(chunk_lines, str):
                chunk_lines = [chunk_lines]

            # 차수가 일치하거나 "any"인 경우 가점
            if line in chunk_lines or "any" in chunk_lines:
                score += 0.1

        # 바이오마커 태그 중복도에 따른 가점
        chunk_tags = set(payload.get("biomarker_tags", []))
        overlap = len(target_tags.intersection(chunk_tags))
        score += (overlap * 0.05)

        scored_results.append({
            "score": score,
            "version": payload.get("version", "0000-00"),
            "data": payload
        })

    # 최종 점수로 내림차순 정렬
    scored_results.sort(key=lambda x: (x["score"], x["version"]), reverse=True)
    return [item["data"] for item in scored_results[:top_k]]


def close_searcher():
    close_client()