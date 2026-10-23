"""VC-0102 PIK3CA 변이, 내분비 2차 결정. 진단일 2016-02-08, 오늘 외래 day 3735.

경과는 VC-0101과 같고 유전자 결과만 다르다: 원발 조직 NGS PIK3CA H1047R, cfDNA ESR1 미검출.
anthracycline 용량이 mg로만 적혀 있어 키·몸무게로 mg/m2를 구해야 한다 (380 mg ÷ 체표면적 1.57 ≈ 242 mg/m2).
"""
from src.input.chart.virtual_chart import Chart, F, allred, allred_text, kdate

CYC = lambda n, days: {"value": n, "basis": "recorded", "interval_days": days, "interval_basis": "recorded"}  # noqa: E731


def build() -> Chart:
    c = Chart("VC-0102", "2016-02-08", 3735)
    D = c.on
    idx = c.index_date

    d = c.doc("progress_note", idx)
    d.t(f"[종양내과 진료기록]   {kdate(idx)}\n").ident(68).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.put("58세", F("patient.age", 58)).t(" ")
    d.put("폐경 후", F("patient.menopausal_status", "postmenopausal")).t(" ")
    d.put("여성", F("patient.gender", "FEMALE")).t(". ")
    d.put(f"{kdate(D(0))} 좌측 유방 IDC 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0))),
          F("diagnosis.histology", "IDC", within="IDC")).t(", ")
    d.put("cT2N1M0", F("stage.ctnm", {"t": "T2", "n": "N1", "m": "M0", "edition": None}, observed_date=D(0))).t(".\n")
    d.t("보조 AC #4 → weekly paclitaxel #12 → letrozole 5년 복용 후 ")
    d.put(f"{kdate(D(2056))} 종료", F("recurrence.adjuvant_endocrine_end_date", D(2056), raw=kdate(D(2056)))).t(". ")
    d.put(f"{kdate(D(3151))} 뼈·간 전이",
          F("recurrence.recurrence_date", D(3151), raw=kdate(D(3151))),
          F("recurrence.metastasis_day", 3151), F("recurrence.recurrence_day", 3151),
          F("recurrence.status", "distant", within="뼈·간 전이"),
          F("recurrence.metastatic_sites", ["bone", "liver"], within="뼈·간 전이"))
    d.t("로 1차 letrozole + palbociclib 시작, 18개월 뒤 진행.\n")
    d.put("ECOG PS 1", F("patient.ecog", 1, observed_date=idx)).t(", ")
    d.put("Ht 155cm, Wt 57kg", F("patient.height_cm", 155, within="Ht 155cm"),
          F("patient.weight_kg", 57, within="Wt 57kg")).t(". ")
    d.put("심장 질환 과거력 없음", F("patient.cardiac_history", "no")).t(".\n")
    d.t("원발 조직 NGS에서 PIK3CA H1047R 검출, cfDNA에서 ESR1 미검출. 2차 내분비 기반 치료 결정 예정.\n")

    d = c.doc("pathology", D(26))
    d.t("[병리결과보고서]\n").ident(58, full=False)
    d.t(f"접수일: {kdate(D(20))}   보고일: {kdate(D(26))}\n검체: ")
    d.put("Left breast, partial mastectomy + axillary dissection", F("stage.operable", "yes")).t("\n\n진단 (DIAGNOSIS)\n  ")
    d.t("Invasive ductal carcinoma, NST\n  Histologic grade: ")
    d.put("NG2", F("diagnosis.grade", 2)).t("\n  Tumor size: ")
    d.put("2.6 cm", F("stage.pathologic_size_mm", 26, observed_date=D(20))).t("\n  Lymph node: ")
    d.put("2/12 (+)", F("stage.positive_ln_count", {"positive": 2, "examined": 12})).t("\n  pTNM: ")
    d.put("pT2 N1a M0, stage IIB (AJCC 8th)",
          F("stage.ptnm", {"t": "T2", "n": "N1a", "m": "M0", "edition": "8th"}, observed_date=D(20)),
          F("stage.group", "IIB", within="stage IIB"), F("stage.disease_extent", "early", within="stage IIB"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT2 N1a M0"))
    d.t("\n\n면역조직화학 (IHC)\n  ")
    hist = dict(role="history:recurrence", specimen="primary", observed_date=D(20))
    d.put(f"ER : 양성, {allred_text(5, 3)}", F("receptors.er_percent", allred(5, 3, "positive"), **hist)).t("\n  ")
    d.put(f"PR : 양성, {allred_text(4, 2)}", F("receptors.pr_percent", allred(4, 2, "positive"), **hist)).t("\n  ")
    d.put("HER2 (4B5): 1+", F("receptors.her2_ihc", {"score": "1+"}, **hist)).t("\n  ")
    d.put("Ki-67: 25%", F("proliferation.ki67_percent", {"percent": 25}, specimen="primary", observed_date=D(20)))
    d.t("\n\n판독의: 박가상\n")

    d = c.doc("pathology", D(3168))
    d.t("<병리 조직검사 결과>\n").ident(66, full=False)
    d.t(f"{kdate(D(3168))} 간 침생검 ({kdate(D(3165))} 시행). Metastatic carcinoma, consistent with breast primary.\n")
    meta = dict(specimen="metastasis", observed_date=D(3165))
    d.put("ER Allred 8 (5+3)", F("receptors.er_percent", allred(5, 3), **meta)).t(", ")
    d.put("PR Allred 6 (4+2)", F("receptors.pr_percent", allred(4, 2), **meta)).t(", ")
    d.put("HER2 1+", F("receptors.her2_ihc", {"score": "1+"}, **meta)).t(". 원발 종양과 같은 결과.\n")

    d = c.doc("molecular", D(3705))
    d.t("[분자병리 검사 결과]\n").ident(68, full=False)
    d.t(f"검사기관: 가상유전체검사센터   보고일: {kdate(D(3705))}\n")
    d.t(f"검체: 원발 종양 FFPE 조직 ({kdate(D(20))} 수술 검체)\n검사법: 표적 NGS (52 genes)\n종양세포 비율: 60%\n\n")
    d.t("검출된 변이 (Clinically significant variants)\n  ")
    d.put("PIK3CA   c.3140A>G (p.H1047R)   VAF 28%",
          F("molecular.mutations.PIK3CA", result="detected", specimen="primary",
            variants=[{"protein_change": "H1047R", "variant_type": "Missense_Mutation", "vaf": 0.28,
                       "raw": "PIK3CA c.3140A>G (p.H1047R) VAF 28%"}]))
    d.t("\n\n검출되지 않음 (Not detected)\n  ")
    d.put("AKT1, PTEN, BRCA1, BRCA2", *(F(f"molecular.mutations.{g}", result="not_detected", specimen="primary")
                                        for g in ("AKT1", "PTEN", "BRCA1", "BRCA2")))
    d.t("\n\n* 패널 포함 유전자: PIK3CA, AKT1, PTEN, BRCA1, BRCA2, ERBB2 외 46개 (ESR1 제외)\n")
    d.genomic_report("primary", D(3705))

    d = c.doc("molecular", D(3730))
    d.t("[NGS 보고서]\n").ident(68, full=False)
    d.t(f"검사기관: 가상유전체검사센터   보고일: {kdate(D(3730))}\n검체: Plasma cfDNA ({kdate(D(3725))} 채혈)\n")
    d.t("검사법: Liquid biopsy panel (ESR1)\n\n")
    d.put("ESR1: 변이 검출되지 않음 (Not detected)",
          F("molecular.mutations.ESR1", result="not_detected", specimen="cfDNA"))
    d.t("\n")
    d.genomic_report("cfDNA", D(3730))

    d = c.doc("medication", None)
    d.t("<항암 처방 이력>\n").ident(68, full=False)
    d.t("- ").row(f"AC (doxorubicin 95mg + cyclophosphamide 950mg) q3w #4 : {kdate(D(45))} ~ {kdate(D(108))}, paclitaxel로 계획된 변경",
                  drugs=["doxorubicin", "cyclophosphamide"], setting="adjuvant", start=D(45), end=D(108),
                  cycles=CYC(4, 21), stop_reason="planned_switch",
                  anthra=[{"drug": "doxorubicin", "dose_per_admin": {"value": 95, "unit": "mg"},
                           "cycles": CYC(4, 21), "total_dose": {"value": 380, "unit": "mg"}}])
    d.t("\n- ").row(f"paclitaxel 125mg weekly #12 : {kdate(D(129))} ~ {kdate(D(206))}, 완료",
                    drugs=["paclitaxel"], setting="adjuvant", start=D(129), end=D(206), cycles=CYC(12, 7),
                    stop_reason="completed")
    d.t("\n- ").row(f"페마라 2.5mg qd (보조) : {kdate(D(230))} ~ {kdate(D(2056))}, 5년 완료",
                    drugs=["letrozole"], setting="adjuvant", start=D(230), end=D(2056), stop_reason="completed")
    d.t("\n- ").row(f"입랜스 125mg qd (3주 복용 1주 휴약) + 페마라 2.5mg qd : {kdate(D(3180))} ~ {kdate(D(3720))}, PD로 중단",
                    drugs=["palbociclib", "letrozole"], setting="metastatic", start=D(3180), end=D(3720),
                    cycles=None, stop_reason="progression", best_response="PD", progression=D(3720))
    d.t("\n")
    return c
