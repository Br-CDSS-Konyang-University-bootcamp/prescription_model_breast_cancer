"""정답에서 만든 후보 목록 (src/input/candidates.py): 정답의 근거가 빠짐없이 후보가 되고,
구절만으로(문서 안 첫 위치) 정답 위치를 다시 찾을 수 있는지 본다. LLM 후보도 같은 방식으로 위치를 찾는다.
"""
import json

import pytest

from src.input.candidates import KEYS, from_expected
from src.input.chart.cases.pairs import PAIRS
from src.input.chart.virtual_chart import CASES, DOC_GAP, out_dir

ALL = CASES + [p.id for p in PAIRS]


def _load(ref):
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    ps = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    return chart, ps


def _sources(x):
    if isinstance(x, dict):
        if isinstance(x.get("source"), dict):
            yield x["source"]
        for k, v in x.items():
            if k != "source":
                yield from _sources(v)
    elif isinstance(x, list):
        for v in x:
            yield from _sources(v)


@pytest.mark.parametrize("ref", ALL)
def test_every_source_becomes_candidate(ref):
    _, ps = _load(ref)
    cands = from_expected(ps)
    assert all(tuple(c) == KEYS for c in cands)
    got = sorted((c["doc_id"], c["quote"]) for c in cands)
    want = sorted((s["doc_id"], s["quote"]) for s in _sources([ps["fields"], ps.get("conflicts", [])]))
    assert got == want


@pytest.mark.parametrize("ref", ALL)
def test_quote_alone_finds_expected_position(ref):
    """문서 안에서 구절이 처음 나오는 곳 = 정답 위치. 어긋나면 구절만으로는 위치를 정할 수 없는 후보다."""
    chart, ps = _load(ref)
    starts, pos = {}, 0
    for d, text in zip(ps["documents"], chart.rstrip("\n").split(DOC_GAP)):
        starts[d["doc_id"]] = (pos, text)
        pos += len(text) + len(DOC_GAP)
    want = {(s["doc_id"], s["quote"]): s["char_start"] for s in _sources([ps["fields"], ps.get("conflicts", [])])}
    bad = []
    for (doc_id, quote), start in want.items():
        base, text = starts[doc_id]
        if base + text.find(quote) != start:
            bad.append((doc_id, quote))
    assert bad == []
