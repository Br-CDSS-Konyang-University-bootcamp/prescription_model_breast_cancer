# tests/recommend/test_conditions_eval.py
# 급여 조건 판정기: D 조건 형식(schemas/chunk.json, src/reimbursement/schema_proposal.md "읽는 법")을 가짜 조건으로 시험한다.
# 조건 text는 모두 지어낸 테스트 문장이다 (심평원 공고 원문을 옮기지 않는다).
from src.recommend.conditions_eval import evaluate_conditions, evaluate_item, make_conditions_checker
from src.recommend.postprocess import postprocess


def item(field, op, value, **kw):
    return {"id": f"{field}-{op}", "field": field, "op": op, "value": value, "text": f"{field} {op} {value}", **kw}


def cond(all_of=(), any_of=(), exceptions=(), line_rule=None, prior=()):
    return {"all_of": list(all_of), "any_of": list(any_of), "any_of_exceptions": list(exceptions), "stage_rules": [],
            "counts_as_prior_line": list(prior), "notes": [], "human_review": [], "unmapped": [],
            "line_rule": line_rule}


def record(subtype="HR+/HER2-", disease="metastatic", **statuses):
    return {"subtype": subtype, "setting": {"disease": disease, "line": "2L"},
            "records": [{"marker": m, "status": s} for m, s in statuses.items()]}


def present(v):
    return {"status": "present", "value": v}


def patient(**fields):
    base = {"patient": {"menopausal_status": present("postmenopausal"), "gender": present("FEMALE")},
            "stage": {"group": present("IIIA"), "ptnm": present({"t": "T2", "n": "N1a", "m": "M0"})},
            "recurrence": {"status": present("distant"), "recurrence_day": present(900), "metastasis_day": present(900),
                           "metastatic_sites": present(["bone"])},
            "treatment_history": [
                {"drugs": ["letrozole"], "setting": "adjuvant", "start_day": 100, "end_day": 700, "line": None,
                 "endocrine_line": None, "chemo_line": None, "stop_reason": None, "best_response": "unknown"},
                {"drugs": ["letrozole", "palbociclib"], "setting": "metastatic", "start_day": 920, "end_day": 1300,
                 "line": 1, "endocrine_line": 1, "chemo_line": None, "stop_reason": "progression", "best_response": "PD"}]}
    base.update(fields)
    return {"fields": base, "index_day": 1400}


def ev(c, rec=None, ps=None):
    return evaluate_conditions(c, ps or patient(), rec or record(PIK3CA="positive", HER2="low"))["status"]


def test_biomarker_values():
    assert ev(cond([item("pik3ca", "eq", "positive")])) == "met"
    assert ev(cond([item("pik3ca", "eq", "positive")]), record(PIK3CA="not_done")) == "unknown"   # 급여 아님이 아니라 검사 필요
    assert ev(cond([item("pik3ca", "eq", "positive")]), record(PIK3CA="vus")) == "not_met"        # VUS는 음성 처리
    assert ev(cond([item("pik3ca", "eq", "positive")]), record(PIK3CA="retest_needed")) == "unknown"
    assert ev(cond([item("her2", "in", ["negative", "low", "ultralow"])])) == "met"               # HER2 음성 = 저발현 포함
    assert ev(cond([item("hr", "eq", "positive")])) == "met"
    assert ev(cond([item("gbrca", "eq", "positive")]), record(sBRCA1="positive")) == "unknown"    # gBRCA 줄이 없으면 알 수 없음


def test_patient_values_and_missing_fields():
    assert ev(cond([item("menopause", "eq", "postmenopausal")])) == "met"
    assert ev(cond([item("disease", "eq", "metastatic")])) == "met"
    assert ev(cond([item("recurrence_operable", "eq", "no")])) == "unknown"                       # 환자 JSON에 칸 없음
    assert ev(cond([item("cardiac_history", "eq", True)])) == "unknown"
    assert ev(cond([item("bone_metastasis", "eq", True)])) == "unknown"   # 전이 부위에 뼈만 있고 영상 소견 없음
    assert ev(cond([item("ln_status", "eq", "positive")])) == "met"


def test_stage_comparisons():
    assert ev(cond([item("stage_group", "eq", "III")])) == "met"                                  # III는 IIIA~IIIC 포함
    assert ev(cond([item("stage_group", "gte", "IIIB")])) == "not_met"
    assert ev(cond([item("stage_group", "gte", "IIIA")])) == "met"
    ps = patient(stage={"group": present("III"), "ptnm": present({"t": "T1", "n": "N0", "m": "M0"})})
    assert ev(cond([item("stage_group", "gte", "IIIB")]), ps=ps) == "unknown"                     # 주 병기만 있으면 알 수 없음
    assert ev(cond([item("t_stage", "gte", "T1c")]), ps=ps) == "unknown"                          # T1은 T1a~c 범위
    assert ev(cond([item("t_stage", "gte", "T2")]), ps=ps) == "not_met"
    assert ev(cond([item("t_stage", "gte", "T2")])) == "met"


def test_any_of_exceptions_and_unless():
    # '전이성 또는 절제 불가능한 국소 재발성': any_of에 전이성, 예외에 국소 재발 + 절제 불가
    c = cond(any_of=[{"text": "전이성", "items": [item("disease", "eq", "metastatic")]}],
             exceptions=[{"text": "국소 재발 절제 불가", "all_of": [item("recurrence", "eq", "locoregional"),
                                                              item("operable", "eq", "no")]}])
    assert ev(c) == "met"
    early = record(disease="early", PIK3CA="positive")
    loc = patient(recurrence={"status": present("locoregional")}, stage={"operable": present("no")})
    assert ev(c, early, loc) == "met"                                                            # 예외로 통과
    assert ev(c, early, patient(recurrence={"status": present("none")})) == "not_met"
    # unless: 항목이 실패해도 unless를 만족하면 통과
    it = item("prior_drugs", "not_contains", ["letrozole"], unless=item("days_end_to_recurrence", "gt", 100,
                                                                         of={"setting": ["adjuvant"]}))
    assert evaluate_item(it, patient(), record()) is True                                        # 900 - 700 = 200 > 100


def test_prior_drugs_and_failed():
    assert ev(cond([item("prior_drugs", "contains", ["CDK4/6_inhibitor"], of={"setting": ["metastatic"]})])) == "met"
    assert ev(cond([item("prior_drugs", "not_contains", ["fulvestrant"])])) == "met"
    assert ev(cond([item("prior_failed", "contains", ["AI_nonsteroidal"])])) == "met"             # letrozole 진행
    assert ev(cond([item("prior_failed", "contains", ["taxane"])])) == "not_met"


def test_line_rule():
    assert ev(cond(line_rule={"stage": "palliative_endocrine", "line": "2차 이상"})) == "met"      # 내분비 1차 받음 → 2차
    assert ev(cond(line_rule={"stage": "palliative_endocrine", "line": "1차"})) == "not_met"
    assert ev(cond(line_rule={"stage": "palliative_chemo", "line": "1차"})) == "met"               # 항암은 따로 셈
    deemed = patient(deemed_lines=[{"rule_id": "DEEM-ANTHRA-TAXANE", "category": "chemo", "status": "met"}])
    c = cond(line_rule={"stage": "palliative_chemo", "line": "2차 이상"}, prior=[{"text": "간주", "setting": ["adjuvant"],
                                                                               "drugs": ["anthracycline", "taxane"]}])
    assert ev(c) == "unknown"                                                                     # deemed_lines 없음
    assert ev(c, ps=deemed) == "met"
    other = patient(deemed_lines=[{"rule_id": "DEEM-ANTHRA-TAXANE", "category": "chemo", "status": "not_met"},
                                  {"rule_id": "DEEM-SG-1Y", "category": "chemo", "status": "met"}])
    assert ev(c, ps=other) == "not_met"                                                           # 다른 규칙 met은 안 셈
    sg = cond(line_rule={"stage": "palliative_chemo", "line": "2차 이상"},
              prior=[{"text": "1년 이내", "setting": ["adjuvant"], "drugs": [], "within_days": 365}])
    assert ev(sg, ps=other) == "met"


def test_checker_in_postprocess():
    rchunk = {"chunk_id": "r1", "doc_type": "reimbursement", "source": "HIRA-booklet",
              "reimbursement": {"source_type": "baseline", "notice_no": "x", "effective_from": "2026-10-01",
                                "conditions": cond([item("pik3ca", "eq", "positive")])}}
    g = {"chunk_id": "g1", "source": "ESMO-MBC", "drugs": ["capivasertib"], "text": "capivasertib"}
    opt = {"therapy": "capivasertib", "drugs": ["capivasertib"], "rationale": "권고 [g1].", "citations": ["g1"],
           "reimbursement": "covered", "reimbursement_reason": "", "reimbursement_citations": ["r1"]}
    from datetime import date
    def run(rec, reviewed, chunk=rchunk):
        chk = make_conditions_checker(patient(), rec, conditions_reviewed=reviewed)
        out, _ = postprocess({"options": [dict(opt)]}, rec, [g], [chunk], date(2026, 10, 21), chk)
        return out["options"][0]["reimbursement"] if out["options"] else None
    assert run(record(PIK3CA="positive"), reviewed=False) == "covered_conditions_unverified"      # 사람 검수 전
    assert run(record(PIK3CA="positive"), reviewed=True) == "covered"
    assert run(record(PIK3CA="not_done", AKT1="not_done", PTEN="not_done"), reviewed=True) is None  # 검사 권고로 바뀜
    assert run(record(PIK3CA="vus", AKT1="negative", PTEN="negative"), reviewed=True) is None
    first_line = {**rchunk, "reimbursement": {**rchunk["reimbursement"],
                  "conditions": cond(line_rule={"stage": "palliative_endocrine", "line": "1차"})}}
    assert run(record(PIK3CA="positive"), reviewed=True, chunk=first_line) == "no_criteria"       # 검수 후 불충족
    assert run(record(PIK3CA="positive"), reviewed=False, chunk=first_line) == "covered_conditions_unverified"


def test_endocrine_adjuvant_relapse_counts_as_first_line():
    """VC-0103: 보조 anastrozole 중 전이 (전이 후 투약 없음). 공고에 보조요법 1년 이내 진행을 인정하는 문구가 있는 행에만
    D가 counts_as_prior_line + rule_id: DEEM-ENDO-ADJ-1Y를 넣는다 (A 기대값: fulvestrant + CDK4/6 급여, D 확인 2026-10-22).
    문구 없는 내분비 "2차 이상" 행에는 적용하지 않는다."""
    adj = {"drugs": ["anastrozole"], "setting": "adjuvant", "start_day": 40, "end_day": 765, "line": None,
           "endocrine_line": None, "chemo_line": None, "stop_reason": "progression", "best_response": "PD"}
    def vc(status):
        return patient(recurrence={"status": present("distant"), "recurrence_day": present(760),
                                   "metastasis_day": present(760)}, treatment_history=[adj],
                       deemed_lines=[{"rule_id": "DEEM-ENDO-ADJ-1Y", "category": "endocrine", "status": status}])
    deem = [{"text": "TEST (made up): 보조 내분비 1년 이내 진행 간주", "setting": ["adjuvant"], "drugs": [], "rule_id": "DEEM-ENDO-ADJ-1Y"}]
    c = cond(any_of=[{"text": "내분비요법 후 진행", "items": [
        item("days_end_to_metastasis", "lte", 365, of={"drugs": ["AI_nonsteroidal"], "setting": ["adjuvant"]}),
        item("days_end_to_progression", "lte", 30, of={"setting": ["metastatic"]})]}],
        line_rule={"stage": "palliative_endocrine", "line": "2차 이상"}, prior=deem)
    assert ev(c, ps=vc("met")) == "met"
    assert ev(c, ps=vc("not_met")) == "not_met"
    assert ev(c, ps=vc("unknown")) == "unknown"
    plain = cond(line_rule={"stage": "palliative_endocrine", "line": "2차 이상"})       # 문구 없는 행 (3다 연번 1~3 등)
    assert ev(plain, ps=vc("met")) == "not_met"
    assert evaluate_item(item("days_end_to_metastasis", "lte", 365, of={"setting": ["adjuvant"]}),
                         vc("met"), record()) is True                     # 765 - 760 = 투여 중 전이
    assert evaluate_item(item("days_end_to_recurrence", "gt", 365, of={"setting": ["adjuvant"]}),
                         vc("met"), record()) is False                    # recurrence_day는 {status, value} 칸


def test_counts_as_prior_line_rule_id_used_as_is():
    """D가 counts_as_prior_line에 rule_id를 적으면 대응표 대신 그 규칙을 본다 (D 요청 2026-10-22)."""
    ps = patient(deemed_lines=[{"rule_id": "DEEM-HER2ADC-6M", "category": "chemo", "status": "met"},
                               {"rule_id": "DEEM-ANTHRA-TAXANE", "category": "chemo", "status": "not_met"}])
    c = cond(line_rule={"stage": "palliative_chemo", "line": "2차 이상"},
             prior=[{"text": "보조요법 6개월 이내 재발", "setting": ["adjuvant"], "drugs": ["trastuzumab"],
                     "rule_id": "DEEM-HER2ADC-6M"}])
    assert ev(c, ps=ps) == "met"
    c_other = cond(line_rule={"stage": "palliative_chemo", "line": "2차 이상"},
                   prior=[{"text": "간주", "setting": ["adjuvant"], "drugs": [], "rule_id": "DEEM-ANTHRA-TAXANE"}])
    assert ev(c_other, ps=ps) == "not_met"


def test_at_index_fields():
    """판정 기준일 나이·최근 4주 투여 (patient_state.fields.at_index, A가 계산)."""
    ps = patient(at_index={"age": 72, "recent_therapy_28d": {"status": "yes", "basis": "", "regimen_refs": [0],
                                                            "gap_days": 10}})
    assert ev(cond([item("age_at_index", "gte", 70)]), ps=ps) == "met"
    assert ev(cond([item("age_at_index", "lt", 65)]), ps=ps) == "not_met"
    assert ev(cond([item("recent_therapy_28d", "eq", "yes")]), ps=ps) == "met"
    unknown = patient(at_index={"age": None, "recent_therapy_28d": {"status": "unknown", "basis": "",
                                                                     "regimen_refs": [], "gap_days": None}})
    assert ev(cond([item("age_at_index", "gte", 19)]), ps=unknown) == "unknown"
    assert ev(cond([item("recent_therapy_28d", "eq", "yes")]), ps=unknown) == "unknown"
    assert ev(cond([item("recent_therapy_28d", "eq", "yes")])) == "unknown"                       # at_index 칸 없음


def test_d_requests_2026_10_22():
    """D 요청: 재발 병소 절제(recurrence_operable), 폐경 indeterminate, 빈 투약 기록의 not_contains."""
    rec = lambda surgery, intent: patient(recurrence={"status": present("locoregional"), "surgery": present(surgery),
                                                      "surgery_intent": present(intent)})
    assert ev(cond([item("recurrence_operable", "eq", "yes")]), ps=rec("yes", "curative")) == "met"
    assert ev(cond([item("recurrence_operable", "eq", "no")]), ps=rec("yes", "curative")) == "not_met"
    assert ev(cond([item("recurrence_operable", "eq", "no")]), ps=rec("no", "unknown")) == "unknown"
    assert ev(cond([item("recurrence_operable", "eq", "yes")]), ps=rec("yes", "palliative")) == "unknown"
    indet = patient(patient={"menopausal_status": present("indeterminate"), "gender": present("FEMALE")})
    assert ev(cond([item("menopause", "eq", "postmenopausal")]), ps=indet) == "unknown"
    empty = patient(treatment_history=[])
    assert ev(cond([item("prior_drugs", "not_contains", ["letrozole"])]), ps=empty) == "unknown"
    assert ev(cond([item("prior_drugs", "not_contains", ["tamoxifen"])])) == "met"                # 기록이 있으면 판정


def test_cardiac_and_mediastinal_fields():
    """심장 병력·종격동 방사선 칸 (2026-10-22 추가, draft7 체크리스트 §1.2): yes/no를 조건의 true/false로 읽는다."""
    base = patient()["fields"]["patient"]
    yes = patient(patient={**base, "cardiac_history": present("yes"), "mediastinal_radiation": present("yes")})
    no = patient(patient={**base, "cardiac_history": present("no"), "mediastinal_radiation": present("no")})
    blank = patient(patient={**base, "cardiac_history": {"status": "not_recorded"},
                             "mediastinal_radiation": {"status": "not_recorded"}})
    for field in ("cardiac_history", "mediastinal_radiation"):
        c = cond([item(field, "eq", True)])
        assert ev(c, ps=yes) == "met"
        assert ev(c, ps=no) == "not_met"
        assert ev(c, ps=blank) == "unknown"                       # 기록 없음은 알 수 없음
        assert ev(cond([item(field, "eq", False)]), ps=no) == "met"
    # 지어낸 조건: 누적 용량 기준 또는 심장 위험·종격동 방사선 중 하나 (any_of)
    either = cond(any_of=[{"text": "누적 용량 또는 심장 위험", "items": [
        item("cumulative_dose_mg_m2", "gte", 240), item("cardiac_history", "eq", True),
        item("mediastinal_radiation", "eq", True)]}])
    assert ev(either, ps=yes) == "met"
    assert ev(either, ps=no) == "unknown"                         # 누적 용량을 몰라 알 수 없음


def test_bone_metastasis_by_imaging():
    """"영상으로 골전이 입증" (draft7 체크리스트 §1.2): imaging_findings에 뼈가 confirmed로 있어야 충족."""
    c = cond([item("bone_metastasis", "eq", True)])

    def with_imaging(*finds, sites=None):
        ps = patient(imaging_findings=[{"modality": m, "sites": s, "certainty": cert} for m, s, cert in finds])
        if sites is not None:
            ps["fields"]["recurrence"]["metastatic_sites"] = present(sites)
        return ps

    assert ev(c, ps=with_imaging(("bone_scan", ["bone"], "confirmed"))) == "met"              # VC-0108
    assert ev(c, ps=with_imaging(("PET", ["bone"], "suspected"))) == "unknown"               # VC-0143 의심만
    assert ev(c, ps=with_imaging(("CT", ["liver"], "confirmed"), sites=["liver"])) == "not_met"
    assert ev(c, ps=with_imaging(("CT", ["liver"], "confirmed"), sites=["liver", "bone"])) == "unknown"
