"""표현 변형 사례 (src/input/script/virtual/build_variant_cases.py, tests/fixtures/virtual_charts/variants/):
저장된 파일이 사례 코드로 다시 만든 것과 같고, 날짜 표기만 바뀌었을 뿐 정답 값은 원래 사례와 같은지 본다.
"""
import json

import pytest

from src.input.script.evaluation import _strip
from src.input.script.virtual.build_variant_cases import VARIANTS, build
from src.input.script.virtual.virtual_chart import check, dumps, load_case, out_dir


@pytest.mark.parametrize("ref", list(VARIANTS))
def test_variant_matches_fixture_and_base_values(ref):
    chart, ps = build(ref)
    assert check(chart, ps) == []
    assert (out_dir(ref) / "chart.txt").read_text(encoding="utf-8") == chart
    assert (out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8") == dumps(ps)
    base_chart, base = load_case(VARIANTS[ref][0]).build()
    assert chart != base_chart                                       # 표기가 바뀌었고
    values = lambda f: _strip({k: v for k, v in f.items() if k != "genomic_reports"})    # noqa: E731 (보고서 원문은 표기째)
    assert values(ps["fields"]) == values(base["fields"])            # 값은 그대로


def test_saved_variant_is_valid():
    for ref in VARIANTS:
        chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
        ps = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        assert check(chart, ps) == []
