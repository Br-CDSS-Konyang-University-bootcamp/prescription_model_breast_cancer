"""VC-0105 HER2 양성, 선행 TCHP 후 잔존 병변, 보조 결정. 진단일 2023-01-09, 오늘 외래 day 180.

선행요법 환자라 수술 병리는 stage.yptnm에 넣고 ptnm·positive_ln_count·pathologic_size_mm는 비운다.
치료 전 크기는 유방 초음파의 clinical_size_mm.
"""
from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, kdate

CYC = lambda n, days: {"value": n, "basis": "recorded", "interval_days": days, "interval_basis": "recorded"}  # noqa: E731


def build() -> Chart:
    c = Chart("VC-0105", "2023-01-09", 180)
    D = c.on
    idx = c.index_date

    d = c.doc("pathology", D(4))
    d.t("SURGICAL PATHOLOGY REPORT\n").ident(49, F("patient.gender", "FEMALE"), F("patient.age", 49), full=False)
    d.t(f"Received: {kdate(D(0))}   Reported: {kdate(D(4))}\nSpecimen: Left breast, US-guided core needle biopsy\n\n")
    d.t("DIAGNOSIS\n  ").put("Invasive ductal carcinoma, NST", F("diagnosis.histology", "IDC")).t("\n  Histologic grade: ")
    d.put("Nottingham grade 3 (3+3+2=8)", F("diagnosis.grade", 3)).t("\n\nIMMUNOHISTOCHEMISTRY\n  ")
    pri = dict(specimen="primary", observed_date=D(0))
    d.put(f"ER: negative, {allred_text(0, 0)}", F("receptors.er_percent", allred(0, 0, "negative"), **pri)).t("\n  ")
    d.put(f"PR: negative, {allred_text(0, 0)}", F("receptors.pr_percent", allred(0, 0, "negative"), **pri)).t("\n  ")
    d.put("HER2 (4B5): 3+", F("receptors.her2_ihc", {"score": "3+"}, **pri)).t("\n  ")
    d.put("Ki-67: 50%", F("proliferation.ki67_percent", {"percent": 50}, **pri)).t("\n\nPathologist: 박가상\n")

    d = c.doc("radiology", D(2))
    d.t("[영상의학 판독]\n").ident(49, full=False)
    d.t(f"검사: Breast ultrasound   검사일: {kdate(D(2))}\n\nFindings:\n")
    d.t("  좌측 유방 2시 방향 불규칙 종괴. 좌측 액와 림프절 2개 피질 비후.\nConclusion:\n  ")
    d.put("좌측 유방 2.8 cm 종괴", F("stage.clinical_size_mm", 28, observed_date=D(2))).t(" (BI-RADS 5), ")
    d.image("좌측 액와 림프절 전이 의심", modality="ultrasound", date=D(2), sites=[], certainty="suspected").t("\n")

    d = c.doc("pathology", D(156))
    d.t("[병리결과보고서]\n").ident(49, full=False)
    d.t(f"보고일: {kdate(D(156))}\n검체: ")
    d.put("좌측 유방 부분절제술 + 감시림프절 생검 (선행 항암 후)", F("stage.operable", "yes")).t("\n\n진단\n  잔존 침윤암: ")
    d.put("있음 (residual invasive carcinoma)", F("neoadjuvant_response.pcr", "no")).t("\n  잔존 종양 크기: 1.4 cm\n")
    d.t("  림프절: 1/3 (+), 최대 전이 4 mm\n  ypTNM: ")
    d.put("ypT1c ypN1a (sn) (AJCC 8th)",
          F("stage.yptnm", {"t": "T1c", "n": "N1a", "m": "M0", "edition": "8th", "residual_size_mm": 14,
                            "positive_ln": 1, "examined_ln": 3}, observed_date=D(150))).t("\n  RCB: ")
    d.put("RCB class II", F("neoadjuvant_response.rcb", "RCB-II")).t("\n\n판독의: 박가상\n")

    d = c.doc("progress_note", idx)
    d.t(f"<외래 경과기록>   {kdate(idx)}   종양내과\n").ident(49).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.t("S) 수술 후 특별한 불편감 없음.\n   폐경: ")
    d.put("폐경 전, 월경 규칙적", F("patient.menopausal_status", "premenopausal", within="폐경 전"),
          F("patient.menopausal_basis", "age_amenorrhea", within="월경 규칙적")).t("\n   과거력: ")
    d.put("심장 질환 과거력 없음", F("patient.cardiac_history", "no")).t("\n\n")
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=idx)).t("\n")
    d.t(f"   Echo ({kdate(D(170))}): ").put("LVEF 62%", F("patient.lvef_percent", 62, observed_date=D(170))).t("\n\n")
    d.t("A) Lt. breast IDC, ").put(f"{kdate(D(0))} core bx로 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0))))
    d.t("\n   ").put("cT2N1M0, stage IIB",
                    F("stage.ctnm", {"t": "T2", "n": "N1", "m": "M0", "edition": None}, observed_date=D(0),
                      within="cT2N1M0"),
                    F("stage.group", "IIB", within="stage IIB"), F("stage.disease_extent", "early", within="stage IIB"),
                    F("stage.metastatic_sites", "[Not Applicable]", within="cT2N1M0"))
    d.t(", HER2+ (IHC 3+), ER/PR 음성\n   선행 TCHP #6 후 수술: ypT1c ypN1a, 잔존 침윤암 (RCB-II)\n   ")
    d.put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 보조 HER2 표적치료 결정\n")

    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(49, full=False)
    d.t("구분    요법                                                 시작         종료         주기     반응   중단 사유\n")
    d.t("선행    ").row(f"TCHP (탁소텔 + 카보플라틴 + 허셉틴 + 퍼제타)   {kdate(D(14))}   {kdate(D(119))}   q3w #6   PR     완료",
                         drugs=["docetaxel", "carboplatin", "trastuzumab", "pertuzumab"], setting="neoadjuvant",
                         start=D(14), end=D(119), cycles=CYC(6, 21), stop_reason="completed", best_response="PR")
    d.t("\n")
    return c
