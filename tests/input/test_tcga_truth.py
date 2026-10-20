"""TCGA 정답 생성기 테스트.

1. 예시 3개(tests/input/expected/, 2026-10-14 커밋 5d92ab2의 src/input/examples/ 사본)와 생성 결과가 완전히 같은지
2. 정답 세트 전체가 schemas/patient_state.json을 통과하는지
3. tcga_mapping.md에 적힌 건수와 생성 결과가 맞는지 (문서와 코드가 어긋나면 여기서 실패한다)
4. 주기 수·HER2 보정 같은 세부 규칙

실행 (team_project 폴더에서): python -m pytest tests/input
"""
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from src.input.truth import tcga_truth as T

EXAMPLES = sorted((Path(__file__).parent / "expected").glob("patient_state_*.json"))


@pytest.fixture(scope="module")
def rows() -> pd.DataFrame:
    return T.load_rows()


@pytest.fixture(scope="module")
def truth(rows) -> dict[str, dict]:
    return {r.patient_id: T.build(r) for _, r in rows.iterrows()}


# ---------- 1. 예시와 같은지 ----------
@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_examples_match_generator(path: Path, truth):
    example = json.loads(path.read_text(encoding="utf-8"))
    assert truth[example["patient_ref"]] == example


def test_three_examples_exist():
    assert len(EXAMPLES) == 3


# ---------- 2. 스키마 ----------
def test_all_truth_valid_against_schema(truth):
    v = T.validator()
    failed = {pid: next(v.iter_errors(doc)).message for pid, doc in truth.items() if not v.is_valid(doc)}
    assert failed == {}


# ---------- 3. tcga_mapping.md의 건수 ----------
def test_truth_set_size(truth):
    assert len(truth) == 838  # §2.2: 크롭본 838명 = 정답 세트


def test_histology_counts(truth):
    c = Counter(doc["fields"]["diagnosis"]["histology"]["value"] for doc in truth.values())
    # §3.1: IDC 603 + 수질암 2, ILC 165, Other 28 + Mixed 20 = invasive_NOS 48
    assert c == {"IDC": 605, "ILC": 165, "invasive_NOS": 48, "mucinous": 13, "metaplastic": 7}


def test_ptnm_not_assessed_counts(truth):
    c = Counter()
    for doc in truth.values():
        p = doc["fields"]["stage"]["ptnm"]
        for k in ("t", "n", "m"):
            if p.get("value", {}).get(k) == "not_assessed":
                c[k] += 1
    assert c == {"n": 10, "m": 132}  # §3.2: TX 0, NX 10, MX 132


def test_positive_ln_count_cases(truth):
    c = Counter()
    for doc in truth.values():
        ln = doc["fields"]["stage"]["positive_ln_count"]
        if ln["status"] != "present":
            c["none"] += 1
        else:
            c[(ln["value"]["positive"] == "[Not Available]", ln["value"]["examined"] == "[Not Available]")] += 1
    # §3.2 양성 림프절 수 표: 둘 다 700, examined만 없음 1, positive만 없음 42 (N 병기와 맞지 않는 13명 포함), 둘 다 없음 95
    assert c == {(False, False): 700, (False, True): 1, (True, False): 42, "none": 95}


def test_metastatic_sites_not_applicable(truth):
    c = Counter(str(doc["fields"]["stage"]["metastatic_sites"].get("value")) == "[Not Applicable]" for doc in truth.values())
    assert c[True] == 303 + 445  # §3.2: 전이 여부 NO 303 + 기록 없음이지만 M0 445


def test_metastatic_sites_other_specify_uses_other_column(truth):
    for doc in truth.values():
        sites = doc["fields"]["stage"]["metastatic_sites"].get("value")
        if isinstance(sites, list):
            assert "other: Other, specify" not in sites


def test_treatment_counts(truth):
    items = [t for doc in truth.values() for t in doc["fields"]["treatment_history"]]
    assert len(items) == 1931  # §3.6: 투약 기록 1,931건 (같은 약·같은 날짜 중복 6건 합침) (unknown 14건 제외)
    assert sum(t["duration_days"] is not None for t in items) == 1429
    no_record = sum(1 for doc in truth.values() if doc["fields"]["anthracycline_drug_dose"]["administered"] == "No value")
    assert no_record == 199  # §3.6: 투약 기록 자체가 없는 환자 199명
    empty = sum(1 for doc in truth.values() if not doc["fields"]["treatment_history"])
    assert empty == 199 + 6  # 성분명 unknown 항목만 있는 6명도 치료 이력이 빈 배열


def test_operable_from_primary_surgery(truth):
    c = Counter(doc["fields"]["stage"]["operable"].get("value", doc["fields"]["stage"]["operable"]["status"])
                for doc in truth.values())
    assert c == {"yes": 807, "not_recorded": 31}  # §3.2 operable: 원발 수술 기록 있음 807, 없음 31


def test_metastatic_sites_rules_2026_10_20(truth):
    # §3.2 전이 부위 규칙 7~9, §3.7 재발 후 수술
    assert truth["TCGA-A7-A13E"]["fields"]["recurrence"]["metastatic_sites"]["value"] == [
        "lung", "bone", "liver", "brain", "other: Skin Nodules"]
    assert truth["TCGA-A8-A07W"]["fields"]["stage"]["metastatic_sites"] == {"status": "not_done"}
    assert truth["TCGA-LL-A73Z"]["fields"]["stage"]["metastatic_sites"]["value"] == ["brain"]
    surgery = Counter(doc["fields"]["recurrence"]["surgery"]["value"] for doc in truth.values()
                      if "surgery" in doc["fields"]["recurrence"])
    assert surgery == {"yes": 15, "no": 15}


def test_progression_day_from_pfs(truth):
    got = {(pid, t["drugs"][0]): t["progression_day"] for pid, doc in truth.items()
           for t in doc["fields"]["treatment_history"] if t["progression_day"] is not None}
    # §3.6: 진단 시 IV기 PFS 진행일. AO-A0J5(두 요법), B6-A3ZX(그때 쓰던 약 없음)는 비움
    assert got == {("TCGA-A2-A0SV", "capecitabine"): 826, ("TCGA-A2-A0SW", "tamoxifen"): 653,
                   ("TCGA-A2-A0T2", "capecitabine"): 255, ("TCGA-LL-A73Z", "fulvestrant"): 192}


def test_neoadjuvant_setting_patients(truth):
    n = sum(1 for doc in truth.values()
            if any(t["setting"] == "neoadjuvant" for t in doc["fields"]["treatment_history"]))
    assert n == 7  # §3.6 setting 규칙 2a·3: 진단일 전 항암 1명(C8-A1HO) + 선행요법 이력 6명


def test_index_day_and_recurrence_day_counts(truth):
    """§2.3: index_day = fu_last_days (776명, 62명 null). §3.7: recurrence_day는 distant 15 + locoregional 12명 (진단 시 IV기 제외)."""
    assert sum(doc["index_day"] is not None for doc in truth.values()) == 776
    assert sum("recurrence_day" in doc["fields"]["recurrence"] for doc in truth.values()) == 27


def test_at_index_counts(truth):
    """§2.3: 최근 4주 이내 항암제·호르몬제 투여. unknown = 기준일 없음 62명 + 종료일 없는 투약 365명."""
    c = Counter(doc["fields"]["at_index"]["recent_therapy_28d"]["status"] for doc in truth.values())
    assert c == {"yes": 33, "no": 378, "unknown": 427}
    assert sum(doc["fields"]["at_index"]["age"] is None for doc in truth.values()) == 62


def test_line_counts(truth):
    """§3.6: 차수가 붙은 투약 70건, 환자 23명."""
    items = [t for doc in truth.values() for t in doc["fields"]["treatment_history"] if t["line"] is not None]
    assert len(items) == 70
    assert sum(any(t["line"] for t in doc["fields"]["treatment_history"]) for doc in truth.values()) == 23


def test_deemed_lines_counts(truth):
    """§3.6b 표."""
    c = Counter((d["rule_id"], d["status"]) for doc in truth.values() for d in doc["fields"]["deemed_lines"])
    assert {k: v for k, v in c.items() if k[1] != "not_applicable"} == {
        ("DEEM-ANTHRA-TAXANE", "met"): 5, ("DEEM-ANTHRA-TAXANE", "not_met"): 18,
        ("DEEM-SG-1Y", "met"): 10, ("DEEM-SG-1Y", "not_met"): 12, ("DEEM-SG-1Y", "unknown"): 1,
        ("DEEM-HER2ADC-6M", "met"): 1, ("DEEM-HER2ADC-6M", "not_met"): 22,
        ("DEEM-ENDO-ADJ-1Y", "met"): 7, ("DEEM-ENDO-ADJ-1Y", "not_met"): 15, ("DEEM-ENDO-ADJ-1Y", "unknown"): 1}
    assert c[("DEEM-SG-1Y", "not_applicable")] == 815


def test_er_low_positive_only_er(truth):
    er = Counter(doc["fields"]["receptors"]["er_percent"].get("value", {}).get("result") for doc in truth.values())
    pr = Counter(doc["fields"]["receptors"]["pr_percent"].get("value", {}).get("result") for doc in truth.values())
    assert er["low_positive"] == 11  # §3.3: ER Low Positive 11명
    assert pr["low_positive"] == 0  # PR에는 저발현 범주가 없다


def test_no_score_in_er_pr(truth):
    for doc in truth.values():
        for k in ("er_percent", "pr_percent"):
            assert "score" not in doc["fields"]["receptors"][k].get("value", {})


def test_all_dates_empty(truth):
    for doc in truth.values():
        f = doc["fields"]
        assert f["diagnosis"]["diagnosis_date"] == {"status": "not_recorded"}
        assert f["recurrence"]["recurrence_date"] == {"status": "not_recorded"}
        assert all(t["start_date"] is None and t["end_date"] is None for t in f["treatment_history"])


# ---------- 4. 세부 규칙 ----------
def her2_row(score, status, fish):
    return pd.Series({"gdc_her2_ihc_score": score, "gdc_her2_status_by_ihc": status, "gdc_her2_fish_status": fish})


@pytest.mark.parametrize("score,status,fish,expected", [
    ("2+", "Equivocal", "Negative", {"score": "2+", "result": "negative"}),
    ("2+", "Equivocal", "Positive", {"score": "2+", "result": "positive"}),
    ("2+", "Equivocal", "[Not Evaluated]", {"score": "2+", "result": "unknown"}),
    ("[Not Available]", "Equivocal", "Negative", {"score": "2+", "result": "negative"}),  # 점수 없는 Equivocal → 2+
    ("2+", "Positive", "[Not Evaluated]", {"score": "2+", "result": "positive"}),  # Equivocal이 아니면 판정 유지
    ("3+", "Positive", "[Not Evaluated]", {"score": "3+", "result": "positive"}),
    ("1+", "Negative", "[Not Evaluated]", {"score": "1+", "result": "negative"}),
])
def test_her2_adjustment(score, status, fish, expected):
    ihc, _ = T.her2(her2_row(score, status, fish))
    assert ihc["value"] == expected


def test_her2_ish_indeterminate_is_not_recorded():
    _, ish = T.her2(her2_row("1+", "Negative", "Indeterminate"))
    assert ish == {"status": "not_recorded"}


@pytest.mark.parametrize("drugs,recorded,dur,expected", [
    (["doxorubicin"], "4", 42, {"value": 4, "basis": "recorded", "interval_days": 14, "interval_basis": "derived"}),
    (["fulvestrant"], None, 196, {"value": 8, "basis": "estimated", "interval_days": 28, "interval_basis": "standard"}),
    (["anastrozole"], None, 591, None),  # 매일 먹는 약
])
def test_cycles_rule(drugs, recorded, dur, expected):
    assert T.cycles_of(drugs, recorded, dur) == expected


def test_cycles_recorded_without_duration_uses_standard():
    std = T.CYCLE_DAYS["doxorubicin"]
    assert T.cycles_of(["doxorubicin"], "4", None) == {
        "value": 4, "basis": "recorded", "interval_days": std, "interval_basis": "standard"}


@pytest.mark.parametrize("text,expected", [("90-99%", [90, 99]), ("1-9%", [1, 9]), ("<1%", [0, 0]), (None, None)])
def test_bin_range(text, expected):
    assert T.bin_range(text) == expected


def test_anthracycline_combined_dose_split():
    # 병용 기록 'doxorubicin+cyclophosphamide', 용량 '60+600' → doxorubicin 60
    assert T.dose("60+600", "mg/m2", 0, 2) == {"value": 60.0, "unit": "mg/m2"}
    assert T.dose("100-102", "mg", 0, 1) == {"value": 102.0, "unit": "mg"}  # 범위는 최대값
    assert T.dose("60", "mg", 0, 2) == "No value"  # 약 수와 용량 수가 다르면 나눌 수 없음
