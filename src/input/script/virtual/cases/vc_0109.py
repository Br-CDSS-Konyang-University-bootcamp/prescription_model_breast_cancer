"""VC-0109 보조 tamoxifen 중 흉벽 국소 재발 → 완치 목적 절제, 원격 전이 없음. 진단일 2019-07-22, 오늘 외래 day 1190.

국소 재발이라 recurrence_day는 있고 metastasis_day는 없다 (차수 칸 null, 간주 규칙 not_applicable).
재발 병소 수용체는 '원발과 같음'으로만 적혀 있어 칸으로 옮기지 않는다 (판정은 원발 값).

짝 사례 매개변수: pr = PR Allred (PS, IS) (기본 3+2 = 5). PR은 총점 0~2 음성, 3 이상 양성 (저발현 없음).
"""
from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, kdate


def build(pr: tuple[int, int] = (3, 2)) -> Chart:
    pr_word = "음성" if sum(pr) <= 2 else "양성"
    c = Chart("VC-0109", "2019-07-22", 1190)
    D = c.on
    idx = c.index_date

    d = c.doc("progress_note", idx)
    d.t(f"[종양내과 진료기록]   {kdate(idx)}\n").ident(61).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.put("폐경 후", F("patient.menopausal_status", "postmenopausal")).t(" 61세 여성. ")
    d.put(f"{kdate(D(0))} 좌측 유방 IDC 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0)))).t(", ")
    d.t("부분절제 후 pT2N0(0/3), IIA. 보조 tamoxifen 복용 중 ")
    d.put(f"{kdate(D(1140))} 흉벽 국소 재발",
          F("recurrence.recurrence_date", D(1140), raw=kdate(D(1140))), F("recurrence.recurrence_day", 1140),
          F("recurrence.status", "locoregional", within="흉벽 국소 재발"))
    d.t(" (조직검사로 확인).\n")
    d.put(f"tamoxifen {kdate(D(1150))} 중단", F("recurrence.adjuvant_endocrine_end_date", D(1150), raw=kdate(D(1150))))
    d.t(". PET-CT에서 ").put("원격 전이 없음", F("recurrence.metastatic_sites", "[Not Applicable]")).t(".\n")
    d.put(f"{kdate(D(1165))} 흉벽 광범위 절제", F("recurrence.surgery", "yes")).t(" (")
    d.put("완치 목적", F("recurrence.surgery_intent", "curative")).t(", 절제연 음성). ")
    d.put("수술 후 원격 전이 소견 없음", F("recurrence.later_distant", "no")).t(".\n")
    d.put("ECOG PS 0", F("patient.ecog", 0, observed_date=idx)).t(". 재발 후 보조 내분비요법 결정.\n")

    d = c.doc("progress_note", D(1165))
    d.t("[수술 기록 요약]\n").ident(61, full=False)
    d.t(f"수술일: {kdate(D(1165))}   집도의: 정가상 (유방외과)\n")
    d.t("수술명: 좌측 흉벽 재발 병소 광범위 절제술\n수술 목적: 국소 재발 병소 완전 절제 (완치 목적)\n")
    d.t("소견: 흉벽 피하 1.6 cm 결절, 근막 침범 없음. 육안적 완전 절제.\n")

    d = c.doc("radiology", D(1160))
    d.t("[PET-CT 판독지]\n").ident(61, full=False)
    d.t(f"검사: F-18 FDG PET-CT   검사일: {kdate(D(1160))}\n\nFindings:\n")
    d.t("  좌측 흉벽 피하 결절 섭취 증가 (SUVmax 4.1). 그 밖의 비정상 섭취 없음.\nConclusion:\n  ")
    d.image("흉벽 국소 재발, 원격 전이 소견 없음", modality="PET", date=D(1160), sites=[], certainty="confirmed").t("\n")

    d = c.doc("pathology", D(20))
    d.t("[병리결과보고서]\n").ident(58, F("patient.gender", "FEMALE"), F("patient.age", 58), full=False)
    d.t(f"접수일: {kdate(D(14))}   보고일: {kdate(D(20))}\n검체: ")
    d.put("좌측 유방 부분절제술 + 감시림프절 생검", F("stage.operable", "yes")).t("\n\n진단\n  조직형: ")
    d.put("침윤성 유관암", F("diagnosis.histology", "IDC")).t("\n  조직학적 등급: ")
    d.put("II (Nottingham 2+2+1=5)", F("diagnosis.grade", 2)).t("\n  종양 크기: ")
    d.put("2.4 cm", F("stage.pathologic_size_mm", 24, observed_date=D(14))).t("\n  림프절: ")
    d.put("전이 없음 (0/3)", F("stage.positive_ln_count", {"positive": 0, "examined": 3})).t("\n  pTNM: ")
    d.put("pT2 N0 M0, stage IIA (AJCC 8th)",
          F("stage.ptnm", {"t": "T2", "n": "N0", "m": "M0", "edition": "8th"}, observed_date=D(14)),
          F("stage.group", "IIA", within="stage IIA"), F("stage.disease_extent", "early", within="stage IIA"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT2 N0 M0"))
    d.t("\n\n면역조직화학\n  ")
    pri = dict(specimen="primary", observed_date=D(14))
    d.put(f"ER : 양성, {allred_text(5, 2)}", F("receptors.er_percent", allred(5, 2, "positive"), **pri)).t("\n  ")
    d.put(f"PR : {pr_word}, {allred_text(*pr)}", F("receptors.pr_percent", allred(*pr, "negative" if sum(pr) <= 2 else "positive"), **pri)).t("\n  ")
    d.put("HER2 (4B5): 0", F("receptors.her2_ihc", {"score": "0"}, **pri)).t("\n\n판독의: 박가상\n")

    d = c.doc("pathology", D(1145))
    d.t("<병리 조직검사 결과>\n").ident(61, full=False)
    d.t(f"{kdate(D(1145))} 좌측 흉벽 결절 절개 생검 ({kdate(D(1140))} 시행). Recurrent invasive ductal carcinoma.\n")
    d.t("ER, PR, HER2 결과는 원발 종양과 같음.\n")

    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(61, full=False)
    d.t("구분    요법                         시작         종료         반응   중단 사유\n보조    ")
    d.row(f"놀바덱스 (tamoxifen) 20mg qd   {kdate(D(45))}   {kdate(D(1150))}   PD     흉벽 재발",
          drugs=["tamoxifen"], setting="adjuvant", start=D(45), end=D(1150), stop_reason="progression",
          best_response="PD", progression=D(1140))
    d.t("\n")
    return c
