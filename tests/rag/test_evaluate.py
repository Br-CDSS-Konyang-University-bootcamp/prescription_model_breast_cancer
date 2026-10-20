# tests/rag/test_evaluate.py
# 평가 문제집(data/eval/rag_eval_cases.csv)이 청크와 맞는지, 채점이 맞게 되는지 본다. 검색 모델 없이 돈다.
import csv
import json
from collections import Counter
from pathlib import Path

from src.rag.chunk_store import load_guideline_chunks, select_index_chunks
from src.rag.evaluate import doc_of, evaluate, load_cases, score_case

BASE_DIR = Path(__file__).resolve().parents[2]
CASES = load_cases()
CHUNKS = {c["chunk_id"]: c for c in load_guideline_chunks()}
INDEXED = {c["chunk_id"] for c in select_index_chunks(list(CHUNKS.values()))}
with open(BASE_DIR / "data" / "dictionaries" / "field_vocab.csv", encoding="utf-8-sig", newline="") as _f:
    SITES = {r["canonical"] for r in csv.DictReader(_f) if r["field"] == "metastatic_sites"}
with open(BASE_DIR / "data" / "dictionaries" / "drug_classes.csv", encoding="utf-8-sig", newline="") as _f:
    _drugs = list(csv.DictReader(_f))
DRUG_SUBCLASSES = {r["drug_subclass"] for r in _drugs if r["drug_subclass"]}
DRUG_CLASSES = {r["drug_class"] for r in _drugs}


def _enum(*path):
    node = json.loads((BASE_DIR / "schemas" / "biomarker_record.json").read_text(encoding="utf-8"))
    for key in path:
        node = node[key]
    return set(node["enum"])


def test_case_ids_unique_and_values_valid():
    assert not [cid for cid, n in Counter(c["case_id"] for c in CASES).items() if n > 1]
    settings = _enum("properties", "setting", "properties", "disease")
    subtypes = _enum("properties", "subtype")
    lines = _enum("properties", "setting", "properties", "line")
    for c in CASES:
        assert c["setting"] in settings and c["subtype"] in subtypes and c["line"] in lines, c["case_id"]
        assert c["status"] in ("draft", "reviewed"), c["case_id"]
        assert c["query"] and c["expected_chunks"] and c["expected_parents"], c["case_id"]
        # 전이 부위는 field_vocab.csv의 metastatic_sites 값 또는 "other: 자유 기재" (schemas/patient_state.json sites_value)
        assert all(s in SITES or s.startswith("other:") for s in c["metastatic_sites"]), c["case_id"]
        # 환자 정보 칸은 patient_state·약 사전 값이다 (비우면 모름)
        assert c["menopausal_status"] in ("", "premenopausal", "perimenopausal", "postmenopausal"), c["case_id"]
        assert c["pcr"] in ("", "yes", "no") and c["stage_at_diagnosis"] in ("", "early", "locally_advanced",
                                                                             "metastatic"), c["case_id"]
        assert set(c["prior_subclasses"]) <= DRUG_SUBCLASSES and set(c["prior_classes"]) <= DRUG_CLASSES, c["case_id"]


def test_expected_chunks_exist_and_are_reachable():
    # 정답 권고가 색인에 있고, 그 문항의 하드 필터(setting, subtype)를 통과해야 맞힐 수 있다
    for c in CASES:
        for cid in c["expected_chunks"]:
            chunk = CHUNKS.get(cid)
            assert chunk and cid in INDEXED, (c["case_id"], cid)
            assert doc_of(chunk) == c["expected_doc"], (c["case_id"], cid)
            assert chunk["parent_id"] in c["expected_parents"], (c["case_id"], cid)
            if c["setting"] != "unknown":
                assert c["setting"] in chunk["setting"], (c["case_id"], cid)
            if c["subtype"] != "unknown":
                assert c["subtype"] in chunk["subtype"] or "any" in chunk["subtype"], (c["case_id"], cid)


def _result(cid):
    return {**CHUNKS[cid], "score": 0.5}


def test_score_case_levels():
    case = next(c for c in CASES if c["case_id"] == "M04")
    right = case["expected_chunks"][0]
    same_section = "esmo-mbc-2026-05-luminal-2l-4bcee1"
    other_doc = "esmo-ebc-2024-02-hrpos-0656d9"

    perfect = score_case(case, [_result(right), _result(same_section)])
    assert (perfect["l0_doc"], perfect["l1_section"], perfect["l2_hit"], perfect["mrr"]) == (1, 1, 1, 1.0)

    second = score_case(case, [_result(same_section), _result(right)])
    assert second["mrr"] == 0.5 and second["l2_recall"] == 1.0

    section_only = score_case(case, [_result(same_section)])
    assert (section_only["l1_section"], section_only["l2_hit"], section_only["mrr"]) == (1, 0, 0.0)

    wrong = score_case(case, [_result(other_doc)])
    assert (wrong["l0_doc"], wrong["l1_section"], wrong["l2_hit"]) == (0, 0, 0)


def test_answer_outside_top_k_does_not_count():
    case = next(c for c in CASES if c["case_id"] == "M04")
    filler = [_result(cid) for cid in list(INDEXED - set(case["expected_chunks"]))[:5]]
    row = score_case(case, filler + [_result(case["expected_chunks"][0])], k=5)
    assert row["l2_hit"] == 0 and row["mrr"] == 0.0


def test_evaluate_summary_with_perfect_search():
    rows, summary = evaluate(CASES, lambda c: [_result(cid) for cid in c["expected_chunks"]])
    assert summary["cases"] == len(CASES)
    assert summary["l0_doc"] == summary["l1_section"] == summary["l2_hit"] == summary["mrr"] == 1.0
    assert all(r["seconds"] >= 0 for r in rows) and summary["avg_seconds"] >= 0
