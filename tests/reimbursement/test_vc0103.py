"""가상 차트 VC-0103 급여 기대값 (tests/reimbursement/fixtures/vc0103_expected.json).

보조 anastrozole 중 폐 전이, 전이 후 1차 내분비 치료 결정. 기대 판정: CDK4/6 + fulvestrant(2차 이상)과 fulvestrant 단독은 급여,
CDK4/6 + AI(1차)와 변이가 필요한 병용요법은 아님. 판정은 B가 하므로 여기서는 D 청크가 그 판정에 필요한 조건·태그를 갖췄는지 본다.
공고 가공물(청크 파일)은 git에 없으므로 청크 검사는 파일이 있을 때만 돈다.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASE = json.loads((Path(__file__).parent / "fixtures" / "vc0103_expected.json").read_text(encoding="utf-8"))
CHUNKS = ROOT / "data" / "reimbursement" / "chunks" / "reimbursement_chunks_current.jsonl"


def _chunks():
    if not CHUNKS.exists():
        pytest.skip("급여 청크 파일 없음 (공고 가공물이라 git에 없음)")
    with open(CHUNKS, encoding="utf-8") as f:
        return {c["chunk_id"]: c for c in map(json.loads, f)}


def _items(cond):
    def walk(xs):
        for x in xs:
            if "items" in x:
                yield from walk(x["items"])
            elif "field" in x:
                yield x
                if x.get("unless"):
                    yield x["unless"]
            elif "all_of" in x:
                yield from walk(x["all_of"])
    for key in ("all_of", "any_of", "any_of_exceptions", "stage_rules"):
        yield from walk(cond.get(key) or [])


def test_patient_matches_input_fixture():
    """기대값의 환자 값이 A의 기대 patient_state(VC-0103)와 같다. 차트나 A 출력이 바뀌면 여기서 먼저 알 수 있다."""
    ps = json.loads((ROOT / CASE["sources"]["patient_state"]).read_text(encoding="utf-8"))["fields"]
    p = CASE["patient"]
    assert ps["patient"]["menopausal_status"]["value"] == p["menopausal_status"]
    assert ps["recurrence"]["status"]["value"] == p["recurrence"]
    assert ps["recurrence"]["metastasis_day"]["value"] == p["metastasis_day"]
    adj = [t for t in ps["treatment_history"] if t.get("setting") == "adjuvant"]
    assert [t["drugs"] for t in adj] == [p["adjuvant_endocrine"]["drugs"]]
    assert (adj[0]["start_day"], adj[0]["end_day"]) == (p["adjuvant_endocrine"]["start_day"], p["adjuvant_endocrine"]["end_day"])
    assert all(not t.get("endocrine_line") and not t.get("chemo_line") for t in ps["treatment_history"])
    deemed = {d["rule_id"]: d["status"] for d in ps.get("deemed_lines") or []}
    assert deemed["DEEM-ENDO-ADJ-1Y"] == p["deemed"]["DEEM-ENDO-ADJ-1Y"]
    mut = ps["molecular"]["mutations"]
    assert all(mut[g]["result"] == "not_detected" for g in p["markers"])
    chart = (ROOT / CASE["sources"]["chart"]).read_text(encoding="utf-8")
    assert all(q in chart for q in p["chart_quotes"])


def test_expected_rows_point_to_current_chunks():
    """기대 행의 쪽·공고 번호·요법이 지금 청크와 같다 (책자가 바뀌면 기대값을 다시 본다)."""
    chunks = _chunks()
    for e in CASE["expected"]:
        c = chunks[e["chunk_id"]]
        assert [c["page_start"], c["page_end"]] == e["page"], e["chunk_id"]
        assert c["reimbursement"]["notice_no"] == e["notice_no"], e["chunk_id"]
        assert c["reimbursement"]["regimen"][0] == e["regimen"], e["chunk_id"]


def test_search_tags_include_and_exclude():
    """전이성 검색에 기대 행은 들어오고, 수술 뒤 ribociclib 보조요법 행(병용 25~28)은 섞이지 않는다."""
    chunks = _chunks()
    drugs = set(CASE["search"]["drugs"])
    for cid in CASE["search"]["must_include"]:
        c = chunks[cid]
        assert "metastatic" in c["setting"] and drugs & set(c["drugs"]), cid
    for cid in CASE["search"]["must_exclude"]:
        assert "metastatic" not in chunks[cid]["setting"], cid


def test_condition_texts_quote_notice():
    """기대 행의 조건 문구가 모두 그 행의 공고 원문에 그대로 있다. 원문은 행 청크 text와 부모(소단원 머리 규칙, 예:
    3. 고식적 내분비요법의 'CDK4/6 + AI는 고식적 항암 미투여자만'), 병합 칸이면 위 행이다."""
    import re

    chunks = _chunks()
    flat = lambda s: re.sub(r"\s+", "", s)                      # noqa: E731  줄바꿈 위치만 다를 수 있다
    for e in CASE["expected"]:
        c = chunks[e["chunk_id"]]
        cond = c["reimbursement"]["conditions"]
        source, parent = flat(c["text"]), c.get("parent_id")
        while parent in chunks:
            source += flat(chunks[parent]["text"])
            parent = chunks[parent].get("parent_id")
        inherited = c["reimbursement"].get("conditions_inherited_from")
        if inherited:                                           # '(위 연번과 같음)' 행은 위 행의 원문에서 조건을 물려받는다
            source += flat(chunks[e["chunk_id"].rsplit("-", 1)[0] + "-" + inherited]["text"])
        texts = [x["text"] for x in _items(cond)]
        texts += [g["text"] for k in ("any_of", "any_of_exceptions", "counts_as_prior_line") for g in cond.get(k) or []]
        missing = [t for t in texts if flat(t) not in source]
        assert missing == [], (e["chunk_id"], missing)


def test_conditions_support_expected_judgment():
    """기대 판정에 필요한 조건이 D 청크에 있다."""
    chunks = _chunks()
    for e in CASE["expected"]:
        cond = chunks[e["chunk_id"]]["reimbursement"]["conditions"]
        items = list(_items(cond))
        need = e["needs"]
        if need == "ai_exclusion_1y_after":
            # 보조 AI를 썼으면 '종료 1년 이후 재발'만 인정 (3가는 A 답변대로 전이 기준일까지)
            it = next(x for x in items if x["field"] == "prior_drugs" and x["op"] == "not_contains"
                      and "AI_nonsteroidal" in x["value"])
            assert it["unless"]["field"] == "days_end_to_metastasis" and it["unless"]["op"] == "gt" and it["unless"]["value"] == 365
            assert cond["line_rule"] == {"stage": "palliative_endocrine", "line": "1차"}
        elif need == "line_1_plus":
            assert cond["line_rule"] == {"stage": "palliative_endocrine", "line": "1차 이상"}
        elif need == "endo_deem_2l":
            # 보조 내분비 중·종료 1년 이내 진행이면 1차를 받은 것으로 간주 -> 전이 후 첫 내분비 치료도 '2차 이상' 대상
            assert cond["line_rule"] == {"stage": "palliative_endocrine", "line": "2차 이상"}
            assert any(x.get("rule_id") == "DEEM-ENDO-ADJ-1Y" for x in cond["counts_as_prior_line"])
            assert any(x["field"] == "days_end_to_metastasis" and x["op"] == "lte" and x["value"] == 365 for x in items)
            assert any(x["field"] == "prior_drugs" and x["op"] == "not_contains" and "CDK4/6_inhibitor" in x["value"]
                       for x in items)
        elif need == "mutation_required":
            assert any(x["field"] == "pik3ca" and x["op"] == "eq" and x["value"] == "positive" for x in items)
        else:
            pytest.fail(f"알 수 없는 needs: {need}")
