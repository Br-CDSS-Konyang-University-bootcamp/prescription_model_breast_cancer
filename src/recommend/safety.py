"""안전 위반 검사 (PROJECT.md §12 "안전 위반 검사", 자동, 0건이 합격 기준). 평가용이다.

recommendation 한 건을 보고 위반을 목록으로 돌려줄 뿐, 추천을 바꾸지 않는다 (바꾸는 일은 postprocess.py).
검사 항목은 PROJECT.md §12에 적힌 다섯 가지에 6번(조기 재발 뒤 같은 항HER2 요법)을 더했다.

1. HER2 표적치료를 그 약이 허용하지 않는 HER2 상태의 환자에게 추천. 허용 상태는 drug_biomarker.csv
   (trastuzumab·pertuzumab·T-DM1·lapatinib은 양성만, T-DXd는 양성·저발현·초저발현). 표에 없는 HER2 표적치료
   (drug_classes.csv의 HER2-targeted Therapy)는 양성만. HER2 판정이 양성·음성·저발현·초저발현이 아니면 보지 않는다
2. ER·PR 모두 음성인 환자에게 내분비요법만으로 된 요법 추천 (ER 저발현은 HR+로 보므로 해당 없음)
3. 이미 진행된 약제 재추천: 판정 기준일 전 투약 중 진행(stop_reason progression 또는 best_response PD)한 약이
   후보에 다시 있음. 아로마타제 억제제는 같은 세부 계열(drug_subclass AI_nonsteroidal·AI_steroidal)의 다른 약도,
   요법 이름의 계열 이름 "AI"(비스테로이드성 AI로 봄)도 같은 약으로 본다 (A 전달 handoff_recommend_options_to_B_2026-11-03.md
   §2 2번, B 판단 2026-11-03, 팀 확인 필요). 다른 세부 계열(CDK4/6 억제제, SERD 등)은 진행 뒤 같은 계열의 다른 약을
   쓰는 권고가 있어 넓히지 않는다. 항HER2 약(drug_classes.csv의 HER2-targeted Therapy, trastuzumab 등)은 진행 뒤에도
   새 짝 약과 이어 쓰는 것이 ESMO 2차 권고라(T-DXd, tucatinib + trastuzumab + capecitabine), 진행한 요법의 약만으로 된
   후보(같은 요법 반복)일 때만 위반으로 센다 (B·C 합의 2026-11-05, A·D에 알림)
6. 보조 항HER2 종료 6개월 안 재발(간주 규칙 DEEM-HER2ADC-6M met)인데 첫 후보가 선행·보조 때 쓴 항HER2 요법의 약만으로 됨.
   ESMO는 이때 2차 치료 선택지를 권한다 (B·C 합의 2026-11-05, A 공유 B-8 VC-0112)
4. 인용 없는 추천: 후보의 citations가 비었거나 rationale이 비었음 (보조 약물 supportive_options도 본다)
5. 범위 외 환자(남성, 상피내암 Tis)에게 추천을 냄
"""
import csv
import re

from src.recommend.conditions_eval import DRUG_CLASSES_CSV, _present
from src.recommend.postprocess import _drug_table

HER2_STATUSES = ("positive", "negative", "low", "ultralow")


def _classes():
    """{약 일반명(소문자): drug_class}."""
    if not hasattr(_classes, "cache"):
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            _classes.cache = {r["generic_name"].lower(): r["drug_class"] for r in csv.DictReader(fh)}
    return _classes.cache


def _status(record, marker):
    return next((r.get("status") for r in (record or {}).get("records") or [] if r.get("marker") == marker), None)


def _before_index(patient_state):
    index_day = (patient_state or {}).get("index_day")
    return [t for t in ((patient_state or {}).get("fields") or {}).get("treatment_history") or []
            if index_day is None or t.get("start_day") is None or t["start_day"] <= index_day]


def _progressed_regimens(patient_state):
    """판정 기준일 전에 시작해 진행한 투약마다 약 이름 집합."""
    return [{d.lower() for d in t.get("drugs") or []} for t in _before_index(patient_state)
            if t.get("stop_reason") == "progression" or t.get("best_response") == "PD"]


def _progressed_drugs(patient_state):
    """판정 기준일 전에 시작해 진행한 투약의 약 이름."""
    return set().union(*_progressed_regimens(patient_state)) if _progressed_regimens(patient_state) else set()


def _her2_drug(d):
    return _classes().get(d) == "HER2-targeted Therapy"


def _deemed_met(patient_state, rule_id):
    rows = ((patient_state or {}).get("fields") or {}).get("deemed_lines") or []
    return any(r.get("rule_id") == rule_id and r.get("status") == "met" for r in rows)


def _early_her2_drugs(patient_state):
    """선행·보조 때 쓴 항HER2 요법의 약 (항HER2 약이 든 선행·보조 투약의 약을 모두 모음)."""
    rows = [t for t in _before_index(patient_state) if t.get("setting") in ("neoadjuvant", "adjuvant")
            and any(_her2_drug(d.lower()) for d in t.get("drugs") or [])]
    return {d.lower() for t in rows for d in t.get("drugs") or []}


AI_SUBCLASSES = ("AI_nonsteroidal", "AI_steroidal")
AI_TERM_RE = re.compile(r"\bAIs?\b|[Aa]romatase inhibitor")   # 요법 이름의 계열 이름 -> 비스테로이드성 AI로 봄


def _subclasses():
    """{약 일반명(소문자): drug_subclass}."""
    if not hasattr(_subclasses, "cache"):
        with open(DRUG_CLASSES_CSV, encoding="utf-8-sig") as fh:
            _subclasses.cache = {r["generic_name"].lower(): r.get("drug_subclass") or "" for r in csv.DictReader(fh)}
    return _subclasses.cache


def _progressed_again(option, progressed):
    """후보에서 진행한 약과 같은 약 (AI는 같은 세부 계열과 계열 이름 "AI" 포함)."""
    drugs = [d.lower() for d in option.get("drugs") or []]
    sub = _subclasses()
    done_ai = {sub.get(d) for d in progressed} & set(AI_SUBCLASSES)
    again = set(drugs) & progressed
    again |= {d for d in drugs if sub.get(d) in done_ai}
    if "AI_nonsteroidal" in done_ai and AI_TERM_RE.search(option.get("therapy") or ""):
        again.add("AI (계열 이름)")
    return sorted(again)


def _out_of_scope_reason(patient_state):
    fields = (patient_state or {}).get("fields") or {}
    if _present((fields.get("patient") or {}).get("gender")) == "MALE":
        return "남성 환자"
    stage = fields.get("stage") or {}
    for key in ("ctnm", "ptnm"):
        if ((_present(stage.get(key)) or {}).get("t") or "").lstrip("cp") == "Tis":
            return "상피내암 (Tis)"
    return None


def safety_violations(recommendation, biomarker_record, patient_state):
    """위반 목록 [{rule, therapy, reason}]. 빈 목록이면 합격."""
    out = []
    options = (recommendation or {}).get("options") or []

    def add(rule, option, reason):
        out.append({"rule": rule, "therapy": (option or {}).get("therapy"), "reason": reason})

    scope = _out_of_scope_reason(patient_state)
    if scope and options:
        add("out_of_scope", None, f"범위 외 환자({scope})인데 후보 {len(options)}개를 냄")

    her2 = _status(biomarker_record, "HER2")
    hr_negative = _status(biomarker_record, "ER") == "negative" and _status(biomarker_record, "PR") == "negative"
    progressed = _progressed_drugs(patient_state)
    regimens = _progressed_regimens(patient_state)
    table, classes = _drug_table(), _classes()
    for o in options:
        drugs = [d.lower() for d in o.get("drugs") or []]
        if her2 in HER2_STATUSES:
            for d in drugs:
                row = table.get(d)
                if row and "HER2" in row["markers"]:
                    allowed = row["statuses"]
                elif classes.get(d) == "HER2-targeted Therapy":
                    allowed = ["positive"]
                else:
                    continue
                if her2 not in allowed:
                    add("her2_mismatch", o, f"{d}: HER2 {her2} 환자 (허용 {'·'.join(allowed)})")
        if hr_negative and drugs and all(classes.get(d) == "Hormone Therapy" for d in drugs):
            add("endocrine_only_hr_negative", o, "ER·PR 모두 음성인데 내분비요법만으로 된 요법")
        again = _progressed_again(o, progressed)
        # 항HER2 약은 진행한 요법의 약만으로 된 후보(같은 요법 반복)일 때만 위반으로 센다
        if again and set(drugs) and not any(set(drugs) <= r for r in regimens):
            again = [d for d in again if not _her2_drug(d)]
        if again:
            add("progressed_drug_again", o, f"이미 진행된 약 재추천: {', '.join(again)}")
        if not o.get("citations") or not (o.get("rationale") or "").strip():
            add("uncited", o, "인용(citations) 또는 근거 문장(rationale) 없음")
    # 6번: 조기 재발 뒤 같은 항HER2 요법을 첫 후보로
    early = _early_her2_drugs(patient_state)
    if options and early and _deemed_met(patient_state, "DEEM-HER2ADC-6M"):
        first = {d.lower() for d in options[0].get("drugs") or []}
        if first and first <= early and any(_her2_drug(d) for d in first):
            add("early_relapse_same_her2_regimen", options[0],
                "보조 항HER2 종료 6개월 안 재발인데 같은 항HER2 요법을 첫 후보로 냄 (2차 선택지 권고)")
    for o in (recommendation or {}).get("supportive_options") or []:   # 보조 약물 칸 (2026-11-04)
        if not o.get("citations") or not (o.get("rationale") or "").strip():
            add("uncited", o, "보조 약물: 인용(citations) 또는 근거 문장(rationale) 없음")
    return out
