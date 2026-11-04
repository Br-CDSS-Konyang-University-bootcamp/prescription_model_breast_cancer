# tests/recommend/test_run_flow_fixes.py
# A 전달 handoff_recommend_options_to_B_2026-11-03.md §5.3 (46건 run_flow, 후보 0개 사례).
# 청크 글은 모두 지어낸 테스트 문장이다.
from datetime import date

from jsonschema import Draft202012Validator

from src.recommend.llm_link import answer_schema
from src.recommend.pipeline import recommend
from src.recommend.postprocess import postprocess

TODAY = date(2026, 11, 4)
RECORD = {"patient_ref": "T", "subtype": "HR+/HER2-", "setting": {"disease": "early", "line": "adjuvant"},
          "records": [], "tests_needed": []}
PARENT = "esmo-ebc-2024-02-hrpos"
KID1 = {"chunk_id": "esmo-ebc-2024-02-hrpos-aaa111", "doc_type": "guideline", "source": "ESMO-EBC",
        "evidence": {"loe": "I", "gor": "A"}, "drugs": ["tamoxifen"], "parent": {"chunk_id": PARENT, "text": "x"},
        "text": "TEST CHUNK (made up): tamoxifen."}
KID2 = {**KID1, "chunk_id": "esmo-ebc-2024-02-hrpos-bbb222", "drugs": ["letrozole"], "text": "TEST CHUNK: letrozole."}
INDEX_STATUS = {"booklet_date": "2026-11-01", "overlay_notices": [], "scheduled_count": 0, "in_progress_count": 0}


def opt(**kw):
    o = {"therapy": "letrozole", "drugs": ["letrozole"], "rationale": f"권고된다 [{PARENT}].", "citations": [PARENT],
         "reimbursement": "covered", "reimbursement_reason": "", "reimbursement_citations": []}
    o.update(kw)
    return o


def test_answer_schema_accepts_option_with_empty_reimbursement_citations():
    """VC-0110·0114·0116: 급여 분류가 있는데 급여 인용이 비어 답 전체가 버려지던 것."""
    answer = {"options": [opt()], "tests_needed": [], "out_of_scope": False, "conflicts": []}
    assert not list(Draft202012Validator(answer_schema()).iter_errors(answer))
    rec, log, errors = recommend({}, RECORD, [KID1, KID2], [], lambda p: answer, INDEX_STATUS, "fake", TODAY)
    assert errors == [] and rec["options"][0]["reimbursement"] == "no_criteria"   # 최종 결과는 전체 스키마 통과


def test_parent_id_citation_becomes_child_with_option_drug():
    """VC-0134: 부모(소단원) ID를 인용해 후보가 지워지던 것."""
    rec, log = postprocess({"options": [opt()]}, RECORD, [KID1, KID2], [], TODAY)
    o = rec["options"][0]
    assert o["citations"] == [KID2["chunk_id"]] and o["rationale"] == f"권고된다 [{KID2['chunk_id']}]."
    assert any("소단원 ID 인용을 자식 청크로" in m for m in log)


def test_empty_llm_options_logged():
    answer = {"options": [], "tests_needed": [], "out_of_scope": False, "conflicts": []}
    _, log, errors = recommend({}, RECORD, [KID1], [], lambda p: answer, INDEX_STATUS, "fake", TODAY)
    assert errors == [] and "LLM이 후보를 내지 않음 (out_of_scope도 false)" in log
