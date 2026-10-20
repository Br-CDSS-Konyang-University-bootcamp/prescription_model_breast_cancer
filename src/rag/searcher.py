# src/rag/searcher.py
import copy
import math
import warnings

from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue
from .chunk_store import get_parent
from .client import get_qdrant_client, get_embedding_model, get_reranker, close_client, COLLECTION_NAME

LINE_MATCH_BONUS = 0.1  # 요청 차수와 청크 차수가 같을 때
LINE_ANY_BONUS = 0.03  # 청크 차수가 any일 때
# 청크 차수가 요청과 명확히 다를 때 (예: 2차 환자에게 1차 권고). 빼지 않고 뒤로 보낸다.
# 재정렬 모델은 1차 권고 문장의 "ER-positive, HER2-negative … MBC"가 질의와 글자 그대로 겹치면 거의 만점(≈1.0)을 줘서,
# 차수 가점(+0.1)이나 -0.3 감점으로는 2·3차 질의에서도 1차 권고가 1위였다 (평가 --auto-query M10·M11, 2026-10-20).
# 점수 범위(약 0~1.2)보다 크게 깎아, 차수가 다른 권고는 맞는 차수·any 권고 뒤에만 온다 (맞는 권고가 모자라면 채워짐)
LINE_MISMATCH_PENALTY = 1.0
TAG_BONUS = 0.05  # 요청 바이오마커 태그가 청크 태그와 하나 겹칠 때마다
RERANK_CANDIDATES = 20  # 재정렬할 때 뜻 검색으로 먼저 뽑는 후보 수
SITE_MATCH_BONUS = 0.05  # 환자에게 있는 전이 부위의 부위별 권고
# 환자에게 없는 전이 부위의 부위별 권고. 차수 감점과 같은 이유로 점수 범위보다 크게 깎는다: 재정렬 점수가
# "HER2 양성 뇌 전이 2차 T-DXd" 권고에 0.97이라 -0.3으로는 일반 2차 권고(0.15)보다 계속 위였다 (--auto-query M10).
# 부위를 알면 그런 권고는 후보에서도 뺀다(_mismatched_site_parents). 감점은 그 목록 밖의 경우를 위한 안전장치
SITE_MISMATCH_PENALTY = 1.0
# 부위별 소단원(부모 청크 이름 끝) → 그 권고가 맞는 전이 부위 (field_vocab.csv의 metastatic_sites 값).
# 연수막 전이(LMD)는 표준값이 없어 "other: leptomeningeal ..."처럼 적힌 값을 찾는다. 뇌 전이만으로는 LMD로 보지 않는다.
# de novo IV기(site-denovo)와 소수 전이(site-omd)는 부위가 아닌 상황이라 여기 넣지 않는다.
SITE_SECTIONS = {
    "site-bone": {"bone"},
    "site-bm": {"brain"},
    "site-bm-lrt": {"brain"},
    "site-bm-her2": {"brain"},
    "site-bm-her2neg": {"brain"},
    "site-lmd": {"leptomeningeal"},
}
# 환자가 음성으로 확인된 바이오마커만을 조건으로 하는 권고 (예: gBRCA 음성 환자에게 gBRCA 변이용 olaparib).
# 권고 문장이 "adjuvant … HR-positive EBC"처럼 질의와 겹쳐 재정렬 점수가 높아도 맞지 않는다 (--auto-query E01·E02·E05)
NEGATIVE_MARKER_PENALTY = 1.0
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
        metastatic_sites: list[str] = None,
        negative_tags: list[str] = None,
) -> list[dict]:
    """지침 권고 청크를 찾는다. with_parent=True면 각 결과에 부모(소단원) 청크를 "parent" 키로 붙인다
    (LLM에는 소단원 전체를 함께 넘긴다, PROJECT.md §6).
    rerank=True(기본, PROJECT.md §6)면 뜻 검색으로 후보 RERANK_CANDIDATES개를 뽑은 뒤 재정렬 모델(bge-reranker-v2-m3)의
    점수로 순위를 다시 매긴다. 모델이 없거나 불러오지 못하면 경고하고 뜻 검색 점수를 쓴다.
    차수는 같으면 가점, 청크가 다른 차수만 가리키면 감점한다. 차수·태그 가점은 두 경우 모두 더한다. 결과의 score는 그 최종 점수다.
    metastatic_sites(예: ["bone", "liver"])를 주면 부위별 권고(뼈·뇌·연수막 전이)를 그 부위 전이가 있으면 가점,
    없으면 후보에서 뺀다. 주지 않거나 빈 목록이면 부위를 모르는 것으로 보고 점수를 바꾸지 않는다.
    negative_tags(예: ["gBRCA"])는 환자가 음성으로 확인된 바이오마커의 태그다. 권고의 바이오마커 태그가 모두 여기에
    들면 감점한다 (예: "PIK3CA, AKT1 or PTEN" 권고는 셋 다 음성일 때만). src/rag/query.py의 search_args가 만든다.
    같은 조건의 검색은 기억해 둔 결과를 돌려준다 (색인을 바꾸면 비워진다)."""
    sites = _site_keys(metastatic_sites)
    negatives = frozenset(negative_tags or ())
    key = (query_text, setting, subtype, line, source, tuple(biomarker_tags or ()), top_k, with_parent, rerank,
           tuple(sorted(sites)) if sites is not None else None, negatives)
    if key not in _cache:
        if len(_cache) >= CACHE_SIZE:
            _cache.clear()
        _cache[key] = _search(query_text, setting, subtype, line, source, biomarker_tags, top_k, with_parent, rerank,
                              sites, negatives)
    return copy.deepcopy(_cache[key])  # 받은 쪽이 결과를 고쳐도 기억해 둔 값은 그대로


def clear_search_cache():
    _cache.clear()


def _site_keys(metastatic_sites):
    """환자 전이 부위를 SITE_SECTIONS와 비교할 값으로 바꾼다. 모르면 None (점수를 바꾸지 않음)."""
    if not metastatic_sites or isinstance(metastatic_sites, str):  # "[Not Available]" 같은 값
        return None
    keys = set()
    for site in metastatic_sites:
        s = str(site).strip().lower()
        if "lepto" in s or "mening" in s or s.endswith("lmd"):
            keys.add("leptomeningeal")
        elif s:
            keys.add(s)
    return keys or None


def _mismatched_site_parents(sites) -> list[str]:
    """환자에게 없는 전이 부위의 부위별 소단원(부모 청크) ID 목록."""
    from .chunk_store import load_guideline_chunks
    out = []
    for chunk in load_guideline_chunks():
        pid = chunk["chunk_id"]
        for section, needed in SITE_SECTIONS.items():
            if pid.endswith("-" + section) and not needed & sites:
                out.append(pid)
    return out


def _site_adjust(parent_id, sites) -> float:
    if sites is None or not parent_id:
        return 0.0
    for section, needed in SITE_SECTIONS.items():
        if parent_id.endswith("-" + section):
            return SITE_MATCH_BONUS if needed & sites else -SITE_MISMATCH_PENALTY
    return 0.0


def _search(query_text, setting, subtype, line, source, biomarker_tags, top_k, with_parent, rerank,
            sites=None, negatives=frozenset()) -> list[dict]:
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
    # 환자 전이 부위를 알면, 없는 부위의 부위별 권고는 후보에서 뺀다. 감점(-1.0)은 뽑힌 후보 안에서만 순위를 바꾸므로,
    # 그런 권고가 후보 자리를 채우면 맞는 권고가 후보에 못 들어간다 (retrieve 연결 확인, 2026-10-20)
    must_not = [FieldCondition(key="parent_id", match=MatchAny(any=_mismatched_site_parents(sites)))] \
        if sites is not None and _mismatched_site_parents(sites) else []
    query_filter = Filter(must=must_conditions, must_not=must_not) if must_conditions or must_not else None

    # Qdrant 검색 실행 (가점 부여를 위해 top_k보다 여유 있게 검색)
    limit = max(top_k * 3, RERANK_CANDIDATES) if rerank else top_k * 3
    hits = []
    if line and line.lower() != "unknown":
        # 후보의 절반은 차수가 맞거나 any인 권고에서 먼저 뽑는다. 가점·감점은 뽑힌 후보 안에서만 순위를 바꾸므로,
        # 질의가 다른 차수 권고와 글자가 많이 겹치면 맞는 차수 권고가 후보에 아예 못 들어갔다 (--auto-query M10·M11)
        line_filter = Filter(must=must_conditions + [FieldCondition(key="line", match=MatchAny(any=[line, "any"]))],
                             must_not=must_not)
        hits = client.query_points(collection_name=COLLECTION_NAME, query=query_vector, query_filter=line_filter,
                                   limit=limit // 2).points
    seen = {hit.id for hit in hits}
    for hit in client.query_points(collection_name=COLLECTION_NAME, query=query_vector, query_filter=query_filter,
                                   limit=limit).points:
        if len(hits) >= limit:
            break
        if hit.id not in seen:
            hits.append(hit)
            seen.add(hit.id)
    base_scores = [hit.score for hit in hits]
    if rerank and hits:
        base_scores = _rerank_scores(query_text, [hit.payload.get("text", "") for hit in hits]) or base_scores

    scored_results = []
    target_tags = set(biomarker_tags) if biomarker_tags else set()

    for hit, score in zip(hits, base_scores):
        payload = hit.payload

        # 3. line(치료 차수)은 거르지 않고 점수로 반영한다 (같으면 가점, 다른 차수면 감점)
        if line and line.lower() != "unknown":
            chunk_lines = payload.get("line", [])
            if isinstance(chunk_lines, str):
                chunk_lines = [chunk_lines]

            # 차수가 정확히 일치하면 가점. any 청크는 수가 많아 같은 가점을 주면 차수로 순위를 가르지 못한다
            if line in chunk_lines:
                score += LINE_MATCH_BONUS
            elif "any" in chunk_lines:
                score += LINE_ANY_BONUS
            elif chunk_lines:
                score -= LINE_MISMATCH_PENALTY

        # 바이오마커 태그 중복도에 따른 가점
        chunk_tags = set(payload.get("biomarker_tags", []))
        overlap = len(target_tags.intersection(chunk_tags))
        score += overlap * TAG_BONUS

        # 전이 부위: 부위별 소단원 권고만 해당
        score += _site_adjust(payload.get("parent_id"), sites)

        # 음성 바이오마커: 권고가 조건으로 삼는 태그가 모두 환자에게 음성이면 감점
        if negatives and chunk_tags and chunk_tags <= negatives:
            score -= NEGATIVE_MARKER_PENALTY

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
