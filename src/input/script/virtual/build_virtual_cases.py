"""가상 환자 사례 N01~N20 (VC-0110~VC-0129) 차트 만들기: src/input/virtual_patient_cases_2026-10-23.md §3.

사례 목록 문서 §3의 "이야기 핵심 값"을 차트 글로 쓰고, 값을 쓰는 순간 정답 patient_state의 값과 원문 위치를 함께 기록한다
(src/input/script/virtual/virtual_chart.py의 Chart·F를 그대로 쓴다). 차수·간주 규칙은 lines.annotate로 계산하고, 스키마·인용 위치를 검사한다.
기대 결과(B·C·D·추천)는 코드에 다시 적지 않고 문서 §3의 해당 표를 사례 폴더의 scenario.md로 옮긴다. 기대 결과를 고칠 때는 문서를 고친다.

결과 (tests/fixtures/virtual_charts/, 기존 10건 옆):
    <VC-01xx>/chart.txt                      차트 원문
    <VC-01xx>/expected/patient_state.json    A 정답
    <VC-01xx>/scenario.md                    문서 §3의 사례 표 (시험할 조건, 짝 사례, 기대 결과 초안)
    cases.csv                                새 사례 20건 목록

usage (team_project 폴더에서):
    python -m src.input.script.virtual.build_virtual_cases                 # 20건 모두
    python -m src.input.script.virtual.build_virtual_cases --ids VC-0112   # 한 건만
    python -m src.input.script.virtual.build_virtual_cases --check         # 쓰지 않고, 저장된 파일과 같은지만 본다

짝 사례(문서 §3 "짝 사례" 행, §4 G7~)는 아직 만들지 않는다. 기본 사례만.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

from src.input.script.virtual.virtual_chart import Chart, F, allred, allred_text, check, dumps, kdate

ROOT = Path(__file__).resolve().parents[4]
CASES_MD = ROOT / "src" / "input" / "virtual_patient_cases_2026-10-23.md"
OUT = ROOT / "tests" / "fixtures" / "virtual_charts"

CYC = lambda n, days: {"value": n, "basis": "recorded", "interval_days": days, "interval_basis": "recorded"}  # noqa: E731
SETTING_KO = {"neoadjuvant": "선행", "adjuvant": "보조", "metastatic": "고식"}
NA = "[Not Applicable]"


# ---------- 공통 문서 ----------
def er(ps: int, is_: int, res: str, label: str = "ER") -> tuple[str, str, dict]:
    ko = {"positive": "양성", "negative": "음성"}[res]
    return f"receptors.{label.lower()}_percent", f"{label} : {ko}, {allred_text(ps, is_)}", allred(ps, is_, res)


def pct(label: str, p: int, res: str, ko: str) -> tuple[str, str, dict]:
    return f"receptors.{label.lower()}_percent", f"{label} : {ko} {p}%", {"percent": p, "result": res}


def her2(score: str, faint: bool | None = None) -> tuple[str, str, dict]:
    v = {"score": score} if faint is None else {"score": score, "faint": faint}
    text = {None: "", False: " (no staining)", True: " (10% 미만 세포에서 희미한 불완전 막 염색)"}[faint]
    return "receptors.her2_ihc", f"HER2 (4B5): {score}{text}", v


def receptor_lines(d, recs, ki67: int | None, *, role: str = "current", specimen: str, observed: str,
                   sep: str = "\n  "):
    """ER·PR·HER2 (+ Ki-67) 줄. role이 history:recurrence면 재발 병소 재생검 값에 밀려난 원발 값."""
    kw = dict(role=role, specimen=specimen, observed_date=observed)
    for i, (path, text, value) in enumerate(recs):
        if i:
            d.t(sep)
        d.put(text, F(path, value, **kw))
    if ki67 is not None:
        d.t(sep).put(f"Ki-67: {ki67}%", F("proliferation.ki67_percent", {"percent": ki67}, specimen=specimen,
                                          observed_date=observed))


def surgery_path(c: Chart, day: int, age: int, *, op: str, grade: int, size_mm: int, ln: tuple[int, int],
                 ptnm: tuple[str, str], group: str, extent: str, recs, ki67: int | None, recur: bool = False,
                 ish: tuple[str, dict] | None = None, gender: str = "FEMALE", first: bool = True):
    """수술을 먼저 한 환자의 수술 병리 (ptnm). recur=True면 수용체는 history[] (뒤에 재발 병소 재생검이 있음)."""
    D = c.on
    d = c.doc("pathology", D(day + 6))
    fs = (F("patient.gender", gender), F("patient.age", age)) if first else ()
    d.t("[병리결과보고서]\n").ident(age, *fs, full=False)
    d.t(f"접수일: {kdate(D(day))}   보고일: {kdate(D(day + 6))}\n검체: ")
    d.put(op, F("stage.operable", "yes")).t("\n\n진단\n  조직형: ")
    d.put("침윤성 유관암 (invasive ductal carcinoma, NST)", F("diagnosis.histology", "IDC")).t("\n  조직학적 등급: ")
    d.put(f"{'I' * grade} (Nottingham grade {grade})", F("diagnosis.grade", grade)).t("\n  종양 크기: ")
    size = f"{size_mm} mm" if size_mm < 10 else f"{size_mm / 10:g} cm"
    d.put(size, F("stage.pathologic_size_mm", size_mm, observed_date=D(day))).t("\n  림프절: ")
    d.put(f"전이 {ln[0]}개 / 검사 {ln[1]}개", F("stage.positive_ln_count", {"positive": ln[0], "examined": ln[1]}))
    t, n = ptnm
    d.t("\n  절제연: 음성\n  pTNM: ")
    d.put(f"p{t} {n} M0, stage {group} (AJCC 8th)",
          F("stage.ptnm", {"t": t, "n": n, "m": "M0", "edition": "8th"}, observed_date=D(day)),
          F("stage.group", group, within=f"stage {group}"), F("stage.disease_extent", extent, within=f"stage {group}"),
          F("stage.metastatic_sites", NA, within=f"p{t} {n} M0"))
    d.t("\n\n면역조직화학\n  ")
    receptor_lines(d, recs, ki67, role="history:recurrence" if recur else "current", specimen="primary",
                   observed=D(day))
    if ish:
        d.t("\n  ").put(ish[0], F("receptors.her2_ish", ish[1], role="history:recurrence" if recur else "current",
                                   specimen="primary", observed_date=D(day)))
    d.t("\n\n판독의: 박가상\n")
    return d


def core_path(c: Chart, age: int, *, grade: int, recs, ki67: int | None, recur: bool = False,
              ish: tuple[str, dict] | None = None, side: str = "좌측"):
    """진단 중심 생검 (day 0 시행, day 4 보고). 선행요법 환자·de novo 환자."""
    D = c.on
    d = c.doc("pathology", D(4))
    d.t("SURGICAL PATHOLOGY REPORT\n").ident(age, F("patient.gender", "FEMALE"), F("patient.age", age), full=False)
    d.t(f"Received: {kdate(D(0))}   Reported: {kdate(D(4))}\nSpecimen: {side} 유방, 초음파 유도 중심 생검\n\n")
    d.t("DIAGNOSIS\n  ").put("Invasive ductal carcinoma, NST", F("diagnosis.histology", "IDC"))
    d.t("\n  Histologic grade: ").put(f"Nottingham grade {grade}", F("diagnosis.grade", grade))
    d.t("\n\nIMMUNOHISTOCHEMISTRY\n  ")
    role = "history:recurrence" if recur else "current"
    receptor_lines(d, recs, ki67, role=role, specimen="primary", observed=D(0))
    if ish:
        d.t("\n  ").put(ish[0], F("receptors.her2_ish", ish[1], role=role, specimen="primary", observed_date=D(0)))
    d.t("\n\nPathologist: 박가상\n")
    return d


def meta_path(c: Chart, day: int, age: int, site: str, recs, *, pdl1: tuple[str, dict] | None = None):
    """전이 병소 생검 (day 시행, day + 5 보고). 수용체는 지금 값 (IN-4 재생검 우선)."""
    D = c.on
    d = c.doc("pathology", D(day + 5))
    d.t("<병리 조직검사 결과>\n").ident(age, full=False)
    d.t(f"{kdate(D(day + 5))} {site} 생검 ({kdate(D(day))} 시행). Metastatic carcinoma, consistent with breast primary.\n")
    receptor_lines(d, recs, None, specimen="metastasis", observed=D(day), sep=", ")
    d.t(".\n")
    if pdl1:
        d.t("PD-L1 IHC: ").put(pdl1[0], F("receptors.pdl1", pdl1[1], specimen="metastasis", observed_date=D(day)))
        d.t("\n")
    return d


def image(c: Chart, day: int, age: int, modality: str, exam: str, findings: str, conclusion: str, sites: list[str],
          certainty: str = "confirmed"):
    d = c.doc("radiology", c.on(day))
    d.t("[영상의학 판독]\n").ident(age, full=False)
    d.t(f"검사: {exam}   검사일: {kdate(c.on(day))}\n\nFindings:\n  ")
    # 치료 전 유방 종괴 크기는 임상 크기 정답 (차트에 적힌 값은 칸이 있으면 정답에 넣는다, 2026-10-27 A 결정)
    m = re.search(r"\S+ 유방 (\d+(?:\.\d+)?) cm 종괴", findings)
    if m:
        d.t(findings[:m.start()]).put(m.group(0), F("stage.clinical_size_mm", round(float(m.group(1)) * 10),
                                                    observed_date=c.on(day))).t(findings[m.end():])
    else:
        d.t(findings)
    d.t("\nConclusion:\n  ")
    d.image(conclusion, modality=modality, date=c.on(day), sites=sites, certainty=certainty).t("\n")
    return d


def ngs(c: Chart, day: int, age: int, specimen: str, spec_text: str, detected: list[tuple], not_detected: list[str]):
    """종양 NGS (IN-7). detected = [(gene, cDNA, 단백 변화, VAF)]."""
    d = c.doc("molecular", c.on(day))
    d.t("[분자병리 검사 결과]\n").ident(age, full=False)
    d.t(f"검사기관: 가상유전체검사센터   보고일: {kdate(c.on(day))}\n검체: {spec_text}\n검사법: 표적 NGS\n\n")
    d.t("검출된 변이 (Clinically significant variants)\n")
    for gene, cdna, prot, vaf in detected:
        raw = f"{gene}   {cdna} (p.{prot})   VAF {vaf * 100:g}%"
        d.t("  ").put(raw, F(f"molecular.mutations.{gene}", result="detected", specimen=specimen,
                             variants=[{"protein_change": prot, "variant_type": "Missense_Mutation", "vaf": vaf,
                                        "raw": raw}])).t("\n")
    if not detected:
        d.t("  없음\n")
    d.t("\n검출되지 않음 (Not detected)\n  ")
    d.put(", ".join(not_detected), *(F(f"molecular.mutations.{g}", result="not_detected", specimen=specimen)
                                     for g in not_detected))
    d.t("\n\n* 패널 포함 유전자: PIK3CA, ESR1, AKT1, PTEN, ERBB2\n")
    d.genomic_report(specimen, c.on(day))
    return d


def germline(c: Chart, day: int, age: int, results: dict[str, tuple | None]):
    """생식세포 유전 검사 (혈액). results = {gene: (cDNA, 단백 변화, 판정) 또는 None(변이 없음)}."""
    d = c.doc("molecular", c.on(day))
    d.t("[유전성 유방암 유전자 검사 결과]\n").ident(age, full=False)
    d.t(f"검사기관: 가상유전체검사센터   보고일: {kdate(c.on(day))}\n검체: 말초혈액 (germline)\n")
    d.t("검사법: BRCA1/BRCA2 전장 염기서열 분석 + MLPA\n\n결과\n")
    for gene, r in results.items():
        if r is None:
            d.t("  ").put(f"{gene}: 병원성 변이 검출되지 않음",
                          F(f"molecular.germline.{gene}", result="not_detected")).t("\n")
            continue
        cdna, prot, call = r
        raw = f"{gene}   {cdna} (p.{prot})   {call}"
        kind = "Frame_Shift_Del" if "del" in cdna else "Frame_Shift_Ins"     # c.5946delT 결실, c.5266dupC 삽입 (MAF 표기)
        d.t("  ").put(raw, F(f"molecular.germline.{gene}", result="detected",
                             variants=[{"protein_change": prot, "variant_type": kind, "vaf": None,
                                        "raw": raw}])).t("\n")
    d.genomic_report(None, c.on(day))
    return d


def note(c: Chart, age: int, title: str = "<외래 경과기록>", dept: str = "종양내과"):
    d = c.doc("progress_note", c.index_date)
    d.t(f"{title}   {kdate(c.index_date)}   {dept}\n").ident(age).t(f"병원: 가상대학교병원 {dept}   담당의: 이가상\n\n")
    return d


def dx(d, c: Chart, text: str = "core bx로 진단"):
    return d.put(f"{kdate(c.on(0))} {text}", F("diagnosis.diagnosis_date", c.on(0), raw=kdate(c.on(0))))


def distant(d, c: Chart, day: int, sites: list[str], words: str):
    """원격 전이 재발 구절."""
    return d.put(f"{kdate(c.on(day))} {words}",
                 F("recurrence.recurrence_date", c.on(day), raw=kdate(c.on(day))),
                 F("recurrence.metastasis_day", day), F("recurrence.recurrence_day", day),
                 F("recurrence.status", "distant", within=words),
                 F("recurrence.metastatic_sites", sites, within=words))


def de_novo(d, c: Chart, ctnm: tuple[str, str], sites: list[str], words: str):
    """진단 시 IV기: metastasis_day 0, 재발 아님."""
    t, n = ctnm
    d.put(f"c{t}{n}M1, stage IV",
          F("stage.ctnm", {"t": t, "n": n, "m": "M1", "edition": None}, observed_date=c.on(5), within=f"c{t}{n}M1"),
          F("stage.group", "IV", within="stage IV"), F("stage.disease_extent", "metastatic", within="stage IV"))
    d.t(" ").put(f"(de novo, {words})", F("stage.metastatic_sites", sites), F("recurrence.metastasis_day", 0))
    return d


def clinical_stage(d, c: Chart, ctnm: tuple[str, str], group: str, extent: str):
    t, n = ctnm
    return d.put(f"c{t}{n}M0, stage {group}",
                 F("stage.ctnm", {"t": t, "n": n, "m": "M0", "edition": None}, observed_date=c.on(0),
                   within=f"c{t}{n}M0"),
                 F("stage.group", group, within=f"stage {group}"),
                 F("stage.disease_extent", extent, within=f"stage {group}"),
                 F("stage.metastatic_sites", NA, within=f"c{t}{n}M0"))


def meno(d, status: str, basis: str, text: str, within_status: str, within_basis: str):
    return d.put(text, F("patient.menopausal_status", status, within=within_status),
                 F("patient.menopausal_basis", basis, within=within_basis))


def meds(c: Chart, age: int, rows: list[dict]):
    """투약 기록 표. 행 = dict(name, drugs, setting, s, e, cyc=(n, 간격), resp, why, stop, prog, ongoing, anthra).
    prog는 차트에 근거가 있어야 한다: 진행 영상·전이 날짜가 차트에 없으면 종료일 (2026-10-27 A 결정)."""
    D = c.on
    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(age, full=False)
    d.t("구분    요법                                              시작         종료         주기       반응   중단 사유\n")
    for r in rows:
        cyc = r.get("cyc")
        cyc_txt = "-" if not cyc else (f"weekly #{cyc[0]}" if cyc[1] == 7 else f"q{cyc[1] // 7}w #{cyc[0]}")
        end = kdate(D(r["e"])) if r.get("e") is not None else "현재 투약 중"
        text = f"{r['name']}   {kdate(D(r['s']))}   {end}   {cyc_txt}   {r.get('resp') or '-'}   {r.get('why', '-')}"
        kw = dict(drugs=r["drugs"], setting=r["setting"], start=D(r["s"]),
                  end=D(r["e"]) if r.get("e") is not None else None, cycles=CYC(*cyc) if cyc else None,
                  stop_reason=r.get("stop"), best_response=r.get("resp"),
                  progression=D(r["prog"]) if r.get("prog") is not None else None, anthra=r.get("anthra", ()))
        if "ongoing" in r:
            kw["ongoing"] = r["ongoing"]
        d.t(f"{SETTING_KO[r['setting']]}    ").row(text, **kw).t("\n")
    return d


def ac(s: int, e: int, n: int = 4, why: str = "계획된 변경", stop: str = "planned_switch", dose: int = 60,
       setting: str = "adjuvant") -> dict:
    return dict(name=f"AC (doxorubicin {dose}mg/m2 + cyclophosphamide 600mg/m2)", drugs=["doxorubicin", "cyclophosphamide"],
                setting=setting, s=s, e=e, cyc=(n, 21), why=why, stop=stop,
                anthra=[{"drug": "doxorubicin", "dose_per_admin": {"value": dose, "unit": "mg/m2"}, "cycles": CYC(n, 21),
                         "total_dose": {"value": dose * n, "unit": "mg/m2"}}])


def wpac(s: int, e: int, setting: str = "adjuvant", why: str = "완료", stop: str = "completed", **kw) -> dict:
    return dict(name="paclitaxel 80mg/m2", drugs=["paclitaxel"], setting=setting, s=s, e=e, cyc=(12, 7), why=why,
                stop=stop, **kw)


def heart(d, c: Chart, lvef: int, day: int, history: str = "심장 질환 과거력 없음", yes: bool = False):
    d.put(history, F("patient.cardiac_history", "yes" if yes else "no")).t("\n")
    d.t(f"   Echo ({kdate(c.on(day))}): ").put(f"LVEF {lvef}%", F("patient.lvef_percent", lvef, observed_date=c.on(day)))
    return d.t("\n")


# ---------- 사례 ----------
def vc_0110() -> Chart:
    """N01 HR+/HER2+ 전이 1차, 항암 가능."""
    c = Chart("VC-0110", "2018-05-14", 2480)
    D = c.on
    d = note(c, 57)
    d.t("S) 우상복부 불편감, 허리 통증.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (LMP 2016년)", "폐경 후", "LMP 2016년").t("\n   과거력: ")
    heart(d, c, 62, 2470)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N0, IIA, HR+/HER2+ (IHC 3+)\n")
    d.t("   보조 AC #4 → paclitaxel + trastuzumab → trastuzumab 단독 (총 18회) 완료\n   ")
    d.put(f"보조 letrozole {kdate(D(2026))} 5년 복용 완료",
          F("recurrence.adjuvant_endocrine_end_date", D(2026), raw=kdate(D(2026)), within=kdate(D(2026)))).t("\n   ")
    distant(d, c, 2451, ["liver", "bone"], "간·골 전이").t(" (letrozole 종료 14개월 뒤)\n")
    d.t("   간 생검: ER 70%, PR 10%, HER2 3+\n\n")
    d.t("P) 전이성 HER2 양성 1차 요법 결정 (항암 가능)\n")

    surgery_path(c, 0, 51, op="좌측 유방 부분절제술 + 감시림프절 생검", grade=3, size_mm=26, ln=(0, 3),
                 ptnm=("T2", "N0"), group="IIA", extent="early", recur=True,
                 recs=[er(5, 2, "positive"), er(3, 2, "positive", "PR"), her2("3+")], ki67=40)
    image(c, 2451, 57, "CT", "Abdomen-pelvis CT (contrast)", "간 S5, S7에 2.4 cm, 1.6 cm 저음영 결절.",
          "간 다발성 전이", ["liver"])
    image(c, 2452, 57, "bone_scan", "Whole body bone scan", "L3 척추체, 우측 6번 늑골 열소 증가.", "골전이 (L3, Rt. 6th rib)",
          ["bone"])
    meta_path(c, 2458, 57, "간", [pct("ER", 70, "positive", "양성"), pct("PR", 10, "positive", "양성"), her2("3+")])
    meds(c, 57, [
        ac(30, 93),
        dict(name="paclitaxel 80mg/m2 + trastuzumab", drugs=["paclitaxel", "trastuzumab"], setting="adjuvant",
             s=114, e=191, cyc=(12, 7), why="계획된 변경", stop="planned_switch"),
        dict(name="허셉틴 (trastuzumab) 6mg/kg", drugs=["trastuzumab"], setting="adjuvant", s=212, e=485,
             cyc=(14, 21), why="완료 (총 18회)", stop="completed"),
        dict(name="페마라 (letrozole) 2.5mg qd", drugs=["letrozole"], setting="adjuvant", s=200, e=2026,
             why="완료 (5년)", stop="completed"),
    ])
    return c


def vc_0111() -> Chart:
    """N02 HER2+ 전이 2차, 활동성 뇌 전이."""
    c = Chart("VC-0111", "2023-02-06", 600)
    D = c.on
    d = note(c, 53, "[다학제 진료 회의록]", "종양내과")
    d.t("증례: ").put("폐경 전 (월경 있음)", F("patient.menopausal_status", "premenopausal", within="폐경 전"),
                    F("patient.menopausal_basis", "age_amenorrhea", within="월경 있음")).t(". ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T3", "N2"), ["liver"], "liver").t(", ER/PR 음성, HER2 3+.\n")
    d.t("      1차 docetaxel + pertuzumab + trastuzumab #6 → HP 유지 15개월 → 뇌·간 진행.\n      ")
    d.put("ECOG 1", F("patient.ecog", 1, observed_date=c.index_date)).t(". ")
    heart(d, c, 58, 595, "심장 질환 과거력 없음")
    d.t("논의: 새 뇌 전이 3개 (최대 1.8 cm, 두통·어지럼 있음). 신경외과·방사선종양학과: 국소 치료(수술·SRS) 적응 없음.\n")
    d.t("결론: 전이성 HER2 양성 2차 전신 요법 결정. anthracycline 사용 이력 없음.\n")

    core_path(c, 51, grade=3, recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")], ki67=45)
    image(c, 5, 51, "CT", "Chest-abdomen CT (contrast)", "간 S6·S8 다발성 결절, 좌측 액와·쇄골하 림프절 비대.",
          "간 다발성 전이", ["liver"])
    image(c, 590, 53, "MRI", "Brain MRI (contrast)", "좌측 전두엽 1.8 cm, 우측 두정엽 1.1 cm, 소뇌 0.7 cm 조영 증강 병변, 주위 부종.",
          "다발성 뇌 전이 (3개), 새로 생김", ["brain"])
    image(c, 588, 53, "CT", "Abdomen-pelvis CT (contrast)", "간 결절 크기·개수 증가.", "간 전이 진행 (PD)", ["liver"])
    meds(c, 53, [
        dict(name="DPH (docetaxel 75mg/m2 + 퍼제타 + 허셉틴)", drugs=["docetaxel", "pertuzumab", "trastuzumab"],
             setting="metastatic", s=14, e=119, cyc=(6, 21), resp="PR", why="유지요법 전환", stop="maintenance"),
        dict(name="HP 유지 (퍼제타 + 허셉틴)", drugs=["pertuzumab", "trastuzumab"], setting="metastatic", s=140,
             e=581, cyc=(22, 21), resp="PD", why="뇌·간 진행", stop="progression", prog=588),
    ])
    return c


def vc_0112() -> Chart:
    """N03 HER2+ 보조 trastuzumab 종료 120일 뒤 원격 전이 (DEEM-HER2ADC-6M met)."""
    c = Chart("VC-0112", "2022-09-05", 635)
    D = c.on
    d = note(c, 47)
    d.t("S) 마른 기침 1개월, 우상복부 불편감.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 규칙적", "폐경 전", "월경 규칙적").t("\n   과거력: ")
    heart(d, c, 60, 625)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a(2/14), IIB, HR-/HER2+ (IHC 3+)\n")
    d.t(f"   보조 AC #4 → paclitaxel + trastuzumab → trastuzumab, {kdate(D(490))} 총 18회 완료\n   ")
    distant(d, c, 610, ["lung", "liver"], "폐·간 전이").t(" (trastuzumab 종료 4개월 뒤), Brain MRI 음성\n\n")
    d.t("P) 전이성 HER2 양성 첫 전신 요법 결정\n")

    surgery_path(c, 0, 46, op="우측 유방 부분절제술 + 액와 림프절 절제", grade=3, size_mm=31, ln=(2, 14),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")], ki67=55)
    image(c, 610, 47, "CT", "Chest-abdomen CT (contrast)", "양측 폐 다발성 결절 (최대 1.4 cm), 간 S4 2.0 cm 결절.",
          "폐·간 다발성 전이", ["lung", "liver"])
    image(c, 614, 47, "MRI", "Brain MRI (contrast)", "뇌실질 내 조영 증강 병변 없음.", "뇌 전이 없음", [])
    meta_path(c, 616, 47, "폐", [er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("3+")])
    meds(c, 47, [
        ac(35, 98),
        dict(name="paclitaxel 80mg/m2 + trastuzumab", drugs=["paclitaxel", "trastuzumab"], setting="adjuvant",
             s=119, e=196, cyc=(12, 7), why="계획된 변경", stop="planned_switch"),
        dict(name="허셉틴 (trastuzumab) 6mg/kg", drugs=["trastuzumab"], setting="adjuvant", s=217, e=490,
             cyc=(14, 21), why="완료 (총 18회)", stop="completed"),
    ])
    return c


def _luminal_late(ref: str, dx_date: str, age_dx: int, age_now: int, *, adj_ai: tuple[str, str], mets: int,
                  first: dict, second: dict, idx: int, rebiopsy, primary_her2, sites: list[str], words: str) -> Chart:
    """N04·N16 공통: 보조 AC → paclitaxel → AI 5년, 재발 후 내분비 2차례 진행, 간 재생검, 내분비 부적합."""
    c = Chart(ref, dx_date, idx)
    D = c.on
    ai, ai_ko = adj_ai
    d = note(c, age_now)
    d.t("S) 식욕 저하, 우상복부 불편감.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (50세 폐경)", "폐경 후", "50세 폐경").t("\n   과거력: ")
    heart(d, c, 61, idx - 10)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a, IIB\n")
    d.t(f"   보조 AC #4 → weekly paclitaxel #12 → ")
    d.put(f"{ai} {kdate(D(2041))} 5년 복용 완료",
          F("recurrence.adjuvant_endocrine_end_date", D(2041), raw=kdate(D(2041)), within=kdate(D(2041)))).t("\n   ")
    distant(d, c, mets, sites, words).t("\n")
    d.t(f"   1L {first['label']} → PD, 2L {second['label']} → PD\n")
    d.t("   간 재생검 결과 아래 병리 참조\n   ")
    d.t("내분비 치료 더 이상 부적합 (내분비 저항성, 간 병변 빠른 진행)\n\n")
    d.t("P) 3차 치료 결정 (고식 항암 경험 없음)\n")

    surgery_path(c, 0, age_dx, op="좌측 유방 부분절제술 + 액와 림프절 절제", grade=2, size_mm=28, ln=(2, 14),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), primary_her2], ki67=20)
    bone = ", L2 척추체 골용해성 병변" if "bone" in sites else ""
    image(c, mets, age_now - 2, "CT", "Abdomen-pelvis CT (contrast)", f"간 S6 2.1 cm 저음영 결절{bone}.", words, sites)
    image(c, idx - 30, age_now, "CT", "Abdomen-pelvis CT (contrast)", "간 결절 크기 증가, 새 결절 4개.", "간 전이 진행 (PD)",
          ["liver"])
    meta_path(c, idx - 25, age_now, "간", [er(5, 2, "positive"), er(2, 1, "positive", "PR"), rebiopsy])
    meds(c, age_now, [
        ac(40, 103), wpac(124, 201),
        dict(name=f"{ai_ko} ({ai}) qd", drugs=[ai], setting="adjuvant", s=215, e=2041, why="완료 (5년)",
             stop="completed"),
        {**first, "setting": "metastatic", "resp": "PD", "why": "진행", "stop": "progression"},
        {**second, "setting": "metastatic", "resp": "PD", "why": "진행", "stop": "progression"},
    ])
    return c


def vc_0113() -> Chart:
    """N04 HR+/HER2- 3차, 이전 고식 항암 없음, 간 재생검 HER2 1+ (저발현)."""
    return _luminal_late(
        "VC-0113", "2014-03-10", 51, 60, adj_ai=("letrozole", "페마라"), mets=2600, idx=3460,
        first=dict(label="letrozole + palbociclib", name="입랜스 (palbociclib) + 페마라 (letrozole)",
                   drugs=["palbociclib", "letrozole"], s=2620, e=3230, cyc=(21, 28), prog=3230),
        second=dict(label="exemestane + everolimus", name="아로마신 (exemestane) + 아피니토 (everolimus)",
                    drugs=["exemestane", "everolimus"], s=3245, e=3430, prog=3430),
        rebiopsy=her2("1+"), primary_her2=her2("1+"), sites=["liver", "bone"], words="간·골 전이")


def vc_0125() -> Chart:
    """N16 N04와 같은 경과, 원발 HER2 0, 간 재생검 HER2 0 + 희미한 막 염색 (초저발현)."""
    return _luminal_late(
        "VC-0125", "2018-01-15", 50, 58, adj_ai=("anastrozole", "아리미덱스"), mets=2200, idx=2935,
        first=dict(label="fulvestrant + palbociclib", name="파슬로덱스 (fulvestrant) + 입랜스 (palbociclib)",
                   drugs=["fulvestrant", "palbociclib"], s=2220, e=2700, cyc=(17, 28), prog=2700),
        second=dict(label="exemestane + everolimus", name="아로마신 (exemestane) + 아피니토 (everolimus)",
                    # 진행일 = 진행 CT 날 (idx - 30, 종료 5일 뒤 '간 전이 진행 (PD)', 2026-10-27 A 결정)
                    drugs=["exemestane", "everolimus"], s=2720, e=2900, prog=2905),
        rebiopsy=her2("0", True), primary_her2=her2("0", False), sites=["liver"], words="간 전이")


def vc_0114() -> Chart:
    """N05 HR+/HER2- de novo, 내분비 2차례·고식 항암 2차례 진행, HER2 0."""
    c = Chart("VC-0114", "2020-01-13", 1620)
    d = note(c, 66)
    d.t("S) 호흡곤란 악화, 기침.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (52세 폐경)", "폐경 후", "52세 폐경").t("\n   과거력: ")
    heart(d, c, 59, 1610)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N1"), ["bone", "lung"], "bone, lung").t("\n")
    d.t("   ER Allred 8 / PR Allred 5 / HER2 0\n")
    d.t("   1L anastrozole + ribociclib 26개월 → PD, 2L fulvestrant → PD\n")
    d.t("   고식 항암 capecitabine → PD, paclitaxel → PD. doxorubicin 사용 이력 없음\n\n")
    d.t("P) 고식 항암 3차 결정\n")

    core_path(c, 62, grade=2, recs=[er(5, 3, "positive"), er(3, 2, "positive", "PR"), her2("0", False)], ki67=25,
              recur=True, side="우측")
    image(c, 5, 62, "bone_scan", "Whole body bone scan", "T10, L1 척추체, 골반 다발성 열소 증가.", "다발성 골전이", ["bone"])
    image(c, 5, 62, "CT", "Chest CT (contrast)", "양측 폐 다발성 결절 (최대 1.1 cm).", "폐 다발성 전이 의증", ["lung"],
          "suspected")
    meta_path(c, 9, 62, "폐", [er(5, 3, "positive"), er(3, 2, "positive", "PR"), her2("0", False)])
    meds(c, 66, [
        dict(name="키스칼리 (ribociclib) + 아리미덱스 (anastrozole)", drugs=["ribociclib", "anastrozole"],
             setting="metastatic", s=20, e=810, cyc=(28, 28), resp="PD", why="진행", stop="progression", prog=810),
        dict(name="파슬로덱스 (fulvestrant) 500mg", drugs=["fulvestrant"], setting="metastatic", s=830, e=1010,
             resp="PD", why="진행", stop="progression", prog=1010),
        dict(name="젤로다 (capecitabine) 1000mg/m2 bid", drugs=["capecitabine"], setting="metastatic", s=1030, e=1300,
             cyc=(13, 21), resp="PD", why="진행", stop="progression", prog=1300),
        wpac(1320, 1600, setting="metastatic", why="진행", stop="progression", resp="PD", prog=1600),
    ])
    return c


def vc_0115() -> Chart:
    """N06 TNBC, 보조 종료 300일 뒤 폐 전이, 1차 gemcitabine + carboplatin 진행, gBRCA 음성."""
    c = Chart("VC-0115", "2021-07-05", 750)
    d = note(c, 42)
    d.t("S) 기침, 흉통.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 규칙적", "폐경 전", "월경 규칙적").t("\n   과거력: ")
    heart(d, c, 63, 740)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a(2/10), IIB, TNBC\n   보조 AC #4 → weekly paclitaxel #12\n   ")
    distant(d, c, 496, ["lung"], "폐 전이").t(" (보조 종료 300일 뒤)\n")
    d.t("   1L gemcitabine + carboplatin 7개월 → PD\n   생식세포 BRCA1/2 음성\n\n")
    d.t("P) 전이성 TNBC 2차 요법 결정\n")

    surgery_path(c, 0, 40, op="좌측 유방 부분절제술 + 액와 림프절 절제", grade=3, size_mm=34, ln=(2, 10),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("0", False)], ki67=80)
    image(c, 496, 41, "CT", "Chest CT (contrast)", "양측 폐 다발성 결절 (최대 1.6 cm), 흉막 삼출 없음.", "폐 다발성 전이 의증",
          ["lung"], "suspected")
    meta_path(c, 505, 41, "폐", [er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("0", False)],
              pdl1=("22C3 pharmDx, CPS 2", {"assay": "22C3", "score_type": "CPS", "score": 2}))
    germline(c, 520, 41, {"BRCA1": None, "BRCA2": None})
    meds(c, 42, [
        ac(35, 98), wpac(119, 196),
        dict(name="gemcitabine 1000mg/m2 + carboplatin AUC 2 (d1, d8)", drugs=["gemcitabine", "carboplatin"],
             setting="metastatic", s=525, e=735, cyc=(10, 21), resp="PD", why="진행", stop="progression", prog=735),
    ])
    return c


def vc_0116() -> Chart:
    """N07 TNBC 1차, PD-L1 CPS 1, 생식세포 BRCA1 병원성 변이, 보조 TC (anthracycline 없음)."""
    c = Chart("VC-0116", "2021-11-08", 685)
    d = note(c, 38)
    d.t("S) 우상복부 통증.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 규칙적", "폐경 전", "월경 규칙적").t("\n   과거력: ")
    heart(d, c, 65, 680)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT1cN0, IA, TNBC\n   보조 TC (docetaxel + cyclophosphamide) #4\n   ")
    distant(d, c, 646, ["liver", "distant_ln"], "간·종격동 림프절 전이").t(" (보조 종료 18개월 뒤)\n")
    d.t("   PD-L1 22C3 CPS 1, 생식세포 BRCA1 병원성 변이\n\n")
    d.t("P) 전이성 TNBC 1차 요법 결정\n")

    surgery_path(c, 0, 36, op="우측 유방 부분절제술 + 감시림프절 생검", grade=3, size_mm=15, ln=(0, 3),
                 ptnm=("T1c", "N0"), group="IA", extent="early", recur=True,
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("0", False)], ki67=75)
    image(c, 646, 37, "CT", "Chest-abdomen CT (contrast)", "간 S2·S7 결절 2개 (최대 2.6 cm), 기관분지하 림프절 1.8 cm.",
          "간·종격동 림프절 전이 의증", ["liver", "distant_ln"], "suspected")
    meta_path(c, 655, 37, "간", [er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("0", False)],
              pdl1=("22C3 pharmDx, CPS 1", {"assay": "22C3", "score_type": "CPS", "score": 1}))
    germline(c, 670, 37, {"BRCA1": ("c.5266dupC", "Q1756Pfs*74", "Pathogenic (병원성)"), "BRCA2": None})
    meds(c, 38, [
        dict(name="TC (docetaxel 75mg/m2 + cyclophosphamide 600mg/m2)", drugs=["docetaxel", "cyclophosphamide"],
             setting="adjuvant", s=35, e=98, cyc=(4, 21), why="완료", stop="completed"),
    ])
    return c


def vc_0117() -> Chart:
    """N08 조기 TNBC cT2N1, 선행 KEYNOTE-522 요법 후 잔존 (ypT1b N1a, RCB-II)."""
    c = Chart("VC-0117", "2024-01-15", 220)
    D = c.on
    d = note(c, 44)
    d.t("S) 수술 부위 통증 호전.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 규칙적", "폐경 전", "월경 규칙적").t("\n   과거력: ")
    heart(d, c, 61, 210)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T2", "N1"), "IIB", "early").t(", TNBC\n")
    d.t("   선행 pembrolizumab + paclitaxel + carboplatin → pembrolizumab + AC 후 수술: ypT1b N1a, 잔존 침윤암 (RCB-II)\n   ")
    d.t("생식세포 BRCA1/2 음성\n   ").put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 수술 후 보조 요법 결정 (pembrolizumab 계속 여부, capecitabine)\n")

    core_path(c, 44, grade=3, recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("1+")], ki67=70)
    image(c, 2, 44, "ultrasound", "Breast ultrasound", "좌측 유방 3시 불규칙 종괴, 좌측 액와 림프절 2개 피질 비후.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    germline(c, 40, 44, {"BRCA1": None, "BRCA2": None})
    d = c.doc("pathology", D(203))
    d.t("[병리결과보고서]\n").ident(44, full=False)
    d.t(f"보고일: {kdate(D(203))}\n검체: ")
    d.put("좌측 유방 부분절제술 + 액와 림프절 절제 (선행 항암 후)", F("stage.operable", "yes")).t("\n\n진단\n  잔존 침윤암: ")
    d.put("있음 (residual invasive carcinoma)", F("neoadjuvant_response.pcr", "no")).t("\n  잔존 종양 크기: 0.8 cm\n")
    d.t("  림프절: 1/12 (+)\n  ypTNM: ")
    d.put("ypT1b ypN1a (AJCC 8th)",
          F("stage.yptnm", {"t": "T1b", "n": "N1a", "m": "M0", "edition": "8th", "residual_size_mm": 8,
                            "positive_ln": 1, "examined_ln": 12}, observed_date=D(196))).t("\n  RCB: ")
    d.put("RCB class II", F("neoadjuvant_response.rcb", "RCB-II")).t("\n\n판독의: 박가상\n")
    meds(c, 44, [
        dict(name="키트루다 (pembrolizumab) + paclitaxel + carboplatin", drugs=["pembrolizumab", "paclitaxel", "carboplatin"],
             setting="neoadjuvant", s=14, e=98, cyc=(4, 21), why="계획된 변경", stop="planned_switch"),
        {**ac(105, 168, setting="neoadjuvant", why="완료", stop="completed"),
         "name": "키트루다 (pembrolizumab) + AC (doxorubicin 60mg/m2 + cyclophosphamide 600mg/m2)",
         "drugs": ["pembrolizumab", "doxorubicin", "cyclophosphamide"], "resp": "PR"},
    ])
    return c


def vc_0118() -> Chart:
    """N09 조기 TNBC pT1b(8 mm) N0, 수술 먼저."""
    c = Chart("VC-0118", "2024-06-03", 35)
    d = note(c, 63, dept="종양내과")
    d.t("S) 검진 유방촬영에서 발견, 증상 없음.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (51세 폐경)", "폐경 후", "51세 폐경").t("\n   과거력: ")
    heart(d, c, 64, 30)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", 수술: pT1b(8 mm) N0(0/2), IA, TNBC\n   ")
    d.put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 보조 전신 요법 필요 여부 결정\n")
    surgery_path(c, 14, 63, op="우측 유방 부분절제술 + 감시림프절 생검", grade=2, size_mm=8, ln=(0, 2),
                 ptnm=("T1b", "N0"), group="IA", extent="early",
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("0", False)], ki67=30)
    return c


def vc_0119() -> Chart:
    """N10 HR+/HER2- 고위험 조기, 선행 AC → paclitaxel 후 잔존, 생식세포 BRCA2 병원성 변이."""
    c = Chart("VC-0119", "2023-04-10", 215)
    D = c.on
    d = note(c, 41)
    d.t("S) 수술 후 회복 양호.\n   폐경: ")
    meno(d, "premenopausal", "age_amenorrhea", "폐경 전, 월경 규칙적", "폐경 전", "월경 규칙적").t("\n   과거력: ")
    heart(d, c, 63, 205)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T3", "N1"), "IIIA", "locally_advanced").t(", HR+/HER2-, grade 3\n")
    d.t("   선행 AC #4 → weekly paclitaxel #12 후 수술: ypT2 ypN1a (2/15), 잔존 침윤암\n")
    d.t("   생식세포 BRCA2 병원성 변이\n   ").put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 보조 요법 결정 (내분비요법 + olaparib / abemaciclib)\n")

    core_path(c, 41, grade=3, recs=[pct("ER", 80, "positive", "양성"), pct("PR", 30, "positive", "양성"),
                                    her2("0", False)], ki67=35)
    image(c, 2, 41, "MRI", "Breast MRI (contrast)", "좌측 유방 5.5 cm 종괴, 좌측 액와 림프절 3개 비대.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    germline(c, 60, 41, {"BRCA1": None, "BRCA2": ("c.5946delT", "S1982Rfs*22", "Pathogenic (병원성)")})
    d = c.doc("pathology", D(195))
    d.t("[병리결과보고서]\n").ident(41, full=False)
    d.t(f"보고일: {kdate(D(195))}\n검체: ")
    d.put("좌측 유방 전절제술 + 액와 림프절 절제 (선행 항암 후)", F("stage.operable", "yes")).t("\n\n진단\n  잔존 침윤암: ")
    d.put("있음 (residual invasive carcinoma)", F("neoadjuvant_response.pcr", "no")).t("\n  잔존 종양 크기: 2.5 cm\n")
    d.t("  림프절: 2/15 (+)\n  ypTNM: ")
    d.put("ypT2 ypN1a (AJCC 8th)",
          F("stage.yptnm", {"t": "T2", "n": "N1a", "m": "M0", "edition": "8th", "residual_size_mm": 25,
                            "positive_ln": 2, "examined_ln": 15}, observed_date=D(189))).t("\n  RCB: ")
    d.put("RCB class II", F("neoadjuvant_response.rcb", "RCB-II")).t("\n\n판독의: 박가상\n")
    meds(c, 41, [ac(14, 77, setting="neoadjuvant"),
                 wpac(84, 161, setting="neoadjuvant", resp="PR")])
    return c


def vc_0120() -> Chart:
    """N11 HR+/HER2+ cT2N1, 선행 TCHP 후 pCR."""
    c = Chart("VC-0120", "2023-08-21", 170)
    D = c.on
    d = note(c, 50)
    d.t("S) 특이 증상 없음.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (LMP 2021년)", "폐경 후", "LMP 2021년").t("\n   과거력: ")
    heart(d, c, 60, 160)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T2", "N1"), "IIB", "early").t(", HR+/HER2+ (IHC 3+)\n")
    d.t("   선행 TCHP #6 후 수술: ypT0 ypN0, pCR\n   ").put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 보조 HER2 표적치료·내분비요법 결정\n")

    core_path(c, 50, grade=2, recs=[er(4, 3, "positive"), er(3, 1, "positive", "PR"), her2("3+")], ki67=40,
              side="우측")
    d = c.doc("pathology", D(153))
    d.t("[병리결과보고서]\n").ident(50, full=False)
    d.t(f"보고일: {kdate(D(153))}\n검체: ")
    d.put("우측 유방 부분절제술 + 감시림프절 생검 (선행 항암 후)", F("stage.operable", "yes")).t("\n\n진단\n  잔존 침윤암: ")
    d.put("없음 (no residual invasive carcinoma, pCR)", F("neoadjuvant_response.pcr", "yes")).t("\n  림프절: 0/3\n  ypTNM: ")
    d.put("ypT0 ypN0 (AJCC 8th)",
          F("stage.yptnm", {"t": "T0", "n": "N0", "m": "M0", "edition": "8th", "residual_size_mm": 0,
                            "positive_ln": 0, "examined_ln": 3}, observed_date=D(147))).t("\n  RCB: ")
    d.put("RCB-0 (pCR)", F("neoadjuvant_response.rcb", "RCB-0")).t("\n\n판독의: 박가상\n")
    meds(c, 50, [
        dict(name="TCHP (탁소텔 + 카보플라틴 + 허셉틴 + 퍼제타)", drugs=["docetaxel", "carboplatin", "trastuzumab", "pertuzumab"],
             setting="neoadjuvant", s=14, e=119, cyc=(6, 21), resp="CR", why="완료", stop="completed"),
    ])
    return c


def vc_0121() -> Chart:
    """N12 HR+/HER2- cT3N1 IIIA, 선행 항암 결정 (치료 전)."""
    c = Chart("VC-0121", "2025-03-03", 14)
    d = note(c, 47, "[다학제 진료 회의록]")
    d.t("증례: ").put("폐경 전 (월경 규칙적)", F("patient.menopausal_status", "premenopausal", within="폐경 전"),
                    F("patient.menopausal_basis", "age_amenorrhea", within="월경 규칙적")).t(". ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T3", "N1"), "IIIA", "locally_advanced").t(", HR+/HER2- (HER2 1+), grade 3.\n      ")
    d.put("ECOG 0", F("patient.ecog", 0, observed_date=c.index_date)).t(". ")
    heart(d, c, 64, 10)
    d.t("논의: 종양 크고 림프절 양성, Ki-67 높음 → 선행 항암 후 수술.\n결론: 선행 항암 요법 결정\n")
    core_path(c, 47, grade=3, recs=[pct("ER", 90, "positive", "양성"), pct("PR", 5, "positive", "약양성"), her2("1+")],
              ki67=45)
    image(c, 5, 47, "MRI", "Breast MRI (contrast)", "좌측 유방 5.6 cm 종괴, 좌측 액와 림프절 2개 비대.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    image(c, 8, 47, "PET", "F-18 FDG PET-CT", "좌측 유방 종괴 (SUVmax 9.1), 좌측 액와 림프절 섭취.", "원격 전이 없음", [])
    return c


def vc_0122() -> Chart:
    """N13 보조 letrozole 3년째 폐 전이, 원발 조직 PIK3CA E545K."""
    c = Chart("VC-0122", "2020-02-17", 1165)
    D = c.on
    d = note(c, 55)
    d.t("S) 기침 1개월.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (50세 폐경)", "폐경 후", "50세 폐경").t("\n   과거력: ")
    heart(d, c, 62, 1155)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N0, IIA\n   보조 letrozole 복용 중 ")
    distant(d, c, 1130, ["lung"], "폐 전이").t(" → ")
    d.put(f"letrozole {kdate(D(1135))} 중단",
          F("recurrence.adjuvant_endocrine_end_date", D(1135), raw=kdate(D(1135)), within=kdate(D(1135)))).t(" (PD)\n")
    d.t("   원발 조직 NGS: PIK3CA E545K 검출. 보조 CDK4/6 억제제 사용 없음\n\n")
    d.t("P) 전이성 1차 내분비 기반 치료 결정\n")
    surgery_path(c, 0, 52, op="좌측 유방 부분절제술 + 감시림프절 생검", grade=2, size_mm=24, ln=(0, 3),
                 ptnm=("T2", "N0"), group="IIA", extent="early", recur=True,
                 recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("1+")], ki67=20)
    image(c, 1130, 55, "CT", "Chest CT (contrast)", "양측 폐 다발성 결절 (최대 1.3 cm).", "폐 다발성 전이 의증", ["lung"],
          "suspected")
    meta_path(c, 1140, 55, "폐", [er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("1+")])
    ngs(c, 1150, 55, "primary", f"원발 수술 조직 ({kdate(D(0))})", [("PIK3CA", "c.1633G>A", "E545K", 0.31)],
        ["ESR1", "AKT1", "PTEN"])
    meds(c, 55, [
        dict(name="페마라 (letrozole) 2.5mg qd", drugs=["letrozole"], setting="adjuvant", s=40, e=1135, resp="PD",
             why="폐 전이", stop="progression", prog=1130),
    ])
    return c


def vc_0123() -> Chart:
    """N14 de novo 뼈 전이, 1차 letrozole + abemaciclib 진행, 원발 조직 AKT1 E17K."""
    c = Chart("VC-0123", "2022-01-10", 730)
    d = note(c, 64)
    d.t("S) 골반 통증 악화.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (51세 폐경)", "폐경 후", "51세 폐경").t("\n   과거력: ")
    heart(d, c, 60, 720)
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N1"), ["bone"], "bone only").t("\n")
    d.t("   1L letrozole + abemaciclib 22개월 → PD (골병변 증가)\n")
    d.t("   골 생검: 검체 부족으로 판정 불가 → 원발 조직 NGS: AKT1 E17K 검출\n\n")
    d.t("P) 고식 내분비 2차 결정\n")
    core_path(c, 62, grade=2, recs=[er(5, 3, "positive"), er(3, 2, "positive", "PR"), her2("0", False)], ki67=15)
    image(c, 5, 62, "bone_scan", "Whole body bone scan", "흉추·요추·골반 다발성 열소 증가.", "다발성 골전이", ["bone"])
    image(c, 680, 64, "bone_scan", "Whole body bone scan", "새 열소 3곳 (우측 대퇴골, T6, 좌측 늑골).", "골전이 진행 (PD)",
          ["bone"])
    ngs(c, 715, 64, "primary", f"원발 중심 생검 조직 ({kdate(c.on(0))})", [("AKT1", "c.49G>A", "E17K", 0.22)],
        ["PIK3CA", "ESR1", "PTEN"])
    meds(c, 64, [
        dict(name="버제니오 (abemaciclib) 150mg bid + 페마라 (letrozole)", drugs=["abemaciclib", "letrozole"],
             setting="metastatic", s=20, e=690, resp="PD", why="진행", stop="progression", prog=680),
    ])
    return c


def vc_0124() -> Chart:
    """N15 ER 5% (저발현), PR 0, HER2 2+ / SISH 비증폭, cT2N1, 선행 결정."""
    c = Chart("VC-0124", "2025-05-12", 12)
    d = note(c, 39, "[다학제 진료 회의록]")
    d.t("증례: ").put("폐경 전 (월경 규칙적)", F("patient.menopausal_status", "premenopausal", within="폐경 전"),
                    F("patient.menopausal_basis", "age_amenorrhea", within="월경 규칙적")).t(". ")
    dx(d, c).t(", ")
    clinical_stage(d, c, ("T2", "N1"), "IIB", "early").t(", ER 5% (약양성), PR 0%, HER2 2+ / SISH 비증폭, grade 3.\n      ")
    d.put("ECOG 0", F("patient.ecog", 0, observed_date=c.index_date)).t(". ")
    heart(d, c, 66, 10)
    d.t("논의: ER 저발현 — 삼중음성에 준해 치료할지 논의.\n결론: 선행 항암 요법 결정\n")
    core_path(c, 39, grade=3, recs=[pct("ER", 5, "low_positive", "약양성"), pct("PR", 0, "negative", "음성"), her2("2+")],
              ki67=60, ish=("SISH: not amplified (HER2/CEP17 ratio 1.4)", {"result": "not_amplified", "method": "SISH"}))
    image(c, 3, 39, "MRI", "Breast MRI (contrast)", "좌측 유방 3.5 cm 종괴, 좌측 액와 림프절 1개 비대.",
          "좌측 액와 림프절 전이 의심", [], "suspected")
    return c


def vc_0126() -> Chart:
    """N17 de novo 다발성 간 전이, visceral crisis (의사 판단 문장), ECOG 2."""
    c = Chart("VC-0126", "2025-06-02", 12)
    d = note(c, 59)
    d.t("S) 황달, 복부 팽만, 식욕 저하 2주.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (52세 폐경)", "폐경 후", "52세 폐경").t("\n   과거력: ")
    heart(d, c, 58, 9)
    d.t("O) ").put("ECOG PS 2", F("patient.ecog", 2, observed_date=c.index_date)).t("\n")
    d.t(f"   Lab ({kdate(c.on(10))}): T.bil 3.1 mg/dL, AST 145, ALT 160, ALP 410\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c).t(", ")
    de_novo(d, c, ("T2", "N1"), ["liver"], "liver").t(", HR+/HER2-\n   ")
    d.put("간 기능 악화를 동반한 visceral crisis로 판단", F("patient.visceral_crisis", "yes")).t("\n\n")
    d.t("P) 전이성 1차 요법 결정\n")
    core_path(c, 59, grade=2, recs=[er(5, 3, "positive"), er(4, 2, "positive", "PR"), her2("0", False)], ki67=30)
    image(c, 3, 59, "CT", "Abdomen-pelvis CT (contrast)", "간 양엽에 무수한 저음영 결절, 간내 담관 경도 확장.",
          "간 다발성 전이", ["liver"])
    return c


def vc_0127() -> Chart:
    """N18 TNBC, 보조 AC 3주기 (심부전 의심 중단, doxorubicin mg 표기), 좌측 흉벽·내유림프절 방사선, 협심증."""
    c = Chart("VC-0127", "2019-03-18", 1520)
    D = c.on
    d = note(c, 61)
    d.t("S) 호흡곤란, 기침.\n   폐경: ")
    meno(d, "postmenopausal", "age_amenorrhea", "폐경 후 (53세 폐경)", "폐경 후", "53세 폐경").t("\n   과거력: ")
    heart(d, c, 48, 1510, "협심증 (2017년 스텐트 시술)", yes=True)
    d.t("   방사선: ").put("좌측 흉벽·내유림프절 방사선 치료 (50 Gy)", F("patient.mediastinal_radiation", "yes")).t("\n")
    d.t("O) ").put("ECOG PS 1", F("patient.ecog", 1, observed_date=c.index_date)).t("\n   ")
    d.put("Ht 158cm / Wt 58kg", F("patient.height_cm", 158, within="Ht 158cm"),
          F("patient.weight_kg", 58, within="Wt 58kg")).t("\n\n")
    d.t("A) Lt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a(1/10), IIB, TNBC\n")
    d.t("   보조 AC #3 후 심부전 의심으로 중단 → weekly paclitaxel #12\n   ")
    distant(d, c, 1310, ["lung"], "폐 전이").t("\n   1L paclitaxel → PD\n\n")
    d.t("P) 고식 항암 2차 결정\n")
    surgery_path(c, 0, 57, op="좌측 유방 전절제술 + 액와 림프절 절제", grade=3, size_mm=29, ln=(1, 10),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("1+")], ki67=65)
    image(c, 1310, 61, "CT", "Chest CT (contrast)", "양측 폐 다발성 결절 (최대 1.9 cm).", "폐 다발성 전이", ["lung"])
    meta_path(c, 1318, 61, "폐", [er(0, 0, "negative"), er(0, 0, "negative", "PR"), her2("1+")])
    meds(c, 61, [
        dict(name="AC (doxorubicin 96mg + cyclophosphamide 960mg)", drugs=["doxorubicin", "cyclophosphamide"],
             setting="adjuvant", s=35, e=77, cyc=(3, 21), why="심부전 의심 (LVEF 저하)", stop="toxicity",
             anthra=[{"drug": "doxorubicin", "dose_per_admin": {"value": 96, "unit": "mg"}, "cycles": CYC(3, 21),
                      "total_dose": {"value": 288, "unit": "mg"}}]),
        wpac(98, 175),
        wpac(1330, 1500, setting="metastatic", why="진행", stop="progression", resp="PD", prog=1500),
    ])
    return c


def vc_0128() -> Chart:
    """N19 43세 폐경 전, 보조 tamoxifen 2년째 뼈·림프절 전이, FSH로 폐경 전 확인."""
    c = Chart("VC-0128", "2022-05-09", 800)
    D = c.on
    d = note(c, 43)
    d.t("S) 허리 통증.\n   폐경: ")
    meno(d, "premenopausal", "fsh", f"폐경 전 (월경 불규칙, FSH 6.2 mIU/mL·E2 85 pg/mL, {kdate(D(775))})",
         "폐경 전", "FSH 6.2 mIU/mL").t("\n   과거력: ")
    heart(d, c, 64, 790)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Rt. breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a(2/13), IIB. 유전자 발현 검사 저위험으로 항암 생략\n")
    d.t("   보조 tamoxifen 복용 중 ")
    distant(d, c, 760, ["bone", "distant_ln"], "뼈·종격동 림프절 전이").t(" → ")
    d.put(f"tamoxifen {kdate(D(770))} 중단",
          F("recurrence.adjuvant_endocrine_end_date", D(770), raw=kdate(D(770)), within=kdate(D(770)))).t(" (PD)\n")
    d.t("   림프절 생검 NGS: PIK3CA 미검출\n\n")
    d.t("P) 전이성 1차 내분비 기반 치료 결정 (난소 기능 억제 포함)\n")
    surgery_path(c, 0, 41, op="우측 유방 부분절제술 + 액와 림프절 절제", grade=2, size_mm=27, ln=(2, 13),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", recur=True,
                 recs=[er(5, 3, "positive"), er(4, 3, "positive", "PR"), her2("1+")], ki67=18)
    image(c, 760, 43, "bone_scan", "Whole body bone scan", "T12, L3 척추체, 좌측 장골 열소 증가.", "다발성 골전이", ["bone"])
    image(c, 761, 43, "CT", "Chest CT (contrast)", "기관옆 림프절 2.1 cm, 폐 실질 이상 없음.", "종격동 림프절 전이 의증",
          ["distant_ln"], "suspected")
    meta_path(c, 765, 43, "종격동 림프절 (EBUS)", [er(5, 3, "positive"), er(3, 2, "positive", "PR"), her2("1+")])
    ngs(c, 785, 43, "metastasis", f"종격동 림프절 생검 조직 ({kdate(D(765))})", [], ["PIK3CA", "ESR1", "AKT1", "PTEN"])
    meds(c, 43, [
        dict(name="놀바덱스 (tamoxifen) 20mg qd", drugs=["tamoxifen"], setting="adjuvant", s=30, e=770, resp="PD",
             why="뼈·림프절 전이", stop="progression", prog=760),
    ])
    return c


def vc_0129() -> Chart:
    """N20 범위 외: 66세 남성 유방암, pT2N1a HR+/HER2-, 보조 결정."""
    c = Chart("VC-0129", "2025-04-07", 40)
    c.sex = "M"
    d = note(c, 66)
    d.t("S) 수술 후 회복 양호.\n   과거력: ")
    heart(d, c, 60, 35)
    d.t("O) ").put("ECOG PS 0", F("patient.ecog", 0, observed_date=c.index_date)).t("\n\n")
    d.t("A) Lt. male breast IDC, ")
    dx(d, c, "수술로 진단").t(", pT2N1a(1/3), IIB, HR+/HER2-\n   ")
    d.put("재발 소견 없음", F("recurrence.status", "none")).t("\n\n")
    d.t("P) 보조 요법 결정\n")
    surgery_path(c, 14, 66, op="좌측 유방 전절제술 + 감시림프절 생검", grade=2, size_mm=23, ln=(1, 3),
                 ptnm=("T2", "N1a"), group="IIB", extent="early", gender="MALE",
                 recs=[er(5, 3, "positive"), er(4, 3, "positive", "PR"), her2("1+")], ki67=15)
    return c


BUILDERS = {
    "VC-0110": ("N01", vc_0110), "VC-0111": ("N02", vc_0111), "VC-0112": ("N03", vc_0112),
    "VC-0113": ("N04", vc_0113), "VC-0114": ("N05", vc_0114), "VC-0115": ("N06", vc_0115),
    "VC-0116": ("N07", vc_0116), "VC-0117": ("N08", vc_0117), "VC-0118": ("N09", vc_0118),
    "VC-0119": ("N10", vc_0119), "VC-0120": ("N11", vc_0120), "VC-0121": ("N12", vc_0121),
    "VC-0122": ("N13", vc_0122), "VC-0123": ("N14", vc_0123), "VC-0124": ("N15", vc_0124),
    "VC-0125": ("N16", vc_0125), "VC-0126": ("N17", vc_0126), "VC-0127": ("N18", vc_0127),
    "VC-0128": ("N19", vc_0128), "VC-0129": ("N20", vc_0129),
}


# ---------- 문서 §3 → scenario.md, cases.csv ----------
def read_sections(md: str = None) -> dict[str, dict]:
    """§3의 '### Nxx 제목 (VC-01xx' 절마다 제목과 표(항목 → 내용)."""
    md = md if md is not None else CASES_MD.read_text(encoding="utf-8")
    part = md.split("## 3.", 1)[1].split("\n## 4.", 1)[0]
    out = {}
    for block in re.split(r"\n(?=### N\d\d )", part)[1:]:
        head, *lines = block.strip().splitlines()
        m = re.match(r"### (N\d\d) (.+?) \((VC-\d{4})", head)
        rows = {}
        for ln in lines:
            cells = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(cells) == 2 and cells[0] not in ("항목", "---"):
                rows[cells[0]] = cells[1]
        out[m.group(3)] = {"n": m.group(1), "title": m.group(2), "head": head, "rows": rows, "text": block.strip()}
    return out


def scenario(ref: str, sec: dict) -> str:
    return (f"# {ref} ({sec['n']}) {sec['title']}\n\n"
            f"> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 {sec['n']}. "
            f"차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. "
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
    secs = read_sections()
    missing = [r for r in BUILDERS if r not in secs]
    if missing:
        print(f"사례 목록 문서 §3에 없는 사례: {missing}")
        return 1
    bad = 0
    index = cases_csv(secs)
    if args.check:
        if (OUT / "cases.csv").read_text(encoding="utf-8") != index:
            print("cases.csv가 문서와 다름")
            bad += 1
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "cases.csv").write_text(index, encoding="utf-8", newline="\n")
    for ref in args.ids:
        chart, ps = BUILDERS[ref][1]().build()
        errs = check(chart, ps)
        sc = scenario(ref, secs[ref])
        out = OUT / ref
        files = {out / "chart.txt": chart, out / "expected" / "patient_state.json": dumps(ps), out / "scenario.md": sc}
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
