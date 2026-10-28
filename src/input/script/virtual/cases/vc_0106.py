"""VC-0106 HR+ 고위험 조기 (pT3 5.5cm N1a 2/15, IIIA), 시점이 다른 Ki-67 두 값. 진단일 2022-09-14, 다학제 day 45.

외부 병원 생검(day 0)의 ER·Ki-67은 본원 수술 조직(day 25)에 밀려 history[] (newer_result).
"""
from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, kdate


def surgery_report(c: Chart, ki67: str = "single") -> None:
    """본원 전절제 병리 (VC-0106b가 같이 쓴다). ki67 = single (값 하나) / conflict (본문 15%, 판독 요약 25%)."""
    D = c.on
    d = c.doc("pathology", D(31))
    d.t("[병리결과보고서]\n").ident(55, F("patient.gender", "FEMALE"), F("patient.age", 55), full=False)
    d.t(f"접수일: {kdate(D(25))}   보고일: {kdate(D(31))}\n검체: ")
    d.put("좌측 유방 전절제술 + 액와 림프절 절제", F("stage.operable", "yes")).t("\n\n진단 (DIAGNOSIS)\n  조직형: ")
    d.put("Invasive ductal carcinoma, NST", F("diagnosis.histology", "IDC")).t("\n  조직학적 등급: ")
    d.put("II (Nottingham 2+2+2=6)", F("diagnosis.grade", 2)).t("\n  종양 크기: ")
    d.put("5.5 cm", F("stage.pathologic_size_mm", 55, observed_date=D(25))).t("\n  림프절: ")
    d.put("전이 2개 / 검사 15개", F("stage.positive_ln_count", {"positive": 2, "examined": 15})).t("\n  절제연: 음성\n  pTNM: ")
    d.put("pT3 N1a M0, stage IIIA (AJCC 8th)",
          F("stage.ptnm", {"t": "T3", "n": "N1a", "m": "M0", "edition": "8th"}, observed_date=D(25)),
          F("stage.group", "IIIA", within="stage IIIA"),
          F("stage.disease_extent", "locally_advanced", within="stage IIIA"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT3 N1a M0"))
    if ki67 == "conflict":
        d.t("\n  ")
        d.put("Ki-67 labeling index 25%",
              F("proliferation.ki67_percent", {"percent": 25}, role="conflict", specimen="primary", observed_date=D(25),
                note="같은 보고서 안에서 값이 다름 (판독 요약 25%, 면역염색 표 15%)"))
    d.t("\n\n면역조직화학 (IHC)\n  ")
    pri = dict(specimen="primary", observed_date=D(25))
    d.put(f"ER : 양성, {allred_text(5, 3)}", F("receptors.er_percent", allred(5, 3, "positive"), **pri)).t("\n  ")
    d.put(f"PR : 양성, {allred_text(5, 2)}", F("receptors.pr_percent", allred(5, 2, "positive"), **pri)).t("\n  ")
    d.put("HER2 (4B5): 0", F("receptors.her2_ihc", {"score": "0"}, **pri)).t("\n  ")
    if ki67 == "conflict":
        d.put("Ki-67: 15%", F("proliferation.ki67_percent", {"percent": 15}, role="conflict", **pri))
    else:
        d.put("Ki-67: 25%", F("proliferation.ki67_percent", {"percent": 25}, **pri))
    d.t("\n\n판독의: 박가상\n")


def mdt_note(c: Chart) -> None:
    D = c.on
    idx = c.index_date
    d = c.doc("progress_note", idx)
    d.t(f"[다학제 진료 회의록]   {kdate(idx)}\n").ident(55).t("참석: 유방외과, 종양내과, 영상의학과, 병리과, 방사선종양학과\n")
    d.t("증례: 55세, ")
    d.put("폐경 후 (LMP 2017년)", F("patient.menopausal_status", "postmenopausal", within="폐경 후"),
          F("patient.menopausal_basis", "age_amenorrhea", within="LMP 2017년")).t(". ")
    d.put(f"{kdate(D(0))} 좌측 유방암 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0)))).t(", ")
    d.t("전절제술 후 pT3N1a(2/15)M0, IIIA. HR+/HER2-.\n      ")
    d.put("ECOG PS 0", F("patient.ecog", 0, observed_date=idx)).t(". ")
    d.put("수술 후 영상에서 원격 전이 없음", F("recurrence.status", "none")).t(".\n")
    d.t("논의: 보조 항암 후 내분비요법에 CDK4/6 억제제를 추가할지\n결론: 보조 항암 시작, 이후 내분비 기반 요법 재논의\n")


def build() -> Chart:
    c = Chart("VC-0106", "2022-09-14", 45)
    D = c.on

    d = c.doc("pathology", D(3))
    d.t("<병리 조직검사 결과>\n").ident(55, full=False)
    d.t(f"{kdate(D(3))} 가상의원 판독 (사본). {kdate(D(0))} 좌측 유방 중심 생검. Invasive ductal carcinoma.\n")
    old = dict(role="history:newer_result", specimen="primary", observed_date=D(0))
    d.put("ER 양성", F("receptors.er_percent", {"result": "positive"}, **old)).t(", ")
    d.put("Ki-67 15%", F("proliferation.ki67_percent", {"percent": 15}, **old)).t(".\n")

    surgery_report(c)
    mdt_note(c)
    return c
