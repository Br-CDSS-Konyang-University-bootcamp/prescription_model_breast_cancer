"""IN-0 비식별화 (src/input/script/pipeline/deid.py)와 파이프라인 연결: 가상 차트 29건의 가짜 식별정보가 하나도 남지 않고 (합격 기준 0건),
임상 글(정답 구절)은 그대로이며, extract(LLM 자리)는 가린 문서만 받는다.
"""
import json
import re

import pytest

from src.input.script.evaluation.candidates import from_expected
from src.input.script.virtual.cases.pairs import PAIRS
from src.input.script.virtual.virtual_chart import CASES, out_dir
from src.input.script.pipeline.classify import split
from src.input.script.pipeline.deid import identifiers, mask
from src.input.script.pipeline.pipeline import run

ALL = CASES + [p.id for p in PAIRS]
# 가상 차트 식별정보 (virtual_chart.Doc.ident, 사례 코드의 의료진 이름): 사례와 따로 정규식으로 센다
LEAKS = [r"[김이박최정]가상(?![가-힣])", r"등록번호\s*:\s*\d", r"\d{6}-[1-4]", r"010-\d{4}-\d{4}"]


def _load(ref):
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    ps = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    return chart, ps


@pytest.mark.parametrize("ref", ALL)
def test_no_identifier_left(ref):
    chart, _ = _load(ref)
    masked = mask(chart, identifiers(chart))
    assert [p for p in LEAKS if re.search(p, masked)] == []


@pytest.mark.parametrize("ref", ALL)
def test_clinical_text_kept(ref):
    """정답 구절은 가린 문서에도 그대로 있다 (날짜·나이·성별·병원 이름은 가리지 않는다)."""
    chart, ps = _load(ref)
    mapping = identifiers(chart)
    docs = {d.doc_id: mask(d.text, mapping) for d in split(chart)}
    assert [c["quote"] for c in from_expected(ps) if c["quote"] not in docs[c["doc_id"]]] == []


@pytest.mark.parametrize("ref", ALL)
def test_extract_sees_only_masked_text(ref):
    chart, ps = _load(ref)
    seen = []
    got, issues = run(chart, lambda docs: seen.extend(d.text for d in docs) or from_expected(ps),
                      patient_ref=ref, created_at=ps["created_at"])
    assert issues == []
    assert not any(re.search(p, t) for p in LEAKS for t in seen)


def test_mapping_and_restore():
    chart = ("<외래 경과기록>   2023.5.4\n환자명: 홍길동   등록번호: 12345678   F/54   주민번호: 690101-2******\n"
             "연락처: 010-1234-5678   주소: 서울시 강남구 가상로 1\n담당의: 이의사\n홍길동님 내원.\n")
    mapping = identifiers(chart)
    assert mapping == {"[이름1]": "홍길동", "[이름2]": "이의사", "[등록번호1]": "12345678",
                       "[주민번호1]": "690101-2******", "[연락처1]": "010-1234-5678", "[주소1]": "서울시 강남구 가상로 1"}
    masked = mask(chart, mapping)
    assert "[이름1]님 내원" in masked and "F/54" in masked and "2023.5.4" in masked
    assert mask(masked, {v: k for k, v in mapping.items()}) == chart
