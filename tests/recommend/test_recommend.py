# tests/recommend/test_recommend.py
# [4] 추천 모듈의 LLM 없는 부분(프롬프트, 후처리, 형식 검사)을 가짜 LLM 답으로 시험한다 (PROJECT.md §7, §15.5).
import csv
import json
from datetime import date
from pathlib import Path

from src.recommend.pipeline import recommend
from src.recommend.postprocess import DRUG_BIOMARKER_CSV, postprocess
from src.recommend.prompt import build_prompt
from src.recommend.validate import validate

BASE_DIR = Path(__file__).resolve().parents[2]
TODAY = date(2026, 10, 20)

G1 = {"chunk_id": "g-capi", "doc_type": "guideline", "source": "ESMO-MBC", "version": "2026-05",
      "section": "Second-line", "page_start": 1205, "evidence": {"loe": "I", "gor": "A"},
      "drugs": ["fulvestrant", "capivasertib"],
      "text": "Fulvestrant—capivasertib is recommended for tumours harbouring PIK3CA, AKT1 or PTEN alterations."}
G2 = {"chunk_id": "g-ola", "doc_type": "guideline", "source": "ESMO-MBC", "version": "2026-05",
      "section": "Second-line", "page_start": 1206, "evidence": {"loe": "I", "gor": "A"}, "drugs": ["olaparib"],
      "text": "PARPi monotherapy is recommended for patients with a germline BRCA1/2 mutation. Options include olaparib."}
R_OK = {"chunk_id": "r-fulv", "doc_type": "reimbursement", "source": "HIRA-booklet", "text": "fulvestrant 단독",
        "reimbursement": {"source_type": "baseline", "notice_no": "제2026-210호", "effective_from": "2026-10-01"}}
R_PREVIEW = {"chunk_id": "r-pre", "doc_type": "reimbursement", "source": "HIRA-preview", "text": "예고",
             "reimbursement": {"source_type": "preview", "notice_no": "제2026-300호", "effective_from": "2026-12-01"}}
R_OFF = {"chunk_id": "r-off", "doc_type": "reimbursement", "source": "HIRA-offlabel", "text": "olaparib 허가초과",
         "reimbursement": {"source_type": "baseline", "notice_no": "제2026-1호", "effective_from": "2026-01-01",
                           "copay": "100/100"}}
GUIDE, REIMB = [G1, G2], [R_OK, R_PREVIEW, R_OFF]
INDEX_STATUS = {"booklet_date": "2026-09-01", "overlay_notices": [], "scheduled_count": 0, "in_progress_count": 0}


def bm(**statuses):
    """biomarker_record. 예: bm(PIK3CA="positive")."""
    return {"patient_ref": "VC-T1", "subtype": "HR+/HER2-",
            "setting": {"disease": "metastatic", "line": "2L", "reason": "1차 진행"},
            "records": [{"marker": m, "status": s, "reason": f"{m} {s}"} for m, s in statuses.items()],
            "tests_needed": []}


def opt(**kw):
    o = {"therapy": "fulvestrant + capivasertib", "drugs": ["fulvestrant", "capivasertib"],
         "rationale": "PIK3CA 변이 환자에게 권고된다 [g-capi].", "citations": ["g-capi"],
         "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "fulvestrant 급여",
         "reimbursement_citations": ["r-fulv"]}
    o.update(kw)
    return o


def run(options, record, **kw):
    return postprocess({"options": options}, record, kw.get("guide", GUIDE), REIMB, TODAY, kw.get("checker"))


def test_drug_biomarker_table_shape():
    """약→바이오마커 표: 칸이 맞고, 마커와 상태값이 biomarker_record 스키마 값이며, 출처가 있다."""
    schema = json.load(open(BASE_DIR / "schemas" / "biomarker_record.json", encoding="utf-8"))
    markers = set(schema["$defs"]["record"]["properties"]["marker"]["enum"])
    statuses = set(schema["$defs"]["record"]["properties"]["status"]["enum"])
    with open(DRUG_BIOMARKER_CSV, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert rows
    for r in rows:
        assert set(r["markers"].split("|")) <= markers, r
        assert set(r["statuses"].split("|")) <= statuses, r
        assert r["source"].strip(), r


def test_keeps_valid_option():
    rec, log = run([opt()], bm(PIK3CA="positive"))
    assert len(rec["options"]) == 1 and rec["options"][0]["guideline_source"] == "ESMO"
    assert rec["options"][0]["reimbursement"] == "covered_conditions_unverified" and not log


def test_unknown_chunk_id_removed():
    rec, log = run([opt(citations=["g-capi", "g-없음"], reimbursement_citations=["r-fulv", "r-없음"])],
                   bm(PIK3CA="positive"))
    o = rec["options"][0]
    assert o["citations"] == ["g-capi"] and o["reimbursement_citations"] == ["r-fulv"]
    assert any("받지 않은 청크 ID" in x for x in log)


def test_uncited_sentence_removed():
    rec, log = run([opt(rationale="PIK3CA 변이 환자에게 권고된다 [g-capi]. 생존이 2배 늘어난다.")], bm(PIK3CA="positive"))
    assert rec["options"][0]["rationale"] == "PIK3CA 변이 환자에게 권고된다 [g-capi]."
    assert any("인용 없는 문장 1개" in x for x in log)


def test_option_without_citation_removed():
    rec, log = run([opt(rationale="근거 없이 권고한다.", citations=[])], bm(PIK3CA="positive"))
    assert rec["options"] == [] and any("후보 삭제" in x for x in log)


def test_drug_not_in_cited_chunk_removed():
    rec, log = run([opt(drugs=["fulvestrant", "alpelisib"])], bm(PIK3CA="positive"))
    assert rec["options"] == [] and any("약 이름 없음" in x and "alpelisib" in x for x in log)


def test_not_done_biomarker_becomes_test():
    """capivasertib은 PIK3CA·AKT1·PTEN 중 하나라도 양성이어야 한다. 셋 다 미시행이면 검사 권고로."""
    rec, log = run([opt()], bm(PIK3CA="not_done", AKT1="not_done", PTEN="not_done"))
    assert rec["options"] == []
    assert {t["test"] for t in rec["tests_needed"]} == {"PIK3CA 검사 결과 확인", "AKT1 검사 결과 확인", "PTEN 검사 결과 확인"}
    assert all(t["blocks_therapy"] == "fulvestrant + capivasertib" for t in rec["tests_needed"])


def test_any_positive_marker_is_enough():
    rec, _ = run([opt()], bm(PIK3CA="negative", AKT1="not_done", PTEN="positive"))
    assert len(rec["options"]) == 1 and rec["tests_needed"] == []


def test_negative_biomarker_goes_to_conflicts():
    rec, log = run([opt()], bm(PIK3CA="negative", AKT1="negative", PTEN="vus"))
    assert rec["options"] == [] and rec["tests_needed"] == []
    assert rec["conflicts"] and "capivasertib" in rec["conflicts"][0] and "출처" in rec["conflicts"][0]


def test_gbrca_missing_in_virtual_chart_becomes_test():
    """gBRCA 판정이 없으면 (예: sBRCA만 있는 옛 기록) olaparib 대신 검사 권고."""
    o = opt(therapy="olaparib", drugs=["olaparib"], rationale="생식세포 BRCA 변이에 권고된다 [g-ola].",
            citations=["g-ola"], reimbursement="no_criteria", reimbursement_citations=[])
    rec, _ = run([o], bm(sBRCA1="positive", PALB2="negative"))
    assert rec["options"] == [] and {t["test"] for t in rec["tests_needed"]} == {"gBRCA1 검사 결과 확인",
                                                                                 "gBRCA2 검사 결과 확인"}


def test_covered_downgraded_without_checker():
    rec, log = run([opt(reimbursement="covered")], bm(PIK3CA="positive"))
    assert rec["options"][0]["reimbursement"] == "covered_conditions_unverified"
    rec, log = run([opt(reimbursement="covered")], bm(PIK3CA="positive"), checker=lambda o, c: True)
    assert rec["options"][0]["reimbursement"] == "covered"


def test_preview_notice_is_not_reimbursement_basis():
    rec, log = run([opt(reimbursement_citations=["r-pre"])], bm(PIK3CA="positive"))
    o = rec["options"][0]
    assert o["reimbursement"] == "no_criteria" and o["reimbursement_citations"] == []


def test_offlabel_needs_offlabel_chunk():
    o = opt(reimbursement="offlabel_approved", reimbursement_citations=["r-fulv"])
    rec, _ = run([o], bm(PIK3CA="positive"))
    assert rec["options"][0]["reimbursement"] == "no_criteria"
    o = opt(reimbursement="offlabel_approved", reimbursement_citations=["r-off"])
    rec, _ = run([o], bm(PIK3CA="positive"))
    assert rec["options"][0]["reimbursement"] == "offlabel_approved" and rec["options"][0]["copay"] == "100/100"


def test_no_chunks_out_of_scope():
    rec, log = run([opt()], bm(PIK3CA="positive"), guide=[])
    assert rec["options"] == [] and rec["out_of_scope"] is True and rec["out_of_scope_reason"]


def test_prompt_has_rules_ids_and_no_chart_quotes():
    ps = {"fields": {"patient": {"menopausal_status": {"status": "present", "value": "postmenopausal",
                                                        "source": {"doc_id": "D1", "quote": "차트원문인용"}}}}}
    text = build_prompt(ps, bm(PIK3CA="positive"), GUIDE, REIMB)
    assert "[g-capi]" in text and "[r-fulv]" in text and "제2026-210호" in text and "LoE I, GoR A" in text
    assert "[청크ID]" in text and "postmenopausal" in text and "차트원문인용" not in text


def test_pipeline_with_fake_llm_passes_schema():
    answer = "설명입니다.\n```json\n" + json.dumps({"options": [opt(), opt(therapy="엉뚱한 약", drugs=["xyz"])],
                                                    "tests_needed": [], "out_of_scope": False, "conflicts": []},
                                                   ensure_ascii=False) + "\n```"
    record = bm(PIK3CA="positive")
    record["tests_needed"] = [{"test": "ESR1 (cfDNA)", "reason": "재검", "rule_id": "BM4-ESR1-RETEST"}]
    rec, log, errors = recommend({}, record, GUIDE, REIMB, lambda p: answer, INDEX_STATUS, "fake-local", TODAY)
    assert errors == [], errors
    assert [o["therapy"] for o in rec["options"]] == ["fulvestrant + capivasertib"]
    assert rec["tests_needed"] == [{"test": "ESR1 (cfDNA)", "reason": "재검"}]


def test_pipeline_unreadable_llm_answer():
    rec, log, errors = recommend({}, bm(), GUIDE, REIMB, lambda p: "답을 못 하겠습니다", INDEX_STATUS, "fake", TODAY)
    assert errors == [] and rec["out_of_scope"] is True and rec["options"] == []


def test_validate_catches_missing_citation():
    bad = {"schema_version": "0.1-draft", "patient_ref": "x", "generated_at": "2026-10-20T10:00:00+09:00",
           "model": "m", "options": [opt(citations=[])], "tests_needed": [], "out_of_scope": False,
           "conflicts": [], "index_status": INDEX_STATUS}
    assert any("citations" in e for e in validate(bad))
