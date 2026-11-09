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
    # B-10: 약이 없는 KID1 인용은 빠지고, 문장 안 인용도 약이 든 KID2로 바뀐다
    assert rec["options"][0]["citations"] == [KID2["chunk_id"]]
    assert rec["options"][0]["rationale"] == f"권고된다 [{KID2['chunk_id']}]."
    assert any("그 약이 든 받은 청크를 근거에 더함" in m for m in log)


# A 공유 2026-11-05 §6.4 B-8·B-9·B-10·B-11
EARLY_REC = {"patient_ref": "T", "subtype": "HR+/HER2-", "setting": {"disease": "early", "line": "adjuvant"},
             "records": [{"marker": "gBRCA1", "status": "positive", "reason": "테스트"}], "tests_needed": []}
ABE = {**KID1, "chunk_id": "esmo-ebc-hrpos-abe", "drugs": ["abemaciclib", "letrozole"], "text": "TEST: abemaciclib + ET."}
OLA = {**KID1, "chunk_id": "esmo-ebc-hrpos-ola", "drugs": ["olaparib"], "text": "TEST: adjuvant olaparib."}
BIS = {**KID1, "chunk_id": "esmo-ebc-hrpos-bis", "drugs": ["zoledronic acid", "clodronate"],
       "text": "TEST: adjuvant bisphosphonates."}


def test_neoadjuvant_drops_post_surgery_drugs_and_low_risk_drops_abemaciclib():
    """B-11: 선행 결정에는 수술 뒤 약을 내지 않고, 고위험이 아니면 abemaciclib을 내지 않는다."""
    o_abe = opt(therapy="abemaciclib + letrozole", drugs=["abemaciclib", "letrozole"],
                rationale=f"권고된다 [{ABE['chunk_id']}].", citations=[ABE["chunk_id"]], reimbursement="no_criteria")
    o_ola = opt(therapy="olaparib", drugs=["olaparib"], rationale=f"권고된다 [{OLA['chunk_id']}].",
                citations=[OLA["chunk_id"]], reimbursement="no_criteria")
    o_ext = opt(therapy="Extended ET beyond 5 years", drugs=[], rationale=f"권고된다 [{KID1['chunk_id']}].",
                citations=[KID1["chunk_id"]], reimbursement="no_criteria")
    o_let = opt(rationale=f"권고된다 [{KID2['chunk_id']}].", citations=[KID2["chunk_id"]], reimbursement="no_criteria")
    chunks = [KID1, KID2, ABE, OLA]
    rec, log = postprocess({"options": [o_abe, o_ola, o_ext, o_let]}, EARLY_REC, chunks, [], TODAY, phase="neoadjuvant")
    assert [o["therapy"] for o in rec["options"]] == ["letrozole"]
    assert sum("선행요법 결정이라" in m for m in log) == 3
    rec, log = postprocess({"options": [o_abe, o_let]}, EARLY_REC, chunks, [], TODAY, phase="adjuvant",
                           high_risk_early={"hira": "no", "esmo": "no"})
    assert [o["therapy"] for o in rec["options"]] == ["letrozole"] and any("고위험 조기" in m for m in log)
    rec, _ = postprocess({"options": [o_abe]}, EARLY_REC, chunks, [], TODAY, phase="adjuvant",
                         high_risk_early={"hira": "yes", "esmo": "yes"})
    assert [o["therapy"] for o in rec["options"]] == ["abemaciclib + letrozole"]


def test_unrelated_bisphosphonate_citation_dropped_and_supportive_purity():
    """B-10: 골 보호제가 아닌 후보의 골 보호제 청크 인용은 빼고, 보조 칸에 내분비요법이 섞이면 지운다."""
    o = opt(therapy="ET alone", drugs=[], rationale=f"권고된다 [{KID1['chunk_id']}]. 뼈도 본다 [{BIS['chunk_id']}].",
            citations=[KID1["chunk_id"], BIS["chunk_id"]], reimbursement="no_criteria")
    mixed = opt(therapy="ET + bisphosphonate", drugs=[], rationale=f"권고된다 [{BIS['chunk_id']}].",
                citations=[BIS["chunk_id"]], reimbursement="no_criteria")
    rec, log = postprocess({"options": [o], "supportive_options": [mixed]}, EARLY_REC, [KID1, BIS], [], TODAY,
                           phase="adjuvant")
    assert rec["options"][0]["citations"] == [KID1["chunk_id"]]
    assert rec["options"][0]["rationale"] == f"권고된다 [{KID1['chunk_id']}]."
    assert rec["supportive_options"] == [] and any("보조 약물 칸에는 골 보호제만" in m for m in log)


def test_prompt_has_phase_risk_deemed_and_positive_markers():
    """B-8·B-9·B-11: 수술 전후, 위험도, 간주 규칙, 양성 바이오마커를 질문지에 넣는다."""
    from src.recommend.prompt import build_prompt
    confirmed = {"items": {"setting.phase": {"confirmed": "adjuvant"},
                           "high_risk_early": {"confirmed": {"hira": "no", "esmo": "no"}},
                           "deemed_lines": {"confirmed": {"DEEM-HER2ADC-6M": "met", "DEEM-SG-1Y": "not_met"}}}}
    text = build_prompt({}, EARLY_REC, [KID1], [], confirmed)
    assert '"phase": "adjuvant"' in text and '"esmo": "no"' in text
    assert '"deemed_lines_met": ["DEEM-HER2ADC-6M"]' in text and '"positive_markers": ["gBRCA1"]' in text
    assert "DEEM-HER2ADC-6M이 있으면" in text and "PARP 억제제" in text



def test_class_name_option_gets_class_rows_and_unverified():
    """B-12 (D 의견 2026-11-05, VC-0118): 'systemic ChT'처럼 약을 정하지 않은 후보는 항암제만으로 된 급여 행을 붙이고
    '급여(약 확인 필요)'. 내분비·표적 약이 섞인 행은 붙이지 않는다."""
    chemo = {**KID1, "chunk_id": "esmo-ebc-tnbc-cht", "drugs": [], "text": "TEST: systemic ChT for 6-8 cycles."}

    def row(cid, drugs):
        return {"chunk_id": cid, "doc_type": "reimbursement", "source": "HIRA-booklet", "drugs": drugs, "text": "지어낸 행",
                "reimbursement": {"source_type": "baseline", "notice_no": "x", "effective_from": "2026-11-01"}}
    rows = [row("adj-r10-ac", ["doxorubicin", "cyclophosphamide"]), row("adj-r17-tc", ["docetaxel", "cyclophosphamide"]),
            row("adj-r01-ana", ["anastrozole"]), row("pal-tras", ["paclitaxel", "trastuzumab"])]
    o = opt(therapy="6-8 cycles systemic ChT", drugs=[], rationale=f"권고된다 [{chemo['chunk_id']}].",
            citations=[chemo["chunk_id"]], reimbursement="no_criteria")
    rec, log = postprocess({"options": [o]}, RECORD, [chemo], rows, TODAY)
    out = rec["options"][0]
    assert out["reimbursement"] == "covered_conditions_unverified"
    assert out["reimbursement_citations"] == ["adj-r10-ac", "adj-r17-tc"]
    assert out["reimbursement_reason"].startswith("약 확인 필요 (관련 급여 요법 2개)")


# B·C 합의 (2026-11-05): 안전 검사 ③·⑥, 수술 후 bisphosphonate 보조 칸(B-6), 약 확인 필요 개수(B-12)
from src.recommend.safety import safety_violations

HER2_REC = {"patient_ref": "T", "subtype": "HR-/HER2+", "setting": {"disease": "metastatic", "line": "1L"},
            "records": [{"marker": "HER2", "status": "positive", "reason": "t"}], "tests_needed": []}


def her2_opt(drugs):
    return {"therapy": " + ".join(drugs), "drugs": drugs, "rationale": "권고 [x].", "citations": ["x"]}


def test_safety_trastuzumab_continuation_and_early_relapse():
    progressed = {"index_day": 900, "fields": {"treatment_history": [
        {"drugs": ["docetaxel", "trastuzumab", "pertuzumab"], "setting": "palliative", "start_day": 100,
         "stop_reason": "progression"}]}}
    rules = lambda rec, ps: [v["rule"] for v in safety_violations(rec, HER2_REC, ps)]
    # 새 짝 약과 trastuzumab을 이어 쓰면 위반 아님, 같은 요법 반복은 위반
    assert rules({"options": [her2_opt(["tucatinib", "trastuzumab", "capecitabine"])]}, progressed) == []
    assert rules({"options": [her2_opt(["trastuzumab", "pertuzumab"])]}, progressed) == ["progressed_drug_again"]
    early = {"index_day": 500, "fields": {
        "deemed_lines": [{"rule_id": "DEEM-HER2ADC-6M", "status": "met"}],
        "treatment_history": [
            {"drugs": ["paclitaxel", "trastuzumab"], "setting": "adjuvant", "start_day": 10, "stop_reason": "planned_switch"},
            {"drugs": ["trastuzumab"], "setting": "adjuvant", "start_day": 100, "stop_reason": "completed"}]}}
    assert rules({"options": [her2_opt(["paclitaxel", "trastuzumab"])]}, early) == ["early_relapse_same_her2_regimen"]
    assert rules({"options": [her2_opt(["trastuzumab deruxtecan"])]}, early) == []
    no_deem = {**early, "fields": {**early["fields"], "deemed_lines": []}}
    assert rules({"options": [her2_opt(["paclitaxel", "trastuzumab"])]}, no_deem) == []


def test_early_bisphosphonate_fill_conditions():
    """B-6: 수술 후 + HR+/HER2- + (폐경 후 또는 OFS)면 bisphosphonate 청크로 보조 칸을 채운다."""
    rec_hr = {**RECORD, "subtype": "HR+/HER2-", "setting": {"disease": "early", "line": "adjuvant"}}
    bis = {**KID1, "chunk_id": "esmo-ebc-hrpos-bis", "setting": ["early"], "drugs": ["zoledronic acid", "clodronate"],
           "text": "TEST: bisphosphonates such as zoledronic acid."}
    let = opt(rationale=f"권고된다 [{KID2['chunk_id']}].", citations=[KID2["chunk_id"]], reimbursement="no_criteria")

    def sup(**kw):
        rec, _ = postprocess({"options": [dict(let)]}, rec_hr, [KID1, KID2, bis], [], TODAY, **kw)
        return [o["therapy"] for o in rec["supportive_options"]]
    filled = ["zoledronic acid", "bisphosphonates 계열 (clodronate 중 하나)"]
    assert sup(phase="adjuvant", menopausal="postmenopausal") == filled
    assert sup(phase="adjuvant", menopausal="premenopausal", ofs=True) == filled
    assert sup(phase="adjuvant", menopausal="premenopausal") == []           # 폐경 전, OFS 없음
    assert sup(phase="neoadjuvant", menopausal="postmenopausal") == []       # 선행 결정
    rec, _ = postprocess({"options": [dict(let)]}, {**rec_hr, "subtype": "HR+/HER2+"}, [KID1, KID2, bis], [], TODAY,
                         phase="adjuvant", menopausal="postmenopausal")
    assert rec["supportive_options"] == []                                    # v0.1은 HR+/HER2-만
