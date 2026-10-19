# tests/rag/test_guideline_terms.py
# 지침 표현 사전(data/dictionaries/guideline_terms.csv)의 형식과, 대표 표현이 실제 청크에 있는지 본다.
import csv
import json
from collections import Counter
from pathlib import Path

from src.rag.chunk_store import load_guideline_chunks, select_index_chunks
from src.rag.guideline_terms import coverage, load_terms, query_terms

BASE_DIR = Path(__file__).resolve().parents[2]
TERMS = load_terms()


def _enum(schema_file, *path):
    node = json.loads((BASE_DIR / "schemas" / schema_file).read_text(encoding="utf-8"))
    for key in path:
        node = node[key]
    return set(node["enum"])


def test_columns_and_no_duplicates():
    assert list(TERMS[0]) == ["field", "canonical", "expression", "lang", "source", "preferred", "note"]
    keys = Counter((t["field"], t["canonical"], t["expression"]) for t in TERMS)
    assert not [k for k, n in keys.items() if n > 1]
    assert all(t["source"] in ("esmo", "asco", "both") and t["preferred"] in ("", "1") for t in TERMS)


def test_exactly_one_preferred_expression_per_value():
    preferred = Counter((t["field"], t["canonical"]) for t in TERMS if t["preferred"] == "1")
    values = {(t["field"], t["canonical"]) for t in TERMS}
    assert {v: preferred[v] for v in values if preferred[v] != 1} == {}


def test_canonical_values_match_schemas_and_drug_dictionary():
    allowed = {
        "biomarker_record.subtype": _enum("biomarker_record.json", "properties", "subtype"),
        "biomarker_record.setting.disease": _enum("biomarker_record.json", "properties", "setting", "properties", "disease"),
        "biomarker_record.setting.line": _enum("biomarker_record.json", "properties", "setting", "properties", "line"),
    }
    markers = _enum("biomarker_record.json", "$defs", "record", "properties", "marker")
    statuses = _enum("biomarker_record.json", "$defs", "record", "properties", "status")
    with open(BASE_DIR / "data" / "dictionaries" / "drug_classes.csv", encoding="utf-8-sig", newline="") as f:
        drug_rows = list(csv.DictReader(f))
    allowed["treatment_history.drug_subclass"] = {r["drug_subclass"] for r in drug_rows if r["drug_subclass"]}
    allowed["treatment_history.drug_class"] = {r["drug_class"] for r in drug_rows}
    for t in TERMS:
        if t["field"] == "biomarker_record.records":
            marker, status = t["canonical"].split(":")
            assert marker in markers and status in statuses, t
        elif t["field"] in allowed:
            assert t["canonical"] in allowed[t["field"]], t


def test_preferred_expressions_appear_in_chunks():
    # 질의문에 쓰는 대표 표현이 지침 원문에 없으면 검색에 도움이 안 된다
    chunks = select_index_chunks(load_guideline_chunks())
    missing = [(t["field"], t["canonical"], t["expression"]) for t, n in coverage(chunks)
               if t["preferred"] == "1" and n == 0]
    assert not missing, missing


def test_query_terms_from_profile():
    profile = {"subtype": "HR+/HER2-", "disease": "metastatic", "line": "2L", "markers": ["ESR1:positive"],
               "prior_subclasses": ["AI_nonsteroidal", "CDK4/6_inhibitor"], "menopausal_status": "unknown"}
    assert query_terms(profile) == ["ER-positive, HER2-negative", "metastatic breast cancer", "second-line",
                                    "ESR1-mutated", "aromatase inhibitor", "CDK4/6 inhibitor"]
