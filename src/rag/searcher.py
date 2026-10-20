# src/rag/searcher.py
from qdrant_client.models import Filter, FieldCondition, MatchValue
from .chunk_store import get_parent
from .client import get_qdrant_client, get_embedding_model, close_client, COLLECTION_NAME

LINE_MATCH_BONUS = 0.1  # 요청 차수와 청크 차수가 같을 때
LINE_ANY_BONUS = 0.03  # 청크 차수가 any일 때


def search_guidelines(
        query_text: str,
        setting: str = None,
        subtype: str = None,
        line: str = None,
        source: str = None,
        biomarker_tags: list[str] = None,
        top_k: int = 5,
        with_parent: bool = False,
) -> list[dict]:
    """지침 권고 청크를 찾는다. with_parent=True면 각 결과에 부모(소단원) 청크를 "parent" 키로 붙인다
    (LLM에는 소단원 전체를 함께 넘긴다, PROJECT.md §6)."""
    client = get_qdrant_client()
    model = get_embedding_model()

    must_conditions = []

    # 1. doc_type 하드 필터: 지침(guideline) 데이터만 검색 (D 파트 급여 데이터와 분리)
    must_conditions.append(FieldCondition(key="doc_type", match=MatchValue(value="guideline")))

    if source and source.lower() != "unknown":
        must_conditions.append(FieldCondition(key="source", match=MatchValue(value=source)))

    # 2. 하드 필터: setting은 정확히 일치 (chunk.json의 setting에는 any가 없다),
    #    subtype은 요청값과 일치하거나 청크 값이 "any"이면 통과
    if setting and setting.lower() != "unknown":
        must_conditions.append(FieldCondition(key="setting", match=MatchValue(value=setting)))

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

            # 차수가 정확히 일치하면 가점. any 청크는 수가 많아 같은 가점을 주면 차수로 순위를 가르지 못한다
            if line in chunk_lines:
                score += LINE_MATCH_BONUS
            elif "any" in chunk_lines:
                score += LINE_ANY_BONUS

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
    # score: 뜻 검색 점수 + 차수·태그 가점. 평가와 "근거 부족" 기준에 쓴다
    results = [{**item["data"], "score": round(item["score"], 4)} for item in scored_results[:top_k]]
    if with_parent:
        results = [{**r, "parent": get_parent(r)} for r in results]
    return results


def close_searcher():
    close_client()
