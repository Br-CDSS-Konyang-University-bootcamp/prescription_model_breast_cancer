# src/rag/searcher.py
import copy
import math
import warnings

from qdrant_client.models import Filter, FieldCondition, MatchValue
from .chunk_store import get_parent
from .client import get_qdrant_client, get_embedding_model, get_reranker, close_client, COLLECTION_NAME

LINE_MATCH_BONUS = 0.1  # 요청 차수와 청크 차수가 같을 때
LINE_ANY_BONUS = 0.03  # 청크 차수가 any일 때
TAG_BONUS = 0.05  # 요청 바이오마커 태그가 청크 태그와 하나 겹칠 때마다
RERANK_CANDIDATES = 20  # 재정렬할 때 뜻 검색으로 먼저 뽑는 후보 수
CACHE_SIZE = 256  # 같은 조건의 검색 결과를 기억해 두는 개수. 색인이 바뀌면 indexer가 비운다

_cache = {}
_reranker_failed = False  # 재정렬 모델을 못 불러왔으면 한 번만 경고하고 뜻 검색 점수로 대신한다


def search_guidelines(
        query_text: str,
        setting: str = None,
        subtype: str = None,
        line: str = None,
        source: str = None,
        biomarker_tags: list[str] = None,
        top_k: int = 5,
        with_parent: bool = False,
        rerank: bool = True,
) -> list[dict]:
    """지침 권고 청크를 찾는다. with_parent=True면 각 결과에 부모(소단원) 청크를 "parent" 키로 붙인다
    (LLM에는 소단원 전체를 함께 넘긴다, PROJECT.md §6).
    rerank=True(기본, PROJECT.md §6)면 뜻 검색으로 후보 RERANK_CANDIDATES개를 뽑은 뒤 재정렬 모델(bge-reranker-v2-m3)의
    점수로 순위를 다시 매긴다. 모델이 없거나 불러오지 못하면 경고하고 뜻 검색 점수를 쓴다.
    차수·태그 가점은 두 경우 모두 더한다. 결과의 score는 그 최종 점수다.
    같은 조건의 검색은 기억해 둔 결과를 돌려준다 (색인을 바꾸면 비워진다)."""
    key = (query_text, setting, subtype, line, source, tuple(biomarker_tags or ()), top_k, with_parent, rerank)
    if key not in _cache:
        if len(_cache) >= CACHE_SIZE:
            _cache.clear()
        _cache[key] = _search(query_text, setting, subtype, line, source, biomarker_tags, top_k, with_parent, rerank)
    return copy.deepcopy(_cache[key])  # 받은 쪽이 결과를 고쳐도 기억해 둔 값은 그대로


def clear_search_cache():
    _cache.clear()


def _search(query_text, setting, subtype, line, source, biomarker_tags, top_k, with_parent, rerank) -> list[dict]:
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
        limit=max(top_k * 3, RERANK_CANDIDATES) if rerank else top_k * 3
    )
    hits = response.points
    base_scores = [hit.score for hit in hits]
    if rerank and hits:
        base_scores = _rerank_scores(query_text, [hit.payload.get("text", "") for hit in hits]) or base_scores

    scored_results = []
    target_tags = set(biomarker_tags) if biomarker_tags else set()

    for hit, score in zip(hits, base_scores):
        payload = hit.payload

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
        score += overlap * TAG_BONUS

        scored_results.append({
            "score": score,
            "version": payload.get("version", "0000-00"),
            "data": payload
        })

    # 최종 점수로 내림차순 정렬
    scored_results.sort(key=lambda x: (x["score"], x["version"]), reverse=True)
    # score: 뜻 검색(또는 재정렬) 점수 + 차수·태그 가점. 평가와 "근거 부족" 기준에 쓴다
    results = [{**item["data"], "score": round(item["score"], 4)} for item in scored_results[:top_k]]
    if with_parent:
        results = [{**r, "parent": get_parent(r)} for r in results]
    return results


def _rerank_scores(query_text: str, texts: list[str]):
    """재정렬 모델 점수를 0~1로 맞춘다. 버전에 따라 0~1 확률 또는 원점수(logit)가 나오므로 범위를 보고 sigmoid를 씌운다.
    0~1로 맞춰야 뜻 검색 점수(코사인 유사도)에 맞춘 차수·태그 가점의 크기가 그대로 통한다.
    모델을 불러오지 못하면(미설치, 내려받기 실패) None을 돌려주고, 검색은 뜻 검색 점수로 계속한다."""
    global _reranker_failed
    if _reranker_failed:
        return None
    try:
        reranker = get_reranker()
    except Exception as e:  # sentence_transformers 미설치, 네트워크 차단, 모델 파일 손상 등
        _reranker_failed = True
        warnings.warn(f"재정렬 모델을 불러오지 못해 뜻 검색 점수만 씁니다: {e}")
        return None
    raw = [float(x) for x in reranker.predict([(query_text, t) for t in texts])]
    if all(0.0 <= x <= 1.0 for x in raw):
        return raw
    return [1 / (1 + math.exp(-x)) for x in raw]


def close_searcher():
    close_client()
