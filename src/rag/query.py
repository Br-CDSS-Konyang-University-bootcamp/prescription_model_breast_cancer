# src/rag/query.py
# B의 biomarker_record(schemas/biomarker_record.json)로 지침 검색 질의와 검색 인자를 만든다.
# B의 추천 모듈은 이렇게 부르면 된다:
#     from src.rag import search_guidelines
#     from src.rag.query import search_args
#     results = search_guidelines(**search_args(record, metastatic_sites=["bone"], prior_subclasses=["AI_nonsteroidal"]))
# 질의 문장은 코드 값을 지침이 쓰는 영어 대표 표현(guideline_terms.csv의 preferred)으로 바꿔 이어 붙인다.
# 예: HR+/HER2-, metastatic, 2L, ESR1 positive → "ER-positive, HER2-negative MBC second-line ESR1-mutated"
from .guideline_terms import load_terms, query_terms

# 질의에 넣는 바이오마커 상태. 음성·미시행·VUS는 넣지 않는다 (질의가 "없다"는 권고로 끌려가지 않게)
QUERY_STATUSES = {"positive", "low", "ultralow"}

# 청크 biomarker_tags(= B의 rag_tags) → biomarker_record의 marker:status. 평가 문제집처럼 태그만 있을 때 쓴다
TAG_TO_MARKER = {
    "HER2-low": "HER2:low",
    "HER2-ultralow": "HER2:ultralow",
    "ER-low": "ER:low",
    "gBRCA": "gBRCA1:positive",
    "sBRCA": "sBRCA1:positive",
    "gPALB2": "PALB2:positive",
    "PIK3CA-mut": "PIK3CA:positive",
    "AKT1-mut": "AKT1:positive",
    "PTEN-alt": "PTEN:positive",
    "ESR1-mut": "ESR1:positive",
    "PD-L1+": "PD-L1:positive",
}


def profile_from_record(record: dict, metastatic_sites=None, prior_subclasses=None) -> dict:
    """biomarker_record → query_terms가 받는 프로필."""
    setting = record.get("setting") or {}
    markers = [f"{r['marker']}:{r['status']}" for r in record.get("records", []) if r.get("status") in QUERY_STATUSES]
    return {
        "subtype": record.get("subtype"),
        "disease": setting.get("disease"),
        "line": setting.get("line"),
        "markers": markers,
        "prior_subclasses": list(prior_subclasses or []),
        "metastatic_sites": _sites(metastatic_sites),
    }


def profile_from_tags(subtype, disease, line, biomarker_tags=(), metastatic_sites=None, prior_subclasses=None) -> dict:
    """태그로 프로필을 만든다 (평가 문제집용)."""
    return {
        "subtype": subtype,
        "disease": disease,
        "line": line,
        "markers": [TAG_TO_MARKER[t] for t in biomarker_tags if t in TAG_TO_MARKER],
        "prior_subclasses": list(prior_subclasses or []),
        "metastatic_sites": _sites(metastatic_sites),
    }


def build_query(profile: dict, terms: list[dict] = None) -> str:
    """프로필 → 질의 문장. 사전에 없는 값과 unknown은 빠진다."""
    return " ".join(query_terms(profile, terms or load_terms()))


def search_args(record: dict, metastatic_sites=None, prior_subclasses=None, **overrides) -> dict:
    """biomarker_record → search_guidelines(**인자). top_k, with_parent 등은 overrides로 넘긴다."""
    profile = profile_from_record(record, metastatic_sites, prior_subclasses)
    tags = []
    for r in record.get("records", []):
        if r.get("status") in QUERY_STATUSES:
            tags += [t for t in r.get("rag_tags", []) if t not in tags]
    setting = record.get("setting") or {}
    args = {
        "query_text": build_query(profile),
        "setting": setting.get("disease"),
        "subtype": record.get("subtype"),
        "line": setting.get("line"),
        "biomarker_tags": tags,
        "metastatic_sites": profile["metastatic_sites"] or None,
    }
    args.update(overrides)
    return args


def _sites(metastatic_sites) -> list:
    # patient_state의 metastatic_sites는 목록 또는 "[Not Available]" 같은 괄호 코드다
    return list(metastatic_sites) if isinstance(metastatic_sites, (list, tuple)) else []
