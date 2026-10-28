"""보류 세트 사례 N21~N35와 짝 G20·G21 (src/input/script/virtual/build_holdout_cases.py, tests/fixtures/virtual_charts/VC-0130~VC-0144 등):
저장된 chart.txt·정답 patient_state·scenario.md가 사례 코드와 사례 목록 문서 §3으로 다시 만든 것과 같고,
스키마·인용 위치·차수 재계산 검사를 통과하는지 본다. 사례를 고치면 `python -m src.input.script.virtual.build_holdout_cases`로 다시 쓴다.
"""
import json

import pytest

from src.input.script.virtual.virtual_chart import check, dumps
from src.input.script.virtual.build_holdout_cases import BUILDERS, INDEX, OUT, cases_csv, scenario, sections

SECTIONS = sections()


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
    assert INDEX.read_text(encoding="utf-8") == cases_csv(SECTIONS)


def test_pair_differs_from_base_only_where_intended():
    """짝 사례는 기본 사례에서 정한 값만 다르다."""
    from src.input.script.virtual.build_virtual_cases import vc_0111, vc_0115
    base, g20b = vc_0111().build()[1]["fields"], BUILDERS["VC-0111-g20b"][1]().build()[1]["fields"]
    assert [t["progression_day"] for t in base["treatment_history"]] == [None, 588]
    assert [t["progression_day"] for t in g20b["treatment_history"]] == [None, 590]
    base, g21 = vc_0115().build()[1]["fields"], BUILDERS["VC-0115-g21"][1]().build()[1]["fields"]
    assert base["molecular"]["germline"]["BRCA1"]["result"] == "not_detected"
    assert g21["molecular"]["germline"]["BRCA1"]["result"] == "detected"
