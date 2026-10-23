"""IN-3 정규화 (src/input/normalize.py): 가상 차트 30건 정답의 구절마다 정규화한 값이 정답 값과 같은지 본다.

후보에서 오는 칸(specimen, observed_date)과 4단계가 채우는 칸(progression_day, 차수, 표 첫 칸이 없을 때의 setting),
그리고 raw(원문 표기)는 비교에서 뺀다.
"""
import json

import pytest

from src.input.chart.cases.pairs import PAIRS
from src.input.chart.virtual_chart import CASES, out_dir
from src.input.classify import split
from src.input.normalize import Context, normalize
from src.input.quote import locate

ALL = CASES + [p.id for p in PAIRS]
FROM_CANDIDATE = {"source", "raw", "history", "superseded_reason", "specimen", "observed_date"}
LATER = {"progression_day", "line", "endocrine_line", "chemo_line"}


def _entries(x, path):
    """(칸 경로, source가 있는 정답 항목)."""
    if isinstance(x, dict):
        if isinstance(x.get("source"), dict):
            yield ".".join(path), x
        for k, v in x.items():
            if k != "source":
                yield from _entries(v, path if k == "history" else path + [k])
    elif isinstance(x, list):
        for v in x:
            yield from _entries(v, path)


def _cases():
    for ref in ALL:
        chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
        ps = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        yield ref, chart, ps


@pytest.mark.parametrize("ref,chart,ps", list(_cases()), ids=ALL)
def test_gold_quote_normalizes_to_expected_value(ref, chart, ps):
    docs = {d.doc_id: d for d in split(chart)}
    dx = ps["fields"]["diagnosis"]["diagnosis_date"].get("value")
    entries = list(_entries(ps["fields"], []))
    entries += [(c["field"], e) for c in ps["conflicts"] for e in c["candidates"]]
    bad = []
    for field, entry in entries:
        doc = docs[entry["source"]["doc_id"]]
        src = locate(entry["source"]["quote"], doc)
        got = normalize(field, src["quote"], Context.of(doc, src["char_start"], dx))
        want = {k: v for k, v in entry.items() if k not in FROM_CANDIDATE | LATER}
        if got is not None:
            got = {k: v for k, v in got.items() if k not in LATER and not (k == "setting" and v is None)}
            if "setting" not in got:
                want.pop("setting", None)
            got.pop("raw", None)
        if got != want:
            bad.append((field, src["quote"], got, want))
    assert bad == []


@pytest.mark.parametrize("quote,want", [
    ("PD-L1: 미시행", {"status": "not_done"}),
    ("PD-L1 22C3 의뢰함 (결과 대기)", {"status": "not_done", "raw": "결과 대기"}),
    ("PD-L1 검사 시행 예정", {"status": "not_done", "raw": "예정"}),
    ("PD-L1 SP263 TPS 5%", {"status": "present", "value": {"assay": "SP263", "score_type": "TPS", "score": 5}}),
    ("PD-L1 판독 불가", None),        # 정규화 실패 → 확인 요청
])
def test_not_done_and_failure(quote, want):
    doc = split("[병리결과보고서]\n" + quote + "\n")[0]
    assert normalize("receptors.pdl1", quote, Context(doc)) == want
