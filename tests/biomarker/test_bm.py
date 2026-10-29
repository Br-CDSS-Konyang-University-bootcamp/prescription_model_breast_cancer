"""BM 채점 스크립트 (BM-2 판정, 아형, 치료 상황, BM-4 검사 공백). team_project 폴더에서 실행:
    python -m pytest tests/biomarker        (pytest)
    python -m tests.biomarker.test_bm       (케이스별 PASS/FAIL 출력)

각 케이스는 (case_id, 마커, 입력, 정답 상태, 정답 태그, 메모) 로 적는다.
메모가 있는 케이스는 설계서에 없거나 팀 확인이 필요한 부분이다.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from src.input.script.tcga.tcga_to_patient_state import convert, load_rows

ROOT = Path(__file__).resolve().parents[2]

# BM 파일 이름에 괄호·쉼표가 있어 import 문으로 불러올 수 없으므로 파일 경로로 불러온다
BM_PATH = ROOT / "src" / "biomarker" / "BM1_ER,PR,HER2,Ki_67,subtype.py"
_spec = importlib.util.spec_from_file_location("bm", BM_PATH)
bm = importlib.util.module_from_spec(_spec)
sys.modules["bm"] = bm
_spec.loader.exec_module(bm)

VALID_MARKERS, VALID_STATUS = bm.VALID_MARKERS, bm.VALID_STATUS
assess, assess_receptors = bm.assess, bm.assess_receptors
judge_er, judge_pr, judge_her2, judge_ki67 = bm.judge_er, bm.judge_pr, bm.judge_her2, bm.judge_ki67
subtype_of, molecular_subtype_of = bm.subtype_of, bm.molecular_subtype_of


def f(value, specimen="primary"):
    """값이 있는 칸 (A의 patient_state 형식)"""
    return {"status": "present", "value": value, "specimen": specimen,
            "source": {"doc_id": "D1", "quote": "원문"}}


ND = {"status": "not_done"}
NR = {"status": "not_recorded"}

ER_PR_CASES = [
    # (id, 마커, 칸, 정답 상태, 정답 태그, 메모)
    ("ER01", "ER", f({"percent": 90}), "positive", [], ""),
    ("ER02", "ER", f({"percent": 5}), "low", ["ER-low"], ""),
    ("ER03", "ER", f({"percent": 1}), "low", ["ER-low"], "경계: 1%"),
    ("ER04", "ER", f({"percent": 10}), "low", ["ER-low"], "경계: 10% (PROJECT.md 기준 1~10)"),
    ("ER05", "ER", f({"percent": 11}), "positive", [], ""),
    ("ER06", "ER", f({"percent": 0}), "negative", [], ""),
    ("ER07", "ER", f({"range": [1, 9], "result": "low_positive"}), "low", ["ER-low"], "TCGA 14명 유형"),
    ("ER08", "ER", f({"range": [10, 19], "result": "positive"}), "positive", [], ""),
    ("ER09", "ER", f({"range": [90, 99], "result": "positive"}), "positive", [], ""),
    ("ER10", "ER", f({"range": [0, 0], "result": "negative"}), "negative", [], "TCGA 48명 유형"),
    ("ER11", "ER", f({"range": [0, 9]}), "low", ["ER-low"], "0부터 시작하는 구간은 최대값으로 판정 (2026-10-15)"),
    ("ER32", "ER", f({"range": [0, 1]}), "negative", [], "0부터 시작, 최대 1 -> 음성"),
    ("ER33", "ER", f({"range": [0, 10]}), "low", ["ER-low"], "0부터 시작, 최대 10 -> 저발현"),
    ("ER34", "ER", f({"range": [0, 15]}), "positive", [], "0부터 시작, 최대 15를 percent로 -> 양성"),
    ("ER12", "ER", f({"range": [5, 15]}), "positive", [], "10%에 걸치는 구간은 실무상 양성 (전달 문서 4.1)"),
    ("ER13", "ER", f({"allred": {"total": 5, "ps": 2, "is": 3}}), "low", ["ER-low"], "총점 5 + PS 2"),
    ("ER14", "ER", f({"allred": {"total": 5, "ps": 3, "is": 2}}), "positive", [], "총점 5 + PS 3"),
    ("ER15", "ER", f({"allred": {"total": 5, "ps": 4, "is": 1}}), "positive", [], "총점 5 + PS 4"),
    ("ER16", "ER", f({"allred": {"total": 5}}), "unknown", [], "총점 5, 비율 없음"),
    ("ER17", "ER", f({"allred": {"total": 7}}), "positive", [], "총점만 6~8"),
    ("ER18", "ER", f({"allred": {"total": 2}}), "negative", [], "총점만 0~2"),
    ("ER19", "ER", f({"allred": {"total": 3, "ps": 1, "is": 2}}), "low", ["ER-low"],
     "총점 3~4는 비율과 상관없이 저발현 (2026-10-15 팀 결정, PS 1이어도)"),
    ("ER26", "ER", f({"allred": {"total": 4, "ps": 3, "is": 1}}), "low", ["ER-low"], "총점 4 + PS 3도 저발현"),
    ("ER27", "ER", f({"allred": {"total": 4}}), "low", ["ER-low"], "총점만 3~4"),
    ("ER28", "ER", f({"allred": {"total": 0}}), "negative", [], ""),
    ("ER29", "ER", f({"allred": {"total": 6, "ps": 4, "is": 2}}), "positive", [], ""),
    ("ER30", "ER", f({"percent": 5, "allred": {"total": 5}}), "low", ["ER-low"], "총점 5, 비율은 percent로"),
    ("ER31", "ER", f({"range": [20, 29], "allred": {"total": 5}}), "positive", [], "총점 5, 비율은 range로"),
    ("ER35", "ER", f({"result": "indeterminate"}), "unknown", [], "적힌 판정이 indeterminate"),
    ("ER36", "ER", f({"allred": {"total": 7}, "percent": 5}), "positive", [], "총점과 비율이 달라도 총점"),
    ("ER21", "ER", f({"result": "low_positive"}), "low", ["ER-low"], "적힌 판정만"),
    ("ER22", "ER", f({"range": [0, 0], "result": "positive"}), "negative", [], "수치와 판정 충돌: reason에 확인 필요"),
    ("ER23", "ER", ND, "not_done", [], ""),
    ("ER24", "ER", NR, "not_recorded", [], ""),
    ("ER25", "ER", None, "not_recorded", [], "칸 자체가 없음"),

    # PR 순서 (2026-10-15): Allred 총점 -> range -> percent -> ps -> result -> unknown
    ("PR10", "PR", f({"allred": {"total": 4}}), "positive", [], "1단계 총점 3 이상 -> 양성"),
    ("PR11", "PR", f({"allred": {"total": 3}}), "positive", [], "경계: 총점 3"),
    ("PR12", "PR", f({"allred": {"total": 2}}), "negative", [], "총점 0~2 -> 음성"),
    ("PR09", "PR", f({"allred": {"total": 4, "ps": 2, "is": 2}}), "positive", [], "총점으로 양성 (PR-low 태그 없음)"),
    ("PR17", "PR", f({"allred": {"total": 2}, "percent": 50}), "negative", [], "총점이 있으면 percent보다 총점"),
    ("PR08", "PR", f({"range": [0, 0], "result": "negative"}), "negative", [], "2단계 [0,0] -> 음성 (TCGA 75명)"),
    ("PR07", "PR", f({"range": [10, 19], "result": "positive"}), "positive", [], "최대값 19 >= 10 -> 양성"),
    ("PR06", "PR", f({"range": [1, 9], "result": "positive"}), "positive", [], "경계: 최대값 9 >= 9 -> 양성 (TCGA 49명)"),
    ("PR22", "PR", f({"range": [1, 8]}), "negative", [], "최대값 8 < 9 -> 음성"),
    ("PR18", "PR", f({"range": [0, 15]}), "positive", [], "0부터 시작해도 최대값 15 >= 10 -> 양성"),
    ("PR19", "PR", f({"range": [1, 10]}), "positive", [], "최대값 10 -> 양성"),
    ("PR01", "PR", f({"percent": 0}), "negative", [], "3단계 percent"),
    ("PR03", "PR", f({"percent": 5}), "negative", [], "9% 미만 -> 음성"),
    ("PR02", "PR", f({"percent": 9}), "positive", [], "경계: 9% -> 양성"),
    ("PR23", "PR", f({"percent": 8.5}), "negative", [], "9% 미만 -> 음성"),
    ("PR04", "PR", f({"percent": 10}), "positive", [], "PR-low 태그는 쓰지 않음"),
    ("PR05", "PR", f({"percent": 11}), "positive", [], ""),
    ("PR20", "PR", f({"allred": {"ps": 1}}), "negative", [], "4단계 PS 0~1 -> 음성"),
    ("PR21", "PR", f({"allred": {"ps": 2}}), "positive", [], "PS 2~5 -> 양성"),
    ("PR13", "PR", f({"result": "positive"}), "positive", [], "5단계 result만이면 태그 없음"),
    ("PR14", "PR", f({"result": "low_positive"}), "positive", [], "low_positive -> positive"),
    ("PR16", "PR", f({"result": "indeterminate"}), "unknown", [], "6단계 쓸 값 없음 -> unknown"),
    ("PR15", "PR", ND, "not_done", [], ""),
]


def her2(score=None, faint=None, result=None, ish=None, ish_state="present"):
    ihc_val = {}
    if score is not None:
        ihc_val["score"] = score
    if faint is not None:
        ihc_val["faint"] = faint
    if result is not None:
        ihc_val["result"] = result
    ihc = f(ihc_val) if ihc_val else NR
    if ish_state == "present" and ish is not None:
        ish_field = f({"result": ish, "method": "FISH"})
    elif ish_state == "present":
        ish_field = NR
    else:
        ish_field = {"status": ish_state}
    return ihc, ish_field


HER2_CASES = [
    # 1단계 IHC 3+
    ("H01", her2("3+"), "positive", [], ""),
    ("H16", her2("3+", result="negative"), "positive", [], "3+는 무조건 양성"),
    # 2단계 IHC 2+ -> ISH
    ("H02", her2("2+", ish="amplified"), "positive", [], ""),
    ("H03", her2("2+", ish="not_amplified"), "low", [], "저발현 (HER2-low 태그 없음)"),
    ("H04", her2("2+", ish_state="not_done"), "unknown", [], "ISH 미시행: reason에 ISH 검사 권고"),
    ("H05", her2("2+"), "unknown", [], "ISH 기록 없음"),
    ("H06", her2("2+", ish="equivocal"), "unknown", [], "ISH equivocal은 들어올 수 없는 값"),
    ("H15", her2("2+", result="positive"), "positive", [], "ISH 기록 없음 + 적힌 판정 positive -> 양성 (ISH 검사 권고)"),
    ("H20", her2("2+", result="positive", ish_state="not_done"), "positive", [], "ISH 미시행 + 적힌 판정 positive -> 양성"),
    ("H25", her2("2+", result="negative", ish_state="not_done"), "negative", [], "ISH 미시행 + 적힌 판정 negative -> 음성"),
    ("H26", her2("2+", result="unknown", ish_state="not_done"), "unknown", [], "ISH 없고 판정이 그 외 -> 판정 불가 (TCGA는 삭제)"),
    ("H21", her2("2+", result="positive", ish="equivocal"), "unknown", [], "ISH equivocal은 결과 없음이 아님 -> 판정 불가"),
    # 3단계 IHC 1+
    ("H07", her2("1+"), "low", [], ""),
    ("H08", her2("1+", ish="amplified"), "low", [], "1+는 ISH와 무관"),
    # 4단계 IHC 0
    ("H09", her2("0", faint=True), "ultralow", [], "미약한 막 염색 -> 초저발현 (심평원 기준 최종 음성)"),
    ("H10", her2("0", faint=False), "negative", [], "zero는 쓰지 않음"),
    ("H11", her2("0"), "negative", [], "faint 기록 없음 -> 음성"),
    ("H22", her2("0", ish="amplified"), "unknown", [], "IHC 0 + ISH 증폭은 데이터 오류"),
    # 5단계 점수 없음
    ("H17", her2(ish="amplified"), "positive", [], "ISH 증폭"),
    ("H12", her2(result="positive"), "positive", [], "적힌 판정 positive"),
    ("H13", her2(result="negative"), "negative", [], "적힌 판정 negative"),
    ("H24", (ND, f({"result": "not_amplified", "method": "FISH"})), "negative", [], "IHC 미시행, ISH 비증폭"),
    ("H14", her2(result="unknown"), "unknown", [], "5단계 5번: 팀 확인 중"),
    ("H18", (ND, {"status": "not_recorded"}), "not_done", [], "5단계 6번: IHC 미시행"),
    ("H19", (NR, NR), "not_recorded", [], "5단계 7번"),
]

def recur(field, old_value):
    """재발 재생검 칸에 원발 결과를 history로 붙인다 (전달 문서 3.5)."""
    field = dict(field)
    field["history"] = [{"status": "present", "value": old_value, "specimen": "primary",
                         "superseded_reason": "recurrence"}]
    return field


# A의 전달 문서 8.2절 예시 환자 (재발 환자: ER 70-79 양성 유지, PR 50-59 양성 -> 음성, HER2 2+ / ISH 음성)
SAMPLE_PATIENT = {"fields": {"receptors": {
    "er_percent": recur(f({"range": [70, 79], "result": "positive"}, "metastasis"),
                        {"range": [90, 99], "result": "positive"}),
    "pr_percent": recur(f({"range": [0, 0], "result": "negative"}, "metastasis"),
                        {"range": [50, 59], "result": "positive"}),
    "her2_ihc": f({"score": "2+", "result": "negative"}),
    "her2_ish": f({"result": "not_amplified", "method": "FISH"}),
}}}


def gene(*variants, specimen="primary"):
    """molecular.mutations 한 유전자 칸. 변이를 ('H1047R', 'Missense_Mutation')로 적는다. 비면 변이 없음."""
    vs = [{"protein_change": pc, "variant_type": vt, "vaf": 0.3, "raw": f"{pc} ({vt})"} for pc, vt in variants]
    return {"status": "present", "result": "detected" if vs else "not_detected", "variants": vs, "specimen": specimen}



KI67_CASES = [
    ("K01", f({"percent": 30}), "positive", ["Ki-67-high"], "기준 20% (임시값)"),
    ("K02", f({"percent": 20}), "positive", ["Ki-67-high"], "경계: 20% 이상"),
    ("K03", f({"percent": 10}), "negative", [], ""),
    ("K04", f({"range": [15, 25]}), "intermediate", [], "구간이 기준에 걸침 -> 중간"),
    ("K05", f({"result": "high"}), "positive", ["Ki-67-high"], ""),
    ("K06", NR, "not_recorded", [], "TCGA는 전부 기록 없음"),
    ("K07", f({"result": "intermediate"}), "intermediate", [], "적힌 판정 intermediate"),
    ("K08", f({"range": [25, 40]}), "positive", ["Ki-67-high"], "구간 최소 20 이상"),
    ("K09", f({"range": [5, 15]}), "negative", [], "구간 최대 20 미만"),
    ("K10", ND, "not_done", [], ""),
]

PDL1_CASES = [
    # (id, 칸, 정답 상태, 정답 태그, 메모) - 전달 문서 6.5절
    ("P01", f({"assay": "22C3", "score_type": "CPS", "score": 12}), "positive", ["PD-L1+"], "pembrolizumab 기준. 태그는 C 표준 태그"),
    ("P02", f({"assay": "22C3", "score_type": "CPS", "score": 10}), "positive", ["PD-L1+"], "경계: CPS 10은 양성"),
    ("P03", f({"assay": "22C3", "score_type": "CPS", "score": 5}), "negative", [], ""),
    ("P04", f({"assay": "SP142", "score_type": "IC", "score": 2}), "positive", ["PD-L1+"], "atezolizumab 기준"),
    ("P05", f({"assay": "SP142", "score_type": "IC", "score": 1}), "positive", ["PD-L1+"], "경계: IC 1%는 양성"),
    ("P06", f({"assay": "SP142", "score_type": "IC", "score": 0}), "negative", [], ""),
    ("P07", f({"assay": "SP263", "score_type": "TPS", "score": 50}), "unknown", [], "기준 검사법이 아니면 판정 안 함"),
    ("P08", f({"assay": "22C3", "score_type": "TPS", "score": 50}), "unknown", [], "22C3여도 CPS가 아니면 판정 안 함"),
    ("P09", f({"assay": "22C3", "score_type": "CPS"}), "unknown", [], "점수 없음"),
    ("P10", ND, "not_done", [], ""),
    ("P11", NR, "not_recorded", [], "TCGA는 모두 이 경우"),
]

MOLECULAR_CASES = [
    # (id, 아형, Ki-67 상태값, 정답 분자 아형)
    ("M01", "HR+/HER2-", "negative", "Luminal A"),
    ("M02", "HR+/HER2-", "positive", "Luminal B(HER2 negative)"),
    ("M03", "HR+/HER2-", "intermediate", "Luminal B(HER2 negative)"),
    ("M04", "HR+/HER2-", "not_recorded", "unknown"),
    ("M05", "HR+/HER2-", "unknown", "unknown"),
    ("M06", "HR+/HER2+", "negative", "Luminal B(HER2 positive)"),
    ("M07", "HR+/HER2+", "not_recorded", "Luminal B(HER2 positive)"),
    ("M08", "HR-/HER2+", "positive", "HER2_enriched"),
    ("M09", "TNBC", "not_recorded", "Basal_like"),
    ("M10", "unknown", "positive", "unknown"),
]

SUBTYPE_CASES = [
    # (id, ER, PR, HER2, 정답)
    ("S01", "positive", "positive", "low", "HR+/HER2-"),
    ("S02", "negative", "positive", "positive", "HR+/HER2+"),
    ("S03", "negative", "negative", "positive", "HR-/HER2+"),
    ("S04", "negative", "negative", "negative", "TNBC"),
    ("S05", "low", "negative", "ultralow", "HR+/HER2-"),
    ("S07", "positive", "negative", "unknown", "unknown"),
    ("S08", "not_done", "not_done", "low", "unknown"),
    ("S09", "negative", "unknown", "negative", "unknown"),
]


def patient(ref="TCGA-XX-0001", extent="metastatic", recurrence="none", er=None, pr=None, ihc=None, ish=None,
            mutations=None, treatments=None, pdl1=None):
    """assess()에 넣는 patient_state. 적지 않은 칸은 값 있음 기본값."""
    return {"patient_ref": ref, "fields": {
        "stage": {"disease_extent": {"status": "present", "value": extent}},
        "recurrence": {"status": {"status": "present", "value": recurrence}},
        "receptors": {"er_percent": er or f({"percent": 90}), "pr_percent": pr or f({"percent": 50}),
                      "her2_ihc": ihc or f({"score": "1+"}), "her2_ish": ish or NR, "pdl1": pdl1 or NR},
        "proliferation": {"ki67_percent": NR},
        "molecular": {"mutations": mutations if mutations is not None else
                      {g: gene() for g in ("ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2")}},
        "treatment_history": treatments or [],
    }}


TNBC = dict(er=f({"percent": 0}), pr=f({"percent": 0}), ihc=f({"score": "0"}))


def with_germline(germline, **tumor):
    """생식세포 칸(molecular.germline)을 더한 VC 환자. tumor는 mutations에서 바꿀 유전자 칸."""
    ps = patient(ref="VC-1")
    ps["fields"]["molecular"]["mutations"].update(tumor)
    ps["fields"]["molecular"]["germline"] = germline
    return ps


def genes_with(field):
    """유전자 7개를 모두 같은 칸(미시행·기록 없음 등)으로 채운 molecular.mutations."""
    return {g: dict(field) for g in ("ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2")}

ASSESS_CASES = [
    # (id, patient_state, 정답 subtype, 정답 disease, 정답 tests_needed rule_id 모음, 메모)
    ("A01", patient(), "HR+/HER2-", "metastatic", set(), "HR+/HER2- 전이성, 유전자 검사 모두 시행"),
    ("A02", patient(extent="early"), "HR+/HER2-", "early", set(), "조기"),
    ("A03", patient(extent="early", recurrence="distant"), "HR+/HER2-", "metastatic", set(), "원격 전이 재발 -> 전이성"),
    ("A04", patient(extent="locally_advanced", recurrence="locoregional"), "HR+/HER2-", "locally_advanced", set(),
     "국소 재발은 전이 아님"),
    ("A05", patient(ihc=f({"score": "2+"}), ish={"status": "not_done"}), "unknown", "metastatic",
     {"BM4-HER2-ISH"}, "IHC 2+ ISH 미시행"),
    ("A10", patient(ihc=f({"score": "2+", "result": "positive"}), ish={"status": "not_done"}), "HR+/HER2+", "metastatic",
     {"BM4-HER2-ISH"}, "IHC 2+ ISH 미시행 + 판정 positive -> 양성, ISH 검사 권고"),
    ("A06", patient(pdl1={"status": "not_done"}, **TNBC), "TNBC", "metastatic",
     {"BM4-PDL1", "BM4-HER2-REASSESS"}, "전이성 TNBC, PD-L1 미시행, HER2 0 재판정 확인"),
    ("A07", patient(ihc=f({"result": "negative"})), "HR+/HER2-", "metastatic", {"BM4-HER2-REASSESS"},
     "판정만 negative: 아형은 HER2-, 전이성이라 재판정 확인"),
    ("A09", patient(er={"status": "not_done"}), "HR+/HER2-", "metastatic", {"BM4-ER"},
     "ER 미시행이어도 PR 양성이면 HR+"),
    # 유전자 검사 공백 (PROJECT.md 5절, 2026-10-16)
    ("A11", patient(mutations=genes_with(ND)), "HR+/HER2-", "metastatic",
     {"BM4-GBRCA1", "BM4-GBRCA2", "BM4-PALB2", "BM4-PIK3CA", "BM4-AKT1", "BM4-PTEN", "BM4-ESR1"},
     "전이성 HR+/HER2-, 유전자 7개 모두 미시행"),
    ("A12", patient(mutations=genes_with(ND), **TNBC), "TNBC", "metastatic",
     {"BM4-GBRCA1", "BM4-GBRCA2", "BM4-PALB2", "BM4-HER2-REASSESS"},
     "전이성 TNBC: BRCA·PALB2만 권고 (PIK3CA·ESR1은 HR+/HER2- 대상)"),
    ("A13", patient(mutations=genes_with(NR)), "HR+/HER2-", "metastatic", set(),
     "기록 없음은 권고하지 않음 (B 결정 2026-10-16, 선택지 가)"),
    ("A14", patient(extent="early", mutations=genes_with(ND)), "HR+/HER2-", "early", set(), "조기는 유전자 권고 없음"),
    ("A15", patient(ref="VC-0001", mutations=genes_with(ND)), "HR+/HER2-", "metastatic",
     {"BM4-GBRCA1", "BM4-GBRCA2", "BM4-PALB2", "BM4-PIK3CA", "BM4-AKT1", "BM4-PTEN", "BM4-ESR1"},
     "TCGA가 아닌 차트도 BRCA는 gBRCA라 미시행이면 권고 (전달 문서 4.7절, A 결정 2026-10-21)"),
    ("A16", patient(ihc=f({"score": "3+"}), mutations=genes_with(ND)), "HR+/HER2+", "metastatic", set(),
     "HER2 양성은 유전자 권고 대상 아님"),
    ("A17", patient(treatments=[{"drugs": ["letrozole"], "start_day": 1500, "best_response": "PD",
                                 "stop_reason": None}]), "HR+/HER2-", "metastatic", {"BM4-ESR1-RETEST"},
     "원발 ESR1 결과 + 내분비요법 진행 -> 재검 권고"),
    # 미시행 + raw "결과 대기"·"예정" -> 검사 권고 대신 결과 확인 (전달 문서 0절 5번, B 결정 2026-10-19)
    ("A18", patient(mutations=genes_with({"status": "not_done", "raw": "결과 대기"})), "HR+/HER2-", "metastatic",
     {"BM4-GBRCA1-PENDING", "BM4-GBRCA2-PENDING", "BM4-PALB2-PENDING", "BM4-PIK3CA-PENDING", "BM4-AKT1-PENDING",
      "BM4-PTEN-PENDING", "BM4-ESR1-PENDING"}, "유전자 검사 결과 대기"),
    ("A19", patient(mutations=genes_with({"status": "not_done", "raw": "예정"})), "HR+/HER2-", "metastatic",
     {"BM4-GBRCA1-SCHEDULED", "BM4-GBRCA2-SCHEDULED", "BM4-PALB2-SCHEDULED", "BM4-PIK3CA-SCHEDULED",
      "BM4-AKT1-SCHEDULED", "BM4-PTEN-SCHEDULED", "BM4-ESR1-SCHEDULED"}, "유전자 검사 예약"),
    ("A20", patient(pdl1={"status": "not_done", "raw": "예정"}, **TNBC), "TNBC", "metastatic",
     {"BM4-PDL1-SCHEDULED", "BM4-HER2-REASSESS"}, "PD-L1 검사 예약"),
    ("A21", patient(er={"status": "not_done", "raw": "결과 대기"}), "HR+/HER2-", "metastatic", {"BM4-ER-PENDING"},
     "ER 결과 대기"),
    ("A22", patient(mutations=genes_with({"status": "not_done", "raw": "시행하지 않음"})), "HR+/HER2-", "metastatic",
     {"BM4-GBRCA1", "BM4-GBRCA2", "BM4-PALB2", "BM4-PIK3CA", "BM4-AKT1", "BM4-PTEN", "BM4-ESR1"},
     "raw가 고정 표기가 아니면 그대로 검사 권고"),
]


MIS, NON, FS = "Missense_Mutation", "Nonsense_Mutation", "Frame_Shift_Del"

GERMLINE_CASES = [
    # (id, patient_state, 정답 marker, 정답 상태, 정답 이유 시작, BM-4 권고 rule_id 포함 여부, 메모)
    # 생식세포 칸 우선 (A 결정 2026-10-28, PROJECT.md §14, draft7 체크리스트 §1.1)
    ("GL01", with_germline({"BRCA1": gene(("Q1756Pfs*74", FS), specimen=None)}, BRCA1=NR),
     "gBRCA1", "positive", "생식세포 검사: ", False, "VC-0116처럼 생식세포 양성 + 종양 기록 없음 -> 양성"),
    ("GL02", with_germline({"BRCA2": gene(specimen=None)}, BRCA2=gene(("X2602_splice", "Splice_Site"))),
     "gBRCA2", "negative", "생식세포 검사: ", False, "생식세포 음성이면 종양 양성보다 생식세포 결과를 쓴다"),
    ("GL03", with_germline({"BRCA1": NR}, BRCA1=gene(("Q934*", NON))),
     "gBRCA1", "positive", "종양 검사 결과 (생식세포 검사 결과 없음): ", False,
     "생식세포 결과가 없으면 2순위로 종양 결과"),
    ("GL04", with_germline({"PALB2": ND}, PALB2=NR),
     "PALB2", "not_done", "생식세포 검사: ", True, "둘 다 결과 없음 -> 생식세포 미시행, 검사 권고"),
    ("GL05", with_germline({"BRCA2": NR}, BRCA2=NR),
     "gBRCA2", "not_recorded", "생식세포 검사: ", False, "기록 없음은 권고하지 않음 (PROJECT.md §14, VC-0132)"),
    ("GL06", patient(ref="VC-1", mutations={**genes_with({"status": "present", "result": "not_detected",
                                                          "variants": []}), "BRCA1": gene(("Q934*", NON))}),
     "gBRCA1", "positive", "BRCA1 ", False, "생식세포 칸이 없으면(TCGA 등) 지금처럼 mutations만"),
]

GENE_CASES = [
    # (id, 유전자, patient_ref, 칸, 정답 marker, 정답 상태, 정답 태그, 메모)
    ("G01", "PIK3CA", "VC-1", gene(("H1047R", MIS)), "PIK3CA", "positive", ["PIK3CA-mut"], "알펠리십 동반진단 변이"),
    ("G02", "PIK3CA", "VC-1", gene(("N345K", MIS)), "PIK3CA", "vus", [], "목록에 없는 변이 -> VUS (BM-3에서 다시 판정)"),
    ("G03", "PIK3CA", "VC-1", gene(("M1004I", MIS), ("E542K", MIS)), "PIK3CA", "positive", ["PIK3CA-mut"],
     "여러 변이 중 하나라도 목록에 있으면 양성"),
    ("G04", "PIK3CA", "VC-1", gene(), "PIK3CA", "negative", [], ""),
    ("G05", "PIK3CA", "VC-1", ND, "PIK3CA", "not_done", [], ""),
    ("G06", "PIK3CA", "VC-1", NR, "PIK3CA", "not_recorded", [], ""),
    ("G07", "AKT1", "VC-1", gene(("E17K", MIS)), "AKT1", "positive", ["AKT1-mut"], "변이 목록 원문 확인 필요"),
    ("G08", "AKT1", "VC-1", gene(("L52R", MIS)), "AKT1", "vus", [], ""),
    ("G09", "PTEN", "VC-1", gene(("R130*", NON)), "PTEN", "positive", ["PTEN-alt"],
     "PTEN은 변이 유무로 판정 (팀 회의 2026-10-20). 태그는 C 표준 태그 (RAG 설계 3.5절)"),
    ("G10", "PTEN", "VC-1", gene(("K267Rfs*9", "Frame_Shift_Ins")), "PTEN", "positive", ["PTEN-alt"], ""),
    ("G11", "PTEN", "VC-1", gene(("R130Q", MIS)), "PTEN", "positive", ["PTEN-alt"],
     "미스센스도 단백질이 바뀌는 변이라 양성 (ClinVar는 근거로만)"),
    ("G20", "PTEN", "VC-1", gene(("H64_Y65del", "In_Frame_Del")), "PTEN", "positive", ["PTEN-alt"], ""),
    ("G21", "PTEN", "VC-1", gene(("P38P", "Silent")), "PTEN", "negative", [],
     "단백질이 안 바뀌는 변이만 있으면 음성"),
    ("G12", "BRCA1", "TCGA-XX-0001", gene(("Q934*", NON)), "gBRCA1", "positive", ["gBRCA"],
     "TCGA는 gBRCA로 가정 (전달 문서 4.7절)"),
    ("G13", "BRCA1", "TCGA-XX-0001", gene(("E9Q", MIS)), "gBRCA1", "vus", [],
     "전달 문서 4.7절 예시. ClinVar Uncertain significance"),
    ("G14", "BRCA2", "TCGA-XX-0001", gene(("X2602_splice", "Splice_Site")), "gBRCA2", "positive", ["gBRCA"], ""),
    ("G15", "BRCA2", "VC-1", gene(), "gBRCA2", "negative", [], "TCGA가 아니어도 gBRCA (A 결정 2026-10-21)"),
    ("G16", "PALB2", "VC-1", gene(("L381V", MIS)), "PALB2", "vus", [], "ClinVar에 없음"),
    ("G17", "PALB2", "VC-1", gene(("T1030Ifs*13", FS)), "PALB2", "vus", [],
     "PALB2는 절단 변이 규칙이 없고 ClinVar 기준만 (전달 문서 5.4절). 이 이름은 ClinVar에 없음"),
    ("G19", "ESR1", "VC-1", gene(("E380Q", MIS)), "ESR1", "positive", ["ESR1-mut"],
     "FDA 동반진단 범위 codon 310~547 미스센스는 VUS 여부와 관계없이 양성 (A 확인 2026-10-22, 국내 미허가)"),
    ("G22", "ESR1", "VC-1", gene(("A593D", MIS)), "ESR1", "vus", [], "codon 547 밖의 미스센스는 VUS"),
    ("G23", "ESR1", "VC-1", gene(("I451_I452del", "In_Frame_Del")), "ESR1", "vus", [], "범위 안이라도 미스센스가 아니면 VUS"),
    ("G18", "ESR1", "VC-1", gene(("D538G", MIS)), "ESR1", "positive", ["ESR1-mut"], "변이 목록 원문 확인 필요"),
]

# ESR1 재검 (전달 문서 4.6절): (id, ESR1 칸, treatment_history, 정답 상태)
_AI_PD = [{"drugs": ["letrozole"], "start_day": 1500, "best_response": "PD", "stop_reason": None}]
_AI_CR = [{"drugs": ["letrozole"], "start_day": 300, "best_response": "CR", "stop_reason": None}]
_CHEMO_PD = [{"drugs": ["docetaxel"], "start_day": 1500, "best_response": "PD", "stop_reason": None}]
# ClinVar 표가 있어야 정답이 나오는 GENE_CASES (표는 git에 없음, 각자 받음)
CLINVAR_DEPENDENT = set()

# BM-3 ClinVar (전달 문서 5.4절, data/clinvar/clinvar_bm3_genes.tsv): (id, 유전자, 칸, 정답 상태, 정답 규칙 ID, 메모)
CLINVAR_CASES = [
    ("C01", "BRCA1", gene(("C61G", MIS)), "positive", "BM3-BRCA1-CLINVAR", "Pathogenic, 전문가 패널 3성"),
    ("C02", "BRCA1", gene(("G1788V", MIS)), "positive", "BM3-BRCA1-CLINVAR", "TCGA-AN-A0XU"),
    ("C03", "BRCA1", gene(("E9Q", MIS)), "vus", "BM2-BRCA1-VUS", "Uncertain significance"),
    ("C04", "PTEN", gene(("M198K", MIS)), "positive", "BM2-PTEN-PRESENT",
     "PTEN은 변이 유무로 판정, ClinVar(Likely pathogenic 1성)는 근거로만 (팀 회의 2026-10-20)"),
    ("C05", "PALB2", gene(("L381V", MIS)), "vus", "BM2-PALB2-VUS", "ClinVar에 없음"),
    ("C08", "PALB2", gene(("Y551*", "Nonsense_Mutation")), "positive", "BM3-PALB2-CLINVAR",
     "PALB2 절단 변이도 ClinVar 기준으로만 양성 (Pathogenic/Likely pathogenic 2성)"),
    ("C06", "BRCA1", gene(("E9Q", MIS), ("C61G", MIS)), "positive", "BM3-BRCA1-CLINVAR",
     "여러 변이 중 하나라도 기준 충족이면 양성"),
]

# 차수 setting.line (전달 문서 6.2절, draft6): (id, 현재 범주, treatment_history, 정답 line, 메모)
def tx(drugs, setting, start, line=None, endo=None, chemo=None, resp="unknown", stop=None):
    return {"drugs": drugs, "setting": setting, "start_day": start, "line": line, "endocrine_line": endo,
            "chemo_line": chemo, "best_response": resp, "stop_reason": stop}


LINE_CASES = [
    ("L01", "metastatic", [tx(["letrozole", "palbociclib"], "metastatic", 1500, 1, endo=1)], "1L", "1차 진행 기록 없음"),
    ("L02", "metastatic", [tx(["letrozole", "palbociclib"], "metastatic", 1500, 1, endo=1, resp="PD")], "2L",
     "1차에서 진행 -> 2차 대상 (전달 문서 8.2절 예시)"),
    ("L03", "metastatic", [tx(["capecitabine"], "metastatic", 180, 1, chemo=1),
                           tx(["docetaxel"], "metastatic", 242, 2, chemo=2, stop="progression")], ">=3L",
     "2차에서 진행 -> 3차 이상"),
    ("L04", "metastatic", [tx(["paclitaxel"], "adjuvant", 69)], "1L",
     "전이 후 투약 없음: 이번에 결정할 차수는 1차 (handoff_confirmed_state_to_B.md §6 1번, VC-0103)"),
    ("L05", "metastatic", [tx(["letrozole"], "metastatic", 1500)], "unknown", "전이 후 투약은 있는데 line 없음"),
    ("L06", "early", [tx(["doxorubicin"], "adjuvant", 30), tx(["zoledronic acid"], "adjuvant", 400)], "adjuvant",
     "골 보호제는 차수를 정하지 않음"),
    ("L07", "early", [tx(["anastrozole"], "neoadjuvant", 10)], "neoadjuvant", ""),
    ("L08", "early", [], "unknown", "투약 기록 없음"),
]

# 전이성 내분비·항암 차수 setting.line_endocrine / line_chemo (A 전달 문서 handoff_confirmed_state_to_B.md §6 2번):
# (id, 아형, treatment_history, 정답 내분비, 정답 항암, 메모)
LINE_KIND_CASES = [
    ("LK01", "HR+/HER2-", [tx(["anastrozole"], "adjuvant", 40)], "1L", "1L",
     "전이 후 투약 없음: 결정할 차수는 둘 다 1차 (VC-0103)"),
    ("LK02", "HR+/HER2-", [tx(["letrozole", "palbociclib"], "metastatic", 1500, 1, endo=1, resp="PD")], "2L", "1L",
     "내분비 1차 진행 -> 내분비 2차, 항암은 따로 세서 1차"),
    ("LK03", "HR+/HER2-", [tx(["letrozole"], "metastatic", 1500, 1, endo=1)], "1L", "1L", "진행 기록 없으면 그 차수"),
    ("LK04", "TNBC", [tx(["capecitabine"], "metastatic", 180, 1, chemo=1),
                      tx(["docetaxel"], "metastatic", 242, 2, chemo=2, stop="progression")], "not_applicable", ">=3L",
     "HR 음성은 내분비 대상 아님"),
    ("LK05", "HR+/HER2-", [tx(["letrozole"], "metastatic", 1500)], "unknown", "unknown", "전이 후 투약은 있는데 line 없음"),
    ("LK06", "HR+/HER2-", [tx(["paclitaxel"], "metastatic", 100, 1, chemo=1, resp="PD"),
                           tx(["letrozole"], "metastatic", 300, 2, endo=1)], "1L", "2L",
     "항암 1차 진행 후 내분비 시작: 전체로는 2차지만 내분비 1차, 항암 2차 (공고 p.55 따로 셈)"),
]

# BM-3 CIViC (전달 문서 5.4절, 판정에 쓰지 않고 근거로만 2026-10-20, data/civic/civic_bm3_evidence_<받은 날>.csv): (id, 유전자, 칸, 정답 상태, 정답 규칙 ID, 정답 태그, 메모)
CIVIC_CASES = [
    ("V01", "PIK3CA", gene(("R88Q", MIS)), "vus", "BM2-PIK3CA-VUS", [],
     "허가 목록 밖. CIViC 근거 등급 A는 이유에만 적고 판정에 쓰지 않음 (팀 회의 2026-10-20, TCGA-A2-A04P)"),
    ("V02", "PIK3CA", gene(("H1047R", MIS)), "positive", "BM2-PIK3CA-LABEL", ["PIK3CA-mut"],
     "허가 목록이 CIViC보다 먼저"),
    ("V03", "PIK3CA", gene(("N345K", MIS)), "vus", "BM2-PIK3CA-VUS", [], "CIViC에 감수성 근거 없음"),
    ("V04", "AKT1", gene(("Q79K", MIS)), "vus", "BM2-AKT1-VUS", [], "CIViC 근거가 내성(Resistance)뿐이라 양성 아님"),
    ("V05", "PIK3CA", gene(("N345K", MIS), ("K111N", MIS)), "vus", "BM2-PIK3CA-VUS", [],
     "CIViC 근거가 있어도 판정은 허가 목록으로만"),
]

EVIDENCE_CASES = [
    ("EV01", "PIK3CA", "VC-1", gene(("H1047R", MIS)),
     ["H1047R (Missense_Mutation, VAF 0.3)", "허가 동반진단 목록: H1047R 해당", "급여: 심평원 공고책자 2026-11-01판 p.167·170",
      "지침: ESMO MBC 2026 p.1205"], "변이 종류·VAF, 허가 목록, 급여·지침 쪽 번호"),
    ("EV02", "PIK3CA", "VC-1", gene(("N345K", MIS)), ["허가 동반진단 목록: 해당 없음"], "VUS도 근거를 적음"),
    ("EV03", "PTEN", "VC-1", gene(("R130*", NON)), ["절단형", "급여: 심평원 공고책자 2026-11-01판 p.167", "combo-r22"],
     "절단형은 판정이 아니라 근거로만"),
    ("EV04", "ESR1", "VC-1", gene(("D538G", MIS)), ["급여: B가 연결한 심평원 행 없음 (D 확인 전)", "지침: ESMO MBC 2026 p.1206"],
     "B가 연결한 심평원 행이 없는 유전자"),
    ("EV05", "BRCA1", "VC-1", gene(("Q934*", NON)), ["p.171–173", "combo-r31"],
     "TCGA가 아닌 차트도 gBRCA라 olaparib 행 (A 결정 2026-10-21)"),
    ("EV06", "BRCA1", "TCGA-XX-0001", gene(("Q934*", NON)), ["p.171–173", "combo-r31"], "gBRCA는 olaparib 허가사항"),
    ("EV07", "PIK3CA", "VC-1", gene(("N345K", MIS)), ["VUS 포함 여부는 FDA 작성 자료로 확인 불가"],
     "capivasertib·inavolisib는 FDA 승인 검사로 검출된 변이가 대상, VUS 포함 여부 미확인 표시 (A 확인 2026-10-22)"),
    ("EV08", "ESR1", "VC-1", gene(("E380Q", MIS)), ["판단 기준: FDA 동반진단 목록 elacestrant", "국내 미허가"],
     "ESR1 FDA 범위 판정은 판단 기준을 FDA로 표시"),
]

ESR1_CASES = [
    ("E01", gene(), _AI_PD, "retest_needed", "원발 음성 + 내분비요법 진행"),
    ("E02", gene(), _AI_CR, "negative", "진행 없음"),
    ("E03", gene(), _CHEMO_PD, "negative", "항암화학요법 진행은 해당 없음"),
    ("E04", gene(specimen="cfDNA"), _AI_PD, "negative", "진행 후 cfDNA 결과는 그대로 씀"),
    ("E05", ND, _AI_PD, "not_done", "미시행은 미시행 그대로 (검사 권고는 BM-4)"),
]


def handoff_example():
    """전달 문서 8.2절의 가상 차트 입력과 기대 출력."""
    text = (ROOT / "src" / "input" / "handoff_to_B.md").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"<!-- validate:(\w+) -->\s*```json\s*(.*?)```", text, re.S))
    return json.loads(blocks["patient_state"]), json.loads(blocks["biomarker_record"])


def check_shape(rec):
    """biomarker_record.json 의 record 정의와 맞는 모양인지 확인한다."""
    problems = []
    for key in ("marker", "status", "reason", "source_span", "rag_tags"):
        if key not in rec:
            problems.append(f"필수 키 없음: {key}")
    if rec.get("marker") not in VALID_MARKERS:
        problems.append(f"허용되지 않는 marker: {rec.get('marker')}")
    if rec.get("status") not in VALID_STATUS:
        problems.append(f"허용되지 않는 status: {rec.get('status')}")
    sp = rec.get("source_span") or {}
    if set(sp) != {"doc_id", "quote"}:
        problems.append("source_span 은 doc_id, quote 두 키만 있어야 함")
    return problems


def main():
    passed = failed = 0

    def report(case_id, ok, note, detail):
        nonlocal passed, failed
        tag = "PASS" if ok else "FAIL"
        passed += ok
        failed += (not ok)
        extra = f"  (메모: {note})" if note else ""
        print(f"{tag}   {case_id:5} {detail}{extra}")

    for case_id, marker, field, exp_status, exp_tags, note in ER_PR_CASES:
        rec = (judge_er if marker == "ER" else judge_pr)(field)
        ok = rec["status"] == exp_status and rec["rag_tags"] == exp_tags and not check_shape(rec)
        detail = f"{rec['status']} {rec['rag_tags']}"
        if not ok:
            detail += f"  / 정답: {exp_status} {exp_tags}  / {rec['reason']} {check_shape(rec)}"
        report(case_id, ok, note, detail)

    for case_id, (ihc, ish), exp_status, exp_tags, note in HER2_CASES:
        rec = judge_her2(ihc, ish)
        ok = rec["status"] == exp_status and rec["rag_tags"] == exp_tags and not check_shape(rec)
        detail = f"{rec['status']} {rec['rag_tags']}"
        if not ok:
            detail += f"  / 정답: {exp_status} {exp_tags}  / {rec['reason']} {check_shape(rec)}"
        report(case_id, ok, note, detail)

    # 말 그대로 reason 에 들어가야 하는 문구 확인
    extra_checks = [
        ("R01", judge_er(f({"range": [0, 0], "result": "positive"}))["reason"], "확인 필요"),
        ("R02", judge_her2(*her2("2+", ish_state="not_done"))["reason"], "ISH 검사 권고"),
        ("R04", judge_er(f({"allred": {"total": 5}}))["reason"], "비율(PS) 확인 권고"),
        ("R08", judge_her2(*her2("2+", result="positive"))["reason"], "ISH 검사 권고"),
        ("R10", judge_her2(*her2("0", faint=True))["reason"], "심평원 기준 최종 음성"),
        ("R09", judge_her2(*her2("0", ish="amplified"))["reason"], "원자료 확인 필요"),
        ("R05", judge_pr(SAMPLE_PATIENT["fields"]["receptors"]["pr_percent"])["reason"],
         "원발 positive에서 negative로 바뀜"),
        ("R06", judge_er(SAMPLE_PATIENT["fields"]["receptors"]["er_percent"])["reason"],
         "원발 결과(positive)에서 유지"),
        ("R07", judge_her2(recur(f({"score": "0"}, "metastasis"), {"score": "1+"}), NR)["reason"],
         "재생검 결과로 판정"),
    ]
    rebiopsy = f({"score": "1+"})
    rebiopsy["history"] = [{"status": "present", "value": {"score": "3+"}, "specimen": "metastasis",
                            "superseded_reason": "newer_result"}]
    got = judge_her2(rebiopsy, NR)["status"]
    report("R11", got == "positive", "", f"재생검(3+)이 history에 있으면 재생검 우선 -> {got}")
    for case_id, reason, needle in extra_checks:
        report(case_id, needle in reason, "", f"reason에 '{needle}' 포함")

    # 유전자 7개 (전달 문서 3.6·4.6·4.7·5.4절)
    clinvar_ready = bm.CLINVAR_CSV.exists()
    if not clinvar_ready:
        print("SKIP   ClinVar 케이스 (G11, C01~C08): data/clinvar/clinvar_bm3_genes.tsv 없음. "
              "python data/script/clinvar_download.py 실행 후 다시 시험")
    for case_id, g, ref, field, exp_marker, exp_status, exp_tags, note in GENE_CASES:
        if case_id in CLINVAR_DEPENDENT and not clinvar_ready:
            continue
        rec = bm.judge_gene(g, field, ref)
        ok = (rec["marker"] == exp_marker and rec["status"] == exp_status and rec["rag_tags"] == exp_tags
              and not check_shape(rec))
        detail = f"{rec['marker']} {rec['status']} {rec['rag_tags']}"
        if not ok:
            detail += f"  / 정답: {exp_marker} {exp_status} {exp_tags}  / {rec['reason']} {check_shape(rec)}"
        report(case_id, ok, note, detail)
    for case_id, g, field, exp_status, exp_rule, note in CLINVAR_CASES if clinvar_ready else []:
        rec = bm.judge_gene(g, field, "TCGA-XX-0001")
        ok = rec["status"] == exp_status and rec["rule_id"] == exp_rule and not check_shape(rec)
        report(case_id, ok, note, f"{rec['marker']} {rec['status']} {rec['rule_id']} {rec['evidence'].get('clinvar')}"
               + ("" if ok else f"  / 정답: {exp_status} {exp_rule} / {rec['reason']}"))
    # ClinVar 파일이 없으면 BM-3 없이 VUS로 남고 이유에 실행 안내가 붙는다
    saved_path, saved_cache = bm.CLINVAR_CSV, getattr(bm._clinvar, "cache", None)
    bm.CLINVAR_CSV = bm.CLINVAR_CSV.with_name("없는_파일.csv")
    if hasattr(bm._clinvar, "cache"):
        del bm._clinvar.cache
    rec = bm.judge_gene("BRCA1", gene(("C61G", MIS)), "TCGA-XX-0001")
    report("C07", rec["status"] == "vus" and "clinvar_download.py" in rec["reason"], "ClinVar 파일 없음",
           f"{rec['status']} / {rec['reason']}")
    bm.CLINVAR_CSV = saved_path
    if saved_cache is not None:
        bm._clinvar.cache = saved_cache
    elif hasattr(bm._clinvar, "cache"):
        del bm._clinvar.cache

    for case_id, disease, history, exp_line, note in LINE_CASES:
        got, why = bm.line_of({"treatment_history": history}, disease)
        report(case_id, got == exp_line, note, f"{disease} -> {got}" + ("" if got == exp_line else f" / 정답 {exp_line} / {why}"))
    for case_id, subtype, history, exp_endo, exp_chemo, note in LINE_KIND_CASES:
        got = (bm.line_kind_of({"treatment_history": history}, "endocrine", subtype)[0],
               bm.line_kind_of({"treatment_history": history}, "chemo", subtype)[0])
        report(case_id, got == (exp_endo, exp_chemo), note,
               f"내분비 {got[0]}, 항암 {got[1]}" + ("" if got == (exp_endo, exp_chemo) else f" / 정답 {exp_endo}, {exp_chemo}"))
    early = bm.setting_of({"treatment_history": [], "stage": {"disease_extent": {"status": "present", "value": "early"}}})
    report("LK07", "line_endocrine" not in early and "line_chemo" not in early, "조기는 내분비·항암 차수 칸을 만들지 않음",
           str(early))
    deemed = {"treatment_history": [tx(["eribulin"], "metastatic", 900, 1, chemo=1)],
              "deemed_lines": [{"rule_id": "DEEM-ANTHRA-TAXANE", "status": "met"},
                               {"rule_id": "DEEM-SG-1Y", "status": "not_met"}],
              "stage": {"disease_extent": {"status": "present", "value": "metastatic"}}}
    reason = bm.setting_of(deemed)["reason"]
    report("L09", "DEEM-ANTHRA-TAXANE" in reason and "DEEM-SG-1Y" not in reason, "충족(met)한 간주 규칙만 이유에 적음",
           reason)

    for case_id, g, field, exp_status, exp_rule, exp_tags, note in CIVIC_CASES:
        rec = bm.judge_gene(g, field, "TCGA-XX-0001")
        ok = (rec["status"] == exp_status and rec["rule_id"] == exp_rule and rec["rag_tags"] == exp_tags
              and not check_shape(rec))
        report(case_id, ok, note, f"{rec['marker']} {rec['status']} {rec['rule_id']} {rec['rag_tags']}"
               + ("" if ok else f"  / 정답: {exp_status} {exp_rule} {exp_tags} / {rec['reason']}"))
    reason = bm.judge_gene("PIK3CA", gene(("R88Q", MIS)), "TCGA-XX-0001")["reason"]
    report("V06", "등급 A" in reason and "EID" in reason, "근거 등급과 근거 번호를 이유에 남김", reason)
    saved_path, saved_cache = bm.CIVIC_CSV, getattr(bm._civic, "cache", None)
    bm.CIVIC_CSV = bm.CIVIC_CSV.with_name("없는_파일.csv")
    if hasattr(bm._civic, "cache"):
        del bm._civic.cache
    rec = bm.judge_gene("PIK3CA", gene(("R88Q", MIS)), "TCGA-XX-0001")
    report("V07", rec["status"] == "vus" and "civic_download.py" in rec["reason"], "CIViC 파일 없음",
           f"{rec['status']} / {rec['reason']}")
    bm.CIVIC_CSV = saved_path
    if saved_cache is not None:
        bm._civic.cache = saved_cache
    elif hasattr(bm._civic, "cache"):
        del bm._civic.cache

    # 근거 표시 (팀 회의 2026-10-20 5번): (id, 유전자, patient_ref, 칸, 이유에 있어야 할 글, 메모)
    for case_id, g, ref, field, needles, note in EVIDENCE_CASES:
        reason = bm.judge_gene(g, field, ref)["reason"]
        missing = [n for n in needles if n not in reason]
        report(case_id, not missing, note, reason + (f"  / 없는 글: {missing}" if missing else ""))

    for case_id, field, history, exp_status, note in ESR1_CASES:
        rec = bm.judge_esr1(field, {"treatment_history": history})
        ok = rec["status"] == exp_status and not check_shape(rec)
        report(case_id, ok, note, f"ESR1 {rec['status']}" + ("" if ok else f"  / 정답: {exp_status} / {rec['reason']}"))

    # A의 예시 환자 한 명 전체
    records = assess_receptors(SAMPLE_PATIENT)
    got = {r["marker"]: r["status"] for r in records}
    ok = got == {"ER": "positive", "PR": "negative", "HER2": "low"} and not any(check_shape(r) for r in records)
    report("SAMP", ok, "", f"예시 환자(A 문서 6절): {got}")

    def judged(case_id, rec, exp_status, exp_tags, note):
        ok = rec["status"] == exp_status and rec["rag_tags"] == exp_tags and not check_shape(rec)
        detail = f"{rec['marker']} {rec['status']} {rec['rag_tags']}"
        if not ok:
            detail += f"  / 정답: {exp_status} {exp_tags}  / {rec['reason']} {check_shape(rec)}"
        report(case_id, ok, note, detail)

    for case_id, field, exp_status, exp_tags, note in KI67_CASES:
        judged(case_id, judge_ki67(field), exp_status, exp_tags, note)
    for case_id, field, exp_status, exp_tags, note in PDL1_CASES:
        judged(case_id, bm.judge_pdl1(field), exp_status, exp_tags, note)
    for case_id, er, pr, h2, expected in SUBTYPE_CASES:
        got = subtype_of(er, pr, h2)
        report(case_id, got == expected, "",
               f"아형 {er}/{pr}/{h2} -> {got}" + ("" if got == expected else f" / 정답 {expected}"))

    schema = json.loads((ROOT / "schemas" / "biomarker_record.json").read_text(encoding="utf-8"))
    for case_id, sub, ki, expected in MOLECULAR_CASES:
        got = molecular_subtype_of(sub, ki)
        report(case_id, got == expected, "",
               f"분자 아형 {sub} + Ki-67 {ki} -> {got}" + ("" if got == expected else f" / 정답 {expected}"))

    validator = Draft202012Validator(schema)
    for case_id, ps, exp_sub, exp_disease, exp_tests, note in ASSESS_CASES:
        out = assess(ps)
        errors = [e.message for e in validator.iter_errors(out)]
        tests = {t["rule_id"] for t in out["tests_needed"]}
        ok = (out["subtype"] == exp_sub and out["setting"]["disease"] == exp_disease and tests == exp_tests
              and not errors)
        detail = f"{out['subtype']} {out['setting']['disease']} {sorted(tests)}"
        if not ok:
            detail += f"  / 정답: {exp_sub} {exp_disease} {sorted(exp_tests)} {errors[:1]}"
        report(case_id, ok, note, detail)

    for case_id, ps, marker, exp_status, exp_reason, exp_test, note in GERMLINE_CASES:
        out = assess(ps)
        rec = next(r for r in out["records"] if r["marker"] == marker)
        test = f"BM4-{marker.upper()}" in {t["rule_id"] for t in out["tests_needed"]}
        ok = (rec["status"] == exp_status and rec["reason"].startswith(exp_reason) and test == exp_test
              and not list(validator.iter_errors(out)))
        detail = f"{marker} {rec['status']} 권고 {test}"
        if not ok:
            detail += f"  / 정답: {exp_status} 권고 {exp_test} / {rec['reason'][:80]}"
        report(case_id, ok, note, detail)

    # 판정 기준일 뒤에 시작한 투약은 보지 않는다 (B README 차수 절, 2026-10-29)
    first = tx(["letrozole", "palbociclib"], "metastatic", 1500, 1, endo=1, resp="PD")
    later = tx(["fulvestrant"], "metastatic", 1800, 2, endo=2, resp="PD")
    for case_id, index_day, want, note in (("IX01", 1700, "2L", "기준일 1700 뒤 2차(1800 시작)는 빼서 2차를 결정할 차례"),
                                           ("IX02", 1900, ">=3L", "기준일 1900이면 2차 진행까지 봐서 3차"),
                                           ("IX03", None, ">=3L", "기준일이 없으면(TCGA) 그대로")):
        ps = patient(ref="VC-1", treatments=[first, later])
        if index_day is not None:
            ps["index_day"] = index_day
        got = assess(ps)["setting"]["line"]
        report(case_id, got == want, note, f"setting.line {got}" + ("" if got == want else f" / 정답 {want}"))

    pending = assess(patient(mutations=genes_with({"status": "not_done", "raw": "결과 대기"})))["tests_needed"]
    pik = next(t for t in pending if t["rule_id"] == "BM4-PIK3CA-PENDING")
    report("A23", pik["test"] == "PIK3CA 결과 확인" and "결과 확인 필요" in pik["reason"], "결과 확인 문구",
           f"{pik['test']} / {pik['reason']}")

    # 전달 문서 8.2절 가상 차트: 입력 -> 기대 출력 (차수와 보고서 원문 파싱은 아직 비교하지 않음)
    ps, expected = handoff_example()
    out = assess(ps)
    got = {r["marker"]: r["status"] for r in out["records"]}
    want = {r["marker"]: r["status"] for r in expected["records"]
            if r["marker"] in ("ER", "PR", "HER2", "PIK3CA", "ESR1")}
    ok = (all(got.get(m) == s for m, s in want.items()) and out["subtype"] == expected["subtype"]
          and out["setting"]["disease"] == expected["setting"]["disease"] and not list(validator.iter_errors(out)))
    report("HAND", ok, "ER·PR·HER2·PIK3CA·ESR1·아형·현재 범주만 비교 (보고서 원문 파싱(BRCA)·차수는 아직 없음)",
           f"전달 문서 8.2절 {want} -> {({m: got.get(m) for m in want})}, {out['subtype']}, {out['setting']['disease']}")

    # TCGA 크롭본 전체: patient_state로 변환(파일 없이)한 뒤 BM 출력이 스키마를 통과하는지
    docs = convert(load_rows())
    bad = [pid for pid, doc in docs.items() if list(validator.iter_errors(assess(doc)))]
    report("TCGA", not bad, "", f"TCGA 크롭본 {len(docs)}명 중 BM 출력 스키마 검증 실패 {len(bad)}명 {bad[:3]}")

    print()
    print(f"통과 {passed}  실패 {failed}")
    return failed


def test_bm():
    assert main() == 0


if __name__ == "__main__":
    main()
