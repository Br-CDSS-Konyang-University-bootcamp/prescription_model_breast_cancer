"""VC-0108 70세, 진단 시 뼈 전이 (de novo IV), 1차 ribociclib + letrozole 복용 중, 골 보호제 결정.
진단일 2024-02-19, 오늘 외래 day 320.

진단 때부터 전이성이라 metastasis_day 0, recurrence_day 없음. 복용 중인 약은 end_day null + ongoing true.
뼈 전이는 뼈 스캔으로 확정 (imaging_findings confirmed, 골 보호제 '영상으로 골전이 입증'). 동반질환 CKD 3a.
"""
from src.input.chart.virtual_chart import Chart, F, allred, allred_text, kdate


def build() -> Chart:
    c = Chart("VC-0108", "2024-02-19", 320)
    D = c.on
    idx = c.index_date

    d = c.doc("progress_note", idx)
    d.t(f"<외래 경과기록>   {kdate(idx)}   종양내과\n").ident(70).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.t("S) 허리 통증 호전, 진통제 필요 없음.\n   폐경: ")
    d.put("폐경 후 (50세 폐경)", F("patient.menopausal_status", "postmenopausal", within="폐경 후"),
          F("patient.menopausal_basis", "age_amenorrhea", within="50세 폐경")).t("\n   과거력: ")
    d.put("CKD 3a (eGFR 52)", F("patient.comorbidities", ["CKD 3a (eGFR 52)"])).t(", ")
    d.put("심장 질환 과거력 없음", F("patient.cardiac_history", "no")).t("\n\n")
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=idx)).t("\n")
    d.t(f"   Bone scan ({kdate(D(300))}): 기존 골병변 변화 없음, SD\n\n")
    d.t("A) Rt. breast IDC, ").put(f"{kdate(D(0))} core bx로 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0))))
    d.t("\n   ").put("cT2N1M1, stage IV",
                    F("stage.ctnm", {"t": "T2", "n": "N1", "m": "M1", "edition": None}, observed_date=D(5),
                      within="cT2N1M1"),
                    F("stage.group", "IV", within="stage IV"), F("stage.disease_extent", "metastatic", within="stage IV"))
    d.t(" ").put("(de novo, bone only)", F("stage.metastatic_sites", ["bone"]), F("recurrence.metastasis_day", 0))
    d.t("\n   ER Allred 8 / PR Allred 5 / HER2 0\n   1L ribociclib + letrozole 10개월째 복용 중, SD\n   ")
    d.put("재발 아님 (진단 시 IV기)", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 골 보호제 시작 결정, ribociclib + letrozole 유지\n")

    d = c.doc("pathology", D(4))
    d.t("[병리결과보고서]\n").ident(70, F("patient.gender", "FEMALE"), F("patient.age", 70), full=False)
    d.t(f"접수일: {kdate(D(0))}   보고일: {kdate(D(4))}\n검체: 우측 유방 중심 생검\n\n진단\n  조직형: ")
    d.put("침윤성 유관암 (IDC)", F("diagnosis.histology", "IDC")).t("\n  조직학적 등급: ")
    d.put("II", F("diagnosis.grade", 2)).t("\n\n면역조직화학\n  ")
    pri = dict(specimen="primary", observed_date=D(0))
    d.put(f"ER : 양성, {allred_text(5, 3)}", F("receptors.er_percent", allred(5, 3, "positive"), **pri)).t("\n  ")
    d.put(f"PR : 양성, {allred_text(3, 2)}", F("receptors.pr_percent", allred(3, 2, "positive"), **pri)).t("\n  ")
    d.put("HER2 (4B5): 0 (no staining)", F("receptors.her2_ihc", {"score": "0", "faint": False}, **pri))
    d.t("\n\n판독의: 박가상\n")

    d = c.doc("radiology", D(5))
    d.t("BONE SCAN REPORT\n").ident(70, full=False)
    d.t(f"검사: Whole body bone scan   검사일: {kdate(D(5))}\n\nFindings:\n")
    d.t("  L1, L4 척추체, 천골, 우측 장골에 다발성 열소 증가.\nConclusion:\n  ")
    d.image("척추·골반 다발성 골전이", modality="bone_scan", date=D(5), sites=["bone"], certainty="confirmed").t("\n")

    d = c.doc("radiology", D(5))
    d.t("[PET-CT 판독지]\n").ident(70, full=False)
    d.t(f"검사: F-18 FDG PET-CT   검사일: {kdate(D(5))}\n\nFindings:\n")
    d.t("  우측 유방 2.7 cm 종괴(SUVmax 6.2), 우측 액와 림프절 섭취 증가. 골병변은 bone scan과 일치.\nConclusion:\n  ")
    d.image("골전이 외 원격 전이 없음", modality="PET", date=D(5), sites=["bone"], certainty="confirmed").t("\n")

    d = c.doc("medication", None)
    d.t("<항암 처방 이력>\n").ident(70, full=False)
    d.t("- ").row(f"키스칼리 600mg qd (3주 복용 1주 휴약) + 페마라 2.5mg qd : {kdate(D(20))} ~ 현재 복용 중, SD",
                  drugs=["ribociclib", "letrozole"], setting="metastatic", start=D(20), end=None,
                  best_response="SD", ongoing=True)
    d.t("\n")
    return c
