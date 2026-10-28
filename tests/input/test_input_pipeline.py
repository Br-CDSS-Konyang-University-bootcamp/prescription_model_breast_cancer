"""입력 모듈 끝까지 (src/input/script/pipeline.py): IN-2 자리에 정답에서 만든 후보를 넣으면 정답 patient_state가 나온다.
이것이 통과하면 규칙 쪽(문서 나누기·인용 확인·정규화·조립)이 완성된 것이고, LLM을 붙여 달라진 곳은 LLM 오류다.
raw(원문 표기)와 충돌 설명(note)은 사례 코드가 손으로 쓴 글이라 비교에서 뺀다.
"""
import json

import pytest

from src.input.script.evaluation import from_expected
from src.input.script.virtual.cases.pairs import PAIRS
from src.input.script.virtual.virtual_chart import CASES, out_dir
from src.input.script.pipeline import run

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


def _run_with(ref, add=(), drop_fields=()):
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    cands = [c for c in from_expected(want) if c["field"] not in drop_fields] + list(add)
    got, issues = run(chart, lambda docs: cands, patient_ref=ref, created_at=want["created_at"])
    return got, issues, want


def _cand(doc_id, field, quote):
    return {"doc_id": doc_id, "field": field, "quote": quote, "specimen": None, "observed_date": None}


def test_gene_prefers_candidate_with_variant():
    """경과기록 요약(변이 표기 없음, 날짜가 늦음)과 유전자 보고서의 변이 줄이 함께 오면 변이 줄을 고른다 (2026-10-28)."""
    got, issues, want = _run_with("VC-0116", [_cand("D1", "molecular.germline.BRCA1", "생식세포 BRCA1 병원성 변이")])
    assert got["fields"]["molecular"]["germline"]["BRCA1"]["variants"][0]["protein_change"] == "Q1756Pfs*74"
    assert _strip(got["fields"]["molecular"]["germline"]["BRCA1"]) == _strip(want["fields"]["molecular"]["germline"]["BRCA1"])


def test_rules_against_llm_mistakes():
    """10건 LLM 시험(2026-10-23)에서 칸을 잘못 고른 후보가 들어와도 정답과 같게 조립한다."""
    # 나중의 폐 전이를 진단 시 전이 부위로: 진단 시 IIA라 받지 않는다
    got, issues, want = _run_with("VC-0103", [_cand("D1", "stage.metastatic_sites", "lung metastasis")])
    assert got["fields"]["stage"]["metastatic_sites"] == want["fields"]["stage"]["metastatic_sites"]
    # 재발 상태 후보가 'PD'뿐이어도 재발 부위(lung)가 있으면 원격 전이
    got, _, want = _run_with("VC-0103", [_cand("D1", "recurrence.status", "PD")], drop_fields={"recurrence.status"})
    assert got["fields"]["recurrence"]["status"]["value"] == want["fields"]["recurrence"]["status"]["value"] == "distant"
    # 진단 시 전이 부위 후보가 아예 없어도 pTNM의 M0로 '해당 없음'
    got, _, want = _run_with("VC-0104", drop_fields={"stage.metastatic_sites"})
    assert got["fields"]["stage"]["metastatic_sites"]["value"] == "[Not Applicable]"
    # 재발 없는 환자의 재발 부위: 비워 둔다
    got, _, want = _run_with("VC-0107", [_cand("D2", "recurrence.metastatic_sites", "재발·전이 소견 없음")])
    assert got["fields"]["recurrence"]["metastatic_sites"] == {"status": "not_recorded"}
    # 선행요법 뒤 잔존 크기·림프절: yptnm에만
    got, _, want = _run_with("VC-0105", [_cand("D3", "stage.pathologic_size_mm", "1.4 cm"),
                                         _cand("D3", "stage.positive_ln_count", "1/3 (+)")])
    assert "pathologic_size_mm" not in got["fields"]["stage"]                  # 기본 칸이 아니라 후보가 없으면 없다
    assert got["fields"]["stage"]["positive_ln_count"] == want["fields"]["stage"]["positive_ln_count"]
    # 진단 시 IV기: 전이일 후보가 없어도 0, 표 첫 칸이 없는 투약은 전이 setting
    got, _, want = _run_with("VC-0108", drop_fields={"recurrence.metastasis_day"})
    assert got["fields"]["recurrence"]["metastasis_day"]["value"] == 0
    assert [t["setting"] for t in got["fields"]["treatment_history"]] == ["metastatic"]
    assert got["fields"]["treatment_history"] == want["fields"]["treatment_history"]
    # 진단 시 IV기: 진행 소견을 재발 부위·상태로 내도 재발 칸은 비운다 (4단계, 2026-10-27)
    got, _, want = _run_with("VC-0108", [_cand("D1", "recurrence.metastatic_sites", "(de novo, bone only)"),
                                         _cand("D1", "recurrence.status", "(de novo, bone only)")])
    for k in ("status", "metastatic_sites"):
        assert got["fields"]["recurrence"][k] == want["fields"]["recurrence"][k] == {"status": "not_recorded"}
    assert got["fields"]["recurrence"]["metastasis_day"]["value"] == 0


def test_progression_day_from_imaging():
    """진행일은 진행을 보인 영상의 날: 종료일 전(VC-0123 골스캔)이든 종료 1주 뒤(VC-0111 CT)든 (6단계, 2026-10-27)."""
    for ref, drug, day in [("VC-0123", "abemaciclib", 680), ("VC-0111", "pertuzumab", 588)]:
        got, _, _ = _run_with(ref)
        t = next(t for t in got["fields"]["treatment_history"] if t["drugs"][0] == drug)
        assert t["progression_day"] == day


def test_needs_review_goes_to_issues():
    """변이 표기 없는 '병원성 변이' 구절: 값은 '검출', 확인 요청은 issues에 (patient_state에는 표시를 남기지 않는다)."""
    got, issues, want = _run_with("VC-0116", [_cand("D1", "molecular.germline.BRCA1", "생식세포 BRCA1 병원성 변이")],
                                  drop_fields={"molecular.germline.BRCA1"})
    g = got["fields"]["molecular"]["germline"]["BRCA1"]
    assert g["result"] == "detected" and "_review" not in g
    assert [i["reason"] for i in issues if i.get("reason") == "needs_review"] == ["needs_review"]


def test_age_and_repeated_mentions():
    """LLM은 문서마다 'F/54'를 낸다. 나이는 진단 시(가장 이른 문서) 값, 같은 성별은 이력으로 쌓지 않는다."""
    ref = "VC-0103"
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    extra = [{"doc_id": d, "field": f, "quote": "F/54", "specimen": None, "observed_date": None}
             for d in ("D1", "D4", "D6") for f in ("patient.age", "patient.gender")]
    got, issues = run(chart, lambda docs: from_expected(want) + extra, patient_ref=ref, created_at=want["created_at"])
    assert issues == []
    assert got["fields"]["patient"]["age"] == want["fields"]["patient"]["age"]          # F/52 (D2, 2021)
    assert "history" not in got["fields"]["patient"]["gender"]
    assert got["fields"]["at_index"] == want["fields"]["at_index"]


def _vc0105(chart_edits, add):
    """VC-0105(선행 TCHP, cT2N1 IIB)의 차트를 고치고 병기 후보를 바꿔 조립한다."""
    ref = "VC-0105"
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    for old, new in chart_edits:
        assert old in chart
        chart = chart.replace(old, new)
    want = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    stage = ("stage.ctnm", "stage.group", "stage.disease_extent", "stage.metastatic_sites")
    cands = [c for c in from_expected(want) if c["field"] not in stage] + list(add)
    return run(chart, lambda docs: cands, patient_ref=ref, created_at=want["created_at"])


def test_diagnosis_extent_ignores_post_neoadjuvant_stage():
    """선행요법 뒤 병기(ypStage)가 진단 시 병기군·범주를 덮거나 같은 날 충돌로 지우지 않는다 (2026-10-27)."""
    yp = ("ypT1c ypN1a, 잔존", "ypT1c ypN1a, ypStage IIA, 잔존")
    # 진단 병기는 1월 영상 판독에만, 7월 경과기록에는 선행 후 병기만
    got, issues = _vc0105(
        [("좌측 액와 림프절 전이 의심", "좌측 액와 림프절 전이 의심\n  임상 병기: cT3N1M0, stage IIIA"),
         ("   cT2N1M0, stage IIB, HER2+", "   HER2+"), yp],
        [_cand("D2", "stage.ctnm", "cT3N1M0"), _cand("D2", "stage.group", "stage IIIA"),
         _cand("D2", "stage.disease_extent", "stage IIIA"), _cand("D2", "stage.metastatic_sites", "cT3N1M0"),
         _cand("D4", "stage.group", "ypStage IIA"), _cand("D4", "stage.disease_extent", "ypStage IIA")])
    stage = got["fields"]["stage"]
    assert (stage["group"]["value"], stage["disease_extent"]["value"]) == ("IIIA", "locally_advanced")
    assert sum(i.get("note") == "선행요법 뒤 병기 (진단 시 병기군 아님)" for i in issues) == 2
    # 같은 날 경과기록에 두 병기를 함께 적음
    got, _ = _vc0105(
        [("cT2N1M0, stage IIB", "cT3N1M0, stage IIIA"), yp],
        [_cand("D4", "stage.ctnm", "cT3N1M0"), _cand("D4", "stage.group", "stage IIIA"),
         _cand("D4", "stage.disease_extent", "stage IIIA"), _cand("D4", "stage.metastatic_sites", "cT3N1M0"),
         _cand("D4", "stage.group", "ypStage IIA"), _cand("D4", "stage.disease_extent", "ypStage IIA")])
    assert got["conflicts"] == []
    assert got["fields"]["stage"]["disease_extent"]["value"] == "locally_advanced"


def test_diagnosis_extent_from_tnm():
    """병기군 구절이 없으면 ctnm으로 범주를 정한다. 구절이 해부학적 범주와 다르면 TNM 값을 쓰고 확인 요청."""
    # 병기군 구절 없음: cT3N1M0 → IIIA
    got, issues = _vc0105([("cT2N1M0, stage IIB", "cT3N1M0")],
                          [_cand("D4", "stage.ctnm", "cT3N1M0"), _cand("D4", "stage.metastatic_sites", "cT3N1M0")])
    ext = got["fields"]["stage"]["disease_extent"]
    assert (ext["value"], ext["source"]["quote"]) == ("locally_advanced", "cT3N1M0")
    assert issues == []
    # 차트에는 IIA(예후 병기 등)로 적혔지만 해부학적으로 T3N1 = IIIA
    got, issues = _vc0105([("cT2N1M0, stage IIB", "cT3N1M0, stage IIA")],
                          [_cand("D4", "stage.ctnm", "cT3N1M0"), _cand("D4", "stage.group", "stage IIA"),
                           _cand("D4", "stage.disease_extent", "stage IIA"), _cand("D4", "stage.metastatic_sites", "cT3N1M0")])
    assert got["fields"]["stage"]["group"]["value"] == "IIA"
    assert got["fields"]["stage"]["disease_extent"]["value"] == "locally_advanced"
    assert [i["reason"] for i in issues] == ["needs_review"]


@pytest.mark.parametrize("tnm, m, want", [
    ({"t": "T3", "n": "N1mi"}, "M0", "locally_advanced"),   # N1mi가 내려가는 것은 T0~T1뿐
    ({"t": "T1c", "n": "N1mi"}, "M0", "early"),             # IB
    ({"t": "T3", "n": "N0"}, "M0", "early"),                # IIB
    ({"t": "T2", "n": "N3a"}, None, "locally_advanced"),    # IIIC
    ({"t": "T4d", "n": "N0"}, "M0", "locally_advanced"),    # 염증성 IIIB
    ({"t": "TX", "n": "N2"}, "M0", "locally_advanced"),     # 어떤 T든 N2는 III기
    ({"t": "TX", "n": "N1"}, "M0", None),
    ({"t": "T2", "n": "N1"}, "M1", "metastatic"),
])
def test_anatomic_extent(tnm, m, want):
    from src.input.script.pipeline import _anatomic_extent
    assert _anatomic_extent(tnm, m) == want


def test_tnm_with_prefixed_m_and_fna_suffix():
    """림프절 세침흡인(FNA) 양성은 임상 N에 (f)를 붙인다 (AJCC 8판, cN1(f)). 각 범주에 c가 붙어도 M을 읽는다."""
    from src.input.script.pipeline import _tnm
    assert _tnm("cT2 cN1(f) cM0", None, prefix="c") == {"t": "T2", "n": "N1", "m": "M0", "edition": None}
