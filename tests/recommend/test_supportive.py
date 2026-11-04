# tests/recommend/test_supportive.py
# 골 보호제는 보조 약물 칸(supportive_options)으로 (팀 안건 A src/input/team_agenda_A_2026-11-04.md, 2026-11-04).
# 청크 글은 모두 지어낸 테스트 문장이다 (지침·공고 원문을 옮기지 않는다).
from datetime import date

from src.recommend.pipeline import recommend
from src.recommend.postprocess import postprocess
from src.recommend.safety import safety_violations

TODAY = date(2026, 11, 4)
RECORD = {"patient_ref": "T", "subtype": "HR+/HER2-", "setting": {"disease": "metastatic", "line": "1L"},
          "records": [], "tests_needed": []}
LUM = {"chunk_id": "esmo-mbc-luminal-1l-x", "doc_type": "guideline", "source": "ESMO-MBC",
       "evidence": {"loe": "I", "gor": "A"}, "drugs": ["letrozole", "palbociclib", "trastuzumab deruxtecan"],
       "text": "TEST CHUNK (made up): letrozole plus palbociclib."}
BONE = {"chunk_id": "esmo-mbc-2026-05-site-bone-087674", "doc_type": "guideline", "source": "ESMO-MBC",
        "evidence": {"loe": "I", "gor": "A"}, "drugs": ["denosumab", "zoledronic acid"],
        "text": "TEST CHUNK (made up): bone-modifying agents for bone metastases."}
EARLY = {"chunk_id": "esmo-ebc-hrpos-fca2a7", "doc_type": "guideline", "source": "ESMO-EBC",
         "evidence": {"loe": "I", "gor": "A"}, "drugs": ["zoledronic acid"],
         "text": "TEST CHUNK (made up): adjuvant bisphosphonates."}


def row(cid, drugs):
    return {"chunk_id": cid, "doc_type": "reimbursement", "source": "HIRA-booklet", "drugs": drugs, "text": "지어낸 행",
            "reimbursement": {"source_type": "baseline", "notice_no": "x", "effective_from": "2026-11-01"}}


ROWS = [row("supp-denosumab-1", ["denosumab"]), row("supp-zoledronic-a", ["zoledronic acid"])]


def opt(therapy, drugs, cid):
    return {"therapy": therapy, "drugs": drugs, "rationale": f"권고된다 [{cid}].", "citations": [cid],
            "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "", "reimbursement_citations": []}


def test_bma_in_main_moves_to_supportive():
    """VC-0113: 주 후보 1위가 골 보호제였던 사례."""
    rec, log = postprocess({"options": [opt("Denosumab", ["denosumab"], BONE["chunk_id"]),
                                        opt("letrozole + palbociclib", ["letrozole", "palbociclib"], LUM["chunk_id"])]},
                           RECORD, [LUM, BONE], ROWS, TODAY, bone_metastasis=True)
    assert [o["therapy"] for o in rec["options"]] == ["letrozole + palbociclib"]
    assert [o["drugs"] for o in rec["supportive_options"]] == [["denosumab"], ["zoledronic acid"]]
    assert rec["supportive_options"][0]["reimbursement_citations"] == ["supp-denosumab-1"]
    assert any("보조 약물 칸으로 옮김" in m for m in log)


def test_bone_chunk_fills_supportive_when_llm_skips_it():
    """VC-0108: 추천 5개가 모두 CDK4/6 병용이고 골 보호제가 빠짐."""
    rec, log = postprocess({"options": [opt("letrozole + palbociclib", ["letrozole", "palbociclib"], LUM["chunk_id"])]},
                           RECORD, [LUM, BONE], ROWS, TODAY, bone_metastasis=True)
    assert len(rec["options"]) == 1
    sup = rec["supportive_options"]
    assert [o["therapy"] for o in sup] == ["denosumab", "zoledronic acid"]
    assert sup[0]["citations"] == [BONE["chunk_id"]] and sup[0]["rationale"].endswith(f"[{BONE['chunk_id']}].")
    # 뼈 전이가 아니면 규칙으로 채우지 않는다
    rec, _ = postprocess({"options": []}, RECORD, [LUM, BONE], ROWS, TODAY, bone_metastasis=False)
    assert rec["supportive_options"] == []


def test_supportive_checks_and_neoadjuvant_drop():
    early = {**RECORD, "setting": {"disease": "early", "line": "neoadjuvant"}}
    rec, log = postprocess({"options": [opt("Adjuvant bisphosphonate", [], EARLY["chunk_id"])]},
                           early, [LUM, EARLY], ROWS, TODAY, phase="neoadjuvant")
    assert rec["options"] == [] and rec["supportive_options"] == []
    assert any("선행요법 결정" in m for m in log)
    rec, _ = postprocess({"options": [opt("Adjuvant bisphosphonate", [], EARLY["chunk_id"])]},
                         early, [LUM, EARLY], ROWS, TODAY, phase="adjuvant")
    assert [o["therapy"] for o in rec["supportive_options"]] == ["Adjuvant bisphosphonate"]
    # 보조 칸에도 인용 검사, 골 보호제가 아니면 보조 칸에서 지움
    bad = {**opt("zoledronic acid", ["zoledronic acid"], "없는-청크"), "rationale": "근거 없음."}
    rec, log = postprocess({"options": [], "supportive_options": [bad, opt("letrozole", ["letrozole"], LUM["chunk_id"])]},
                           RECORD, [LUM], ROWS, TODAY)
    assert rec["supportive_options"] == [] and any("보조 약물 칸에는 골 보호제만" in m for m in log)


def test_pipeline_passes_schema_and_bone_from_confirmed_state():
    answer = {"options": [opt("letrozole + palbociclib", ["letrozole", "palbociclib"], LUM["chunk_id"])],
              "tests_needed": [], "out_of_scope": False, "conflicts": []}
    confirmed = {"items": {"metastatic_sites": {"confirmed": ["bone", "lung"]}}}
    rec, log, errors = recommend({}, RECORD, [LUM, BONE], ROWS, lambda p: answer,
                                 {"booklet_date": "2026-11-01", "overlay_notices": [], "scheduled_count": 0,
                                  "in_progress_count": 0}, "fake-local", TODAY, confirmed_state=confirmed)
    assert errors == [], errors
    assert [o["therapy"] for o in rec["supportive_options"]] == ["denosumab", "zoledronic acid"]
    assert safety_violations(rec, RECORD, {}) == []
