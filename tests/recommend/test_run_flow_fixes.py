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



# A 공유 team_report_run_flow_2026-11-05.md §4 B-1·B-2·B-4·B-5
def test_answer_schema_keeps_citation_minimum():
    """B-1: 지침 근거(citations) 1개 이상은 LLM 답 양식에 남긴다 (Ollama가 이 양식대로 쓰게 함)."""
    schema = answer_schema()
    assert schema["properties"]["options"]["items"]["properties"]["citations"].get("minItems") == 1
    assert "minItems" not in schema["properties"]["options"]["items"]["properties"]["reimbursement_citations"]


def test_retry_once_when_all_options_deleted_and_counts_only():
    """B-1: 주 후보가 모두 지워지면 한 번 다시 묻는다. B-2: 답 원문 대신 숫자만 기록한다."""
    seen = []
    no_cite = opt(rationale="근거 없이 권고된다.", citations=[], reimbursement="no_criteria")
    good = opt(rationale=f"권고된다 [{KID2['chunk_id']}].", citations=[KID2["chunk_id"]], reimbursement="no_criteria")

    def llm(prompt):
        seen.append(prompt)
        options = [no_cite] if len(seen) == 1 else [good]
        return {"options": options, "tests_needed": [], "out_of_scope": False, "conflicts": []}
    rec, log, errors = recommend({}, RECORD, [KID1, KID2], [], llm, INDEX_STATUS, "fake", TODAY)
    assert errors == [] and len(seen) == 2 and "[다시 쓰기]" in seen[1] and KID2["chunk_id"] in seen[1]
    assert [o["therapy"] for o in rec["options"]] == ["letrozole"]
    assert "주 후보가 모두 지워져 LLM에 한 번 다시 물음" in log
    counts = [m for m in log if m.startswith("LLM 답:")]
    assert counts[0] == ("LLM 답: 주 후보 1개, citations 칸이 빈 후보 1개, 근거 문장에 [ID]가 없는 후보 1개, "
                         "받은 지침 청크 ID를 하나도 인용하지 않은 후보 1개")
    assert not any("근거 없이 권고된다" in m for m in log)          # 답 내용은 남기지 않음


def test_no_retry_when_some_option_survives():
    calls = []

    def llm(prompt):
        calls.append(1)
        return {"options": [opt(rationale=f"권고된다 [{KID2['chunk_id']}].", citations=[KID2["chunk_id"]],
                                reimbursement="no_criteria")],
                "tests_needed": [], "out_of_scope": False, "conflicts": []}
    recommend({}, RECORD, [KID1, KID2], [], llm, INDEX_STATUS, "fake", TODAY)
    assert len(calls) == 1


def test_duplicate_options_merged():
    """B-4: 약이 같은(약이 없으면 이름이 같은) 후보는 하나로 합친다."""
    a = opt(rationale=f"권고된다 [{KID2['chunk_id']}].", citations=[KID2["chunk_id"]], reimbursement="no_criteria")
    b = {**a, "therapy": "Letrozole"}
    c = opt(therapy="ET alone", drugs=[], rationale=f"권고된다 [{KID1['chunk_id']}].", citations=[KID1["chunk_id"]],
            reimbursement="no_criteria")
    rec, log = postprocess({"options": [a, b, c, dict(c)]}, RECORD, [KID1, KID2], [], TODAY)
    assert [o["therapy"] for o in rec["options"]] == ["letrozole", "ET alone"]
    assert sum("같은 요법이라 앞 후보와 합침" in m for m in log) == 2


def test_cite_received_chunk_with_the_drug():
    """B-5: 인용한 청크에 약이 없지만 받은 다른 청크에 있으면 그 청크를 근거에 더한다 (VC-0127)."""
    o = opt(rationale=f"권고된다 [{KID1['chunk_id']}].", citations=[KID1["chunk_id"]], reimbursement="no_criteria")
    rec, log = postprocess({"options": [o]}, RECORD, [KID1, KID2], [], TODAY)
    assert rec["options"][0]["citations"] == [KID1["chunk_id"], KID2["chunk_id"]]
    assert any("그 약이 든 받은 청크를 근거에 더함" in m for m in log)
