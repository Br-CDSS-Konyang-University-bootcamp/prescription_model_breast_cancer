"""VC-0103 보조 anastrozole 복용 중 폐 전이, 내분비 1차 결정. 진단일 2021-03-05, 오늘 외래 2023-05-04 (day 790).

adj_gap (짝 사례): None이면 기본 사례 (anastrozole 복용 중 전이). 숫자면 anastrozole을 관절통으로 일찍 끊고
그 날부터 전이(day 760)까지 adj_gap일이 지난 경우 (보조 내분비 종료 후 1년 이내 재발 경계, DEEM-ENDO-ADJ-1Y).
"""
from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, kdate

NOT_DETECTED = "검출되지 않음 (Not detected): PIK3CA, ESR1, AKT1, PTEN"


def build(adj_gap: int | None = None) -> Chart:
    c = Chart("VC-0103", "2021-03-05", "2023-05-04", created_at="2026-10-19T00:00:00+09:00")
    end = "2023-04-09" if adj_gap is None else c.on(760 - adj_gap)

    d = c.doc("progress_note", "2023-05-04")
    d.t("<외래 경과기록>   2023.5.4   종양내과\n").ident(54).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.t("S) 기침 3주.\n   폐경: ")
    d.put("폐경 후 (postmenopausal)", F("patient.menopausal_status", "postmenopausal")).t("\n\n")
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date="2023-05-04")).t("\n")
    d.t("   Chest CT (23.4.4): 양측 폐 다발성 결절, 전이 의심 → 폐 생검으로 확인\n\n")
    d.t("A) Rt. breast IDC, ").put("2021.3.5 core bx로 진단", F("diagnosis.diagnosis_date", "2021-03-05")).t("\n")
    d.t("   pT2N0(0/2)M0, IIA (2021.3.23 수술)\n")
    d.t("   ER Allred 8 / PR Allred 6 / HER2 0 / Ki-67 15%, grade 2\n")
    if adj_gap is None:
        d.t("   보조 anastrozole 2021.4.14~ 복용 중 ")
    else:
        d.t("   보조 anastrozole 2021.4.14~").put(f"{kdate(end)} 관절통으로 중단", F("recurrence.adjuvant_endocrine_end_date", end, raw=kdate(end)))
        d.t(", 이후 경과 관찰 중 ")
    d.put("2023.4.4 lung metastasis",
          F("recurrence.recurrence_date", "2023-04-04", raw="2023.4.4"),
          F("recurrence.metastasis_day", 760), F("recurrence.recurrence_day", 760),
          F("recurrence.status", "distant", within="lung metastasis"),
          F("recurrence.metastatic_sites", ["lung"], within="lung metastasis"))
    if adj_gap is None:
        d.t(" → ").put("anastrozole 2023.4.9 중단", F("recurrence.adjuvant_endocrine_end_date", "2023-04-09", raw="2023.4.9"))
        d.t(" (PD)")
    d.t("\n   Tissue NGS: PIK3CA, ESR1 미검출\n\n")
    d.t("P) 전이성 1차 내분비 기반 치료 결정\n")

    d = c.doc("pathology", "2021-03-29")
    d.t("[병리결과보고서]\n").ident(52, F("patient.gender", "FEMALE"), F("patient.age", 52), full=False)
    d.t("접수일: 2021.3.23   보고일: 2021.3.29\n검체: ")
    d.put("우측 유방 부분절제술 + 감시림프절 생검", F("stage.operable", "yes")).t("\n\n진단\n  ")
    d.put("침윤성 유관암 (invasive ductal carcinoma, NST)", F("diagnosis.histology", "IDC")).t("\n")
    d.t("  조직학적 등급: ").put("II (Nottingham 2+2+2=6)", F("diagnosis.grade", 2)).t("\n")
    d.t("  종양 크기: ").put("2.3 cm", F("stage.pathologic_size_mm", 23, observed_date="2021-03-23")).t("\n")
    d.t("  림프절: ").put("전이 없음 (0/2)", F("stage.positive_ln_count", {"positive": 0, "examined": 2})).t("\n")
    d.t("  절제연: 음성\n  pTNM: ")
    d.put("pT2 N0 M0, stage IIA (AJCC 8th)",
          F("stage.ptnm", {"t": "T2", "n": "N0", "m": "M0", "edition": "8th"}, observed_date="2021-03-23"),
          F("stage.group", "IIA", within="stage IIA"), F("stage.disease_extent", "early", within="stage IIA"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT2 N0 M0"))
    d.t("\n\n면역조직화학\n  ")
    primary = dict(specimen="primary", observed_date="2021-03-23")
    hist = dict(role="history:recurrence", **primary)
    d.put(f"ER : 양성, {allred_text(5, 3)}", F("receptors.er_percent", allred(5, 3, "positive"), **hist)).t("\n  ")
    d.put(f"PR : 양성, {allred_text(4, 2)}", F("receptors.pr_percent", allred(4, 2, "positive"), **hist)).t("\n  ")
    d.put("HER2 (4B5): 0", F("receptors.her2_ihc", {"score": "0"}, **hist)).t("\n  ")
    d.put("Ki-67: 15%", F("proliferation.ki67_percent", {"percent": 15}, **primary)).t("\n\n판독의: 박가상\n")

    d = c.doc("radiology", "2023-04-04")
    d.t("[영상의학 판독]\n").ident(54, full=False)
    d.t("검사: Chest CT (contrast)   검사일: 2023.4.4\n\nFindings:\n")
    d.t("  양측 폐에 0.5~1.2 cm 크기의 다발성 결절. 종격동 림프절 비대 없음. 간·부신 이상 소견 없음.\n")
    d.t("Conclusion:\n  ")
    d.image("Multiple lung nodules, r/o metastasis", modality="CT", date="2023-04-04", sites=["lung"],
            certainty="suspected").t("\n")

    d = c.doc("pathology", "2023-04-19")
    d.t("[병리결과보고서]\n").ident(54, full=False)
    d.t("보고일: 2023.4.19\n2023.4.16 우하엽 폐 결절 CT 유도 생검. Metastatic carcinoma, compatible with breast primary.\n")
    meta = dict(specimen="metastasis", observed_date="2023-04-16")
    d.put("ER positive (Allred 8, 5+3)", F("receptors.er_percent", allred(5, 3, "positive"), **meta)).t(", ")
    d.put("PR positive (Allred 6, 4+2)", F("receptors.pr_percent", allred(4, 2, "positive"), **meta)).t(", ")
    d.put("HER2 IHC 0", F("receptors.her2_ihc", {"score": "0"}, **meta)).t(".\n")

    d = c.doc("molecular", "2023-04-28")
    d.t("[분자병리 검사 결과]\n").ident(54, full=False)
    d.t("검사기관: 가상유전체검사센터   보고일: 2023.4.28\n검체: 폐 생검 조직 (2023.4.16)\n검사법: 표적 NGS\n\n")
    d.t("검출된 변이: 없음\n")
    d.put(NOT_DETECTED, *(F(f"molecular.mutations.{g}", result="not_detected", specimen="metastasis")
                          for g in ("ESR1", "PIK3CA", "AKT1", "PTEN")))
    d.t("\n\n* 패널 포함 유전자: PIK3CA, ESR1, AKT1, PTEN, ERBB2\n")
    d.genomic_report("metastasis", "2023-04-28")

    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(54, full=False)
    d.t("구분    요법                          시작         종료        반응   중단 사유\n보조    ")
    if adj_gap is None:
        d.row("아리미덱스 (anastrozole) 1mg qd  2021.4.14    2023.4.9    PD     폐 전이", drugs=["anastrozole"],
              setting="adjuvant", start="2021-04-14", end="2023-04-09", stop_reason="progression", best_response="PD",
              progression="2023-04-04")
    else:
        d.row(f"아리미덱스 (anastrozole) 1mg qd  2021.4.14    {kdate(end)}    -      관절통 (부작용)", drugs=["anastrozole"],
              setting="adjuvant", start="2021-04-14", end=end, stop_reason="toxicity")
    d.t("\n")
    return c
