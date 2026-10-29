# tests/recommend/test_safety.py
# 안전 위반 검사 (PROJECT.md §12). 추천 결과는 지어낸 테스트 값이다.
from src.recommend.safety import safety_violations


def record(er="positive", pr="positive", her2="negative"):
    return {"records": [{"marker": "ER", "status": er}, {"marker": "PR", "status": pr},
                        {"marker": "HER2", "status": her2}]}


def option(therapy, drugs, citations=("esmo-test-1",), rationale="TEST (made up)"):
    return {"therapy": therapy, "drugs": list(drugs), "citations": list(citations), "rationale": rationale}


def rules(options, rec=None, ps=None):
    return [v["rule"] for v in safety_violations({"options": options}, rec or record(), ps or {"fields": {}})]


def test_her2_by_drug():
    assert rules([option("trastuzumab + paclitaxel", ["trastuzumab", "paclitaxel"])], record(her2="low")) == ["her2_mismatch"]
    assert rules([option("T-DXd", ["trastuzumab deruxtecan"])], record(her2="low")) == []         # T-DXd는 저발현 허용
    assert rules([option("T-DXd", ["trastuzumab deruxtecan"])], record(her2="negative")) == ["her2_mismatch"]
    assert rules([option("trastuzumab", ["trastuzumab"])], record(her2="positive")) == []
    assert rules([option("trastuzumab", ["trastuzumab"])], record(her2="unknown")) == []           # 판정 불가면 보지 않음


def test_endocrine_only_in_hr_negative():
    tnbc = record(er="negative", pr="negative")
    assert rules([option("letrozole 단독", ["letrozole"])], tnbc) == ["endocrine_only_hr_negative"]
    assert rules([option("letrozole + palbociclib", ["letrozole", "palbociclib"])], tnbc) == []
    assert rules([option("letrozole 단독", ["letrozole"])], record(er="low", pr="negative")) == []  # ER 저발현은 HR+


def test_progressed_drug_again():
    ps = {"index_day": 2000, "fields": {"treatment_history": [
        {"drugs": ["palbociclib", "letrozole"], "start_day": 1500, "stop_reason": "progression"},
        {"drugs": ["fulvestrant"], "start_day": 2100, "best_response": "PD"}]}}               # 기준일 뒤 투약은 보지 않음
    assert rules([option("palbociclib + fulvestrant", ["palbociclib", "fulvestrant"])], ps=ps) == ["progressed_drug_again"]
    assert rules([option("fulvestrant 단독", ["fulvestrant"])], ps=ps) == []


def test_uncited_and_out_of_scope():
    assert rules([option("x", ["capecitabine"], citations=())]) == ["uncited"]
    assert rules([option("x", ["capecitabine"], rationale=" ")]) == ["uncited"]
    male = {"fields": {"patient": {"gender": {"status": "present", "value": "MALE"}}}}
    assert rules([option("x", ["capecitabine"])], ps=male) == ["out_of_scope"]
    tis = {"fields": {"stage": {"ptnm": {"status": "present", "value": {"t": "pTis", "n": "N0", "m": "M0"}}}}}
    assert rules([option("x", ["capecitabine"])], ps=tis) == ["out_of_scope"]
    assert rules([], ps=male) == []                                                                # 추천이 없으면 위반 아님
