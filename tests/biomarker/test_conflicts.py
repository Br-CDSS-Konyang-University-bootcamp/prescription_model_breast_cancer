# tests/biomarker/test_conflicts.py
# 값 충돌 (patient_state.conflicts[], A IN-5): 칸이 비고 후보가 둘 이상이면 후보마다 판정한다 (VC-0106b, 2026-11-03).
import json

from jsonschema import Draft202012Validator

from tests.biomarker.test_bm import ROOT, assess, check_shape


def cand(percent, doc):
    return {"status": "present", "value": {"percent": percent}, "raw": f"Ki-67 {percent}%", "specimen": "primary",
            "observed_date": "2022-09-14", "source": {"doc_id": doc, "quote": f"Ki-67 {percent}%"}}


def ps(*percents, field="proliferation.ki67_percent"):
    return {"patient_ref": "T", "fields": {},
            "conflicts": [{"field": field, "candidates": [cand(p, f"D{i}") for i, p in enumerate(percents, 1)],
                           "note": "테스트"}]}


def ki67(state):
    return next(r for r in assess(state)["records"] if r["marker"] == "Ki-67")


def test_conflict_split_is_unknown_with_both_values():
    r = ki67(ps(25, 15))
    assert r["status"] == "unknown" and r["rule_id"] == "BM2-KI67-CONFLICT"
    assert "25% (D1) -> positive" in r["reason"] and "15% (D2) -> negative" in r["reason"]
    assert check_shape(r) == []


def test_conflict_same_status_keeps_status():
    r = ki67(ps(30, 40))
    assert r["status"] == "positive" and r["rule_id"] == "BM2-KI67-CONFLICT-SAME" and "판정 같음" in r["reason"]


def test_no_conflict_or_other_field_stays_not_recorded():
    assert ki67({"patient_ref": "T", "fields": {}, "conflicts": []})["status"] == "not_recorded"
    assert ki67(ps(25, 15, field="receptors.er_percent"))["status"] == "not_recorded"


def test_vc0106b_record_passes_schema():
    state = json.loads((ROOT / "tests/fixtures/virtual_charts/VC-0106b/expected/patient_state.json").read_text("utf-8"))
    record = assess(state)
    schema = json.loads((ROOT / "schemas/biomarker_record.json").read_text("utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(record)) == []
    assert ki67(state)["status"] == "unknown"
