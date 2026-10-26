"""patient_state <-> 고정 형식 차트 원문 (src/input/script/tcga/fixed_chart.py) 테스트.

실행 (team_project 폴더에서): python -m pytest tests/input/test_fixed_chart.py
"""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from src.input.script.tcga import fixed_chart as F
from src.input.script.tcga.tcga_to_patient_state import convert, load_rows

SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "patient_state.json"


@pytest.fixture(scope="module")
def states():
    return convert(load_rows())


def test_every_tcga_patient_round_trips(states):
    """838명 모두: 차트로 썼다 다시 읽으면 같은 값, 스키마 통과, 인용 위치가 원문과 같음."""
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    bad = {}
    for pid, ps in states.items():
        text, back, diffs = F.round_trip(ps)
        diffs += [f"스키마: {e.message}" for e in validator.iter_errors(back)]
        diffs += [f"인용 위치: {p}" for p in F.quote_errors(text, back)]
        if diffs:
            bad[pid] = diffs[:3]
    assert bad == {}


def test_render_is_fixed_format(states):
    text = F.render(states["TCGA-A2-A0EW"])
    assert text.splitlines()[0] == "[병리결과보고서]"
    assert "ER: 양성, 구간 90-99%" in text           # 구간은 값 그대로
    assert "PR: 양성, 구간 10-19%" in text
    assert F.TABLE_HEADER in text
    assert F.render(states["TCGA-A2-A0EW"]) == text  # 같은 입력 → 같은 원문


def test_parse_fills_source(states):
    text = F.render(states["TCGA-A2-A0EW"])
    back = F.parse(text)
    er = back["fields"]["receptors"]["er_percent"]
    assert er["source"]["doc_id"] == "D1" and er["source"]["quote"] == "양성, 구간 90-99%"
    assert [d["doc_type"] for d in back["documents"]] == ["pathology", "molecular", "progress_note", "medication"]


def test_round_trip_finds_changed_value(states):
    ps = states["TCGA-A2-A0EW"]
    back = F.parse(F.render(ps))
    back["fields"]["receptors"]["er_percent"]["value"]["range"] = [80, 89]
    assert F.differences(F.comparable(ps), F.comparable(back)) == \
        [".fields.receptors.er_percent.value.range[0]: 90 != 80", ".fields.receptors.er_percent.value.range[1]: 99 != 89"]


def test_render_stops_on_values_it_cannot_hold(states):
    ps = copy.deepcopy(states["TCGA-A2-A0EW"])
    ps["fields"]["receptors"]["er_percent"]["observed_date"] = "2021-03-23"
    with pytest.raises(F.Unsupported):
        F.render(ps)
    ps = copy.deepcopy(states["TCGA-A2-A0EW"])
    ps["fields"]["treatment_history"][0]["start_date"] = "2021-04-14"
    with pytest.raises(F.Unsupported):
        F.render(ps)
