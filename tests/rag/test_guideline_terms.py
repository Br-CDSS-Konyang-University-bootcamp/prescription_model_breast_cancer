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


def _enum_in(schema_file, *path):
    """path 끝의 필드에서 value enum을 찾는다 (patient_state의 allOf 구조)."""
    node = json.loads((BASE_DIR / "schemas" / schema_file).read_text(encoding="utf-8"))
    for key in path:
        node = node[key]
    for part in node["allOf"]:
        value = part.get("properties", {}).get("value", {})
        if "enum" in value:
            return set(value["enum"])
    raise KeyError(path)


def test_columns_and_no_duplicates():
    assert list(TERMS[0]) == ["field", "canonical", "expression", "lang", "source", "preferred", "note"]
    keys = Counter((t["field"], t["canonical"], t["expression"]) for t in TERMS)
    assert not [k for k, n in keys.items() if n > 1]
    assert all(t["source"] == "esmo" and t["preferred"] in ("", "1") for t in TERMS)


def test_exactly_one_preferred_expression_per_value():
    preferred = Counter((t["field"], t["canonical"]) for t in TERMS if t["preferred"] == "1")
    values = {(t["field"], t["canonical"]) for t in TERMS}
    assert {v: preferred[v] for v in values if preferred[v] != 1} == {}


def test_canonical_values_match_schemas_and_drug_dictionary():
    # canonical은 B의 biomarker_record 값(과 A의 patient_state 값, 약 사전 값)으로 고정한다. C가 새 값을 만들지 않는다
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
    fields = ("properties", "fields", "properties")
    for field in ("patient.menopausal_status", "patient.gender", "neoadjuvant_response.pcr", "stage.disease_extent"):
        group, name = field.split(".")
        allowed[field] = _enum_in("patient_state.json", *fields, group, "properties", name)
    confirmed = json.loads((BASE_DIR / "schemas" / "confirmed_state.json").read_text(encoding="utf-8"))
    relapse = confirmed["$defs"]["items"]["properties"]["endocrine_relapse_12m"]["allOf"][1]["properties"]["confirmed"]
    allowed["confirmed_state.endocrine_relapse_12m"] = set(relapse["enum"])
    with open(BASE_DIR / "data" / "dictionaries" / "field_vocab.csv", encoding="utf-8-sig", newline="") as f:
        allowed["metastatic_sites"] = {r["canonical"] for r in csv.DictReader(f) if r["field"] == "metastatic_sites"}
    for t in TERMS:
        if t["field"] == "biomarker_record.records":
            marker, status = t["canonical"].split(":")
            assert marker in markers and status in statuses, t
        else:
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
    assert query_terms(profile) == ["ER-positive, HER2-negative", "MBC", "second-line",
                                    "ESR1-mutated", "AI", "CDK4/6 inhibitor"]
