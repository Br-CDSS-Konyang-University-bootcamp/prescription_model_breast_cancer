"""크롭본 CSV ↔ patient_state 대조 (src/input/script/tcga/verify_tcga_conversion.py) 테스트.

실행 (team_project 폴더에서): python -m pytest tests/input/test_verify_conversion.py
"""
import copy

import pytest

from src.input.script.tcga import verify_tcga_conversion as V
from src.input.script.tcga.tcga_to_patient_state import convert, load_rows


@pytest.fixture(scope="module")
def rows():
    return load_rows()


@pytest.fixture(scope="module")
def states(rows):
    return convert(rows)


def test_every_patient_matches_csv(rows, states):
    assert set(states) == set(rows.patient_id)
    bad = {r.patient_id: d for _, r in rows.iterrows() if (d := V.check(r, states[r.patient_id]))}
    assert bad == {}


def test_check_finds_changed_values(rows, states):
    r = rows.set_index("patient_id", drop=False).loc["TCGA-A2-A0EW"]
    d = copy.deepcopy(states["TCGA-A2-A0EW"])
    d["fields"]["patient"]["age"]["value"] = 99
    d["fields"]["treatment_history"].pop()
    d["fields"]["receptors"]["er_percent"]["value"]["range"] = [50, 59]
    assert {"age", "er.range", "treatment_history (약·시작·종료·기록 주기·반응)"} <= set(V.check(r, d))


def test_every_csv_column_is_accounted_for(rows):
    assert [c for c, why in V.coverage(rows, V.CHECKED_COLS) if why.startswith("확인 필요")] == []
