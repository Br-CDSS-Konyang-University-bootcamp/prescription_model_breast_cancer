"""IN-1 문서 나누기 (src/input/script/pipeline/classify.py)와 인용 확인 (src/input/script/pipeline/quote.py)을 가상 차트 30건 정답으로 본다."""
import json

import pytest

from src.input.script.evaluation.candidates import from_expected
from src.input.script.virtual.cases.pairs import PAIRS
from src.input.script.virtual.virtual_chart import CASES, out_dir
from src.input.script.pipeline.classify import classify, split
from src.input.script.pipeline.quote import locate

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
def test_split_matches_expected_documents(ref):
    chart, ps = _load(ref)
    docs = split(chart)
    assert [d.entry() for d in docs] == ps["documents"]
    for d in docs:
        assert chart[d.start:d.end] == d.text


@pytest.mark.parametrize("ref", ALL)
def test_gold_quotes_locate_to_expected_source(ref):
    chart, ps = _load(ref)
    docs = {d.doc_id: d for d in split(chart)}
    got = sorted(tuple(locate(c["quote"], docs[c["doc_id"]]).values()) for c in from_expected(ps))
    want = sorted(tuple(s.values()) for s in _sources([ps["fields"], ps.get("conflicts", [])]))
    assert got == want


@pytest.mark.parametrize("header,doc_type", [
    ("[병리결과보고서]  (가상의원 사본)", "pathology"), ("SURGICAL PATHOLOGY REPORT", "pathology"),
    ("[분자병리 검사 결과]", "molecular"), ("[NGS 보고서]", "molecular"), ("<항암 처방 이력>", "medication"),
    ("BONE SCAN REPORT", "radiology"), ("[PET-CT 판독지]", "radiology"), ("[수술 기록 요약]", "progress_note"),
    ("진료의뢰 회신서", "progress_note"),
])
def test_classify_header(header, doc_type):
    assert classify(header) == doc_type


def _doc(text):
    return split(text)[0]


def test_locate_allows_whitespace_difference_only():
    d = _doc("[병리결과보고서]\nER positive (Allred 8, 5+3),\n  PR positive\n")
    assert locate("ER positive  (Allred 8,5+3)", d)["quote"] == "ER positive (Allred 8, 5+3)"
    assert locate("(Allred 8, 5+3), PR positive", d)["quote"] == "(Allred 8, 5+3),\n  PR positive"
    assert locate("ER positive (Allred 8, 5+2)", d) is None       # 글자가 다르면 버림
    assert locate("ER 양성 (Allred 8, 5+3)", d) is None


def test_locate_restores_masked_names():
    chart = "<외래 경과기록>   2023.5.4\n\n\n[병리결과보고서]\n환자명: 김가상   F/52\n"
    d = split(chart)[1]
    s = locate("환자명: [이름1]   F/52", d, {"[이름1]": "김가상"})
    assert s == {"doc_id": "D2", "quote": "환자명: 김가상   F/52", "char_start": chart.index("환자명"),
                 "char_end": chart.index("F/52") + 4}
