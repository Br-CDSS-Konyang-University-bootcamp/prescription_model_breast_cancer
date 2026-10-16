"""전이 후 차수 계산 (src/input/common/lines.py) 테스트.

실행 (team_project 폴더에서): python -m pytest tests/input/test_lines.py
"""
import json
from pathlib import Path

from src.input.common.lines import palliative_lines

ROOT = Path(__file__).resolve().parents[2]


def state(history, metastasis_day=100):
    rec = {"metastasis_day": {"status": "present", "value": metastasis_day}} if metastasis_day is not None else {}
    return {"fields": {"recurrence": rec, "treatment_history": history}}


def tx(drugs, start, end=None, stop=None, response=None, setting="metastatic"):
    return {"drugs": drugs, "setting": setting, "start_day": start, "end_day": end,
            "stop_reason": stop, "best_response": response}


def numbers(result):
    return [(r["drugs"], r["line"], r["endocrine_line"], r["chemo_line"]) for r in result["regimens"]]


def test_tcga_example_matches_handoff_8_1():
    """전달 문서 §8.1: fulvestrant 1L, tamoxifen 2L, liposomal doxorubicin 3L. 내분비 1·2차, 항암 1차. 골 보호제는 뺌."""
    ps = json.loads((ROOT / "src/input/examples/patient_state_metastatic_TCGA-A2-A0EW.json").read_text(encoding="utf-8"))
    r = palliative_lines(ps)
    assert numbers(r) == [(["fulvestrant"], 1, 1, None),
                          (["tamoxifen"], 2, 2, None),
                          (["liposomal doxorubicin"], 3, None, 1)]
    assert r["counts"] == {"line": 3, "endocrine": 2, "chemo": 1}


def test_adjuvant_before_metastasis_not_counted():
    r = palliative_lines(state([tx(["anastrozole"], 10, setting="adjuvant"), tx(["letrozole"], 120)]))
    assert numbers(r) == [(["letrozole"], 1, 1, None)]


def test_drugs_started_within_28_days_are_one_regimen():
    r = palliative_lines(state([tx(["letrozole"], 110, response="PD"), tx(["palbociclib"], 130)]))
    assert numbers(r) == [(["letrozole", "palbociclib"], 1, 1, None)]


def test_her2_targeted_plus_endocrine_counts_as_chemo():
    """공고 4.가.3: lapatinib + letrozole은 고식적 항암화학요법 표에 있다."""
    r = palliative_lines(state([tx(["lapatinib", "letrozole"], 110)]))
    assert numbers(r) == [(["lapatinib", "letrozole"], 1, None, 1)]


def test_planned_switch_stays_same_line():
    r = palliative_lines(state([tx(["doxorubicin", "cyclophosphamide"], 110, 170, stop="planned_switch"),
                                tx(["paclitaxel"], 180, 260, stop="progression"),
                                tx(["capecitabine"], 280)]))
    assert numbers(r) == [(["doxorubicin", "cyclophosphamide"], 1, None, 1),
                          (["paclitaxel"], 1, None, 1),
                          (["capecitabine"], 2, None, 2)]
    assert r["notes"] == []


def test_endocrine_and_chemo_counted_separately():
    r = palliative_lines(state([tx(["anastrozole"], 110, response="PD"),
                                tx(["paclitaxel"], 300, response="PD"),
                                tx(["fulvestrant", "palbociclib"], 500)]))
    assert numbers(r) == [(["anastrozole"], 1, 1, None),
                          (["paclitaxel"], 2, None, 1),
                          (["fulvestrant", "palbociclib"], 3, 2, None)]


def test_unknown_stop_reason_counts_as_next_line_with_note():
    r = palliative_lines(state([tx(["anastrozole"], 110), tx(["exemestane"], 400)]))
    assert [x["line"] for x in r["regimens"]] == [1, 2]
    assert len(r["notes"]) == 1


def test_supportive_and_bone_agents_not_counted():
    r = palliative_lines(state([tx(["zoledronic acid"], 105), tx(["denosumab"], 400), tx(["letrozole"], 410)]))
    assert numbers(r) == [(["letrozole"], 1, 1, None)]


def test_missing_start_day_is_dropped_with_note():
    r = palliative_lines(state([tx(["letrozole"], None)]))
    assert r["regimens"] == [] and len(r["notes"]) == 1


def test_no_metastasis_day():
    r = palliative_lines(state([tx(["letrozole"], 10)], metastasis_day=None))
    assert r["counts"] is None
