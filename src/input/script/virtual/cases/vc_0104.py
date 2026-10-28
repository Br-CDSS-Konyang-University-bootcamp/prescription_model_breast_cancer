"""VC-0104 TNBC, PD-L1 22C3 CPS 12, 항암 1차 결정. 진단일 2022-06-20, 다학제 회의 day 470.

보조 AC → paclitaxel 종료 240일 뒤 간 전이. 생식세포 BRCA 검사는 시행하지 않음(germline not_done → 검사 권고).

짝 사례 매개변수: dfi = paclitaxel 종료일(day 201)부터 간 전이까지 일수 (기본 240). 전이 뒤 일정(CT, 생검, 회의)은 같이 옮긴다.
pdl1 = (원문 표기, 값) (기본 22C3 CPS 12).
"""
from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, kdate

CYC = lambda n, days: {"value": n, "basis": "recorded", "interval_days": days, "interval_basis": "recorded"}  # noqa: E731


PDL1 = ("22C3 pharmDx, CPS 12", {"assay": "22C3", "score_type": "CPS", "score": 12})


def build(dfi: int = 240, pdl1: tuple[str, dict] = PDL1) -> Chart:
    m = 201 + dfi                                    # 전이일 (기본 441)
    c = Chart("VC-0104", "2022-06-20", m + 29)
    D = c.on
    idx = c.index_date

    d = c.doc("progress_note", idx)
    d.t(f"[다학제 진료 회의록]   {kdate(idx)}\n").ident(46).t("참석: 유방외과, 종양내과, 영상의학과, 병리과, 방사선종양학과\n")
    d.t("증례: ")
    d.put("45세", F("patient.age", 45)).t(" ")
    d.put("여성", F("patient.gender", "FEMALE")).t(", ")
    d.put("폐경 전 (월경 규칙적)", F("patient.menopausal_status", "premenopausal", within="폐경 전"),
          F("patient.menopausal_basis", "age_amenorrhea", within="월경 규칙적")).t(". ")
    d.put(f"{kdate(D(0))} 좌측 유방 IDC 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0)))).t(", pT2N1a(1/14) IIB, TNBC.\n")
    d.t("      보조 AC #4 → weekly paclitaxel #12 후 ")
    d.put(f"{kdate(D(m))} 간 전이",
          F("recurrence.recurrence_date", D(m), raw=kdate(D(m))),
          F("recurrence.metastasis_day", m), F("recurrence.recurrence_day", m),
          F("recurrence.status", "distant", within="간 전이"),
          F("recurrence.metastatic_sites", ["liver"], within="간 전이"))
    d.t(" (간 생검으로 확인).\n      ")
    d.put("ECOG 1", F("patient.ecog", 1, observed_date=idx)).t(". ")
    d.put("심장 질환 과거력 없음", F("patient.cardiac_history", "no")).t(", ")
    d.put("종격동 방사선 치료 이력 없음", F("patient.mediastinal_radiation", "no")).t(".\n")
    d.t(f"      Echo ({kdate(D(m + 19))}): ").put("LVEF 64%", F("patient.lvef_percent", 64, observed_date=D(m + 19))).t("\n")
    d.t("논의: 전이성 TNBC 1차 항암 요법 선택. PD-L1 결과 확인.\n")
    d.t("      ").put("생식세포 BRCA1/2 검사: 시행하지 않음",
                       F("molecular.germline.BRCA1", status="not_done"),
                       F("molecular.germline.BRCA2", status="not_done")).t("\n")
    d.t("결론: 1차 항암 요법 결정, 다음 외래에 치료 시작\n")

    d = c.doc("pathology", D(21))
    d.t("[병리결과보고서]\n").ident(45, full=False)
    d.t(f"접수일: {kdate(D(15))}   보고일: {kdate(D(21))}\n검체: ")
    d.put("좌측 유방 부분절제술 + 액와 림프절 절제", F("stage.operable", "yes")).t("\n\n진단\n  조직형: ")
    d.put("침윤성 유관암", F("diagnosis.histology", "IDC")).t("\n  조직학적 등급: ")
    d.put("III (Nottingham 3+3+3=9)", F("diagnosis.grade", 3)).t("\n  종양 크기: ")
    d.put("2.8 cm", F("stage.pathologic_size_mm", 28, observed_date=D(15))).t("\n  림프절: ")
    d.put("전이 1개 / 검사 14개", F("stage.positive_ln_count", {"positive": 1, "examined": 14})).t("\n  절제연: 음성\n  pTNM: ")
    d.put("pT2 N1a M0, stage IIB (AJCC 8th)",
          F("stage.ptnm", {"t": "T2", "n": "N1a", "m": "M0", "edition": "8th"}, observed_date=D(15)),
          F("stage.group", "IIB", within="stage IIB"), F("stage.disease_extent", "early", within="stage IIB"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT2 N1a M0"))
    d.t("\n\n면역조직화학\n  ")
    hist = dict(role="history:recurrence", specimen="primary", observed_date=D(15))
    d.put(f"ER : 음성, {allred_text(0, 0)}", F("receptors.er_percent", allred(0, 0, "negative"), **hist)).t("\n  ")
    d.put(f"PR : 음성, {allred_text(0, 0)}", F("receptors.pr_percent", allred(0, 0, "negative"), **hist)).t("\n  ")
    d.put("HER2 (4B5): 1+", F("receptors.her2_ihc", {"score": "1+"}, **hist)).t("\n  ")
    d.put("Ki-67: 70%", F("proliferation.ki67_percent", {"percent": 70}, specimen="primary", observed_date=D(15)))
    d.t("\n\n판독의: 박가상\n")

    d = c.doc("radiology", D(m))
    d.t("<CT 판독 결과>\n").ident(46, full=False)
    d.t(f"검사: Chest-abdomen CT (contrast)   검사일: {kdate(D(m))}\n\nFindings:\n")
    d.t("  간 S7에 3.1 cm 신생 저음영 병변. 폐·뼈 이상 없음.\nConclusion:\n  ")
    d.image("간 S7 전이 의증, 조직검사 권함", modality="CT", date=D(m), sites=["liver"], certainty="suspected").t("\n")

    d = c.doc("pathology", D(m + 19))
    d.t("<병리 조직검사 결과>\n").ident(46, full=False)
    d.t(f"{kdate(D(m + 19))} 간 침생검 ({kdate(D(m + 14))} 시행). Metastatic carcinoma, consistent with breast primary.\n")
    meta = dict(specimen="metastasis", observed_date=D(m + 14))
    d.put("ER 음성 (Allred 0)", F("receptors.er_percent", allred(0, 0, "negative"), **meta)).t(", ")
    d.put("PR 음성 (Allred 0)", F("receptors.pr_percent", allred(0, 0, "negative"), **meta)).t(", ")
    d.put("HER2 1+", F("receptors.her2_ihc", {"score": "1+"}, **meta)).t(".\n")
    d.t("PD-L1 IHC: ").put(pdl1[0], F("receptors.pdl1", pdl1[1], **meta)).t("\n")

    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(46, full=False)
    d.t("구분    요법                                         시작         종료         주기         반응   중단 사유\n")
    d.t("보조    ").row(f"AC (doxorubicin 60mg/m2 + cyclophosphamide 600mg/m2)   {kdate(D(40))}   {kdate(D(103))}   q3w #4   -   계획된 변경",
                         drugs=["doxorubicin", "cyclophosphamide"], setting="adjuvant", start=D(40), end=D(103),
                         cycles=CYC(4, 21), stop_reason="planned_switch",
                         anthra=[{"drug": "doxorubicin", "dose_per_admin": {"value": 60, "unit": "mg/m2"},
                                  "cycles": CYC(4, 21), "total_dose": {"value": 240, "unit": "mg/m2"}}])
    d.t("\n보조    ").row(f"paclitaxel 80mg/m2   {kdate(D(124))}   {kdate(D(201))}   weekly #12   -   완료",
                         drugs=["paclitaxel"], setting="adjuvant", start=D(124), end=D(201), cycles=CYC(12, 7),
                         stop_reason="completed")
    d.t("\n")
    return c
