"""R 표기: fields → chart.txt + 정답 patient_state. mini의 Chart/F를 그대로 쓴다 (mini 파일은 고치지 않음).

표기는 rules/phrases.csv에 적은 기존 표기에서만 쓴다: mini 가상 차트 도우미(build_virtual_cases.py의 note·dx·
surgery_path·ngs), field_vocab.csv의 expression, mini TCGA 차트(data/tcga_brca/chart)의 구간 표기.
"""
from __future__ import annotations

from src.virtual_hospital.scripts.common import CREATED_AT, Patient, mini_on_path
from src.virtual_hospital.scripts.tcga import DAY_NGS, DAY_PATH, DAY_SURGERY, GENES

mini_on_path()
from src.input.script.virtual.virtual_chart import Chart, F, check, kdate  # noqa: E402

KO = {"positive": "양성", "negative": "음성", "low_positive": "약양성", "equivocal": "경계"}
ISH_EN = {"amplified": "amplified", "not_amplified": "not amplified", "equivocal": "equivocal"}
HISTOLOGY = {"IDC": "침윤성 유관암 (invasive ductal carcinoma, NST)",                     # VC surgery_path
             "ILC": "Infiltrating Lobular Carcinoma", "mucinous": "Mucinous Carcinoma",   # field_vocab tcga 표기
             "metaplastic": "Metaplastic Carcinoma", "invasive_NOS": "Infiltrating Carcinoma NOS"}
MENO = {"postmenopausal": "폐경 후", "premenopausal": "폐경 전",                            # field_vocab chart 표기
        "perimenopausal": "Peri (6-12 months since last menstrual period)"}               # field_vocab tcga 표기
OPERATION = "유방 절제술 + 액와 림프절 수술"
SIDE_EN = {"좌측": "Lt.", "우측": "Rt."}


SITE_KO = {"bone": "골", "liver": "간", "lung": "폐", "brain": "뇌", "skin": "피부", "distant_ln": "원격 림프절"}
SETTING_KO = {"neoadjuvant": "선행", "adjuvant": "보조", "palliative": "고식"}             # VC SETTING_KO
STOP_KO = {"progression": "진행", "completed": "완료", "planned_switch": "계획된 변경"}     # field_vocab stop_reason


def medication(c, age: int, rows: list[dict]) -> None:
    """투약 기록 표 (VC meds() 형식). 한 줄 = 요법 하나: 약   시작   종료   주기   반응   중단 사유."""
    D = c.on
    d = c.doc("medication", None)
    d.t("[투약 기록]\n").ident(age, full=False)
    d.t("구분    요법                                              시작         종료         주기       반응   중단 사유\n")
    for r in rows:
        cyc = r.get("cycles")
        cyc_txt = "-" if not cyc else (f"weekly #{cyc['value']}" if cyc.get("interval_days") == 7 else
                                       f"q{cyc['interval_days'] // 7}w #{cyc['value']}" if cyc.get("interval_days") in (14, 21, 28)
                                       else f"#{cyc['value']}")
        end = "현재 투약 중" if r.get("ongoing") else kdate(D(r["end_day"])) if r.get("end_day") is not None else "-"
        doses = r.get("doses") or {}             # R-07: 실제 안트라사이클린 1회 용량 (mini가 이 줄에서 누적량 계산)
        names = [f"{g} {doses[g]['value']:g}{doses[g]['unit']}" if g in doses else g for g in r["drugs"]]
        text = (f"{' + '.join(names)}   {kdate(D(r['start_day']))}   {end}   {cyc_txt}   "
                f"{r.get('best_response') or '-'}   {STOP_KO.get(r.get('stop_reason'), '-')}")
        kw = dict(drugs=r["drugs"], setting=r["setting"], start=D(r["start_day"]),
                  end=D(r["end_day"]) if r.get("end_day") is not None and not r.get("ongoing") else None,
                  cycles=cyc, stop_reason=r.get("stop_reason"), best_response=r.get("best_response"),
                  progression=D(r["progression_day"]) if r.get("progression_day") is not None else None,
                  anthra=[{"drug": g, "dose_per_admin": v, "cycles": cyc,
                           "total_dose": cyc and {"value": _num(v["value"] * cyc["value"]), "unit": v["unit"]}}
                          for g, v in doses.items()])
        if r.get("ongoing"):
            kw["ongoing"] = True
        d.t(f"{_get(SETTING_KO, r['setting'], '투약 구분')}    ").row(text, **kw).t("\n")


def _num(x: float):
    """mini pipeline._num와 같은 수 표기 (정수면 int)."""
    x = float(str(x))
    return int(x) if x.is_integer() else x


class RenderError(ValueError):
    """표기 목록에 없는 값 (G2 실패로 기록한다)."""


def _get(table: dict, key, what: str):
    if key not in table:
        raise RenderError(f"{what} 표기 없음: {key}")
    return table[key]


def pct_text(rg: list[int]) -> str:
    lo, hi = rg
    return "<1%" if lo == hi == 0 else f"{lo}%" if lo == hi else f"{lo}-{hi}%"


def receptor(d, path: str, label: str, rec, obs: str) -> None:
    if rec.status == "not_recorded":
        return
    if rec.status == "not_done":
        d.put(f"{label}: 시행하지 않음", F(path, status="not_done", raw="시행하지 않음")).t("\n  ")
        return
    v = rec.value
    if "allred" in v:                       # R-04: 'ER 강양성 (Allred 8, 5+3)' (사용자 지정 형식, 2026-11-10)
        a = v["allred"]
        text = f"{label} {allred_word(label, v['result'], a)} (Allred {a['total']}, {a['ps']}+{a['is']})"
    else:
        text = f"{label} : {_get(KO, v['result'], label)}"
        if "range" in v:
            text += f", 구간 {pct_text(v['range'])}"
    d.put(text, F(path, v, specimen="primary", observed_date=obs)).t("\n  ")


def allred_word(label: str, result: str, a: dict) -> str:
    """R-04 판정 낱말 (mini field_vocab.csv chart 표기): 강도 3점이면 강양성, ER 저발현은 약양성,
    PR은 총점 3~4점이면 약양성 (PR에는 저발현 범주가 없어 양성으로 읽힌다)."""
    if result == "negative":
        return "음성"
    if result == "low_positive":
        return "약양성"
    if a["is"] == 3:
        return "강양성"
    return "약양성" if label == "PR" and a["total"] <= 4 else "양성"


def her2(d, p: Patient, obs: str) -> None:
    ihc, ish = p.recs["receptors.her2_ihc"], p.recs["receptors.her2_ish"]
    if ihc.status == "not_done":
        d.put("HER2 IHC: 시행하지 않음", F("receptors.her2_ihc", status="not_done", raw="시행하지 않음")).t("\n  ")
    elif ihc.status == "present":
        v = ihc.value                                       # D-05: 점수만 (VC her2() 표기)
        d.put(f"HER2 (4B5): {_get(v, 'score', 'HER2 점수')}", F("receptors.her2_ihc", v, specimen="primary",
                                                               observed_date=obs)).t("\n  ")
    if ish.status == "not_done":
        d.put("HER2 ISH: 시행하지 않음", F("receptors.her2_ish", status="not_done", raw="시행하지 않음")).t("\n  ")
    elif ish.status == "present":
        v = ish.value
        text = f"HER2 {v.get('method') or 'ISH'}: {_get(ISH_EN, v['result'], 'ISH')}"
        d.put(text, F("receptors.her2_ish", v, specimen="primary", observed_date=obs)).t("\n  ")


def chart(p: Patient) -> tuple[str, dict, list[str]]:
    """(chart.txt, 정답 patient_state, mini check() 오류)."""
    R = p.recs
    age = R["patient.age"].value
    recur = p.branch == "TCGA_recur"
    c = Chart(p.vp_id, p.dx_date, p.index_day, created_at=CREATED_AT)
    ngs = min(DAY_NGS, p.index_day) if p.branch == "TCGA_postop" else DAY_NGS   # D-10: 분자병리 보고는 외래일보다 늦지 않게
    D = c.on

    # R-01 경과기록 (VC-0118 형식, 재발 갈래는 VC-0103 형식)
    d = c.doc("progress_note", c.index_date)
    d.t(f"<외래 경과기록>   {kdate(c.index_date)}   종양내과\n").ident(age)
    d.t("병원: 가상대학교병원 종양내과   담당의: 이가상\n\n")
    kind = {"endocrine": "내분비", "chemo": "항암"}.get(p.scene_kind, "")
    if recur:                                      # R-05: 장면 = 주 차수 종류와 차수 (D-R1)
        d.t(f"S) 고식 {p.scene_prev} 치료 후 외래.\n   폐경: " if p.scene_prev else "S) 재발 확인 후 외래.\n   폐경: ")
    else:
        d.t("S) 수술 후 외래, 회복 양호.\n   폐경: ")
    meno = R["patient.menopausal_status"].value
    d.put(_get(MENO, meno, "폐경"), F("patient.menopausal_status", meno)).t("\n")
    ecog = R["patient.ecog"].value
    d.t("O) ").put(f"ECOG PS {ecog}", F("patient.ecog", ecog, observed_date=c.index_date)).t("\n\n")
    d.t(f"A) {SIDE_EN[p.side]} breast cancer, ")
    d.put(f"{kdate(D(0))} core bx로 진단", F("diagnosis.diagnosis_date", D(0), raw=kdate(D(0))))
    d.t(f", {kdate(D(DAY_SURGERY))} 수술\n   ")
    if recur:                                      # R-05: VC distant() 형식 '2023.4.4 폐·골 전이'
        mday, sites = R["recurrence.metastasis_day"].value, R["recurrence.metastatic_sites"].value
        words = "·".join(_get(SITE_KO, s, "전이 부위") for s in sites) + " 전이"
        d.put(f"{kdate(D(mday))} {words}", F("recurrence.recurrence_date", D(mday), raw=kdate(D(mday))),
              F("recurrence.metastasis_day", mday), F("recurrence.recurrence_day", R["recurrence.recurrence_day"].value),
              F("recurrence.status", "distant", within=words), F("recurrence.metastatic_sites", sites, within=words))
        d.t("\n")
        ends = [t for t in p.treatments if t.get("adjuvant_endocrine") and t.get("end_day") is not None and not t.get("ongoing")]
        if ends:                                   # R-06: mini는 투약 표의 보조 내분비 종료일을 이 칸에 넣는다
            t = max(ends, key=lambda t: t["end_day"])
            d.t(f"   보조 {' + '.join(t['drugs'])} ").put(f"{kdate(D(t['end_day']))} 종료", F(
                "recurrence.adjuvant_endocrine_end_date", D(t["end_day"]), raw=kdate(D(t["end_day"])))).t("\n")
    else:
        d.put("재발 소견 없음", F("recurrence.status", "none")).t("\n")
    nd_genes = [g for g in GENES if R[f"molecular.mutations.{g}"].status == "not_done"]
    if nd_genes:                                   # N-04: 실제 미시행은 "시행하지 않음"으로 쓴다 (report_templates §1.5)
        d.t("   ").put(f"{', '.join(nd_genes)} 유전자 검사: 시행하지 않음",
                       *(F(f"molecular.mutations.{g}", status="not_done", raw="시행하지 않음") for g in nd_genes))
        d.t("\n")
    d.t(f"\nP) 고식 {kind} {p.scene_line}차 치료 결정\n" if recur else "\nP) 보조 전신 요법 결정\n")

    # R-02 수술 병리 (surgery_path 형식)
    obs = D(DAY_SURGERY)
    d = c.doc("pathology", D(DAY_PATH))
    d.t("[병리결과보고서]\n").ident(age, F("patient.gender", R["patient.gender"].value), F("patient.age", age),
                              full=False)
    d.t(f"접수일: {kdate(obs)}   보고일: {kdate(D(DAY_PATH))}\n검체: ")
    if R["stage.operable"].status == "present":
        d.put(f"{p.side} {OPERATION}", F("stage.operable", R["stage.operable"].value))
    else:
        d.t(f"{p.side} 유방 수술 검체")
    hist = R["diagnosis.histology"].value
    d.t("\n\n진단\n  조직형: ").put(_get(HISTOLOGY, hist, "조직형"), F("diagnosis.histology", hist))
    g = R["diagnosis.grade"].value
    d.t("\n  조직학적 등급: ").put(f"{'I' * g} (Nottingham grade {g})", F("diagnosis.grade", g))
    if p.grade_scores:                             # M-05: 실제 판독 세 점수 (mini에는 칸이 없어 글로만)
        a, b, m = p.grade_scores
        d.t(f"\n    관 형성 {a}, 핵 다형성 {b}, 유사분열 {m} (합 {a + b + m})")
    ln = R["stage.positive_ln_count"]
    if ln.status == "present":
        v = ln.value
        d.t("\n  림프절: ").put(f"전이 {v['positive']}개 / 검사 {v['examined']}개", F("stage.positive_ln_count", v))
    t = R["stage.ptnm"].value
    group, extent = R["stage.group"].value, R["stage.disease_extent"].value
    x = lambda v, k: f"{k}X" if v == "not_assessed" else v      # noqa: E731 — report_templates §1.5 (pNX, MX)
    tnm = f"p{x(t['t'], 'T')} {x(t['n'], 'N')} {x(t['m'], 'M')}"
    text = f"{tnm}, stage {group}" + (f" (AJCC {t['edition']})" if t.get("edition") else "")
    fs = [F("stage.ptnm", t, observed_date=obs), F("stage.group", group, within=f"stage {group}"),
          F("stage.disease_extent", extent, within=f"stage {group}")]
    if R["stage.metastatic_sites"].status == "present":
        fs.append(F("stage.metastatic_sites", R["stage.metastatic_sites"].value, within=tnm))
    d.t("\n  pTNM: ").put(text, *fs)
    d.t("\n\n면역조직화학\n  ")
    receptor(d, "receptors.er_percent", "ER", R["receptors.er_percent"], obs)
    receptor(d, "receptors.pr_percent", "PR", R["receptors.pr_percent"], obs)
    her2(d, p, obs)
    d.put(f"Ki-67: {R['proliferation.ki67_percent'].value['percent']}%",
          F("proliferation.ki67_percent", R["proliferation.ki67_percent"].value, specimen="primary",
            observed_date=obs))
    d.t("\n\n판독의: 박가상\n")

    # R-03 분자병리 (ngs 형식, 원발 조직 엑솜)
    genes = {gname: R[f"molecular.mutations.{gname}"] for gname in GENES}
    if any(r.status == "present" for r in genes.values()):
        d = c.doc("molecular", D(ngs))
        d.t("[분자병리 검사 결과]\n").ident(age, full=False)
        d.t(f"검사기관: 가상유전체검사센터   보고일: {kdate(D(ngs))}\n검체: 원발 종양 조직 (수술 검체)\n")
        d.t("검사법: 전장 엑솜 염기서열 분석\n\n검출된 변이 (Clinically significant variants)\n")
        found = [gname for gname, r in genes.items() if r.status == "present" and r.value["result"] == "detected"]
        for gname in found:
            vs = []
            for v in genes[gname].value["variants"]:               # VC ngs() 표기: GENE   c.… (p.…)   VAF n%
                vaf = f"   VAF {v['vaf'] * 100:g}%" if v.get("vaf") is not None else ""
                cdna = _get(p.cdna, (gname, v["protein_change"]), "변이 c.")
                vs.append({**v, "raw": f"{gname}   {cdna} (p.{v['protein_change']}){vaf}"})
            text = "; ".join(v["raw"] for v in vs)
            d.t("  ").put(text, F(f"molecular.mutations.{gname}", result="detected", specimen="primary",
                                  variants=vs)).t("\n")
        if not found:
            d.t("  없음\n")
        nd = [gname for gname, r in genes.items() if r.status == "present" and r.value["result"] == "not_detected"]
        if nd:
            d.t("\n검출되지 않음 (Not detected)\n  ")
            d.put(", ".join(nd), *(F(f"molecular.mutations.{gname}", result="not_detected", specimen="primary")
                                   for gname in nd))
        d.t(f"\n\n* 분석 유전자: {', '.join(GENES)}\n")
        d.genomic_report("primary", D(ngs))

    if p.treatments:                               # R-06 투약 기록 (VC meds() 형식)
        medication(c, age, p.treatments)

    text, ps = c.build()
    return text, ps, check(text, ps)
