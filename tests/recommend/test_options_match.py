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


def test_class_name_therapy_not_filled_with_one_drug():
    rec, log = run(option("AI—palbociclib", [], ["r-pal-let"]))
    o = rec["options"][0]
    assert o["drugs"] == [] and o["reimbursement"] == "no_criteria"     # 약을 정하지 못해 급여 행도 맞출 수 없음
    assert any("계열 이름(AI)" in c for c in rec["conflicts"])
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
