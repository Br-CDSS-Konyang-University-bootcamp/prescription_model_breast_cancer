"""VC-0101 ESR1 변이, 내분비 2차 결정. 진단일 2016-04-11, 오늘 외래 day 3735.

보조 AC → paclitaxel → letrozole 5년 뒤 골·간 전이, 1차 letrozole + palbociclib 진행, cfDNA ESR1 Y537S.
간 재생검 수용체가 value, 원발 수용체가 history[] (IN-4). 간 재생검 PR은 약양성 (Allred 3 = PS 2 + IS 1). PR은 Allred 3점 이상이 양성이라 원발(6점)과 같은 양성이다.

짝 사례 매개변수: her2 = 간 재생검(지금 값) HER2 결과. 원발은 1+ 그대로 (history[]).
"0" IHC 0, "0f" IHC 0 + 희미한 막 염색(초저발현), "1+" (기본), "2+n" 2+ / SISH 비증폭, "2+a" 2+ / SISH 증폭, "3+".
"""
from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, kdate

CYC = lambda n, days: {"value": n, "basis": "recorded", "interval_days": days, "interval_basis": "recorded"}  # noqa: E731


HER2 = {
    "0": ("HER2 0 (no staining)", {"score": "0", "faint": False}, None),
    "0f": ("HER2 0 (10% 미만 세포에서 희미한 불완전 막 염색)", {"score": "0", "faint": True}, None),
    "1+": ("HER2 1+", {"score": "1+"}, None),
    "2+n": ("HER2 2+", {"score": "2+"}, ("SISH: not amplified (HER2/CEP17 ratio 1.3)", {"result": "not_amplified", "method": "SISH"})),
    "2+a": ("HER2 2+", {"score": "2+"}, ("SISH: amplified (HER2/CEP17 ratio 3.1)", {"result": "amplified", "method": "SISH"})),
    "3+": ("HER2 3+", {"score": "3+"}, None),
}


def build(her2: str = "1+") -> Chart:
    ihc_text, ihc, ish = HER2[her2]
    c = Chart("VC-0101", "2016-04-11", 3735)
    D = c.on
    idx = c.index_date

    d = c.doc("progress_note", idx)
    d.t(f"<외래 경과기록>   {kdate(idx)}   종양내과\n").ident(72).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.t("S) 허리 통증 지속, 식욕 저하.\n   폐경: ")
    d.put("폐경 후 (LMP 2009년)", F("patient.menopausal_status", "postmenopausal", within="폐경 후"),
          F("patient.menopausal_basis", "age_amenorrhea", within="LMP 2009년")).t("\n   과거력: ")
    d.put("심장 질환 과거력 없음", F("patient.cardiac_history", "no")).t(", 고지혈증\n\n")
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=idx)).t("\n   ")
    d.put("Ht 156cm / Wt 58kg", F("patient.height_cm", 156, within="Ht 156cm"),
          F("patient.weight_kg", 58, within="Wt 58kg")).t("\n")
    d.t(f"   Echo ({kdate(D(3730))}): ").put("LVEF 60%", F("patient.lvef_percent", 60, observed_date=D(3730))).t("\n")
    d.t(f"   CT ({kdate(D(3720))}): 간 병변 증가, 새 골병변 → PD\n\n")
    d.t("A) Lt. breast IDC, ").put(f"{kdate(D(0))} 진단", F("diagnosis.diagnosis_date", D(0))).t(", ")
    d.put("cT2N1M0", F("stage.ctnm", {"t": "T2", "n": "N1", "m": "M0", "edition": None}, observed_date=D(0)))
    d.t(" → pT2N1a(2/12), IIB\n")
    d.t("   보조 AC #4 → weekly paclitaxel #12 → ")
    d.put(f"letrozole {kdate(D(2056))} 5년 복용 완료",
          F("recurrence.adjuvant_endocrine_end_date", D(2056), raw=kdate(D(2056)))).t("\n   ")
    d.put(f"{kdate(D(3151))} 골·간 전이",
          F("recurrence.recurrence_date", D(3151), raw=kdate(D(3151))),
          F("recurrence.metastasis_day", 3151), F("recurrence.recurrence_day", 3151),
          F("recurrence.status", "distant", within="골·간 전이"),
          F("recurrence.metastatic_sites", ["bone", "liver"], within="골·간 전이"))
    d.t(" (보조 내분비 종료 3년 뒤)\n")
    d.t("   1L letrozole + palbociclib 18개월 → PD\n")
    d.t("   cfDNA NGS: ESR1 Y537S 검출\n\n")
    d.t("P) 2L 내분비 기반 치료 결정\n")

    d = c.doc("pathology", D(26))
    d.t("[병리결과보고서]\n").ident(62, F("patient.gender", "FEMALE"), F("patient.age", 62), full=False)
    d.t(f"접수일: {kdate(D(20))}   보고일: {kdate(D(26))}\n검체: ")
    d.put("좌측 유방 부분절제술 + 액와 림프절 절제", F("stage.operable", "yes")).t("\n\n진단 (DIAGNOSIS)\n  조직형: ")
    d.put("Invasive ductal carcinoma, NST", F("diagnosis.histology", "IDC")).t("\n  조직학적 등급: ")
    d.put("Nottingham grade 2 (3+2+1=6)", F("diagnosis.grade", 2)).t("\n  종양 크기: ")
    d.put("3.2 cm", F("stage.pathologic_size_mm", 32, observed_date=D(20))).t("\n  림프절: ")
    d.put("2/12 (+)", F("stage.positive_ln_count", {"positive": 2, "examined": 12})).t("\n  절제연: 음성\n  pTNM: ")
    d.put("pT2 N1a M0, stage IIB (AJCC 8th)",
          F("stage.ptnm", {"t": "T2", "n": "N1a", "m": "M0", "edition": "8th"}, observed_date=D(20)),
          F("stage.group", "IIB", within="stage IIB"), F("stage.disease_extent", "early", within="stage IIB"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT2 N1a M0"))
    d.t("\n\n면역조직화학 (IHC)\n  ")
    hist = dict(role="history:recurrence", specimen="primary", observed_date=D(20))
    d.put(f"ER : positive, {allred_text(5, 3)}", F("receptors.er_percent", allred(5, 3, "positive"), **hist)).t("\n  ")
    d.put(f"PR : positive, {allred_text(4, 2)}", F("receptors.pr_percent", allred(4, 2, "positive"), **hist)).t("\n  ")
    d.put("HER2 (4B5): 1+", F("receptors.her2_ihc", {"score": "1+"}, **hist)).t("\n  ")
    d.put("Ki-67: 25%", F("proliferation.ki67_percent", {"percent": 25}, specimen="primary", observed_date=D(20)))
    d.t("\n\n판독의: 박가상\n")

    d = c.doc("radiology", D(3151))
    d.t("BONE SCAN REPORT\n").ident(70, full=False)
    d.t(f"검사: Whole body bone scan   검사일: {kdate(D(3151))}\n\nFindings:\n")
    d.t("  T8, L2 척추체와 좌측 장골에 열소 증가. 퇴행성 변화와 구별되는 양상.\nConclusion:\n  ")
    d.image("Multiple bone metastases (T8, L2, Lt. iliac bone)", modality="bone_scan", date=D(3151), sites=["bone"],
            certainty="confirmed").t("\n")

    d = c.doc("radiology", D(3151))
    d.t("<CT 판독 결과>\n").ident(70, full=False)
    d.t(f"검사: Abdomen-pelvis CT (contrast)   검사일: {kdate(D(3151))}\n\nFindings:\n")
    d.t("  간 S6, S8에 1.5 cm, 2.2 cm 저음영 결절 2개.\nConclusion:\n  ")
    d.image("간 다발성 전이 (S6, S8)", modality="CT", date=D(3151), sites=["liver"], certainty="confirmed").t("\n")

    d = c.doc("pathology", D(3168))
    d.t("<병리 조직검사 결과>\n").ident(70, full=False)
    d.t(f"{kdate(D(3168))} 간 침생검 ({kdate(D(3165))} 시행). Metastatic carcinoma, consistent with breast primary.\n")
    meta = dict(specimen="metastasis", observed_date=D(3165))
    d.put("ER 강양성 (Allred 8, 5+3)", F("receptors.er_percent", allred(5, 3, "positive"), **meta)).t(", ")
    d.put("PR 약양성 (Allred 3, 2+1)", F("receptors.pr_percent", allred(2, 1, "positive"), **meta)).t(", ")
    d.put(ihc_text, F("receptors.her2_ihc", ihc, **meta))
    if ish:
        d.t(", ").put(ish[0], F("receptors.her2_ish", ish[1], **meta))
    d.t(". Ki-67은 평가하지 않음.\n")

    d = c.doc("molecular", D(3730))
    d.t("[NGS 보고서]\n").ident(72, full=False)
    d.t(f"검사기관: 가상유전체검사센터   보고일: {kdate(D(3730))}\n검체: Plasma cfDNA ({kdate(D(3725))} 채혈)\n")
    d.t("검사법: Liquid biopsy panel\n\n검출된 변이 (Clinically significant variants)\n  ")
    d.put("ESR1   c.1610A>C (p.Y537S)   VAF 4.2%",
          F("molecular.mutations.ESR1", result="detected", specimen="cfDNA",
            variants=[{"protein_change": "Y537S", "variant_type": "Missense_Mutation", "vaf": 0.042,
                       "raw": "ESR1 c.1610A>C (p.Y537S) VAF 4.2%"}]))
    d.t("\n\n검출되지 않음 (Not detected)\n  ")
    d.put("PIK3CA, AKT1, PTEN", *(F(f"molecular.mutations.{g}", result="not_detected", specimen="cfDNA")
                                  for g in ("PIK3CA", "AKT1", "PTEN")))
    d.t("\n\n* 패널 포함 유전자: ESR1, PIK3CA, AKT1, PTEN, ERBB2\n")
    d.genomic_report("cfDNA", D(3730))

    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(72, full=False)
    d.t("구분    요법                                        시작         종료         주기         반응   중단 사유\n")
    d.t("보조    ").row(f"AC (doxorubicin 60mg/m2 + cyclophosphamide 600mg/m2)   {kdate(D(45))}   {kdate(D(108))}   q3w #4   -   계획된 변경",
                         drugs=["doxorubicin", "cyclophosphamide"], setting="adjuvant", start=D(45), end=D(108),
                         cycles=CYC(4, 21), stop_reason="planned_switch",
                         anthra=[{"drug": "doxorubicin", "dose_per_admin": {"value": 60, "unit": "mg/m2"},
                                  "cycles": CYC(4, 21), "total_dose": {"value": 240, "unit": "mg/m2"}}])
    d.t("\n보조    ").row(f"paclitaxel 80mg/m2   {kdate(D(129))}   {kdate(D(206))}   weekly #12   -   완료",
                         drugs=["paclitaxel"], setting="adjuvant", start=D(129), end=D(206), cycles=CYC(12, 7),
                         stop_reason="completed")
    d.t("\n보조    ").row(f"페마라 (letrozole) 2.5mg qd   {kdate(D(230))}   {kdate(D(2056))}   -   -   완료 (5년)",
                         drugs=["letrozole"], setting="adjuvant", start=D(230), end=D(2056), stop_reason="completed")
    d.t("\n고식    ").row(f"입랜스 (palbociclib) 125mg + 페마라 2.5mg   {kdate(D(3180))}   {kdate(D(3720))}   28일 #18   PD   진행",
                         drugs=["palbociclib", "letrozole"], setting="metastatic", start=D(3180), end=D(3720),
                         cycles=CYC(18, 28), stop_reason="progression", best_response="PD", progression=D(3720))
    d.t("\n")
    return c
