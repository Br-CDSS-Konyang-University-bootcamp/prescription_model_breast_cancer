"""IN-3 정규화 (src/input/script/pipeline/normalize.py): 가상 차트 30건 정답의 구절마다 정규화한 값이 정답 값과 같은지 본다.

후보에서 오는 칸(specimen, observed_date)과 4단계가 채우는 칸(progression_day, 차수, 표 첫 칸이 없을 때의 setting),
그리고 raw(원문 표기)는 비교에서 뺀다.
"""
import json

import pytest

from src.input.script.virtual.cases.pairs import PAIRS
from src.input.script.virtual.virtual_chart import CASES, out_dir
from src.input.script.pipeline.classify import split
from src.input.script.pipeline.normalize import Context, normalize
from src.input.script.pipeline.quote import locate

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


@pytest.mark.parametrize("field,quote", [
    ("patient.menopausal_basis", "폐경 후"),                       # 상태만 있고 근거가 없음
    ("stage.ctnm", "pT2N0(0/2)M0"),                               # 병리 TNM을 임상 칸에
    ("stage.ptnm", "cT2N1M0"),
    ("stage.clinical_size_mm", "0.5~1.2 cm 크기의 다발성 결절."),  # 폐 결절 크기
    # 10건 시험 (2026-10-23)에서 나온 것
    ("molecular.germline.BRCA1", "PIK3CA H1047R"),                 # 다른 유전자의 구절
    ("patient.cardiac_history", "재발·전이 소견 없음"),            # 일반적인 '없음' 구절을 여러 칸에
    ("patient.mediastinal_radiation", "재발·전이 소견 없음"),
    ("patient.comorbidities", "재발·전이 소견 없음"),
    ("recurrence.surgery", "재발·전이 소견 없음"),
    ("recurrence.later_distant", "재발·전이 소견 없음"),
    ("recurrence.adjuvant_endocrine_end_date", "2023.9.4 간 전이"),  # 종료가 아니라 전이 날짜
    ("recurrence.metastasis_day", "2022.9.4 흉벽 국소 재발"),       # 국소 재발은 원격 전이가 아님
    ("patient.menopausal_basis", "58세 폐경 후"),                   # 58세는 나이
    # 2차 (2026-10-26)
    ("recurrence.metastasis_day", "2022.9.29"),                      # 재발 병소 수술일 (날짜만)
    ("recurrence.recurrence_date", "2022.9.29 흉벽 광범위 절제"),
    # 3차 (2026-10-26)
    ("recurrence.adjuvant_endocrine_end_date", "보조 내분비요법 상의 예정"),  # 치료 계획은 검사 '예정'이 아님
    ("recurrence.status", "PD"),                                            # 치료 반응
])
def test_wrong_field_is_not_normalized(field, quote):
    """LLM이 칸을 잘못 고른 구절은 값을 만들지 않는다 (VC-0103 hari-q3-8b 시험, 2026-10-23)."""
    doc = split("<외래 경과기록>   2023.5.4\n" + quote + "\n")[0]
    assert normalize(field, quote, Context(doc)) is None


def test_basis_cut_before_hu():
    """'58세 폐경 후 여성'에서 LLM이 '58세 폐경'까지만 옮겨도 근거로 보지 않는다."""
    doc = split("<외래 경과기록>   2023.5.4\n58세 폐경 후 여성.\n")[0]
    line = "58세 폐경 후 여성."
    assert normalize("patient.menopausal_basis", "58세 폐경", Context(doc, line)) is None
    assert normalize("patient.menopausal_basis", "50세 폐경", Context(doc, "폐경: 폐경 후 (50세 폐경)"))["value"] \
        == "age_amenorrhea"
