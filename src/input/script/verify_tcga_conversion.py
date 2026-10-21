"""patient_state JSON 파일과 TCGA 크롭본 CSV 대조 (변환이 빠짐없이, 같은 값으로 됐는지).

변환기(tcga_to_patient_state.py)를 쓰지 않고, 크롭본 원본 칸과 tcga_mapping.md 규칙만으로 JSON 칸을 하나씩 확인한다.
값 대응은 data/dictionaries/field_vocab.csv(Vocab)만 쓴다. 원본에 없는 칸(날짜, Ki-67 등)은 비어 있는지만 본다.

usage (team_project 폴더에서):
    python -m src.input.script.tcga_to_patient_state --out data/patient_state/tcga   # 먼저 JSON 파일을 만든다
    python -m src.input.script.verify_tcga_conversion                                  # 대조 (기본 폴더 data/patient_state/tcga)
    python -m src.input.script.verify_tcga_conversion --dir <폴더> --report <txt>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from src.input.common.vocab import Vocab

ROOT = Path(__file__).resolve().parents[3]
CSV = ROOT / "data" / "tcga_brca" / "merged" / "tcga_brca_merging_cropped.csv"
JSON_DIR = ROOT / "data" / "patient_state" / "tcga"
CONVERTER = Path(__file__).with_name("tcga_to_patient_state.py")
VOCAB = Vocab()
NA = re.compile(r"^\[.*\]$")
ANTHRA = {"doxorubicin", "epirubicin", "liposomal doxorubicin"}
GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
ONCOTREE_TYPES = ("Other, specify", "Mixed Histology (please specify)", "Medullary Carcinoma")
ITEM = re.compile(r"^(?P<drug>.+?) \[(?P<cls>.*?)\] (?:d(?P<s>-?\d+)~(?:d(?P<e>-?\d+)|\?)|날짜 없음)(?: \((?P<r>.+)\))?$")
# 변환기가 쓰지 않는 열과 그 이유 (원본 그대로 크롭본에만 남는다)
NOT_CONVERTED = {
    "has_gdc_clinical": "자료 출처 표시", "has_cbio_clinical": "자료 출처 표시", "has_drug": "자료 출처 표시",
    "gdc_race": "처방 판단에 안 씀", "gdc_ethnicity": "처방 판단에 안 씀", "gdc_tissue_source_site": "수집 기관",
    "gdc_history_other_malignancy": "크롭 단계 삭제 규칙에만 씀", "gdc_radiation_treatment_adjuvant": "방사선은 범위 밖",
    "gdc_pharmaceutical_tx_adjuvant": "투약 기록(drug_*)으로 대신", "gdc_initial_pathologic_dx_year": "날짜 칸은 비움 (§2.3)",
    "gdc_lymph_nodes_examined_ihc_count": "가상 차트 문장에만 씀 (§3.2)", "gdc_er_ihc_score": "점수 열은 안 씀 (A 결정)",
    "gdc_pr_positivity_ihc_intensity_score": "점수 열은 안 씀", "gdc_her2_ihc_percent_positive": "점수·판정만 씀",
    "gdc_her2_copy_number": "FISH 판정만 씀", "gdc_cent17_copy_number": "FISH 판정만 씀", "gdc_her2_cent17_ratio": "FISH 판정만 씀",
    "gdc_new_tumor_event_dx_indicator": "재발 상태(recurrence_status)로 대신", "gdc_icd_10": "조직형으로 대신",
    "gdc_icd_o_3_histology": "조직형으로 대신", "gdc_icd_o_3_site": "유방으로 같음",
    "cbio_DFS_MONTHS": "생존 지표 (크롭 단계에서만)", "cbio_DFS_STATUS": "생존 지표", "cbio_DSS_MONTHS": "생존 지표",
    "cbio_DSS_STATUS": "생존 지표 (크롭 단계 삭제 규칙)", "cbio_NEW_TUMOR_EVENT_AFTER_INITIAL_TREATMENT": "재발 상태로 대신",
    "cbio_OS_MONTHS": "생존 지표", "cbio_OS_STATUS": "생존 지표", "cbio_RADIATION_THERAPY": "방사선은 범위 밖",
    "cbio_SUBTYPE": "PAM50 아형. 아형은 B가 수용체로 판정", "cbio_sample_sampleId": "검체 ID",
    "cbio_sample_CANCER_TYPE_DETAILED": "조직형으로 대신", "cbio_sample_MSI_SCORE_MANTIS": "아직 칸 없음",
    "cbio_sample_MSI_SENSOR_SCORE": "아직 칸 없음", "cbio_sample_TMB_NONSYNONYMOUS": "아직 칸 없음",
    "drug_n_records": "투약 항목 수 (drug_timeline으로 확인)", "drug_names": "drug_timeline으로 대신",
    "drug_therapy_types": "drug_timeline으로 대신", "drug_best_responses": "drug_timeline 괄호로 대신",
    "drug_first_start_days": "drug_start_days로 대신", "drug_names_raw": "정규화 전 이름 (대조용)",
    "drug_therapy_types_raw": "정규화 전 분류 (대조용)", "nte_n_records": "재발 기록 수", "nte_event_types": "재발 상태로 대신",
    "nte_dx_days": "metastasis_dx_days·locoregional_dx_days로 대신", "nte_first_dx_days": "같음", "nte_surgery_days": "날짜 칸 없음",
    "fu_n_records": "추적 기록 수", "fu_last_vital_status": "생존 상태 칸 없음", "fu_last_tumor_status": "칸 없음",
    "fu_death_days": "fu_last_days에 포함", "omf_n_records": "크롭 단계 삭제 규칙에만 씀", "omf_malignancy_types": "같음",
    "omf_sites": "같음", "mut_n_total": "전체 변이 수 (칸 없음)", "cna_profiled": "CNA 검사 여부",
    "current_disease_extent": "B가 진단 시 범주와 재발 상태로 다시 정함", "gdc_nte_er_status": "TCGA 정답은 원발 수용체만 (§3.7a)",
}


def val(x):
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return None
    s = str(x).strip()
    return None if s == "" or NA.match(s) else s


def num(x):
    v = val(x)
    try:
        return int(float(v)) if v is not None else None
    except ValueError:
        return None


def parts(r, col: str) -> list[str]:
    return str(r[col]).split(" | ") if val(r[col]) or isinstance(r[col], str) else []


def check(r, d: dict) -> dict[str, list[str]]:
    """환자 1명 → {검사 이름: [다른 점, ...]}. 비어 있으면 모두 맞음."""
    bad = defaultdict(list)
    f = d["fields"]

    def eq(name, got, want):
        if got != want:
            bad[name].append(f"JSON {json.dumps(got, ensure_ascii=False)} / CSV {json.dumps(want, ensure_ascii=False)}")

    eq("patient_ref", d["patient_ref"], r.patient_id)

    # 진단
    h = f["diagnosis"]["histology"]
    want = (VOCAB.lookup("diagnosis.histology.oncotree", r.cbio_sample_ONCOTREE_CODE)
            if r.gdc_histological_type in ONCOTREE_TYPES else VOCAB.lookup("diagnosis.histology", r.gdc_histological_type))
    eq("histology", h["value"], want)
    eq("histology.raw", h["raw"].split(": ")[0], r.gdc_histological_type)

    # 병기
    st = f["stage"]
    tnm = {k: val(r[c]) for k, c in (("t", "gdc_ajcc_tumor_pathologic_pt"), ("n", "gdc_ajcc_nodes_pathologic_pn"),
                                     ("m", "gdc_ajcc_metastasis_pathologic_pm"))}
    if all(tnm.values()):
        want = {k: ("not_assessed" if v.replace(" ", "") in ("TX", "NX", "MX") else v.replace(" ", "")) for k, v in tnm.items()}
        eq("ptnm", {k: st["ptnm"]["value"][k] for k in "tnm"}, want)
        eq("ptnm.edition", st["ptnm"]["value"]["edition"], val(r.gdc_ajcc_staging_edition))
    else:
        eq("ptnm", st["ptnm"], {"status": "not_recorded"})
    g = r.gdc_ajcc_pathologic_tumor_stage
    eq("stage.group", st["group"]["value"], "not_assessed" if g == "Stage X" else g.replace("Stage ", ""))
    eq("stage.disease_extent", st["disease_extent"]["value"], r.stage_disease_extent)
    pos, exa = num(r.gdc_lymph_nodes_examined_he_count), num(r.gdc_lymph_nodes_examined_count)
    ln = st["positive_ln_count"]
    if pos is None and exa is None:
        eq("positive_ln_count", ln, {"status": "not_recorded"})
    else:
        eq("positive_ln_count", ln["value"], {"positive": pos if pos is not None else "[Not Available]",
                                              "examined": exa if exa is not None else "[Not Available]"})
    ms = st["metastatic_sites"]
    if r.gdc_metastatic_tumor_indicator == "NO":
        eq("metastatic_sites (전이 여부 NO)", ms.get("value"), "[Not Applicable]")
    elif r.stage_disease_extent == "metastatic" and not val(r.gdc_metastasis_site) and not val(r.gdc_metastasis_site_other):
        eq("metastatic_sites (IV기 부위 없음)", ms, {"status": "not_done"})
    if val(r.gdc_metastasis_site) and ms.get("status") == "present":
        eq("metastatic_sites.raw", ms.get("raw"), r.gdc_metastasis_site)
    surg = val(r.gdc_surgical_procedure_first)
    eq("operable", st["operable"].get("value"), "yes" if surg else None)

    # 수용체
    rc = f["receptors"]
    for marker, scol, pcol in (("er", "gdc_er_status_by_ihc", "gdc_er_status_ihc_Percent_Positive"),
                               ("pr", "gdc_pr_status_by_ihc", "gdc_pr_status_ihc_percent_positive")):
        x, s, p = rc[f"{marker}_percent"], val(r[scol]), val(r[pcol])
        if s:
            eq(f"{marker}.result", x["value"].get("result"), VOCAB.lookup(f"receptors.{marker}_percent.result", s))
        m = re.fullmatch(r"(\d+)-(\d+)%", p or "")
        if m or p == "<1%":
            eq(f"{marker}.range", x["value"].get("range"), [0, 0] if p == "<1%" else [int(m[1]), int(m[2])])
        if not s and not (m or p == "<1%"):
            eq(f"{marker} (기록 없음)", x["status"], "not_done" if str(r[scol]).strip() == "[Not Evaluated]" else "not_recorded")
    score, fish = val(r.gdc_her2_ihc_score), val(r.gdc_her2_fish_status)
    if score:
        eq("her2_ihc.score", rc["her2_ihc"]["value"].get("score"), score)
    ihc_st = val(r.gdc_her2_status_by_ihc)
    if ihc_st and score != "2+" and ihc_st != "Equivocal":  # 2+·Equivocal은 FISH로 보정 (§3.3)
        eq("her2_ihc.result", rc["her2_ihc"]["value"].get("result"), VOCAB.lookup("receptors.her2_ihc.result", ihc_st))
    if fish:
        eq("her2_ish.result", rc["her2_ish"].get("value", {}).get("result"),
           VOCAB.lookup("receptors.her2_ish.result", fish, strict=False))
    else:
        eq("her2_ish (기록 없음)", rc["her2_ish"]["status"], "not_done" if str(r.gdc_her2_fish_status).strip() == "[Not Evaluated]" else "not_recorded")

    # 환자
    pt = f["patient"]
    eq("gender", pt["gender"]["value"], r.gdc_gender)
    eq("age", pt["age"]["value"], num(r.gdc_age_at_diagnosis))
    meno = val(r.gdc_menopause_status)
    eq("menopausal_status", pt["menopausal_status"].get("value"),
       VOCAB.lookup("patient.menopausal_status", meno) if meno else None)

    # 투약: 크롭본 drug_timeline 항목 = JSON 한 줄 (성분명 unknown 제외)
    items = parts(r, "drug_timeline") if isinstance(r.drug_timeline, str) else []
    starts, ends, cyc = (parts(r, c) for c in ("drug_start_days", "drug_end_days", "drug_cycles"))
    want = []
    for i, it in enumerate(items):
        m = ITEM.match(it.strip())
        if m is None:
            bad["drug_timeline 형식"].append(it)
            continue
        if m["drug"] == "unknown":
            continue
        resp = VOCAB.lookup("treatment_history.best_response", m["r"]) if m["r"] else "unknown"
        want.append((tuple(m["drug"].split("+")), num(starts[i]) if i < len(starts) else None,
                     num(ends[i]) if i < len(ends) else None, num(cyc[i]) if i < len(cyc) else None, resp))
    got = [(tuple(t["drugs"]), t["start_day"], t["end_day"],
            t["cycles"]["value"] if t["cycles"] and t["cycles"]["basis"] == "recorded" else None, t["best_response"])
           for t in f["treatment_history"]]
    key = lambda x: (x[1] is None, x[1] or 0, x[0], x[2] or 0)
    eq("treatment_history (약·시작·종료·기록 주기·반응)", sorted(got, key=key), sorted(want, key=key))

    # setting (§3.6): 전이 기준일 이후 → metastatic, 진단일 전 항암 → neoadjuvant, 선행요법 이력 + 첫 요법 → neoadjuvant
    met = num(r.metastasis_dx_days)
    for t in f["treatment_history"]:
        s = t["start_day"]
        if met is not None and s is not None and s >= met:
            eq("setting (전이 후)", t["setting"], "metastatic")
        elif t["setting"] == "metastatic":
            bad["setting (전이 후)"].append(f"{'+'.join(t['drugs'])} d{s}: 전이 기준일 {met} 전인데 metastatic")
        if t["setting"] == "neoadjuvant" and not (r.gdc_history_neoadjuvant_treatment == "Yes" or (s is not None and s < 0)):
            bad["setting (선행)"].append(f"{'+'.join(t['drugs'])} d{s}: 선행요법 이력도 진단 전 시작도 아님")

    # anthracycline 용량: 크롭본 값 그대로 (크롭 단계에서 mg/m2로 맞춘 값)
    dose_cols = ("drug_prescribed_dose", "drug_dose_units", "drug_total_dose", "drug_total_dose_units")
    cols = {c: parts(r, c) for c in dose_cols}
    for x in f["anthracycline_drug_dose"].get("drugs") or []:
        i, drugs = x["timeline_index"], items[x["timeline_index"]].split(" [")[0].split("+")
        k = drugs.index(x["drug"])
        for jkey, vcol, ucol in (("dose_per_admin", "drug_prescribed_dose", "drug_dose_units"),
                                 ("total_dose", "drug_total_dose", "drug_total_dose_units")):
            v = val(cols[vcol][i]) if i < len(cols[vcol]) else None
            vs = v.split("+") if v else []
            if len(vs) == len(drugs):
                wv = float(vs[k].split("-")[-1])
                eq(f"anthracycline.{jkey}", x[jkey], {"value": wv, "unit": val(cols[ucol][i]) or "unknown"})
            else:
                eq(f"anthracycline.{jkey}", x[jkey], "No value")

    # 재발
    rec = f["recurrence"]
    eq("recurrence.status", rec["status"]["value"], r.recurrence_status)
    eq("recurrence.metastasis_day", (rec.get("metastasis_day") or {}).get("value"), num(r.metastasis_dx_days))
    if r.recurrence_status in ("distant", "locoregional"):
        s = val(r.nte_surgery) or ""
        eq("recurrence.surgery", rec["surgery"]["value"], "yes" if "YES" in s else "no" if "NO" in s else "unknown")
        days = [x for x in (num(r.locoregional_dx_days), met if r.recurrence_status == "distant" else None) if x is not None]
        eq("recurrence.recurrence_day", (rec.get("recurrence_day") or {}).get("value"), min(days) if days and met != 0 else None)
    if r.recurrence_status == "distant":
        named = [VOCAB.lookup("metastatic_sites", x, strict=False) for x in (val(r.nte_sites) or "").split("; ")]
        sites = rec["metastatic_sites"]["value"]
        for x in named:
            if x and x not in sites:
                bad["recurrence.metastatic_sites"].append(f"{x} 빠짐 (CSV {r.nte_sites})")
        for o in (val(r.nte_sites_other) or "").split("; "):
            if o and not any(o == s.removeprefix("other: ") or s.removeprefix("other: ") in o or s in o.lower() for s in sites):
                bad["recurrence.metastatic_sites"].append(f"기타 '{o}' 빠짐")

    # 진행일 (§3.6): 진단 시 IV기 + PFS 진행일 때만 값이 있을 수 있다
    pfs = (round(float(r.cbio_PFS_MONTHS) * 30.4375)
           if r.stage_disease_extent == "metastatic" and str(r.cbio_PFS_STATUS).startswith("1:") else None)
    for t in f["treatment_history"]:
        if t["progression_day"] is not None:
            eq("progression_day", t["progression_day"], pfs)

    # 유전자 보고서 문장: ERBB2 변이·증폭과 CNA가 들어 있어야 한다
    text = " ".join(x["raw_text"] for x in f["genomic_reports"])
    for gname in ["ERBB2"] + GENES:
        if val(r[f"cna_{gname}"]) == "2" and f"{gname} amplification" not in text:
            bad["genomic_reports (CNA)"].append(f"{gname} amplification 빠짐")
        if val(r[f"cna_{gname}"]) == "-2" and f"{gname} deep deletion" not in text:
            bad["genomic_reports (CNA)"].append(f"{gname} deep deletion 빠짐")
    erbb2 = val(r.mut_ERBB2)
    if erbb2 and erbb2 != "변이 없음" and erbb2.split(" (")[0] not in text:
        bad["genomic_reports (ERBB2)"].append(f"{erbb2} 빠짐")

    # 기준일: 마지막 추적일, 그보다 늦은 투약이 있으면 마지막 투약일 (§2.3)
    last = num(r.fu_last_days)
    days = [x[2] if x[2] is not None else x[1] for x in want]
    eq("index_day", d["index_day"], None if last is None else max([last] + [x for x in days if x is not None]))

    # 유전자
    for gname in GENES:
        gv, x = val(r[f"mut_{gname}"]), f["molecular"]["mutations"][gname]
        if gv is None:
            eq(f"mutations.{gname}", x["status"], "not_done")
        else:
            eq(f"mutations.{gname}", x.get("result"), "not_detected" if gv == "변이 없음" else "detected")
            if gv != "변이 없음":
                eq(f"mutations.{gname}.variants", [v.get("protein_change", v.get("raw")) for v in x["variants"]],
                   [one.split(" (")[0] if re.match(r"^\S+ \(\w+, VAF", one) else one for one in gv.split("; ")])

    # TCGA에 없는 칸은 비어 있어야 한다
    for path, value in (("diagnosis.diagnosis_date", f["diagnosis"]["diagnosis_date"]), ("diagnosis.grade", f["diagnosis"]["grade"]),
                        ("proliferation.ki67_percent", f["proliferation"]["ki67_percent"]), ("receptors.pdl1", rc["pdl1"]),
                        ("patient.ecog", pt["ecog"]), ("neoadjuvant_response.pcr", f["neoadjuvant_response"]["pcr"])):
        eq(f"{path} (TCGA에 없음)", value, {"status": "not_recorded"})
    return bad


def coverage(df: pd.DataFrame, checked: set[str]) -> list[tuple[str, str]]:
    """크롭본 열마다 어디에 쓰였는지: 변환기 사용 / 변환 안 함(이유) / 확인 필요."""
    src = CONVERTER.read_text(encoding="utf-8")
    out = []
    for c in df.columns:
        stem = re.sub(r"_(ESR1|PIK3CA|AKT1|PTEN|BRCA1|BRCA2|PALB2|ERBB2)$", "_", c)
        used = c in src or (stem != c and stem.split("_")[0] + "_{" in src)
        if c.startswith(("gdc_nte_",)) and c not in NOT_CONVERTED:
            out.append((c, "변환 안 함: TCGA 정답은 원발 수용체만 (§3.7a)"))
        elif used:
            out.append((c, "변환기 사용" + (", 대조함" if c in checked else "")))
        elif c in NOT_CONVERTED:
            out.append((c, f"변환 안 함: {NOT_CONVERTED[c]}"))
        else:
            out.append((c, "확인 필요: 변환기도 안 쓰고 이유도 없음"))
    return out


CHECKED_COLS = {
    "patient_id", "gdc_histological_type", "cbio_sample_ONCOTREE_CODE", "gdc_ajcc_tumor_pathologic_pt", "gdc_ajcc_nodes_pathologic_pn",
    "gdc_ajcc_metastasis_pathologic_pm", "gdc_ajcc_staging_edition", "gdc_ajcc_pathologic_tumor_stage", "stage_disease_extent",
    "gdc_lymph_nodes_examined_he_count", "gdc_lymph_nodes_examined_count", "gdc_metastatic_tumor_indicator", "gdc_metastasis_site",
    "gdc_metastasis_site_other", "gdc_surgical_procedure_first", "gdc_er_status_by_ihc", "gdc_er_status_ihc_Percent_Positive",
    "gdc_pr_status_by_ihc", "gdc_pr_status_ihc_percent_positive", "gdc_her2_ihc_score", "gdc_her2_fish_status", "gdc_gender",
    "gdc_age_at_diagnosis", "gdc_menopause_status", "drug_timeline", "drug_start_days", "drug_end_days", "drug_cycles",
    "drug_prescribed_dose", "drug_dose_units", "drug_total_dose", "drug_total_dose_units", "recurrence_status",
    "metastasis_dx_days", "nte_surgery", "fu_last_days", "gdc_her2_status_by_ihc", "gdc_history_neoadjuvant_treatment",
    "nte_sites", "nte_sites_other", "locoregional_dx_days", "cbio_PFS_MONTHS", "cbio_PFS_STATUS", "mut_ERBB2",
} | {f"mut_{g}" for g in GENES} | {f"cna_{g}" for g in ["ERBB2"] + GENES}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=Path, default=JSON_DIR, help="patient_state JSON 폴더")
    ap.add_argument("--report", type=Path, help="결과를 저장할 txt")
    args = ap.parse_args(argv)

    df = pd.read_csv(CSV, dtype=str)
    files = {p.stem: p for p in args.dir.glob("*.json")}
    missing, extra = sorted(set(df.patient_id) - set(files)), sorted(set(files) - set(df.patient_id))
    by_check: dict[str, list[str]] = defaultdict(list)
    for _, r in df.iterrows():
        if r.patient_id not in files:
            continue
        d = json.loads(files[r.patient_id].read_text(encoding="utf-8"))
        for name, diffs in check(r, d).items():
            by_check[name] += [f"{r.patient_id}: {x}" for x in diffs]

    lines = [f"TCGA 크롭본 ↔ patient_state 대조 ({CSV.name} ↔ {args.dir})", "",
             f"크롭본 {len(df)}명, JSON {len(files)}개, JSON 없는 환자 {len(missing)}명, 크롭본에 없는 JSON {len(extra)}개"]
    lines += [f"  JSON 없음: {', '.join(missing[:20])}"] if missing else []
    lines += [f"  크롭본에 없음: {', '.join(extra[:20])}"] if extra else []
    lines += ["", f"[다른 점] {sum(len(v) for v in by_check.values())}건" + (" (모두 같음)" if not by_check else "")]
    for name, diffs in sorted(by_check.items()):
        lines.append(f"  {name}: {len(diffs)}건")
        lines += [f"    {x}" for x in diffs[:5]]
    cov = coverage(df, CHECKED_COLS)
    lines += ["", f"[크롭본 열 {len(cov)}개의 쓰임]"]
    for kind in ("변환기 사용", "변환 안 함", "확인 필요"):
        rows = [(c, w) for c, w in cov if w.startswith(kind)]
        lines.append(f"  {kind}: {len(rows)}개")
        lines += [f"    {c}: {w}" for c, w in rows]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    return 1 if by_check or missing or extra else 0


if __name__ == "__main__":
    sys.exit(main())
