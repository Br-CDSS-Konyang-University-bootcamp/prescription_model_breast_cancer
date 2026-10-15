"""TCGA-BRCA 크롭본 -> patient_state (환자 1명 = dict 1개).

규칙 명세: src/input/tcga_mapping.md, src/input/schema_fields.md. 이 코드는 그 문서를 옮긴 것이다.
src/input/truth/tcga_truth.py 에서 변환 부분만 옮겨 왔다 (2026-10-15). 스키마 검증·규칙별 건수 보고서는 넣지 않는다.

- 입력: data/tcga_brca/merged/tcga_brca_merging_cropped.csv (크롭본)
- 출력: 기본은 파일을 만들지 않는다. --out 폴더를 주면 <patient_id>.json 으로 저장한다
- 값 대응: data/dictionaries/field_vocab.csv. 사전에 없는 값이 나오면 멈춘다

usage (team_project 폴더에서):
    python -m src.input.script.tcga_to_patient_state                       # 변환만 하고 인원 수 출력
    python -m src.input.script.tcga_to_patient_state --ids TCGA-A2-A0EW --show   # 한 명 변환 결과를 화면에 출력
    python -m src.input.script.tcga_to_patient_state --out <폴더>          # 파일로 저장
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from src.input.common.vocab import Vocab

ROOT = Path(__file__).resolve().parents[3]
CSV = ROOT / "data" / "tcga_brca" / "merged" / "tcga_brca_merging_cropped.csv"
DRUG_CLASSES = ROOT / "data" / "dictionaries" / "drug_classes.csv"

SCHEMA_VERSION = "0.1-draft5"
# 생성 시각. 실행할 때마다 바뀌지 않게 고정한다 (같은 입력 → 같은 출력)
CREATED_AT = "2026-10-15T00:00:00+09:00"

NA = re.compile(r"^\[.*\]$")
# drug_timeline 항목: '성분명 [치료 종류] d시작~d종료 (최선 반응)' 또는 '… 날짜 없음 …'
ITEM = re.compile(r"^(?P<drug>.+?) \[(?P<cls>.*?)\] (?:d(?P<s>-?\d+)~(?:d(?P<e>-?\d+)|\?)|날짜 없음)(?: \((?P<r>.+)\))?$")
ANTHRA = {"doxorubicin", "epirubicin", "liposomal doxorubicin"}
GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
REPORT_GENES = ["ERBB2", "ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
ONCOTREE_TYPES = ("Other, specify", "Mixed Histology (please specify)", "Medullary Carcinoma")

VOCAB = Vocab()


def load_cycle_days(path: Path = DRUG_CLASSES) -> dict[str, int]:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"cycle_days": "Int64"}).dropna(subset=["cycle_days"])
    return {g: int(c) for g, c in df[["generic_name", "cycle_days"]].values}


CYCLE_DAYS = load_cycle_days()


# ---------- 공통 ----------
def val(x) -> str | None:
    """괄호 코드·빈칸이면 None, 아니면 앞뒤 공백을 지운 문자열."""
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return None
    s = str(x).strip()
    return None if s == "" or NA.match(s) else s


def missing(x) -> dict:
    """괄호 코드 → 상태값 (tcga_mapping.md §2.1). [Not Evaluated] = 미시행, 나머지 = 기록 없음."""
    return {"status": "not_done"} if str(x).strip() == "[Not Evaluated]" else {"status": "not_recorded"}


def present(value, raw=None, **extra) -> dict:
    d = {"status": "present", "value": value}
    if raw is not None:
        d["raw"] = raw
    d.update(extra)
    d["source"] = None  # 가상 차트 생성 단계에서 채운다
    return d


def day(x) -> int | None:
    return int(x) if x is not None and re.fullmatch(r"-?\d+", str(x).strip()) else None


def per_item(r, col: str, n: int) -> list:
    """drug_timeline 항목 순서로 ' | '로 이은 열을 나눈다."""
    v = r[col]
    return v.split(" | ") if isinstance(v, str) else [None] * n


# ---------- 진단 (§3.1) ----------
def diagnosis(r) -> dict:
    t = r.gdc_histological_type
    if t in ONCOTREE_TYPES:
        h = VOCAB.lookup("diagnosis.histology.oncotree", r.cbio_sample_ONCOTREE_CODE)
    else:
        h = VOCAB.lookup("diagnosis.histology", t)
    raw = t if not val(r.gdc_histologic_diagnosis_other) else f"{t}: {r.gdc_histologic_diagnosis_other}"
    return {"diagnosis_date": {"status": "not_recorded"}, "histology": present(h, raw), "grade": {"status": "not_recorded"}}


# ---------- 병기 (§3.2) ----------
def tnm_part(x) -> str | None:
    v = val(x)
    if v is None:
        return None
    v = v.replace(" ", "")
    return "not_assessed" if v in ("TX", "NX", "MX") else v


def sites_from(raw_sites: str, other: str | None) -> list[str]:
    """'Bone|Other, specify' → ['bone', 'other: <기타 부위>'] (§3.2 전이 부위 규칙 6)."""
    out = []
    for x in (s.strip() for s in raw_sites.split("|")):
        site = VOCAB.lookup("metastatic_sites", x, strict=False)
        if site:
            out.append(site)
        elif x == "Other, specify":
            out.append(f"other: {other}" if other else "other")
        else:
            out.append(f"other: {x}")
    return out


def stage(r) -> dict:
    cols = ["gdc_ajcc_tumor_pathologic_pt", "gdc_ajcc_nodes_pathologic_pn", "gdc_ajcc_metastasis_pathologic_pm"]
    t, n, m = (tnm_part(r[c]) for c in cols)
    s = {"ctnm": {"status": "not_recorded"}}
    s["ptnm"] = present({"t": t, "n": n, "m": m, "edition": val(r.gdc_ajcc_staging_edition)},
                        " ".join(str(r[c]) for c in cols)) if t and n and m else {"status": "not_recorded"}

    g = str(r.gdc_ajcc_pathologic_tumor_stage)
    s["group"] = present("not_assessed" if g == "Stage X" else g.replace("Stage ", ""), g)

    pos, exa = val(r.gdc_lymph_nodes_examined_he_count), val(r.gdc_lymph_nodes_examined_count)
    if pos is None and exa is None:
        s["positive_ln_count"] = {"status": "not_recorded"}
    else:
        s["positive_ln_count"] = present({"positive": int(pos) if pos else "[Not Available]",
                                          "examined": int(exa) if exa else "[Not Available]"}, f"{pos}/{exa}")

    s["disease_extent"] = present(r.stage_disease_extent, g)

    indicator = r.gdc_metastatic_tumor_indicator
    m0 = re.match(r"^c?M0", str(r.gdc_ajcc_metastasis_pathologic_pm).replace(" ", ""))
    if indicator == "NO":
        sites = "[Not Applicable]"
    elif m0 and indicator != "YES":
        sites = "[Not Applicable]"  # 진단 시 전이 없음 (M0) → 해당 없음 (사용자 결정, 2026-10-15)
    else:
        other = val(r.gdc_metastasis_site_other)
        raw_sites = val(r.gdc_metastasis_site) or other
        if raw_sites is None:
            sites = "[Not Available]"
        elif val(r.gdc_metastasis_site) is None:
            sites = [f"other: {x.strip()}" for x in other.split("|")]
        else:
            sites = sites_from(raw_sites, other)
    s["metastatic_sites"] = present(sites, str(r.gdc_metastasis_site))
    s["operable"] = {"status": "not_recorded"}
    return s


# ---------- 수용체 (§3.3, schema_fields.md §5) ----------
def bin_range(b: str | None) -> list[int] | None:
    if b == "<1%":
        return [0, 0]
    m = re.fullmatch(r"(\d+)-(\d+)%", b or "")
    return [int(m[1]), int(m[2])] if m else None


def hormone(r, marker: str, status_col: str, pct_col: str) -> dict:
    """ER·PR: 구간과 판정을 모두 넣는다. 점수 열은 쓰지 않는다 (A 결정)."""
    st, pct = r[status_col], r[pct_col]
    value = {}
    rng = bin_range(val(pct))
    if rng:
        value["range"] = rng
    if val(st):
        value["result"] = VOCAB.lookup(f"receptors.{marker}.result", st)
    if not value:
        return missing(st)
    return present(value, f"{st} ({pct})", specimen="primary", observed_date=None)


def her2(r) -> tuple[dict, dict]:
    """HER2 IHC는 점수와 판정을 함께 넣고, 2+ 또는 Equivocal이면 FISH로 판정을 보정한다 (A 결정)."""
    score, st, fish = val(r.gdc_her2_ihc_score), r.gdc_her2_status_by_ihc, r.gdc_her2_fish_status
    ihc = {}
    if score is None and st == "Equivocal":
        score = "2+"  # Equivocal의 정의가 IHC 2+
    if score:
        ihc["score"] = score
    result = VOCAB.lookup("receptors.her2_ihc.result", st) if val(st) else None
    if score == "2+" or st == "Equivocal":
        adjusted = {"Negative": "negative", "Positive": "positive"}.get(fish)
        result = adjusted or ("unknown" if st == "Equivocal" else result)
    if result:
        ihc["result"] = result
    her2_ihc = present(ihc, f"IHC {r.gdc_her2_ihc_score}, {st}", specimen="primary") if ihc else missing(st)

    ish = VOCAB.lookup("receptors.her2_ish.result", fish, strict=False) if val(fish) else None
    her2_ish = present({"result": ish, "method": "FISH"}, f"FISH {fish}", specimen="primary") if ish else missing(fish)
    return her2_ihc, her2_ish


def receptors(r) -> dict:
    rec = {"er_percent": hormone(r, "er_percent", "gdc_er_status_by_ihc", "gdc_er_status_ihc_Percent_Positive"),
           "pr_percent": hormone(r, "pr_percent", "gdc_pr_status_by_ihc", "gdc_pr_status_ihc_percent_positive")}
    rec["her2_ihc"], rec["her2_ish"] = her2(r)
    rec["pdl1"] = {"status": "not_recorded"}
    return rec


# ---------- 환자 (§3.5) ----------
def patient(r) -> dict:
    meno = val(r.gdc_menopause_status)
    return {"gender": present(r.gdc_gender, r.gdc_gender),
            "age": present(int(r.gdc_age_at_diagnosis), r.gdc_age_at_diagnosis, observed_date=None),
            "menopausal_status": present(VOCAB.lookup("patient.menopausal_status", meno), meno) if meno
            else missing(r.gdc_menopause_status),
            "menopausal_basis": {"status": "not_recorded"},
            "ecog": {"status": "not_recorded"}}


# ---------- 치료 이력 (§3.6) ----------
def cycles_of(drugs: list[str], recorded: str | None, dur: int | None) -> dict | None:
    """주기 수 규칙 (§3.6 표). 병용 기록은 사전 기본값 중 큰 값."""
    days = [CYCLE_DAYS[d] for d in drugs if d in CYCLE_DAYS]
    std = max(days) if days else None
    if recorded and recorded.isdigit():
        n = int(recorded)
        if dur is not None and n > 1 and dur > 0:
            return {"value": n, "basis": "recorded", "interval_days": max(1, round(dur / (n - 1))), "interval_basis": "derived"}
        return {"value": n, "basis": "recorded", "interval_days": std, "interval_basis": "standard" if std else None}
    if std and dur is not None:
        return {"value": round(dur / std) + 1, "basis": "estimated", "interval_days": std, "interval_basis": "standard"}
    return None


def treatment(r) -> tuple[list[dict], list[str]]:
    if not isinstance(r.drug_timeline, str):
        return [], []
    items = r.drug_timeline.split(" | ")
    cyc = per_item(r, "drug_cycles", len(items))
    starts, ends = per_item(r, "drug_start_days", len(items)), per_item(r, "drug_end_days", len(items))
    met = day(r.metastasis_dx_days)
    neo = r.gdc_history_neoadjuvant_treatment == "Yes"
    out = []
    for i, it in enumerate(items):
        m = ITEM.match(it.strip())
        if m is None:
            raise ValueError(f"{r.patient_id}: drug_timeline 항목 형식을 읽을 수 없음: '{it}'")
        if m["drug"] == "unknown":
            continue
        s, e = day(starts[i]), day(ends[i])
        dur = e - s if s is not None and e is not None else None
        # setting 유도 규칙 (유도값): 전이 기준일 이후 → metastatic, 선행요법 이력 + 첫 요법 → neoadjuvant, 나머지 → adjuvant
        if met is not None and s is not None and s >= met:
            setting, rule = "metastatic", "시작일 ≥ 전이 기준일"
        elif neo and not out:
            setting, rule = "neoadjuvant", "선행요법 이력 Yes + 첫 요법"
        else:
            setting, rule = "adjuvant", "나머지"
        drugs = m["drug"].split("+")
        cycles = cycles_of(drugs, val(cyc[i]), dur)
        out.append({"drugs": drugs, "setting": setting, "start_date": None, "end_date": None,
                    "start_day": s, "end_day": e, "duration_days": dur, "cycles": cycles, "progression_day": None,
                    "stop_reason": None,
                    "best_response": VOCAB.lookup("treatment_history.best_response", m["r"]) if m["r"] else "unknown",
                    "source": None})
    out.sort(key=lambda t: (t["start_day"] is None, t["start_day"] if t["start_day"] is not None else 0))
    return out, items


# ---------- anthracycline 용량 (§3.7a) ----------
def dose(v, u, pos: int, k: int):
    v, u = val(v), val(u)
    if v is None:
        return "No value"
    parts = v.split("+")
    if len(parts) != k:
        return "No value"
    part = parts[pos].strip()
    if re.fullmatch(r"[\d.]+-[\d.]+", part):  # 범위는 최대값
        part = part.split("-")[1]
    try:
        return {"value": float(part), "unit": u or "unknown"}
    except ValueError:
        return "No value"


def anthracycline(r, items: list[str]) -> dict:
    if not items:
        return {"administered": "No value", "drugs": []}
    n = len(items)
    cols = {c: per_item(r, c, n) for c in
            ["drug_prescribed_dose", "drug_dose_units", "drug_cycles", "drug_total_dose", "drug_total_dose_units"]}
    drugs = []
    for i, it in enumerate(items):
        combo = it.split(" [")[0].split("+")
        m = ITEM.match(it.strip())
        dur = int(m["e"]) - int(m["s"]) if m and m["s"] and m["e"] else None
        for pos, d in enumerate(combo):
            if d not in ANTHRA:
                continue
            c = cycles_of([d], val(cols["drug_cycles"][i]), dur)
            drugs.append({"drug": d, "timeline_index": i, "combined_with": [x for x in combo if x != d],
                          "dose_per_admin": dose(cols["drug_prescribed_dose"][i], cols["drug_dose_units"][i], pos, len(combo)),
                          "cycles": c if c and c["basis"] == "recorded" else "No value",
                          "total_dose": dose(cols["drug_total_dose"][i], cols["drug_total_dose_units"][i], pos, len(combo)),
                          "raw": it, "source": None})
    return {"administered": "positive" if drugs else "negative", "drugs": drugs}


# ---------- 재발 (§3.7) ----------
def recurrence(r) -> dict:
    st = r.recurrence_status
    rec = {"recurrence_date": {"status": "not_recorded"}, "adjuvant_endocrine_end_date": {"status": "not_recorded"},
           "status": present(st, val(r.nte_types))}
    if st == "distant":
        sites = []
        for s in str(r.nte_sites).split("; ") if val(r.nte_sites) else []:
            site = VOCAB.lookup("metastatic_sites", s, strict=False)
            if site:
                sites.append(site)
            elif s.startswith("Other"):
                sites += [f"other: {o}" for o in str(r.nte_sites_other).split("; ") if val(o)]
            else:
                raise ValueError(f"{r.patient_id}: field_vocab.csv에 없는 재발 부위 '{s}'")
        rec["metastatic_sites"] = present(list(dict.fromkeys(sites)) or "[Not Available]", val(r.nte_sites))
    if val(r.metastasis_dx_days) is not None:
        rec["metastasis_day"] = present(int(r.metastasis_dx_days))
    if st in ("distant", "locoregional", "site_unknown"):
        s = val(r.nte_surgery) or ""
        rec["surgery"] = present("yes" if "YES" in s else "no" if "NO" in s else "unknown", s or None)
        rec["surgery_intent"] = present("unknown")
    if st == "locoregional":
        rec["later_distant"] = present("no")
    elif st == "distant" and val(r.locoregional_dx_days) is not None:
        rec["later_distant"] = present("yes" if int(r.locoregional_dx_days) < int(r.metastasis_dx_days) else "no")
    return rec


# ---------- 유전자 (§3.8) ----------
def variants(v: str) -> list[dict]:
    out = []
    for one in v.split("; "):
        m = re.match(r"^(\S+) \((\w+), VAF ([\d.]+)\)$", one)
        out.append({"protein_change": m[1], "variant_type": m[2], "vaf": float(m[3]), "raw": one} if m else {"raw": one})
    return out


def gene(x) -> dict:
    v = val(x)
    if v is None:
        return {"status": "not_done"}
    if v == "변이 없음":
        return {"status": "present", "result": "not_detected", "variants": [], "specimen": "primary", "source": None}
    return {"status": "present", "result": "detected", "variants": variants(v), "specimen": "primary", "source": None}


def genomic_report(r) -> list[dict]:
    """가상 NGS 보고서 원문. 입력 모듈은 이 원문을 해석하지 않고 B에게 넘긴다 (IN-7)."""
    if r.mut_sequenced != "True":
        return []
    found, none = [], []
    for g in REPORT_GENES:
        v = val(r[f"mut_{g}"])
        if v is None:
            continue
        if v == "변이 없음":
            none.append(g)
        else:
            for x in variants(v):
                found.append(f"{g} p.{x['protein_change']} ({x['variant_type']}), VAF {x['vaf'] * 100:.1f}%"
                             if "vaf" in x else f"{g} {x['raw']}")
    cna = [f"{g} amplification" if val(r[f"cna_{g}"]) == "2" else f"{g} deep deletion"
           for g in REPORT_GENES if val(r[f"cna_{g}"]) in ("2", "-2")]
    text = "종양 조직 엑솜 검사 (원발 조직). " + ". ".join(found + cna)
    if none:
        text += (". " if found or cna else "") + ", ".join(none) + ": 검출되지 않음."
    return [{"doc_id": "D1", "report_date": None, "specimen": "primary", "raw_text": text.strip()}]


# ---------- 조립 ----------
def build(r) -> dict:
    th, items = treatment(r)
    reports = genomic_report(r)
    return {
        "schema_version": SCHEMA_VERSION,
        "patient_ref": r.patient_id,
        "created_at": CREATED_AT,
        "documents": [{"doc_id": "D1", "doc_type": "molecular", "doc_date": None}] if reports else [],
        "fields": {
            "diagnosis": diagnosis(r),
            "stage": stage(r),
            "receptors": receptors(r),
            "proliferation": {"ki67_percent": {"status": "not_recorded"}},
            "patient": patient(r),
            "treatment_history": th,
            "anthracycline_drug_dose": anthracycline(r, items),
            "neoadjuvant_response": {"pcr": {"status": "not_recorded"}, "rcb": {"status": "not_recorded"}},
            "recurrence": recurrence(r),
            "molecular": {"mutations": {g: gene(r[f"mut_{g}"]) for g in GENES}},
            "genomic_reports": reports,
        },
        "conflicts": [],
    }


def load_rows(csv: Path = CSV) -> pd.DataFrame:
    return pd.read_csv(csv, dtype=str)


def convert(df: pd.DataFrame) -> dict[str, dict]:
    """크롭본 행들 -> {patient_id: patient_state}."""
    return {r.patient_id: build(r) for _, r in df.iterrows()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", help="환자 ID (없으면 전체)")
    ap.add_argument("--out", type=Path, help="저장할 폴더. 주지 않으면 파일을 만들지 않는다")
    ap.add_argument("--show", action="store_true", help="변환 결과 JSON을 화면에 출력")
    args = ap.parse_args(argv)

    df = load_rows()
    if args.ids:
        unknown = set(args.ids) - set(df.patient_id)
        if unknown:
            raise SystemExit(f"크롭본에 없는 환자: {sorted(unknown)}")
        df = df[df.patient_id.isin(args.ids)]
    docs = convert(df)
    if args.show:
        for doc in docs.values():
            print(json.dumps(doc, ensure_ascii=False, indent=2))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for pid, doc in docs.items():
            (args.out / f"{pid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(docs):,}명 -> {args.out}")
    else:
        print(f"{len(docs):,}명 변환 (파일은 만들지 않음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
