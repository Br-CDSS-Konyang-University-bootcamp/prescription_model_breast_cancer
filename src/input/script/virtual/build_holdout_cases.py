"""보류 세트 가상 환자 N21~N35 (VC-0130~VC-0144)와 짝 G20·G21 차트 만들기: src/input/virtual_patient_cases.md §3.

ESMO 권고와 심평원 급여가 갈리는 환자, 아직 0건인 ESMO 경로를 덮는 사례다. build_virtual_cases.py(N01~N20)와 같은 Chart 도구·
문서 도구를 쓰고, 기대 결과는 문서 §3의 사례 표를 scenario.md로 옮긴다. 기대 결과를 고칠 때는 문서를 고친다.

보류 세트: 입력 규칙·프롬프트를 고칠 때 이 사례의 틀린 칸을 보지 않는다. 성능 보고에만 쓴다 (문서 §5).

결과 (tests/fixtures/virtual_charts/, 기존 사례 옆):
    <VC-01xx>/chart.txt, expected/patient_state.json, scenario.md     새 사례 15건
    <VC-0111-g20a 등>/...                                             짝 G20 (VC-0111 기반)·G21 (VC-0115 기반)
    holdout_cases.csv                                                 목록

usage (team_project 폴더에서):
    python -m src.input.script.virtual.build_holdout_cases                 # 모두
    python -m src.input.script.virtual.build_holdout_cases --ids VC-0130   # 한 건만
    python -m src.input.script.virtual.build_holdout_cases --check         # 쓰지 않고, 저장된 파일과 같은지만 본다
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys

from src.input.script.virtual.build_virtual_cases import (
    OUT, ROOT, ac, clinical_stage, core_path, de_novo, distant, dx, er, germline, heart, her2, image, meds, meno,
    meta_path, ngs, note, pct, surgery_path, vc_0111, vc_0115, wpac)
from src.input.script.virtual.virtual_chart import Chart, F, check, dumps, kdate

CASES_MD = ROOT / "src" / "input" / "virtual_patient_cases.md"
INDEX = OUT / "holdout_cases.csv"


def _no_recur(d) -> None:
    d.put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")


def _ypath(c: Chart, day: int, age: int, op: str, *, pcr: bool, yptnm: dict, size_txt: str | None, ln_txt: str,
           ypt_txt: str, rcb: str, observed: int):
    """선행요법 뒤 수술 병리 (ypTNM)."""
    d = c.doc("pathology", c.on(day))
    d.t("[병리결과보고서]\n").ident(age, full=False)
    d.t(f"보고일: {kdate(c.on(day))}\n검체: ")
    d.put(op, F("stage.operable", "yes")).t("\n\n진단\n  잔존 침윤암: ")
    if pcr:
        d.put("없음 (no residual invasive carcinoma, pCR)", F("neoadjuvant_response.pcr", "yes"))
    else:
        d.put("있음 (residual invasive carcinoma)", F("neoadjuvant_response.pcr", "no"))
    d.t("\n")
    if size_txt:
        d.t(f"  잔존 종양 크기: {size_txt}\n")
    d.t(f"  림프절: {ln_txt}\n  ypTNM: ")
    d.put(ypt_txt, F("stage.yptnm", yptnm, observed_date=c.on(observed))).t("\n  RCB: ")
    d.put(rcb, F("neoadjuvant_response.rcb", rcb.split(" (")[0].replace("RCB class ", "RCB-"))).t("\n\n판독의: 박가상\n")
    return d


# ---------- 사례 ----------
def vc_0130() -> Chart:
    """N21 HER2+ cT1 cN0 수술 먼저, pT1a (8 mm) N0, HR-."""
    c = Chart("VC-0130", "2025-02-10", 45)
    d = note(c, 52)
    d.t("S) 수술 상처 양호.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (LMP 2022년)", "폐경 후", "LMP 2022년").t("\n   과거력: ")
    heart(d, c, 64, 40)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", 수술: pT1a (8 mm) N0 (0/2), stage IA, ER-/PR-/HER2 3+\n   ")
    _no_recur(d)
    d.t("P) 보조 항HER2 요법 필요 여부 결정 (paclitaxel + trastuzumab 고려)\n")
    image(c, 2, 52, "ultrasound", "Breast ultrasound", "우측 유방 0.9 cm 종괴 (10시 방향), 액와 림프절 이상 없음.",
          "우측 유방암 의심 (BI-RADS 4C), 액와 림프절 전이 소견 없음", [], "suspected")
    surgery_path(c, 21, 52, op="우측 유방 부분절제술 + 감시림프절 생검", grade=2, size_mm=8, ln=(0, 2),
                 ptnm=("T1a", "N0"), group="IA", extent="early",
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")], ki67=30)
    return c


def vc_0131() -> Chart:
    """N22 폐경 전 45세 Luminal A 1기, 수술 먼저."""
    c = Chart("VC-0131", "2025-04-07", 40)
    d = note(c, 45)
    d.t("S) 특이 증상 없음.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전 (LMP 3주 전)", "폐경 전", "LMP 3주 전").t("\n   과거력: ")
    heart(d, c, 66, 35)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", 수술: pT1c N0, stage IA, Luminal A-like (G1, Ki-67 8%)\n   ")
    _no_recur(d)
    d.t("P) 보조 내분비요법 결정 (tamoxifen 단독 vs 난소 기능 억제 병용)\n")
    surgery_path(c, 18, 45, op="좌측 유방 부분절제술 + 감시림프절 생검", grade=1, size_mm=14, ln=(0, 3),
                 ptnm=("T1c", "N0"), group="IA", extent="early",
                 recs=[er(5, 3, "positive"), er(4, 3, "positive", "PR"), her2("1+")], ki67=8)
    return c


def vc_0132() -> Chart:
    """N23 HR+/HER2- Luminal A-like stage IIIA (pT3 pN2a, 림프절 5개), 수술 먼저."""
    c = Chart("VC-0132", "2024-09-02", 50)
    d = note(c, 58)
    d.t("S) 수술 후 회복 중.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (52세 폐경)", "폐경 후", "52세 폐경").t("\n   과거력: ")
    heart(d, c, 61, 45)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", 수술: pT3 pN2a (5/18), stage IIIA, ER+/PR+/HER2 0, G2, Ki-67 12%\n   ")
    _no_recur(d)
    d.t("P) 보조 항암 (AC → paclitaxel) 후 내분비요법 + abemaciclib 여부 결정\n")
    image(c, 3, 58, "MRI", "Breast MRI (contrast)", "좌측 유방 5.2 cm 종괴, 좌측 액와 림프절 다수 비대.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    surgery_path(c, 20, 58, op="좌측 유방 전절제술 + 액와 림프절 절제", grade=2, size_mm=55, ln=(5, 18),
                 ptnm=("T3", "N2a"), group="IIIA", extent="locally_advanced",
                 recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("0", False)], ki67=12)
    return c


def vc_0133() -> Chart:
    """N24 폐경 후 63세 HR+/HER2- stage IIB, 보조 anastrozole 복용 중, 보조 bisphosphonate 결정."""
    c = Chart("VC-0133", "2025-01-13", 95)
    d = note(c, 63)
    d.t("S) anastrozole 복용 2주째, 관절통 경미.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (55세 폐경)", "폐경 후", "55세 폐경").t("\n   과거력: ")
    heart(d, c, 63, 30)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n")
    d.t(f"   골밀도 ({kdate(c.on(70))}): 요추 T-score -1.8 (골감소증)\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", 수술: pT2 pN1a (2/12), stage IIB, ER+/PR+/HER2 1+\n")
    d.t("   유전자 발현 검사 (Oncotype DX) RS 12 → 보조 항암 생략, 보조 anastrozole 시작\n   ")
    _no_recur(d)
    d.t("P) 보조 bisphosphonate (zoledronic acid 6개월 간격) 추가 여부 결정\n")
    surgery_path(c, 16, 63, op="우측 유방 부분절제술 + 액와 림프절 절제", grade=2, size_mm=26, ln=(2, 12),
                 ptnm=("T2", "N1a"), group="IIB", extent="early",
                 recs=[pct("ER", 90, "positive", "양성"), pct("PR", 40, "positive", "양성"), her2("1+")], ki67=15)
    meds(c, 63, [
        dict(name="아리미덱스 (anastrozole) 1mg qd", drugs=["anastrozole"], setting="adjuvant", s=81, e=None,
             ongoing=True, why="-"),
    ])
    return c


def vc_0134() -> Chart:
    """N25 폐경 후 고위험 (pN2a) 보조 letrozole 5년 완료, 연장 결정."""
    c = Chart("VC-0134", "2019-06-03", 2070)
    D = c.on
    d = note(c, 61)
    d.t("S) letrozole 5년 복용 마침, 특이 증상 없음.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (50세 폐경)", "폐경 후", "50세 폐경").t("\n   과거력: ")
    heart(d, c, 60, 2060)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2 pN2a (6/15), stage IIIA, HR+/HER2-\n")
    d.t("   보조 AC #4 → weekly paclitaxel #12 → ")
    d.put(f"letrozole {kdate(D(2041))} 5년 복용 완료",
          F("recurrence.adjuvant_endocrine_end_date", D(2041), raw=kdate(D(2041)), within=kdate(D(2041)))).t("\n   ")
    _no_recur(d)
    d.t("P) 연장 내분비요법 여부 결정 (고위험, 총 7~10년)\n")
    surgery_path(c, 0, 56, op="좌측 유방 전절제술 + 액와 림프절 절제", grade=2, size_mm=32, ln=(6, 15),
                 ptnm=("T2", "N2a"), group="IIIA", extent="locally_advanced",
                 recs=[er(5, 3, "positive"), er(4, 3, "positive", "PR"), her2("1+")], ki67=18)
    meds(c, 61, [
        ac(40, 103), wpac(124, 201),
        dict(name="페마라 (letrozole) 2.5mg qd", drugs=["letrozole"], setting="adjuvant", s=215, e=2041,
             why="완료 (5년)", stop="completed"),
    ])
    return c


def vc_0135() -> Chart:
    """N26 TNBC cT1c cN0 (IA), 선행 paclitaxel + carboplatin → AC 후 잔존 ypT1b N0, 생식세포 BRCA1 병원성."""
    c = Chart("VC-0135", "2024-11-04", 210)
    D = c.on
    d = note(c, 38)
    d.t("S) 수술 후 회복 양호.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 규칙적", "폐경 전", "월경 규칙적").t("\n   과거력: ")
    heart(d, c, 65, 200)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T1c", "N0"), "IA", "early").t(", TNBC, grade 3\n")
    d.t("   선행 weekly paclitaxel + carboplatin #12 → AC #4 후 수술: ypT1b ypN0 (0/2), 잔존 침윤암 (RCB-I)\n")
    d.t("   생식세포 BRCA1 병원성 변이\n   ")
    _no_recur(d)
    d.t("P) 수술 후 보조 요법 결정 (olaparib 1년 vs capecitabine)\n")
    core_path(c, 38, grade=3, recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("1+")], ki67=70)
    image(c, 2, 38, "ultrasound", "Breast ultrasound", "좌측 유방 1.8 cm 종괴 (2시 방향), 액와 림프절 이상 없음.",
          "좌측 유방암 의심 (BI-RADS 5), 액와 림프절 전이 소견 없음", [], "suspected")
    germline(c, 25, 38, {"BRCA1": ("c.68_69delAG", "E23Vfs*17", "Pathogenic (병원성)"), "BRCA2": None})
    _ypath(c, 192, 38, "좌측 유방 부분절제술 + 감시림프절 생검 (선행 항암 후)", pcr=False,
           yptnm={"t": "T1b", "n": "N0", "m": "M0", "edition": "8th", "residual_size_mm": 6, "positive_ln": 0,
                  "examined_ln": 2},
           size_txt="0.6 cm", ln_txt="0/2", ypt_txt="ypT1b ypN0 (AJCC 8th)", rcb="RCB class I", observed=185)
    meds(c, 38, [
        dict(name="paclitaxel 80mg/m2 + carboplatin AUC 2", drugs=["paclitaxel", "carboplatin"], setting="neoadjuvant",
             s=14, e=91, cyc=(12, 7), why="계획된 변경", stop="planned_switch"),
        ac(98, 161, setting="neoadjuvant", why="완료", stop="completed"),
    ])
    return c


def vc_0136() -> Chart:
    """N27 조기 TNBC에 선행·보조 pembrolizumab (pCR) 후 18개월 뒤 간 전이, PD-L1 22C3 CPS 15."""
    c = Chart("VC-0136", "2022-03-07", 960)
    D = c.on
    d = note(c, 49)
    d.t("S) 우상복부 불편감.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 불규칙", "폐경 전", "월경 불규칙").t("\n   과거력: ")
    heart(d, c, 62, 950)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T2", "N1"), "IIB", "early").t(", TNBC\n")
    d.t("   선행 KEYNOTE-522 요법 (pembrolizumab + paclitaxel + carboplatin → pembrolizumab + AC) 후 수술: pCR\n")
    d.t(f"   보조 pembrolizumab 9회 {kdate(D(383))} 완료\n   ")
    distant(d, c, 931, ["liver"], "간 전이").t(" (pembrolizumab 종료 18개월 뒤)\n")
    d.t("   간 생검: TNBC, PD-L1 22C3 CPS 15. 생식세포 BRCA1/2 음성\n\n")
    d.t("P) 전이성 TNBC 1차 요법 결정 (이전 면역항암제 사용)\n")
    core_path(c, 47, grade=3, recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("1+")], ki67=80,
              recur=True)
    image(c, 3, 47, "MRI", "Breast MRI (contrast)", "좌측 유방 3.1 cm 종괴, 좌측 액와 림프절 2개 비대.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    germline(c, 30, 47, {"BRCA1": None, "BRCA2": None})
    _ypath(c, 197, 47, "좌측 유방 부분절제술 + 액와 림프절 절제 (선행 항암 후)", pcr=True,
           yptnm={"t": "T0", "n": "N0", "m": "M0", "edition": "8th", "residual_size_mm": 0, "positive_ln": 0,
                  "examined_ln": 9},
           size_txt=None, ln_txt="0/9", ypt_txt="ypT0 ypN0 (AJCC 8th)", rcb="RCB-0 (pCR)", observed=190)
    image(c, 931, 49, "CT", "Abdomen-pelvis CT (contrast)", "간 S4·S6·S8 다발성 저음영 결절 (최대 3.2 cm).",
          "간 다발성 전이", ["liver"])
    meta_path(c, 940, 49, "간", [er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("0", False)],
              pdl1=("22C3 pharmDx, CPS 15", {"assay": "22C3", "score_type": "CPS", "score": 15}))
    meds(c, 49, [
        dict(name="키트루다 (pembrolizumab) + paclitaxel + carboplatin", drugs=["pembrolizumab", "paclitaxel", "carboplatin"],
             setting="neoadjuvant", s=14, e=98, cyc=(4, 21), why="계획된 변경", stop="planned_switch"),
        {**ac(105, 168, setting="neoadjuvant", why="완료", stop="completed"),
         "name": "키트루다 (pembrolizumab) + AC (doxorubicin 60mg/m2 + cyclophosphamide 600mg/m2)",
         "drugs": ["pembrolizumab", "doxorubicin", "cyclophosphamide"], "resp": "CR"},
        dict(name="키트루다 (pembrolizumab) 200mg", drugs=["pembrolizumab"], setting="adjuvant", s=215, e=383,
             cyc=(9, 21), why="완료", stop="completed"),
    ])
    return c


def vc_0137() -> Chart:
    """N28 78세 HR+/HER2+ de novo 뼈·폐 전이, ECOG 3, 항암 어려움 판단, 이전 치료 없음."""
    c = Chart("VC-0137", "2025-07-07", 20)
    d = note(c, 78)
    d.t("S) 요통, 거동 불편 (보행 보조기 사용).\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (50세 폐경)", "폐경 후", "50세 폐경").t("\n   과거력: ")
    d.put("만성 신장병 3b (eGFR 38)", F("patient.comorbidities", ["만성 신장병 3b (eGFR 38)"])).t("\n   ")
    heart(d, c, 57, 15, "심장 질환 과거력 없음")
    d.t("O) ").put("ECOG PS 3", F("patient.ecog", 3, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N1"), ["bone", "lung"], "bone, lung").t(", HR+/HER2+ (IHC 3+)\n")
    d.t("   고령·수행 상태 저하로 세포독성 항암 치료는 어렵다고 판단 (보호자와 상의함)\n\n")
    d.t("P) 전이성 1차 요법 결정: 내분비요법 + 항HER2 요법\n")
    core_path(c, 78, grade=2, recs=[pct("ER", 80, "positive", "양성"), pct("PR", 20, "positive", "양성"), her2("3+")],
              ki67=25, side="우측")
    image(c, 6, 78, "bone_scan", "Whole body bone scan", "L2·L4 척추체, 골반 열소 증가.", "다발성 골전이", ["bone"])
    image(c, 6, 78, "CT", "Chest CT (contrast)", "양측 폐 다발성 결절 (최대 1.2 cm).", "폐 다발성 전이 의증", ["lung"],
          "suspected")
    return c


def vc_0138() -> Chart:
    """N29 HR-/HER2+ 전이 3차: 1차 DPH → HP 유지 진행, 2차 T-DXd 진행, 뇌 전이 없음, 보조 AC 받음."""
    c = Chart("VC-0138", "2019-03-04", 2420)
    D = c.on
    d = note(c, 55)
    d.t("S) 기침, 피로.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (LMP 2021년)", "폐경 후", "LMP 2021년").t("\n   과거력: ")
    heart(d, c, 59, 2410)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a(1/12), IIB, HR-/HER2+ (IHC 3+)\n")
    d.t("   보조 AC #4 → paclitaxel + trastuzumab → trastuzumab 단독 (총 18회) 완료\n   ")
    distant(d, c, 1400, ["liver", "lung"], "간·폐 전이").t(" (trastuzumab 종료 2년 뒤)\n")
    d.t("   1L DPH #6 → HP 유지 → PD, 2L 엔허투 (T-DXd) → PD. Brain MRI 전이 없음\n\n")
    d.t("P) 전이성 HER2 양성 3차 요법 결정\n")
    surgery_path(c, 0, 49, op="우측 유방 전절제술 + 감시림프절 생검 → 액와 림프절 절제", grade=3, size_mm=28,
                 ln=(1, 12), ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")], ki67=50)
    image(c, 1400, 53, "CT", "Chest-abdomen CT (contrast)", "간 S7 2.2 cm 결절, 양측 폐 결절 3개 (최대 1.0 cm).",
          "간·폐 전이", ["liver", "lung"])
    meta_path(c, 1408, 53, "간", [er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")])
    image(c, 1895, 54, "CT", "Chest-abdomen CT (contrast)", "간 결절 크기 증가, 폐 결절 새로 2개.", "간·폐 전이 진행 (PD)",
          ["liver", "lung"])
    image(c, 2398, 55, "CT", "Chest-abdomen CT (contrast)", "간 결절 개수 증가, 폐 결절 크기 증가.", "간·폐 전이 진행 (PD)",
          ["liver", "lung"])
    image(c, 2405, 55, "MRI", "Brain MRI (contrast)", "뇌실질 내 조영 증강 병변 없음.", "뇌 전이 없음", [])
    meds(c, 55, [
        ac(30, 93),
        dict(name="paclitaxel 80mg/m2 + trastuzumab", drugs=["paclitaxel", "trastuzumab"], setting="adjuvant",
             s=114, e=191, cyc=(12, 7), why="계획된 변경", stop="planned_switch"),
        dict(name="허셉틴 (trastuzumab) 6mg/kg", drugs=["trastuzumab"], setting="adjuvant", s=212, e=485,
             cyc=(14, 21), why="완료 (총 18회)", stop="completed"),
        dict(name="DPH (docetaxel 75mg/m2 + 퍼제타 + 허셉틴)", drugs=["docetaxel", "pertuzumab", "trastuzumab"],
             setting="metastatic", s=1420, e=1525, cyc=(6, 21), resp="PR", why="유지요법 전환", stop="maintenance"),
        dict(name="HP 유지 (퍼제타 + 허셉틴)", drugs=["pertuzumab", "trastuzumab"], setting="metastatic", s=1546,
             e=1882, cyc=(17, 21), resp="PD", why="진행", stop="progression", prog=1895),
        dict(name="엔허투 (trastuzumab deruxtecan) 5.4mg/kg", drugs=["trastuzumab deruxtecan"], setting="metastatic",
             s=1910, e=2385, cyc=(23, 21), resp="PD", why="진행", stop="progression", prog=2398),
    ])
    return c


def vc_0139() -> Chart:
    """N30 HR+/HER2- 전이 2차: 보조 anastrozole 5년 뒤 재발, 1차 letrozole + palbociclib 18개월 진행, NGS 표적 변이 없음."""
    c = Chart("VC-0139", "2016-04-11", 3200)
    D = c.on
    d = note(c, 63)
    d.t("S) 우상복부 불편감.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (52세 폐경)", "폐경 후", "52세 폐경").t("\n   과거력: ")
    heart(d, c, 62, 3190)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N0, IIA, HR+/HER2-\n   ")
    d.put(f"보조 anastrozole {kdate(D(1860))} 5년 복용 완료",
          F("recurrence.adjuvant_endocrine_end_date", D(1860), raw=kdate(D(1860)), within=kdate(D(1860)))).t("\n   ")
    distant(d, c, 2600, ["bone", "liver"], "뼈·간 전이").t(" (anastrozole 종료 2년 뒤)\n")
    d.t("   1L letrozole + palbociclib 18개월 → PD. 간 재생검 NGS: 표적 변이 없음\n\n")
    d.t("P) 고식 내분비 2차 결정 (CDK4/6 억제제 계속 여부 포함)\n")
    surgery_path(c, 0, 55, op="좌측 유방 부분절제술 + 감시림프절 생검", grade=2, size_mm=23, ln=(0, 3),
                 ptnm=("T2", "N0"), group="IIA", extent="early", recur=True,
                 recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("1+")], ki67=15)
    image(c, 2600, 62, "CT", "Abdomen-pelvis CT (contrast)", "간 S6 1.8 cm 결절, L1 척추체 골용해성 병변.",
          "간·골 전이", ["liver", "bone"])
    image(c, 3160, 63, "CT", "Abdomen-pelvis CT (contrast)", "간 결절 크기 증가, 새 결절 2개.", "간 전이 진행 (PD)",
          ["liver"])
    meta_path(c, 3170, 63, "간", [er(5, 3, "positive"), er(3, 2, "positive", "PR"), her2("1+")])
    ngs(c, 3185, 63, "metastasis", f"간 생검 조직 ({kdate(D(3170))})", [], ["PIK3CA", "ESR1", "AKT1", "PTEN"])
    meds(c, 63, [
        dict(name="아리미덱스 (anastrozole) 1mg qd", drugs=["anastrozole"], setting="adjuvant", s=30, e=1860,
             why="완료 (5년)", stop="completed"),
        dict(name="입랜스 (palbociclib) + 페마라 (letrozole)", drugs=["palbociclib", "letrozole"], setting="metastatic",
             s=2615, e=3165, cyc=(19, 28), resp="PD", why="진행", stop="progression", prog=3160),
    ])
    return c


def vc_0140() -> Chart:
    """N31 HR+/HER2- de novo 뼈 전이, 1차 letrozole + ribociclib 진행, 생식세포 BRCA2 병원성."""
    c = Chart("VC-0140", "2023-01-09", 630)
    d = note(c, 52)
    d.t("S) 골반 통증 악화.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (50세 폐경)", "폐경 후", "50세 폐경").t("\n   과거력: ")
    heart(d, c, 63, 620)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N1"), ["bone"], "bone only").t(", HR+/HER2-\n")
    d.t("   1L letrozole + ribociclib 19개월 → PD (골병변 증가)\n")
    d.t("   가족력 (어머니 난소암)으로 생식세포 검사: BRCA2 병원성 변이\n\n")
    d.t("P) 고식 2차 결정\n")
    core_path(c, 51, grade=2, recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("0", False)], ki67=20)
    image(c, 5, 51, "bone_scan", "Whole body bone scan", "흉추·골반 다발성 열소 증가.", "다발성 골전이", ["bone"])
    image(c, 588, 52, "bone_scan", "Whole body bone scan", "새 열소 2곳 (좌측 대퇴골, T9).", "골전이 진행 (PD)", ["bone"])
    ngs(c, 600, 52, "primary", f"원발 중심 생검 조직 ({kdate(c.on(0))})", [], ["PIK3CA", "ESR1", "AKT1", "PTEN"])
    germline(c, 612, 52, {"BRCA1": None, "BRCA2": ("c.9097dupA", "T3033Nfs*11", "Pathogenic (병원성)")})
    meds(c, 52, [
        dict(name="키스칼리 (ribociclib) + 페마라 (letrozole)", drugs=["ribociclib", "letrozole"], setting="metastatic",
             s=18, e=590, cyc=(20, 28), resp="PD", why="진행", stop="progression", prog=588),
    ])
    return c


def vc_0141() -> Chart:
    """N32 HR+/HER2- de novo 뼈 전이만, 내분비 2차례 진행 뒤에도 내분비 적합."""
    c = Chart("VC-0141", "2020-02-03", 1265)
    d = note(c, 70)
    d.t("S) 우측 고관절 통증 경미, 일상생활 가능.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (51세 폐경)", "폐경 후", "51세 폐경").t("\n   과거력: ")
    heart(d, c, 60, 1255)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N0"), ["bone"], "bone only").t(", HR+/HER2-\n")
    d.t("   1L anastrozole + palbociclib 30개월 → PD, 2L exemestane + everolimus 10개월 → PD (뼈 병변만 천천히 진행)\n")
    d.t("   내장 전이 없음, 증상 경미 → 내분비 치료 지속 가능하다고 판단\n\n")
    d.t("P) 고식 내분비 3차 결정\n")
    core_path(c, 67, grade=2, recs=[er(5, 3, "positive"), er(4, 3, "positive", "PR"), her2("1+")], ki67=12,
              side="우측")
    image(c, 5, 67, "bone_scan", "Whole body bone scan", "흉추·요추·우측 장골 열소 증가.", "다발성 골전이", ["bone"])
    image(c, 915, 69, "bone_scan", "Whole body bone scan", "새 열소 2곳 (좌측 늑골, T11).", "골전이 진행 (PD)", ["bone"])
    image(c, 1240, 70, "bone_scan", "Whole body bone scan", "우측 대퇴골 근위부 열소 증가.", "골전이 진행 (PD)", ["bone"])
    image(c, 1242, 70, "CT", "Chest-abdomen CT (contrast)", "간·폐 실질 이상 없음.", "흉복부 내장 전이 소견 없음", [])
    ngs(c, 1250, 70, "cfDNA", f"혈장 cfDNA ({kdate(c.on(1245))})", [], ["PIK3CA", "ESR1", "AKT1", "PTEN"])
    meds(c, 70, [
        dict(name="아리미덱스 (anastrozole) + 입랜스 (palbociclib)", drugs=["anastrozole", "palbociclib"],
             setting="metastatic", s=15, e=925, cyc=(32, 28), resp="PD", why="진행", stop="progression", prog=915),
        dict(name="아로마신 (exemestane) + 아피니토 (everolimus)", drugs=["exemestane", "everolimus"], setting="metastatic",
             s=940, e=1245, resp="PD", why="진행", stop="progression", prog=1240),
    ])
    return c


def vc_0142() -> Chart:
    """N33 de novo 간 전이, ER 5% (저발현), PR 0, HER2 0, PD-L1 22C3 CPS 20."""
    c = Chart("VC-0142", "2025-05-19", 25)
    d = note(c, 60)
    d.t("S) 우상복부 통증, 체중 감소.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (53세 폐경)", "폐경 후", "53세 폐경").t("\n   과거력: ")
    heart(d, c, 61, 20)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N1"), ["liver"], "liver").t("\n")
    d.t("   간 생검: ER 5% (약양성), PR 0%, HER2 0, PD-L1 22C3 CPS 20. 생식세포 BRCA1/2 음성\n")
    d.t("   ER 저발현 — 호르몬 수용체 양성으로 볼지, 삼중음성에 준해 치료할지 논의\n\n")
    d.t("P) 전이성 1차 요법 결정\n")
    core_path(c, 60, grade=3, recs=[pct("ER", 5, "low_positive", "약양성"), pct("PR", 0, "negative", "음성"),
                                    her2("0", False)], ki67=55, recur=True)
    image(c, 4, 60, "CT", "Abdomen-pelvis CT (contrast)", "간 S5·S7 저음영 결절 3개 (최대 3.0 cm).", "간 다발성 전이",
          ["liver"])
    meta_path(c, 9, 60, "간", [pct("ER", 5, "low_positive", "약양성"), pct("PR", 0, "negative", "음성"), her2("0", False)],
              pdl1=("22C3 pharmDx, CPS 20", {"assay": "22C3", "score_type": "CPS", "score": 20}))
    germline(c, 18, 60, {"BRCA1": None, "BRCA2": None})
    return c


def vc_0143() -> Chart:
    """N34 HR+/HER2- 보조 letrozole 5년 완료 1년 뒤 흉추 단일 골전이 (소수 전이), 생검 확인."""
    c = Chart("VC-0143", "2018-08-06", 2470)
    D = c.on
    d = note(c, 62, "[다학제 진료 회의록]")
    d.t("증례: ").put("폐경 후 (50세 폐경)", F("patient.menopausal_status", "postmenopausal", within="폐경 후"),
                    F("patient.menopausal_basis", "age_amenorrhea", within="50세 폐경")).t(". ")
    dx(d, c, "수술로 진단").t(", pT2N1a(1/14), IIB, HR+/HER2-.\n      ")
    d.put(f"보조 letrozole {kdate(D(1856))} 5년 복용 완료",
          F("recurrence.adjuvant_endocrine_end_date", D(1856), raw=kdate(D(1856)), within=kdate(D(1856)))).t(", ")
    distant(d, c, 2430, ["bone"], "T8 단일 골전이").t(" (letrozole 종료 19개월 뒤).\n      ")
    d.put("ECOG 0", F("patient.ecog", 0, observed_date=c.index_date)).t(". ")
    heart(d, c, 62, 2460)
    d.t("논의: PET-CT에서 T8 외 병변 없음 → 소수 전이 (oligometastatic disease). 방사선종양학과: T8 SBRT 가능.\n")
    d.t("결론: T8 SBRT + 전신 내분비 기반 치료\n")
    surgery_path(c, 0, 56, op="우측 유방 부분절제술 + 액와 림프절 절제", grade=2, size_mm=24, ln=(1, 14),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("1+")], ki67=15)
    image(c, 2430, 62, "PET", "F-18 FDG PET-CT", "T8 척추체 단일 FDG 섭취 (SUVmax 6.8), 그 밖 이상 섭취 없음.",
          "T8 단일 골전이 의심", ["bone"], "suspected")
    meta_path(c, 2445, 62, "T8 척추체", [er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("1+")])
    meds(c, 62, [
        dict(name="페마라 (letrozole) 2.5mg qd", drugs=["letrozole"], setting="adjuvant", s=30, e=1856,
             why="완료 (5년)", stop="completed"),
    ])
    return c


def vc_0144() -> Chart:
    """N35 범위 밖: 임신 22주 HR-/HER2+ cT2N1, 선행 결정."""
    c = Chart("VC-0144", "2025-08-04", 10)
    d = note(c, 34, "[다학제 진료 회의록]")
    d.t("증례: ").put("폐경 전", F("patient.menopausal_status", "premenopausal")).t(", ")
    d.t("현재 임신 22주 (산부인과 추적 중). ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T2", "N1"), "IIB", "early").t(", ER-/PR-/HER2 3+, grade 3.\n      ")
    d.put("ECOG 0", F("patient.ecog", 0, observed_date=c.index_date)).t(".\n")
    d.t("논의: 임신 중 유방암. 산부인과·종양내과 협진 필요, 항HER2 치료는 임신 중 금기.\n결론: 치료 계획 협진 후 결정\n")
    core_path(c, 34, grade=3, recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")], ki67=40)
    image(c, 3, 34, "ultrasound", "Breast ultrasound", "좌측 유방 2.8 cm 종괴, 좌측 액와 림프절 1개 피질 비후.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    return c


# ---------- 짝 사례 ----------
def g20a() -> Chart:
    """G20 VC-0111 + 국소 치료 적응 있음, 뇌 밖(간) 진행 있음 (MBC 그림 6 f13555)."""
    return vc_0111("VC-0111-g20a", local=True, extracns_pd=True)


def g20b() -> Chart:
    """G20 VC-0111 + 국소 치료 적응 있음, 뇌 밖 진행 없음 (MBC 그림 6 c58fb4)."""
    return vc_0111("VC-0111-g20b", local=True, extracns_pd=False)


def g21() -> Chart:
    """G21 VC-0115 + 생식세포 BRCA1 병원성 변이 (MBC 그림 9 856d0a)."""
    return vc_0115("VC-0115-g21", gbrca1=("c.68_69delAG", "E23Vfs*17", "Pathogenic (병원성)"))


BUILDERS = {
    "VC-0130": ("N21", vc_0130), "VC-0131": ("N22", vc_0131), "VC-0132": ("N23", vc_0132),
    "VC-0133": ("N24", vc_0133), "VC-0134": ("N25", vc_0134), "VC-0135": ("N26", vc_0135),
    "VC-0136": ("N27", vc_0136), "VC-0137": ("N28", vc_0137), "VC-0138": ("N29", vc_0138),
    "VC-0139": ("N30", vc_0139), "VC-0140": ("N31", vc_0140), "VC-0141": ("N32", vc_0141),
    "VC-0142": ("N33", vc_0142), "VC-0143": ("N34", vc_0143), "VC-0144": ("N35", vc_0144),
    "VC-0111-g20a": ("G20", g20a), "VC-0111-g20b": ("G20", g20b), "VC-0115-g21": ("G21", g21),
}


# ---------- 문서 §3 → scenario.md, holdout_cases.csv ----------
def sections() -> dict[str, dict]:
    """문서 §3의 '### N21 제목 (VC-0130)'·'### G20 제목 (VC-0111-g20a)' 절마다 제목과 표(항목 → 내용).
    짝 사례 번호(VC-0111-g20a)까지 읽어야 해서 build_virtual_cases.read_sections를 쓰지 않는다."""
    md = CASES_MD.read_text(encoding="utf-8")
    part = md.split("\n## 3.", 1)[1].split("\n## 4.", 1)[0]
    out = {}
    for block in re.split(r"\n(?=### [NG]\d\d )", part)[1:]:
        head, *lines = block.strip().splitlines()
        m = re.match(r"### ([NG]\d\d) (.+?) \((VC-\d{4}(?:-[a-z0-9]+)?)\)", head)
        if not m:            # 같은 §3의 N01~N20 절('(VC-0110 가번호)')은 build_virtual_cases가 읽는다
            continue
        rows = {}
        for ln in lines:
            cells = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(cells) == 2 and cells[0] not in ("항목", "---"):
                rows[cells[0]] = cells[1]
        out[m.group(3)] = {"n": m.group(1), "title": m.group(2), "rows": rows, "text": block.strip()}
    return out


def scenario(ref: str, sec: dict) -> str:
    return (f"# {ref} ({sec['n']}) {sec['title']}\n\n"
            f"> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 {sec['n']}. "
            f"차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. "
            f"기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.\n\n"
            + sec["text"].split("\n", 1)[1].strip() + "\n")


def cases_csv(secs: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["case_id", "proposal", "title", "decision_point", "test_conditions", "pairs"])
    for ref, (n, _) in BUILDERS.items():
        s = secs[ref]
        w.writerow([ref, n, s["title"], s["rows"].get("결정 시점", ""), s["rows"].get("시험할 조건", ""),
                    s["rows"].get("짝 사례", "")])
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", default=list(BUILDERS))
    ap.add_argument("--check", action="store_true", help="쓰지 않고 저장된 파일과 비교")
    args = ap.parse_args(argv)
    secs = sections()
    missing = [r for r in BUILDERS if r not in secs]
    if missing:
        print(f"사례 목록 문서 §3에 없는 사례: {missing}")
        return 1
    bad = 0
    index = cases_csv(secs)
    if args.check:
        if not INDEX.exists() or INDEX.read_text(encoding="utf-8") != index:
            print(f"{INDEX.name}가 문서와 다름")
            bad += 1
    else:
        INDEX.write_text(index, encoding="utf-8", newline="\n")
    for ref in args.ids:
        chart, ps = BUILDERS[ref][1]().build()
        errs = check(chart, ps)
        out = OUT / ref
        files = {out / "chart.txt": chart, out / "expected" / "patient_state.json": dumps(ps),
                 out / "scenario.md": scenario(ref, secs[ref])}
        if args.check:
            errs += [f"저장된 {p.name}와 다름" for p, text in files.items()
                     if not p.exists() or p.read_text(encoding="utf-8") != text]
        elif not errs:
            for p, text in files.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8", newline="\n")
        print(f"{ref} ({BUILDERS[ref][0]}): {'OK' if not errs else '; '.join(errs[:8])}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
