"""VC-0107 38세 폐경 전, pT1c N0 IA, 등급 3, 보조 내분비 결정. 진단일 2023-05-02, 본원 초진 day 40.

외부 병원 회송서(영문 약어)와 수술 병리 사본. 값의 근거는 병리 사본과 본원 초진기록에 둔다.

짝 사례 매개변수: er = ER Allred (PS, IS) (기본 5+3 = 8). 총점 0~2 음성, 3~4 저발현, 5는 비율 점수로 가름, 6~8 양성
(PROJECT.md §5 ER 세부 규칙). 결과지의 판정 글도 그 점수에 맞춰 쓴다.
"""
from src.input.chart.virtual_chart import Chart, F, allred, allred_text, kdate


def er_call(ps: int, is_: int) -> tuple[str, str, str]:
    """(영문 판정, 회송서 표기, result 값). 5점은 비율 점수 PS 2(1~10%)면 저발현, 3 이상이면 양성."""
    total = ps + is_
    if total <= 2:
        return "negative", "ER-", "negative"
    if total <= 4 or (total == 5 and ps <= 2):
        return "low positive", "ER low+", "low_positive"
    return "positive", "ER+", "positive"


def build(er: tuple[int, int] = (5, 3)) -> Chart:
    word, short, result = er_call(*er)
    c = Chart("VC-0107", "2023-05-02", 40)
    D = c.on
    idx = c.index_date

    d = c.doc("progress_note", D(30))
    d.t(f"진료의뢰 회신서\nFrom: 가상의원 외과   To: 가상대학교병원 종양내과   작성일: {kdate(D(30))}\n").ident(38, full=False)
    d.t(f"Dx) Lt. breast ca., IDC, NG3, pT1cN0(0/3)M0, stage IA\n    {short} (Allred {er[0] + er[1]}), PR+ (Allred 8), HER2 1+, Ki-67 40%\n")
    d.t(f"s/p BCS & SLNB ({kdate(D(12))})\nPremenopausal, regular menses. Pls evaluate for adjuvant endocrine tx.\n")

    d = c.doc("progress_note", idx)
    d.t(f"[종양내과 초진기록]   {kdate(idx)}\n").ident(38).t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    d.put("38세", F("patient.age", 38)).t(" ")
    d.put("여성", F("patient.gender", "FEMALE")).t(". ")
    d.put(f"{kdate(D(0))} 가상의원에서 좌측 유방암 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0)))).t(", ")
    d.t(f"{kdate(D(12))} 유방 부분절제 + 감시림프절 생검 후 회송됨.\n")
    d.put("폐경 전, 월경 주기 28일로 규칙적", F("patient.menopausal_status", "premenopausal", within="폐경 전"),
          F("patient.menopausal_basis", "age_amenorrhea", within="월경 주기 28일로 규칙적")).t(". 출산력 1회.\n")
    d.put("ECOG PS 0", F("patient.ecog", 0, observed_date=idx)).t(". ")
    d.put("재발·전이 소견 없음", F("recurrence.status", "none")).t(".\n보조 내분비요법 상의 예정.\n")

    d = c.doc("pathology", D(18))
    d.t("[병리결과보고서]  (가상의원 사본)\n").ident(38, full=False)
    d.t(f"접수일: {kdate(D(12))}   보고일: {kdate(D(18))}\n검체: ")
    d.put("Left breast, partial mastectomy + sentinel LN biopsy", F("stage.operable", "yes")).t("\n\n")
    d.t("DIAGNOSIS\n  ").put("Invasive ductal carcinoma, NST", F("diagnosis.histology", "IDC")).t("\n  Histologic grade: ")
    d.put("NG3", F("diagnosis.grade", 3)).t("\n  Tumor size: ")
    d.put("1.8 cm", F("stage.pathologic_size_mm", 18, observed_date=D(12))).t("\n  Lymph node: ")
    d.put("0/3", F("stage.positive_ln_count", {"positive": 0, "examined": 3})).t("\n  Margin: clear\n  pTNM: ")
    d.put("pT1c N0(sn) M0, stage IA (AJCC 8th)",
          F("stage.ptnm", {"t": "T1c", "n": "N0", "m": "M0", "edition": "8th"}, observed_date=D(12)),
          F("stage.group", "IA", within="stage IA"), F("stage.disease_extent", "early", within="stage IA"),
          F("stage.metastatic_sites", "[Not Applicable]", within="pT1c N0(sn) M0"))
    d.t("\n\nIHC\n  ")
    pri = dict(specimen="primary", observed_date=D(12))
    d.put(f"ER: {word}, {allred_text(*er)}", F("receptors.er_percent", allred(*er, result), **pri)).t("\n  ")
    d.put(f"PR: positive, {allred_text(5, 3)}", F("receptors.pr_percent", allred(5, 3, "positive"), **pri)).t("\n  ")
    d.put("HER2 (4B5): 1+", F("receptors.her2_ihc", {"score": "1+"}, **pri)).t("\n  ")
    d.put("Ki-67: 40%", F("proliferation.ki67_percent", {"percent": 40}, **pri)).t("\n\nPathologist: 최가상 (가상의원)\n")
    return c
