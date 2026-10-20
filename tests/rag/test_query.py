# tests/rag/test_query.py
# B의 biomarker_record로 검색 질의와 검색 인자를 만드는 함수(src/rag/query.py)를 본다
import json
from pathlib import Path

from src.rag.query import (TAG_TO_MARKER, build_query, negative_tags, profile_from_record, profile_from_tags,
                           search_args, site_search_args)

BASE_DIR = Path(__file__).resolve().parents[2]

RECORD = {
    "subtype": "HR+/HER2-",
    "setting": {"disease": "metastatic", "line": "2L"},
    "records": [
        {"marker": "ESR1", "status": "positive", "rag_tags": ["ESR1-mut"]},
        {"marker": "PIK3CA", "status": "negative", "rag_tags": ["PIK3CA-mut"]},
        {"marker": "HER2", "status": "low", "rag_tags": []},
        {"marker": "gBRCA1", "status": "vus", "rag_tags": ["gBRCA"]},
    ],
}


def test_search_args_from_biomarker_record():
    args = search_args(RECORD, metastatic_sites=["bone", "liver"], prior_subclasses=["AI_nonsteroidal"], top_k=3)
    assert args["query_text"] == "ER-positive, HER2-negative MBC second-line ESR1-mutated HER2-low bone metastases after AI"
    assert (args["setting"], args["subtype"], args["line"]) == ("metastatic", "HR+/HER2-", "2L")
    assert args["biomarker_tags"] == ["ESR1-mut"]  # 음성·VUS 레코드의 태그는 넣지 않는다
    assert args["metastatic_sites"] == ["bone", "liver"] and args["top_k"] == 3


def test_unknown_values_and_missing_sites_are_left_out():
    record = {"subtype": "unknown", "setting": {"disease": "early", "line": "unknown"}, "records": []}
    assert build_query(profile_from_record(record, metastatic_sites="[Not Available]")) == "EBC"
    assert search_args(record)["metastatic_sites"] is None


def test_tag_map_matches_chunk_tags_and_biomarker_schema():
    from src.rag.chunk_common import find_biomarker_tags  # noqa: F401  태그 이름의 출처
    schema = json.loads((BASE_DIR / "schemas" / "biomarker_record.json").read_text(encoding="utf-8"))
    markers = set(schema["$defs"]["record"]["properties"]["marker"]["enum"])
    statuses = set(schema["$defs"]["record"]["properties"]["status"]["enum"])
    chunk_tags = {t for path in (BASE_DIR / "data" / "chunks").glob("*.json")
                  for c in json.loads(path.read_text(encoding="utf-8")) for t in c["biomarker_tags"]}
    for tag, marker_status in TAG_TO_MARKER.items():
        marker, status = marker_status.split(":")
        assert marker in markers and status in statuses, tag
    assert chunk_tags - {"Ki-67-high"} <= set(TAG_TO_MARKER)  # 청크에 붙는 태그는 모두 질의로 바꿀 수 있다


def test_profile_from_tags_for_eval_cases():
    profile = profile_from_tags("TNBC", "metastatic", "1L", ["PD-L1+"], metastatic_sites=["brain"])
    assert build_query(profile) == "TNBC MBC first-line CPS ≥10 brain metastases"


def test_patient_context_separates_otherwise_identical_queries():
    # 같은 아형·병기·차수라도 폐경 상태, pCR, de novo, 이전 치료에 따라 권고가 갈린다
    early = {"subtype": "HR+/HER2-", "setting": {"disease": "early", "line": "adjuvant"}, "records": []}
    assert search_args(early, menopausal_status="premenopausal")["query_text"] == \
        "ER-positive, HER2-negative EBC adjuvant pre- and perimenopausal"
    tnbc = {"subtype": "TNBC", "setting": {"disease": "early", "line": "adjuvant"}, "records": []}
    assert search_args(tnbc, pcr="no")["query_text"] == "TNBC EBC adjuvant residual invasive disease"
    mbc = {"subtype": "HR+/HER2-", "setting": {"disease": "metastatic", "line": "1L"}, "records": []}
    assert search_args(mbc, stage_at_diagnosis="metastatic")["query_text"].endswith("de novo")
    assert "de novo" not in search_args(mbc, stage_at_diagnosis="early")["query_text"]  # 재발 전이
    her2 = {"subtype": "HR-/HER2+", "setting": {"disease": "metastatic", "line": ">=3L"}, "records": []}
    assert search_args(her2, prior_subclasses=["taxane"], prior_classes=["HER2-targeted Therapy"])["query_text"] == \
        "HER2-positive, ER-negative MBC third-line after taxane, HER2-directed therapy"


def test_site_search_args_one_search_per_known_site():
    args = site_search_args(RECORD, metastatic_sites=["bone", "liver", "brain"])
    assert [a["query_text"].split()[0] for a in args] == ["bone", "brain"]  # 간은 부위별 권고가 없다
    assert all(a["line"] is None and a["metastatic_sites"] == ["bone", "liver", "brain"] and a["top_k"] == 3
               for a in args)
    assert site_search_args(RECORD) == []


def test_negative_tags_need_every_marker_behind_the_tag_negative():
    record = {"records": [
        {"marker": "gBRCA1", "status": "negative"}, {"marker": "gBRCA2", "status": "vus"},  # VUS는 음성 처리
        {"marker": "PIK3CA", "status": "negative"}, {"marker": "AKT1", "status": "not_done"},
        {"marker": "PD-L1", "status": "unknown"}, {"marker": "HER2", "status": "negative"},
    ]}
    assert negative_tags(record) == ["gBRCA", "PIK3CA-mut", "HER2-low", "HER2-ultralow"]
    assert negative_tags({"records": [{"marker": "gBRCA1", "status": "negative"}]}) == []  # gBRCA2 모름
    assert search_args(RECORD)["negative_tags"] == ["PIK3CA-mut"]


def test_focused_query_drops_filtered_subtype_and_disease_but_keeps_stage_iii():
    early = {"subtype": "HR+/HER2-", "setting": {"disease": "early", "line": "adjuvant"}, "records": []}
    assert search_args(early, query_style="focused", menopausal_status="premenopausal")["query_text"] == \
        "adjuvant pre- and perimenopausal"
    la = {"subtype": "HR+/HER2-", "setting": {"disease": "locally_advanced", "line": "adjuvant"}, "records": []}
    assert search_args(la, query_style="focused")["query_text"] == "stage III adjuvant"
    assert search_args(RECORD, query_style="focused")["query_text"] == "second-line ESR1-mutated HER2-low"
