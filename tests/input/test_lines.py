"""전이 후 차수 계산 (src/input/common/lines.py) 테스트.

실행 (team_project 폴더에서): python -m pytest tests/input/test_lines.py
"""
import json
from pathlib import Path

import pytest

from src.input.common.lines import annotate, at_index, deemed_lines, palliative_lines

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


def test_anthracycline_then_taxane_is_same_line():
    """§6.2 규칙 5a: 끝난 이유를 몰라도 AC 종료 28일 이내 taxane이면 같은 차수 (2026-10-20)."""
    r = palliative_lines(state([tx(["cyclophosphamide", "doxorubicin"], 110, 166), tx(["paclitaxel"], 167, 250),
                                tx(["capecitabine"], 300)]))
    assert numbers(r) == [(["cyclophosphamide", "doxorubicin"], 1, None, 1), (["paclitaxel"], 1, None, 1),
                          (["capecitabine"], 2, None, 2)]


def test_regimen_started_before_previous_ends_is_same_line():
    """§6.2 규칙 5a: 앞 요법이 끝나기 전에 시작하면 병용 추가 (capecitabine 중 bevacizumab)."""
    r = palliative_lines(state([tx(["capecitabine"], 110, 520), tx(["bevacizumab"], 140, 500)]))
    assert [x["line"] for x in r["regimens"]] == [1, 1]
    assert [x["chemo_line"] for x in r["regimens"]] == [1, 1]


def test_endocrine_maintenance_after_chemo_counts_endocrine_once():
    """§6.2 규칙 5b: 같은 차수 안에서 항암 → 내분비 유지면 내분비 차수만 처음 올린다."""
    r = palliative_lines(state([tx(["doxorubicin", "cyclophosphamide"], 110, 200, stop="maintenance"),
                                tx(["letrozole"], 210)]))
    assert numbers(r) == [(["doxorubicin", "cyclophosphamide"], 1, None, 1), (["letrozole"], 1, 1, None)]


def test_endocrine_after_chemo_without_progression_is_maintenance():
    """§6.2 규칙 5a: 항암 후 진행 기록 없이 내분비로 바뀌면 유지요법, 같은 차수 (2026-10-20)."""
    r = palliative_lines(state([tx(["doxorubicin", "cyclophosphamide"], 110, 200, response="SD"), tx(["letrozole"], 210)]))
    assert numbers(r) == [(["doxorubicin", "cyclophosphamide"], 1, None, 1), (["letrozole"], 1, 1, None)]


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


# ---------- 간주 규칙 (deemed_lines) ----------


def deem(history, metastasis_day=1000):
    return {d["rule_id"]: d for d in deemed_lines(state(history, metastasis_day))}


def test_tcga_example_deemed_rules():
    """보조 AC → paclitaxel, 보조 AI 3종 후 exemestane 투여 중(1,365일 종료) 1,353일에 원격 전이."""
    ps = json.loads((ROOT / "src/input/examples/patient_state_metastatic_TCGA-A2-A0EW.json").read_text(encoding="utf-8"))
    d = {x["rule_id"]: x for x in deemed_lines(ps)}
    assert (d["DEEM-ANTHRA-TAXANE"]["status"], d["DEEM-ANTHRA-TAXANE"]["regimen_refs"]) == ("met", [0, 2])
    assert (d["DEEM-SG-1Y"]["status"], d["DEEM-SG-1Y"]["gap_days"]) == ("met", -12)  # 음수 = 투여 중 전이
    assert d["DEEM-HER2ADC-6M"]["status"] == "not_met"
    assert (d["DEEM-ENDO-ADJ-1Y"]["status"], d["DEEM-ENDO-ADJ-1Y"]["gap_days"]) == ("met", -12)


def test_not_metastatic_all_not_applicable():
    assert {x["status"] for x in deemed_lines(state([tx(["letrozole"], 10)], metastasis_day=None))} == {"not_applicable"}


def test_anthracycline_without_taxane_not_met():
    d = deem([tx(["doxorubicin", "cyclophosphamide"], 30, 100, setting="adjuvant")])
    assert d["DEEM-ANTHRA-TAXANE"]["status"] == "not_met"
    assert "taxane" in d["DEEM-ANTHRA-TAXANE"]["basis"]


@pytest.mark.parametrize("end,expected,gap", [(900, "met", 100), (800, "not_met", 200)])
def test_her2_adc_six_months(end, expected, gap):
    d = deem([tx(["trastuzumab"], 300, end, setting="adjuvant")])
    assert (d["DEEM-HER2ADC-6M"]["status"], d["DEEM-HER2ADC-6M"]["gap_days"]) == (expected, gap)


def test_neoadjuvant_trastuzumab_not_counted_for_her2_adc():
    """공고 문구는 '수술후보조요법'만 인정한다."""
    assert deem([tx(["trastuzumab"], 300, 950, setting="neoadjuvant")])["DEEM-HER2ADC-6M"]["status"] == "not_met"


def test_missing_end_uses_start_as_lower_bound():
    assert deem([tx(["letrozole"], 700, None, setting="adjuvant")])["DEEM-ENDO-ADJ-1Y"]["status"] == "met"
    assert deem([tx(["letrozole"], 100, None, setting="adjuvant")])["DEEM-ENDO-ADJ-1Y"]["status"] == "unknown"


def test_supportive_only_adjuvant_is_not_a_regimen():
    assert deem([tx(["zoledronic acid"], 900, 950, setting="adjuvant")])["DEEM-SG-1Y"]["status"] == "not_met"


def test_annotate_fills_line_fields_and_rules():
    ps = state([tx(["anastrozole"], 50, 300, setting="adjuvant"), tx(["letrozole"], 120, response="PD"),
                tx(["paclitaxel"], 400)], metastasis_day=100)
    th = annotate(ps)["fields"]["treatment_history"]
    assert [(t["line"], t["endocrine_line"], t["chemo_line"]) for t in th] == [(None, None, None), (1, 1, None), (2, None, 1)]
    assert len(ps["fields"]["deemed_lines"]) == 4


# ---------- 판정 기준일 시점 값 (at_index) ----------


def indexed(history, index_day=1000, age=60):
    ps = state(history)
    ps["index_day"] = index_day
    ps["fields"]["patient"] = {"age": {"status": "present", "value": age}}
    return at_index(ps)


@pytest.mark.parametrize("history,status,gap", [
    ([tx(["letrozole"], 500, 980)], "yes", 20),                  # 20일 전 종료
    ([tx(["letrozole"], 500, 972)], "yes", 28),                  # 경계: 28일
    ([tx(["paclitaxel"], 500, 971)], "no", 29),                  # 29일 전 종료
    ([tx(["letrozole"], 500, 1100)], "yes", -100),               # 기준일에 투여 중
    ([tx(["letrozole"], 990, None)], "yes", 10),                 # 종료일 없음, 10일 전 시작
    ([tx(["letrozole"], 500, None)], "unknown", None),           # 투약 중인지 기록 없음인지 모름
    ([tx(["zoledronic acid"], 990, 995)], "no", None),           # 골 보호제는 세지 않음
    ([tx(["letrozole"], 1010, 1020)], "no", None),               # 기준일 뒤 시작은 세지 않음
    ([], "no", None),
])
def test_recent_therapy_28d(history, status, gap):
    r = indexed(history)["recent_therapy_28d"]
    assert (r["status"], r["gap_days"]) == (status, gap)


def test_recent_therapy_unknown_without_index_day():
    assert indexed([tx(["letrozole"], 500, 990)], index_day=None)["recent_therapy_28d"]["status"] == "unknown"


@pytest.mark.parametrize("index_day,age", [(0, 60), (365, 60), (366, 61), (3735, 70), (None, None)])
def test_age_at_index(index_day, age):
    assert indexed([], index_day=index_day)["age"] == age
