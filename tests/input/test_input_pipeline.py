"""입력 모듈 끝까지 (src/input/pipeline.py): IN-2 자리에 정답에서 만든 후보를 넣으면 정답 patient_state가 나온다.
이것이 통과하면 규칙 쪽(문서 나누기·인용 확인·정규화·조립)이 완성된 것이고, LLM을 붙여 달라진 곳은 LLM 오류다.
raw(원문 표기)와 충돌 설명(note)은 사례 코드가 손으로 쓴 글이라 비교에서 뺀다.
"""
import json

import pytest

from src.input.candidates import from_expected
from src.input.chart.cases.pairs import PAIRS
from src.input.chart.virtual_chart import CASES, out_dir
from src.input.pipeline import run

ALL = CASES + [p.id for p in PAIRS]


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in ("raw", "note")}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in a.keys() | b.keys() for d in _diff(a.get(k), b.get(k), f"{path}.{k}")]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _diff(x, y, f"{path}[{i}]")]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


@pytest.mark.parametrize("ref", ALL)
def test_gold_candidates_reproduce_expected(ref):
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    got, issues = run(chart, lambda docs: from_expected(want), patient_ref=ref, created_at=want["created_at"])
    assert issues == []
    assert _diff(_strip(got), _strip(want)) == []
