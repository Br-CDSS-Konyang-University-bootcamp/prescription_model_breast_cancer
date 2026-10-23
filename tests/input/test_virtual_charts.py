"""가상 차트 10건 (tests/fixtures/virtual_charts/): 저장된 chart.txt·정답 patient_state가 사례 코드(src/input/chart/cases/)로
다시 만든 것과 같고, 스키마·인용 위치·문서 범위·근거·차수 재계산이 맞는지 본다.
사례를 고치면 `python -m src.input.chart.virtual_chart`로 다시 쓴다.
"""
import json

import pytest

from src.input.chart.cases.pairs import BY_ID, PAIRS, get
from src.input.chart.virtual_chart import CASES, FIXTURES, check, dumps, load_case, out_dir, pairs_index

ALL = CASES + [p.id for p in PAIRS]


@pytest.mark.parametrize("ref", ALL)
def test_case_matches_fixture(ref):
    chart, ps = load_case(ref).build()
    assert check(chart, ps) == []
    assert (out_dir(ref) / "chart.txt").read_text(encoding="utf-8") == chart
    assert (out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8") == dumps(ps)


@pytest.mark.parametrize("ref", ALL)
def test_saved_fixture_is_valid(ref):
    """다른 모듈이 읽는 저장 파일 자체도 검사를 통과한다."""
    chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
    ps = json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))
    assert check(chart, ps) == []


@pytest.mark.parametrize("ref", [p.id for p in PAIRS])
def test_pair_expected_values(ref):
    """짝 사례가 바꾸려던 값으로 정답이 나온다 (expect_a)."""
    f = load_case(ref).build()[1]["fields"]
    for path, want in BY_ID[ref].expect_a.items():
        assert get(f, path) == want, (ref, path)


@pytest.mark.parametrize("ref", [p.id for p in PAIRS])
def test_pair_changes_only_some_fields(ref):
    """짝 사례는 기본 사례와 일부 칸만 다르다 (값 하나만 바꾼 사례). 위치·원문은 비교에서 뺀다."""
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("source", "raw", "quote")}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    base = strip(load_case(BY_ID[ref].base).build()[1]["fields"])
    var = strip(load_case(ref).build()[1]["fields"])
    changed = {g for g in base.keys() | var.keys() if base.get(g) != var.get(g)}
    if BY_ID[ref].group == "G2":
        # 무병 기간 짝은 전이 시점과 그 뒤 일정이 함께 옮겨진다. 전이 전 치료(보조요법)와 진단 시 값은 같아야 한다
        assert base["treatment_history"] == var["treatment_history"] and base["stage"] == var["stage"], ref
    else:
        # 재발 기간 짝(G1)은 투약 종료일과 그로부터 계산되는 deemed_lines·at_index까지 4묶음이 바뀐다
        assert changed and len(changed) <= 4, (ref, sorted(changed))


def test_pairs_index_matches():
    pj, readme = pairs_index()
    assert (FIXTURES / "pairs" / "pairs.json").read_text(encoding="utf-8") == pj
    assert (FIXTURES / "pairs" / "README.md").read_text(encoding="utf-8") == readme


def test_vc0103_confirmed_state_quotes():
    """VC-0103 confirmed_state의 근거 위치가 새 차트와 맞다 (C·D 테스트가 읽음)."""
    chart = (FIXTURES / "VC-0103" / "chart.txt").read_text(encoding="utf-8")
    cs = json.loads((FIXTURES / "VC-0103" / "expected" / "confirmed_state.json").read_text(encoding="utf-8"))
    refs = [r for item in cs["items"].values() if isinstance(item, dict) for r in item.get("evidence_refs", [])]
    refs += cs["evidence"]
    assert refs
    for r in refs:
        assert chart[r["char_start"]:r["char_end"]] == r["quote"]


def test_scenario_points():
    """scenario.md의 핵심 정답 값 몇 가지."""
    f = {ref: load_case(ref).build()[1]["fields"] for ref in CASES}
    deem = lambda ref: {d["rule_id"]: d["status"] for d in f[ref]["deemed_lines"]}  # noqa: E731
    assert deem("VC-0103")["DEEM-ENDO-ADJ-1Y"] == "met"
    assert deem("VC-0104")["DEEM-SG-1Y"] == "met" and deem("VC-0104")["DEEM-ANTHRA-TAXANE"] == "met"
    assert f["VC-0101"]["receptors"]["pr_percent"]["value"]["allred"]["total"] == 3
    assert f["VC-0101"]["receptors"]["pr_percent"]["history"][0]["value"]["allred"]["total"] == 6
    # ER·PR은 모두 Allred 점수로 적는다 (2026-10-23). 비율(percent)은 쓰지 않는다
    for ref in CASES:
        for k in ("er_percent", "pr_percent"):
            v = f[ref]["receptors"][k].get("value") or {}
            assert "percent" not in v, (ref, k)
    assert f["VC-0101"]["molecular"]["mutations"]["ESR1"]["specimen"] == "cfDNA"
    assert f["VC-0105"]["stage"]["yptnm"]["value"]["t"] == "T1c" and f["VC-0105"]["stage"]["ptnm"]["status"] == "not_recorded"
    assert f["VC-0106"]["proliferation"]["ki67_percent"]["history"][0]["superseded_reason"] == "newer_result"
    assert "ki67_percent" not in f["VC-0106b"]["proliferation"]
    assert f["VC-0108"]["at_index"]["recent_therapy_28d"]["status"] == "yes"
    assert f["VC-0108"]["treatment_history"][0]["ongoing"] is True
    assert f["VC-0109"]["recurrence"]["surgery_intent"]["value"] == "curative"
    assert all(d["status"] == "not_applicable" for d in f["VC-0109"]["deemed_lines"])
