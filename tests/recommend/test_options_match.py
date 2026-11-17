# tests/recommend/test_options_match.py
# A 전달 src/input/handoff_recommend_options_to_B_2026-11-03.md: 약이 다른 급여 행 인용, 계열 이름만 있는 후보.
# 청크 글은 모두 지어낸 테스트 문장이다 (지침·공고 원문을 옮기지 않는다).
from datetime import date

from src.recommend.postprocess import postprocess
from src.recommend.safety import safety_violations

TODAY = date(2026, 11, 3)
G = {"chunk_id": "g1", "doc_type": "guideline", "source": "ESMO-MBC", "evidence": {"loe": "I", "gor": "A"},
     "drugs": ["fulvestrant", "palbociclib", "ribociclib", "abemaciclib", "letrozole", "anastrozole"],
     "text": "TEST CHUNK (made up): fulvestrant plus a CDK4/6 inhibitor; AI plus a CDK4/6 inhibitor."}


def row(cid, drugs):
    return {"chunk_id": cid, "doc_type": "reimbursement", "source": "HIRA-booklet", "drugs": drugs, "text": "지어낸 행",
            "reimbursement": {"source_type": "baseline", "notice_no": "x", "effective_from": "2026-11-01"}}


ROWS = [row("r-pal-fulv", ["palbociclib", "fulvestrant"]), row("r-ribo-fulv", ["ribociclib", "fulvestrant"]),
        row("r-pal-let", ["palbociclib", "letrozole"])]
RECORD = {"subtype": "HR+/HER2-", "setting": {"disease": "metastatic"}, "records": []}


def option(therapy, drugs, cites):
    return {"therapy": therapy, "drugs": drugs, "rationale": "권고된다 [g1].", "citations": ["g1"],
            "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "",
            "reimbursement_citations": cites}


def run(*options):
    return postprocess({"options": list(options)}, RECORD, [G], ROWS, TODAY)


def test_rows_with_other_drugs_removed_and_matching_row_attached():
    rec, log = run(option("fulvestrant + ribociclib", ["fulvestrant", "ribociclib"], ["r-pal-fulv", "r-pal-let"]))
    o = rec["options"][0]
    assert o["reimbursement_citations"] == ["r-ribo-fulv"] and o["reimbursement"] == "covered_conditions_unverified"
    assert any("약이 다른 급여 행 인용 삭제" in m for m in log) and any("붙임" in m for m in log)


def test_no_matching_row_is_no_criteria():
    rec, _ = run(option("fulvestrant + abemaciclib", ["fulvestrant", "abemaciclib"], ["r-pal-fulv"]))
    o = rec["options"][0]
    assert o["reimbursement"] == "no_criteria" and o["reimbursement_citations"] == []
    assert "맞는 시행 중인 급여 행 없음" in o["reimbursement_reason"]


def test_class_name_therapy():
    """계열 이름(ET, AI)이 있으면 약을 비워 두고 표시한다 (A 전달 2026-11-03 규칙 7)."""
    rec, log = run(option("ET alone", [], ["r-pal-let"]))
    o = rec["options"][0]
    assert o["drugs"] == [] and o["reimbursement"] == "covered_conditions_unverified"   # 인용 행은 그대로, 판정 안 함
    assert o["reimbursement_citations"] == ["r-pal-let"] and "후보 약을 정하지 못해" in o["reimbursement_reason"]
    assert any("계열 이름(ET)" in c for c in rec["conflicts"])
    rec, _ = run(option("AI—palbociclib", [], ["r-pal-let"]))
    o = rec["options"][0]
    assert o["drugs"] == [] and any("계열 이름(AI)" in c for c in rec["conflicts"])   # AI는 펼치지 않음 (D 취소 11-04)
    rec, _ = run(option("fulvestrant + palbociclib", [], []))
    assert rec["options"][0]["drugs"] == ["fulvestrant", "palbociclib"]  # 약 이름만 있으면 그대로 채움


def test_safety_flags_same_ai_subclass_after_progression():
    ps = {"index_day": 900, "fields": {"treatment_history": [
        {"drugs": ["anastrozole"], "setting": "adjuvant", "start_day": 100, "stop_reason": "progression"}]}}
    def violations(therapy, drugs):
        rec = {"options": [{**option(therapy, drugs, []), "citations": ["g1"]}]}
        return [v["rule"] for v in safety_violations(rec, RECORD, ps)]
    assert violations("letrozole + palbociclib", ["letrozole", "palbociclib"]) == ["progressed_drug_again"]
    assert violations("AI—palbociclib", []) == ["progressed_drug_again"]       # 계열 이름만 있어도
    assert violations("exemestane + everolimus", ["exemestane", "everolimus"]) == []   # 스테로이드성 AI는 다른 세부 계열
    assert violations("fulvestrant + palbociclib", ["fulvestrant", "palbociclib"]) == []


def test_exact_drug_rows_first():
    """D 요청 (2026-11-04): 약이 똑같은 행이 있으면 약이 더 든 행은 쓰지 않는다. 없을 때만 약이 더 든 행."""
    rows = [row("r-pac", ["paclitaxel"]), row("r-pac-pem", ["paclitaxel", "pembrolizumab"]),
            row("r-pac-tras", ["paclitaxel", "trastuzumab"])]
    g = {**G, "drugs": G["drugs"] + ["paclitaxel"]}
    o = option("paclitaxel", ["paclitaxel"], ["r-pac-pem"])
    rec, log = postprocess({"options": [o]}, RECORD, [g], rows, TODAY)
    assert rec["options"][0]["reimbursement_citations"] == ["r-pac"]
    rec, _ = postprocess({"options": [option("paclitaxel", ["paclitaxel"], [])]}, RECORD, [g], rows[1:], TODAY)
    assert rec["options"][0]["reimbursement_citations"] == ["r-pac-pem", "r-pac-tras"]   # 똑같은 행이 없을 때


def test_empty_drugs_without_cited_row_is_no_criteria():
    rec, _ = run(option("ET alone", [], []))
    assert rec["options"][0]["reimbursement"] == "no_criteria"


def test_lhrh_agonist_expanded_to_goserelin_leuprolide():
    """D 요청 (2026-11-04): "LHRH agonist"를 goserelin·leuprolide로 펼쳐 급여 행과 맞춘다."""
    g = {**G, "drugs": G["drugs"] + ["goserelin", "leuprolide"]}
    rows = [row("r-ana-lhrh", ["anastrozole", "goserelin", "leuprolide"])]
    for therapy in ("anastrozole + LHRH agonist", "Anastrozole + OFS", "anastrozole with ovarian function suppression"):
        rec, log = postprocess({"options": [option(therapy, [], [])]}, RECORD, [g], rows, TODAY)
        o = rec["options"][0]
        assert o["drugs"] == ["anastrozole", "goserelin", "leuprolide"], therapy
        assert o["reimbursement_citations"] == ["r-ana-lhrh"] and not rec["conflicts"]
    rec, _ = postprocess({"options": [option("ET + LHRH agonist", [], [])]}, RECORD, [g], rows, TODAY)
    assert rec["options"][0]["drugs"] == []                     # 넓은 계열(ET)이 남아 있으면 그대로 약 미정


def test_named_drug_kept_even_if_not_in_chunk_drugs_and_reason_is_rule_only():
    """D 확인 (2026-11-04): 청크 drugs에 없더라도 요법 이름의 약은 남기고, 급여 이유는 판정기 문장만."""
    g = {**G, "drugs": ["goserelin", "leuprolide"], "text": "TEST CHUNK (made up): anastrozole plus OFS."}
    rows = [row("r-ana", ["anastrozole", "goserelin", "leuprolide"]), row("r-let", ["letrozole", "goserelin", "leuprolide"])]
    o = {**option("anastrozole + LHRH agonist", [], []), "reimbursement_reason": "조건 확인 불가"}
    rec, _ = postprocess({"options": [o]}, RECORD, [g], rows, TODAY,
                         lambda opt, chunks: {"status": "met", "reason": "조건 충족 (r-ana)"})
    out = rec["options"][0]
    assert out["drugs"] == ["anastrozole", "goserelin", "leuprolide"] and out["reimbursement_citations"] == ["r-ana"]
    assert out["reimbursement"] == "covered" and out["reimbursement_reason"] == "조건 충족 (r-ana)"


def combo_row(cid, drugs, added, coverage, stage="combination"):
    r = row(cid, drugs)
    r["reimbursement"] = {**r["reimbursement"], "stage": stage,
                          "combination": {"added_drug": added, "added_drug_coverage": coverage, "base_regimen": []}}
    return r


def test_combination_row_needs_added_drug_and_shows_nonpaid():
    """D 요청 (2026-11-04): 추가 약제가 없는 후보에 병용 행을 쓰지 않고(VC-0108), 비급여 추가 약제는 이유에 적는다(VC-0122)."""
    g = {**G, "drugs": G["drugs"] + ["inavolisib"]}
    rows = [combo_row("r-ina", ["inavolisib", "palbociclib", "fulvestrant"], ["inavolisib"], "비급여")]
    rec, _ = postprocess({"options": [option("fulvestrant + palbociclib", ["fulvestrant", "palbociclib"], ["r-ina"])]},
                         RECORD, [g], rows, TODAY, lambda o, c: {"status": "met", "reason": "조건 충족"})
    assert rec["options"][0]["reimbursement"] == "no_criteria"   # inavolisib 행은 맞지 않음
    rec, _ = postprocess({"options": [option("inavolisib + palbociclib + fulvestrant",
                                             ["inavolisib", "palbociclib", "fulvestrant"], [])]},
                         {**RECORD, "records": [{"marker": "PIK3CA", "status": "positive"}]}, [g], rows, TODAY,
                         lambda o, c: {"status": "met", "reason": "조건 충족 (r-ina)"})
    o = rec["options"][0]
    assert o["reimbursement"] == "covered" and o["reimbursement_citations"] == ["r-ina"]
    assert o["reimbursement_reason"].startswith("inavolisib 비급여 + palbociclib·fulvestrant 급여")


def test_added_drug_rule_only_for_chapter_40():
    """D 확인 (2026-11-05, VC-0133): 9장 보조요법 행의 각주 추가 약(abemaciclib)은 행을 막지 않는다."""
    g = {**G, "drugs": G["drugs"] + ["tamoxifen", "abemaciclib"]}
    adj = combo_row("r09-adj", ["tamoxifen"], ["abemaciclib"], "100/100", stage="adjuvant")
    rec, _ = postprocess({"options": [option("tamoxifen", ["tamoxifen"], [])]}, RECORD, [g], [adj], TODAY)
    assert rec["options"][0]["reimbursement_citations"] == ["r09-adj"]


def test_no_row_reason_is_rule_text_even_if_llm_said_no_criteria():
    """D #157 (2026-11-17): 맞는 급여 행이 없으면 LLM이 처음부터 no_criteria라고 써도 규칙 문구로 통일한다.
    약이 있는 후보(VC-0121 'Tamoxifen alone')와 계열 이름 후보(VC-0121 'Adjuvant Endocrine Therapy (ET)') 모두."""
    from src.recommend.postprocess import NO_CLASS_ROW_REASON, NO_ROW_REASON
    llm = {"reimbursement": "no_criteria", "reimbursement_reason": "No reimbursement criteria found for this therapy."}
    rec, _ = run({**option("anastrozole", ["anastrozole"], []), **llm})
    o = rec["options"][0]
    assert (o["reimbursement"], o["reimbursement_reason"], o["reimbursement_citations"]) == ("no_criteria", NO_ROW_REASON, [])
    assert "비급여로 확정한 것은 아님" in o["reimbursement_reason"]
    rec, _ = run({**option("Adjuvant Endocrine Therapy (ET)", [], []), **llm})
    o = rec["options"][0]
    assert (o["reimbursement"], o["reimbursement_reason"]) == ("no_criteria", NO_CLASS_ROW_REASON)
    # 계열 이름 후보가 시행 중인 급여 행을 인용했으면 LLM이 no_criteria라고 했어도 조건 확인 필요
    rec, _ = run({**option("ET alone", [], ["r-pal-let"]), **llm})
    assert rec["options"][0]["reimbursement"] == "covered_conditions_unverified"


def test_narrow_class_candidates_and_basis():
    """좁은 계열(AI)을 인용 청크에 있는 약으로 펼쳐 조합마다 급여를 판정한다 (2026-11-17). 후보 drugs는 비운 채,
    급여는 가장 나은 조합. G의 drugs에 AI는 anastrozole·letrozole만 있어 exemestane은 펼치지 않는다."""
    rec, log = run(option("AI—palbociclib", [], []))
    o = rec["options"][0]
    assert o["drugs"] == [] and o["reimbursement_basis"] == "drug_undetermined"
    cands = {tuple(sorted(c["drugs"])): c for c in o["candidates"]}
    assert set(cands) == {("letrozole", "palbociclib"), ("anastrozole", "palbociclib")}
    let = cands[("letrozole", "palbociclib")]
    assert let["reimbursement_citations"] == ["r-pal-let"] and let["reimbursement_basis"] == "conditions_unverified"
    ana = cands[("anastrozole", "palbociclib")]
    assert (ana["reimbursement"], ana["reimbursement_basis"]) == ("no_criteria", "no_matching_row")
    assert o["reimbursement"] == "covered_conditions_unverified" and o["reimbursement_citations"] == ["r-pal-let"]
    assert any("약 조합 2개로 펼쳐" in m for m in log)
    # 넓은 계열(ET)이 섞이면 펼치지 않는다
    rec, _ = run(option("ET + CDK4/6 inhibitor", [], []))
    assert "candidates" not in rec["options"][0]


def test_basis_splits_no_criteria():
    """no_criteria를 '맞는 행 없음'과 '조건 불충족'으로 나눈다 (reimbursement_basis)."""
    rec, _ = run(option("fulvestrant + abemaciclib", ["fulvestrant", "abemaciclib"], ["r-pal-fulv"]))
    assert rec["options"][0]["reimbursement_basis"] == "no_matching_row"
    rec, _ = postprocess({"options": [option("letrozole + palbociclib", ["letrozole", "palbociclib"], [])]}, RECORD, [G], ROWS,
                         TODAY, lambda o, rows: {"status": "not_met", "reason": "r-pal-let 불충족: 폐경 후"})
    o = rec["options"][0]
    assert (o["reimbursement"], o["reimbursement_basis"]) == ("no_criteria", "conditions_not_met")


def test_narrow_class_or_is_alternative():
    """계열 사이 'or'는 둘 중 하나라 조합으로 곱하지 않고, 시험약(tesetaxel)은 넣지 않는다 (20261117 VC-0113)."""
    from src.recommend.postprocess import _narrow_candidates
    cands = _narrow_candidates({"therapy": "Rechallenge with anthracyclines or taxanes", "drugs": []}, [], {}, TODAY, None)
    assert cands and all(len(c["drugs"]) == 1 for c in cands)
    names = {c["drugs"][0] for c in cands}
    assert {"doxorubicin", "paclitaxel"} <= names and "tesetaxel" not in names
