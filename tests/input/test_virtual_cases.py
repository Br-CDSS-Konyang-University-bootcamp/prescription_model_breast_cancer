"""가상 환자 사례 N01~N20 (src/input/script/build_virtual_cases.py, tests/fixtures/virtual_charts/VC-0110~VC-0129):
저장된 chart.txt·정답 patient_state·scenario.md가 사례 코드와 사례 목록 문서 §3으로 다시 만든 것과 같고,
스키마·인용 위치·차수 재계산 검사를 통과하는지 본다. 사례를 고치면 `python -m src.input.script.build_virtual_cases`로 다시 쓴다.
"""
import json

import pytest

from src.input.chart.virtual_chart import check, dumps
from src.input.script.build_virtual_cases import BUILDERS, OUT, cases_csv, read_sections, scenario

SECTIONS = read_sections()


@pytest.mark.parametrize("ref", list(BUILDERS))
def test_case_matches_fixture(ref):
    chart, ps = BUILDERS[ref][1]().build()
    assert ps["patient_ref"] == ref
    assert check(chart, ps) == []
    assert (OUT / ref / "chart.txt").read_text(encoding="utf-8") == chart
    assert (OUT / ref / "expected" / "patient_state.json").read_text(encoding="utf-8") == dumps(ps)
    assert (OUT / ref / "scenario.md").read_text(encoding="utf-8") == scenario(ref, SECTIONS[ref])


@pytest.mark.parametrize("ref", list(BUILDERS))
def test_saved_fixture_is_valid(ref):
    """다른 모듈이 읽는 저장 파일 자체도 검사를 통과한다."""
    chart = (OUT / ref / "chart.txt").read_text(encoding="utf-8")
    ps = json.loads((OUT / ref / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    assert check(chart, ps) == []


def test_cases_index_matches_document():
    assert [SECTIONS[r]["n"] for r in BUILDERS] == [n for n, _ in BUILDERS.values()]
    assert (OUT / "cases.csv").read_text(encoding="utf-8") == cases_csv(SECTIONS)
