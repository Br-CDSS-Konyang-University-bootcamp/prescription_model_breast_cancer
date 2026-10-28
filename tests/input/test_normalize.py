"""IN-3 정규화 (src/input/script/pipeline.py): 가상 차트 30건 정답의 구절마다 정규화한 값이 정답 값과 같은지 본다.

후보에서 오는 칸(specimen, observed_date)과 4단계가 채우는 칸(progression_day, 차수, 표 첫 칸이 없을 때의 setting),
그리고 raw(원문 표기)는 비교에서 뺀다.
"""
import json

import pytest

from src.input.script.virtual.cases.pairs import PAIRS
from src.input.script.virtual.virtual_chart import CASES, out_dir
from src.input.script.pipeline import split
from src.input.script.pipeline import Context, normalize
from src.input.script.pipeline import locate

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


def test_gene_detected_without_variant_is_not_negative():
    """'병원성 변이'만 옮긴 구절을 '검출되지 않음'으로 바꾸지 않는다 (시험 세트 VC-0116·0119, 2026-10-26)."""
    text = ("[생식세포 유전자 검사 결과]\n검출된 변이\n  BRCA1   c.5266dupC (p.Q1756Pfs*74)   Pathogenic (병원성)\n"
            "검출되지 않음 (Not detected)\n  BRCA2, PALB2\n")
    doc = split(text)[0]
    ctx = Context(doc)
    # 2단계 (2026-10-27): 검출로 보고 변이 원문만 남기며 확인 요청 표시를 붙인다
    out = normalize("molecular.germline.BRCA1", "생식세포 BRCA1 병원성 변이", ctx)
    assert out["result"] == "detected" and out["variants"] == [
        {"protein_change": None, "variant_type": None, "vaf": None, "raw": "생식세포 BRCA1 병원성 변이"}]
    assert "_review" in out
    ins = normalize("molecular.germline.BRCA1", "BRCA1   c.5266dupC (p.Q1756Pfs*74)", ctx)["variants"][0]
    assert (ins["protein_change"], ins["variant_type"]) == ("Q1756Pfs*74", "Frame_Shift_Ins")
    dele = normalize("molecular.germline.BRCA2", "BRCA2   c.5946delT (p.S1982Rfs*22)", ctx)["variants"][0]
    assert dele["variant_type"] == "Frame_Shift_Del"
    assert normalize("molecular.germline.BRCA2", "BRCA2, PALB2", ctx)["result"] == "not_detected"   # 머리말 아래 목록
    assert normalize("molecular.germline.BRCA2", "BRCA2: 병원성 변이 검출되지 않음", ctx)["result"] == "not_detected"
    detected_list = split("[NGS]\n검출된 변이\n  BRCA1, BRCA2\n")[0]          # '검출된 변이' 아래 이름만: 알 수 없음
    assert normalize("molecular.germline.BRCA1", "BRCA1, BRCA2", Context(detected_list)) is None


def test_endocrine_end_date_reads_line():
    """보조 내분비 종료일: 날짜만 옮긴 구절도 줄을 보고 받고, 내분비약이 아닌 치료의 완료는 받지 않는다 (5단계, 2026-10-27)."""
    f = "recurrence.adjuvant_endocrine_end_date"
    doc = split("<외래 경과기록>   2024.5.4\n본문\n")[0]
    line = "   보조 letrozole 2023.11.30 5년 복용 완료"
    assert normalize(f, "2023.11.30", Context(doc, line))["value"] == "2023-11-30"
    her = "   보조 AC #4 → paclitaxel + trastuzumab → trastuzumab, 2024.1.8 총 18회 완료"     # VC-0112 (L5)
    assert normalize(f, "2024.1.8 총 18회 완료", Context(doc, her)) is None
    row = "보조    페마라 (letrozole) 2.5mg qd   2018.11.30   2023.11.30   -   -   완료 (5년)"
    assert normalize(f, "2018.11.30", Context(doc, row)) is None                            # 투약 표의 시작일
    assert normalize(f, "2023.11.30", Context(doc, row))["value"] == "2023-11-30"
    meta = "   보조 letrozole 복용 중 2023.3.23 폐 전이 → letrozole 2023.3.28 중단 (PD)"
    assert normalize(f, "2023.3.23", Context(doc, meta)) is None                             # 전이일
    assert normalize(f, "letrozole 2023.3.28 중단", Context(doc, meta))["value"] == "2023-03-28"


@pytest.mark.parametrize("tail, want", [
    ("q3w #6   PR   유지요법 전환", "maintenance"),                 # VC-0111 (R2)
    ("q3w #3   -   심부전 의심 (LVEF 저하)", "toxicity"),          # VC-0127 (R2)
    ("-      관절통 (부작용)", "toxicity"),
    ("q3w #4   -   계획된 변경", "planned_switch"),
    ("q3w #6   CR   완료", "completed"),
    ("q4w #21   PD   진행", "progression"),
    ("관절통 (부작용)으로 중단 후 진행", "toxicity"),                # 둘 다 맞으면 앞 순서
    ("q3w #6   PR", None),                                          # 반응 PR은 중단 사유가 아님
])
def test_stop_reason_from_vocab(tail, want):
    """중단 사유는 field_vocab.csv 단어로 읽는다 (7단계, 2026-10-27)."""
    doc = split("<투약 기록>   2024.5.4\n본문\n")[0]
    q = f"docetaxel 75mg/m2   2023.2.20   2023.6.5   {tail}"
    assert normalize("treatment_history", q, Context(doc, q))["stop_reason"] == want


@pytest.mark.parametrize("field, quote, want", [
    # 8단계: 원격 림프절 (같은 쪽 쇄골상·내유 림프절은 국소, '비대 없음'은 전이 아님)
    ("recurrence.metastatic_sites", "간·종격동 림프절 전이", ["liver", "distant_ln"]),        # VC-0116
    ("recurrence.metastatic_sites", "뼈·종격동 림프절 전이", ["bone", "distant_ln"]),         # VC-0128
    ("recurrence.metastatic_sites", "para-aortic lymph node metastasis", ["distant_ln"]),
    ("recurrence.metastatic_sites", "좌측 쇄골상 림프절 전이", None),
    ("recurrence.metastatic_sites", "내유 림프절 전이", None),
    # 9단계: ER 약양성은 저발현, PR 약양성은 양성
    ("receptors.er_percent", "ER 5% (약양성)", {"percent": 5, "result": "low_positive"}),    # VC-0124
    ("receptors.pr_percent", "PR 약양성 (Allred 3, 2+1)",
     {"allred": {"total": 3, "ps": 2, "is": 1}, "result": "positive"}),                       # VC-0101
    ("patient.visceral_crisis", "간 기능 악화를 동반한 visceral crisis로 판단", "yes"),      # VC-0126
    ("patient.visceral_crisis", "visceral crisis 아님", "no"),
    ("patient.visceral_crisis", "AST 250, ALT 310", None),                                   # 수치만으로 짐작하지 않음
    # 10단계: 칸의 단어를 사전에서
    ("patient.cardiac_history", "협심증 (2017년 스텐트 시술)", "yes"),                       # VC-0127
    ("patient.cardiac_history", "심장 질환 없음", "no"),
    ("patient.cardiac_history", "재발·전이 소견 없음", None),
    ("patient.mediastinal_radiation", "좌측 흉벽·내유림프절 방사선 치료 (50 Gy)", "yes"),    # VC-0127
    ("patient.mediastinal_radiation", "종격동 방사선 치료력 없음", "no"),
])
def test_rules_steps_8_to_10(field, quote, want):
    doc = split("<외래 경과기록>   2024.5.4\n본문\n")[0]
    got = normalize(field, quote, Context(doc, quote))
    assert (got and got["value"]) == want


def test_ypt0_residual_size_is_zero():
    """9단계: 잔존 크기 줄이 없어도 ypT0이면 잔존 0 mm (VC-0120)."""
    doc = split("[병리결과보고서]   2024.5.4\nypT0 ypN0 (AJCC 8th)\n림프절: 0/3\n")[0]
    got = normalize("stage.yptnm", "ypT0 ypN0 (AJCC 8th)", Context(doc, "ypT0 ypN0 (AJCC 8th)"))["value"]
    assert got["residual_size_mm"] == 0 and got["examined_ln"] == 3


@pytest.mark.parametrize("row, want", [
    ("AC (doxorubicin 60mg/m2 + cyclophosphamide 600mg/m2)   2020.1.6   2020.3.9   q3w #4   -   계획된 변경",
     [("doxorubicin", (60, "mg/m2"), (240, "mg/m2")), ("cyclophosphamide", (600, "mg/m2"), (2400, "mg/m2"))]),
    ("놀바덱스 (tamoxifen) 20mg qd   2018.1.2   2023.1.2   -   -   완료", [("tamoxifen", (20, "mg"), "No value")]),
    ("입랜스 (palbociclib) 125mg + 페마라 2.5mg   2021.5.12   2023.1.12   q4w #21   PD   진행",      # 매일 먹는 약
     [("palbociclib", (125, "mg"), "No value"), ("letrozole", (2.5, "mg"), "No value")]),
    ("gemcitabine 1000mg/m2 + carboplatin AUC 2 (d1, d8)   2022.12.12   2023.7.10   q3w #10   PD   진행",
     [("gemcitabine", (1000, "mg/m2"), (20000, "mg/m2")), ("carboplatin", (2, "AUC"), "No value")]),
    ("엔허투 (trastuzumab deruxtecan) 5.4mg/kg   2024.1.2   2025.1.2   q3w #23   PD   진행",
     [("trastuzumab deruxtecan", (5.4, "mg/kg"), (124.2, "mg/kg"))]),
    ("TCHP (탁소텔 + 카보플라틴 + 허셉틴 + 퍼제타)   2023.9.4   2023.12.18   q3w #6   CR   완료", []),   # 용량 없음
])
def test_treatment_doses(row, want):
    """약별 용량 doses (2026-10-28): 적힌 약만, 매일 먹는 약·AUC는 총량 No value."""
    doc = split("[투약 기록]   2024.5.4\n본문\n")[0]
    got = normalize("treatment_history", row, Context(doc, row)).get("doses", [])
    pair = lambda x: x if x == "No value" else (x["value"], x["unit"])                      # noqa: E731
    assert [(d["drug"], pair(d["per_admin"]), pair(d["total"])) for d in got] == want


def test_basis_cut_before_hu():
    """'58세 폐경 후 여성'에서 LLM이 '58세 폐경'까지만 옮겨도 근거로 보지 않는다."""
    doc = split("<외래 경과기록>   2023.5.4\n58세 폐경 후 여성.\n")[0]
    line = "58세 폐경 후 여성."
    assert normalize("patient.menopausal_basis", "58세 폐경", Context(doc, line)) is None
    assert normalize("patient.menopausal_basis", "50세 폐경", Context(doc, "폐경: 폐경 후 (50세 폐경)"))["value"] \
        == "age_amenorrhea"
