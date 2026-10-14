"""TCGA-BRCA 임상·변이 테이블을 환자 ID로 합쳐 환자 1명 = 1행 파일을 만든다.

입력: tcga_brca_download.py로 받은 data/tcga_brca/ 파일들
출력 (data/tcga_brca/merged/):
- tcga_brca_merged.csv          환자 1명 = 1행. Excel에서 바로 열 수 있게 UTF-8 BOM으로 저장
- tcga_brca_merged_columns.csv  열 설명표: 열 이름, 출처, 설명, 실제 값 비율, 예시 값
- drug_corrections.csv          약제명·치료 종류를 바로잡은 기록 (원본 → 수정값, 건수)

합치는 방법
- 환자 1명 = 1행 테이블 (GDC 환자 임상, cBioPortal 환자·샘플 임상, 복제수): 그대로 붙인다
- 환자당 여러 행 테이블 (투약, 방사선, 재발, 추적 관찰, 다른 암, 변이): 환자별로 요약해 붙인다
  원래의 행 단위 정보는 data/tcga_brca/ 원본 파일에 그대로 있다
- 열 이름 앞에 출처를 붙인다: gdc_, cbio_, drug_, rad_, nte_, fu_, omf_, mut_, cna_
- 투약 기록의 원본 오류(상품명·오타·잘못된 치료 종류)는 data/dictionaries/drug_names.csv,
  drug_classes.csv로 바로잡는다. 원본 값은 drug_*_raw 열에 남긴다
- GDC 결측 코드([Not Available], [Not Evaluated] 등)는 지우지 않고 그대로 둔다.
  "기록 없음"과 "미시행"을 구분하는 데 필요하다
- 빈칸은 해당 출처에 그 환자의 기록이 아예 없다는 뜻이다
- 날짜는 진단일 기준 일수(d77 = 진단 후 77일)다. 투약 타임라인은
  "약제 [치료 종류] d시작~d종료 (최선 반응)" 형식이고, 종료일이 없으면 "?"로 표시한다

실행: conda team_project 환경에서
    python data/script/tcga_brca_merge.py
"""
import re
from pathlib import Path

import pandas as pd

# 이 스크립트는 data/script/에 있다. DATA_ROOT = data/
DATA_ROOT = Path(__file__).resolve().parent.parent
DATA = DATA_ROOT / "tcga_brca"
GDC_DIR = DATA / "gdc_clinical"
CBIO_DIR = DATA / "cbioportal"
OUT_DIR = DATA / "merged"
DICT_DIR = DATA_ROOT / "dictionaries"

BIOMARKER_GENES = ["ERBB2", "ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
GDC_CODE = re.compile(r"^\[.*\]$")
SEP = "; "

# 열 설명표에 쓸 출처 설명
SOURCES = {
    "gdc_": "GDC clinical_patient (환자 1명 = 1행, 원본 그대로)",
    "cbio_sample_": "cBioPortal clinical_sample (원본 그대로)",
    "cbio_": "cBioPortal clinical_patient (원본 그대로)",
    "drug_": "GDC clinical_drug 환자별 요약. 약제명은 성분명, 치료 종류는 data/dictionaries/ 사전으로 바로잡은 값 (_raw 열은 원본)",
    "rad_": "GDC clinical_radiation 환자별 요약",
    "nte_": "GDC clinical_nte + follow_up_v4.0_nte + follow_up_v2.1(재발 기록 행) 환자별 요약",
    "fu_": "GDC follow_up v1.5·v2.1·v4.0 환자별 요약",
    "omf_": "GDC clinical_omf_v4.0 (다른 암 병력) 환자별 요약",
    "mut_": "cBioPortal mutations 환자별 요약",
    "cna_": "cBioPortal GISTIC 복제수 (-2 깊은 결실, -1 얕은 결실, 0 정상, 1 증가, 2 증폭)",
}


# ---------- 읽기 ----------

def read_gdc(name):
    path = GDC_DIR / f"nationwidechildrens.org_{name}_brca.txt"
    return pd.read_csv(path, sep="\t", header=0, skiprows=[1, 2], dtype=str,
                       keep_default_na=False, na_values=[""])


def read_cbio(name):
    return pd.read_csv(CBIO_DIR / f"{name}.tsv", sep="\t", dtype=str,
                       keep_default_na=False, na_values=["", "NA"])


# ---------- 요약 도우미 ----------

def real(s):
    """GDC 결측 코드와 빈칸을 뺀 실제 값만."""
    s = s.dropna()
    return s[~s.str.match(GDC_CODE)]


def uniq(s):
    """순서를 지키며 중복 없이 이어 붙인다."""
    vals = list(dict.fromkeys(real(s)))
    return SEP.join(vals) if vals else pd.NA


def to_num(s):
    return pd.to_numeric(s, errors="coerce")


def prefixed(df, prefix, key="patient_id"):
    return df.rename(columns={c: prefix + c for c in df.columns if c != key})


# ---------- 테이블별 처리 ----------

def gdc_patient():
    # 원본에 patient_id(바코드 끝 4자리) 열이 따로 있어서, 접두어를 먼저 붙인 뒤 키 이름을 바꾼다
    df = read_gdc("clinical_patient")
    df = df.rename(columns={c: "gdc_" + c for c in df.columns})
    return df.rename(columns={"gdc_bcr_patient_barcode": "patient_id"})


def cbio_patient():
    df = read_cbio("clinical_patient").rename(columns={"patientId": "patient_id"})
    return prefixed(df, "cbio_")


def cbio_sample():
    df = read_cbio("clinical_sample").rename(columns={"patientId": "patient_id"})
    # 이 연구는 환자당 샘플 1개 (원발 종양 01)
    assert df["patient_id"].is_unique, "환자당 샘플이 2개 이상입니다. 요약 방식을 정해야 합니다."
    return prefixed(df, "cbio_sample_")


def load_drug_dictionary():
    """약제 사전: 원본 표기 -> 성분명(+로 이어진 복합 요법 가능), 성분명 -> 치료 종류."""
    names = pd.read_csv(DICT_DIR / "drug_names.csv", dtype=str, keep_default_na=False)
    classes = pd.read_csv(DICT_DIR / "drug_classes.csv", dtype=str, keep_default_na=False)
    return (dict(zip(names["raw_name"], names["generic_names"])),
            dict(zip(classes["generic_name"], classes["drug_class"])))


def normalize_drugs(d):
    """원본 약제명·치료 종류를 사전으로 바로잡는다. 원본 값은 *_raw 열로 남긴다."""
    to_generic, to_class = load_drug_dictionary()
    key = d["pharmaceutical_therapy_drug_name"].fillna("").str.strip().str.lower()
    missing = sorted(set(key) - set(to_generic) - {""})
    if missing:
        raise SystemExit(f"약제 사전에 없는 이름이 있습니다. data/dictionaries/drug_names.csv에 추가하세요: {missing}")

    d["drug_generic"] = key.map(to_generic).fillna("unknown")

    def fix_type(row):
        classes = list(dict.fromkeys(to_class[g] for g in row["drug_generic"].split("+")))
        if classes == ["Unknown"]:
            return row["pharmaceutical_therapy_type"]  # 약을 알 수 없으면 원본 분류를 둔다
        return "|".join(c for c in classes if c != "Unknown")  # 원본과 같은 구분 기호

    d["drug_class"] = d.apply(fix_type, axis=1)
    return d


# 투약 기록의 용량·주기 열 → 병합본 열 이름 (anthracycline 누적 용량 계산용, 2026-10-14 추가)
DOSE_COLS = {
    "total_dose": "drug_total_dose",
    "pharmaceutical_tx_total_dose_units": "drug_total_dose_units",
    "prescribed_dose": "drug_prescribed_dose",
    "pharmaceutical_tx_dose_units": "drug_dose_units",
    "pharma_adjuvant_cycles_count": "drug_cycles",
}


def drug_summary():
    """투약 기록: 약제명·치료 종류를 바로잡고, 시작일 순으로 정렬해 요약과 타임라인을 만든다."""
    d = read_gdc("clinical_drug").rename(columns={"bcr_patient_barcode": "patient_id"})
    d = normalize_drugs(d)
    d["_start"] = to_num(d["pharmaceutical_tx_started_days_to"])
    d = d.sort_values(["patient_id", "_start"], na_position="last")

    # 무엇을 고쳤는지 기록한다 (원본 표기 × 원본 분류 → 성분명 × 바로잡은 분류)
    log = (d.groupby(["pharmaceutical_therapy_drug_name", "pharmaceutical_therapy_type",
                      "drug_generic", "drug_class"], dropna=False).size().reset_index(name="n_records"))
    log.columns = ["raw_name", "raw_type", "generic_names", "corrected_type", "n_records"]
    log["name_changed"] = log["raw_name"].str.strip().str.lower() != log["generic_names"]
    log["type_changed"] = log["raw_type"] != log["corrected_type"]
    log.sort_values(["type_changed", "n_records"], ascending=False).to_csv(
        OUT_DIR / "drug_corrections.csv", index=False, encoding="utf-8-sig")

    def line(r):
        start = r["pharmaceutical_tx_started_days_to"]
        end = r["pharmaceutical_tx_ended_days_to"]
        resp = r["treatment_best_response"]
        start = None if GDC_CODE.match(str(start)) or pd.isna(start) else f"d{start}"
        end = "?" if GDC_CODE.match(str(end)) or pd.isna(end) else f"d{end}"
        span = f"{start}~{end}" if start else "날짜 없음"
        out = f"{r['drug_generic']} [{r['drug_class']}] {span}"
        return out + (f" ({resp})" if pd.notna(resp) and not GDC_CODE.match(str(resp)) else "")

    d["_line"] = d.apply(line, axis=1)
    # 용량·주기: drug_timeline과 같은 순서로 " | "로 잇는다. 값이 없으면 "-" (GDC 결측 코드는 그대로)
    for col in DOSE_COLS:
        d[col] = d[col].fillna("-").astype(str).str.strip()
    g = d.groupby("patient_id")
    split_uniq = lambda s, sep: uniq(s.str.split(sep, regex=False).explode())
    return pd.DataFrame({
        "drug_n_records": g.size(),
        "drug_names": g["drug_generic"].agg(split_uniq, "+"),
        "drug_therapy_types": g["drug_class"].agg(split_uniq, "|"),
        "drug_best_responses": g["treatment_best_response"].agg(uniq),
        "drug_first_start_days": g["_start"].min(),
        "drug_timeline": g["_line"].agg(" | ".join),
        **{name: g[col].agg(" | ".join) for col, name in DOSE_COLS.items()},
        "drug_names_raw": g["pharmaceutical_therapy_drug_name"].agg(uniq),
        "drug_therapy_types_raw": g["pharmaceutical_therapy_type"].agg(uniq),
    }).reset_index()


def radiation_summary():
    r = read_gdc("clinical_radiation").rename(columns={"bcr_patient_barcode": "patient_id"})
    g = r.groupby("patient_id")
    return pd.DataFrame({
        "rad_n_records": g.size(),
        "rad_types": g["radiation_therapy_type"].agg(uniq),
        "rad_sites": g["radiation_therapy_site"].agg(uniq),
        "rad_first_start_days": g["radiation_therapy_started_days_to"].agg(lambda s: to_num(s).min()),
    }).reset_index()


def nte_summary():
    """재발·새 종양: 두 사건 테이블과 follow_up_v2.1의 재발 기록 행을 합친다.

    follow_up_v2.1은 추적 관찰 1회 = 1행이고, 재발이 있었던 행(new_tumor_event_dx_indicator = YES)에만
    사건 종류·부위가 적혀 있다. 이 파일을 빼면 46명의 재발 종류가 비게 된다 (2026-10-13 확인).
    """
    cols = ["bcr_patient_barcode", "new_tumor_event_type", "new_tumor_event_site",
            "new_tumor_event_site_other", "new_tumor_event_dx_days_to"]
    fu21 = read_gdc("clinical_follow_up_v2.1")
    fu21 = fu21.loc[fu21["new_tumor_event_dx_indicator"] == "YES", cols]
    n = pd.concat([read_gdc("clinical_nte")[cols],
                   read_gdc("clinical_follow_up_v4.0_nte")[cols], fu21], ignore_index=True)
    n = n.rename(columns={"bcr_patient_barcode": "patient_id"})
    g = n.groupby("patient_id")
    return pd.DataFrame({
        "nte_n_records": g.size(),
        "nte_types": g["new_tumor_event_type"].agg(uniq),
        "nte_sites": g["new_tumor_event_site"].agg(uniq),
        "nte_sites_other": g["new_tumor_event_site_other"].agg(uniq),
        "nte_first_dx_days": g["new_tumor_event_dx_days_to"].agg(lambda s: to_num(s).min()),
    }).reset_index().merge(nte_surgery_summary(), on="patient_id", how="outer")


def nte_surgery_summary():
    """재발 후 수술 여부(new_tumor_event_surgery)와 수술일. follow_up_v1.5에도 수술 여부가 있어 함께 읽는다 (2026-10-14 추가)."""
    cols = ["bcr_patient_barcode", "new_tumor_event_surgery", "new_tumor_event_surgery_days_to"]
    frames = []
    for name in ("clinical_nte", "clinical_follow_up_v4.0_nte", "clinical_follow_up_v2.1", "clinical_follow_up_v1.5"):
        f = read_gdc(name)
        frames.append(f.reindex(columns=cols))
    s = pd.concat(frames, ignore_index=True).rename(columns={"bcr_patient_barcode": "patient_id"})
    g = s.groupby("patient_id")
    out = pd.DataFrame({
        "nte_surgery": g["new_tumor_event_surgery"].agg(uniq),
        "nte_surgery_days": g["new_tumor_event_surgery_days_to"].agg(lambda x: to_num(x).min()),
    }).reset_index()
    return out.dropna(subset=["nte_surgery", "nte_surgery_days"], how="all")


def followup_summary():
    """추적 관찰 3개 버전을 합쳐 마지막 상태를 뽑는다."""
    cols = ["bcr_patient_barcode", "vital_status", "tumor_status",
            "last_contact_days_to", "death_days_to"]
    f = pd.concat([read_gdc(f"clinical_follow_up_{v}")[cols] for v in ("v1.5", "v2.1", "v4.0")],
                  ignore_index=True).rename(columns={"bcr_patient_barcode": "patient_id"})
    f["_t"] = pd.concat([to_num(f["last_contact_days_to"]), to_num(f["death_days_to"])], axis=1).max(axis=1)
    last = f.sort_values("_t").groupby("patient_id").tail(1).set_index("patient_id")
    g = f.groupby("patient_id")
    return pd.DataFrame({
        "fu_n_records": g.size(),
        "fu_last_days": g["_t"].max(),
        "fu_last_vital_status": last["vital_status"],
        "fu_last_tumor_status": last["tumor_status"],
        "fu_death_days": g["death_days_to"].agg(lambda s: to_num(s).min()),
    }).reset_index()


def omf_summary():
    o = read_gdc("clinical_omf_v4.0").rename(columns={"bcr_patient_barcode": "patient_id"})
    g = o.groupby("patient_id")
    return pd.DataFrame({
        "omf_n_records": g.size(),
        "omf_malignancy_types": g["malignancy_type"].agg(uniq),
        "omf_sites": g["other_malignancy_anatomic_site"].agg(uniq),
    }).reset_index()


def mutation_summary():
    """변이: 검사 여부, 전체 변이 수, 바이오마커 유전자별 단백질 변화(VAF)."""
    prof = read_cbio("profiled_samples").rename(columns={"patientId": "patient_id"})
    prof = prof.groupby("patient_id").agg(
        mut_sequenced=("sequenced", lambda s: (s == "True").any()),
        cna_profiled=("cna", lambda s: (s == "True").any()),
    ).reset_index()

    m = read_cbio("mutations").rename(columns={"patientId": "patient_id"})
    out = m.groupby("patient_id").size().rename("mut_n_total").reset_index()

    bm = m[m["gene"].isin(BIOMARKER_GENES)].copy()
    bm["_txt"] = bm["proteinChange"] + " (" + bm["mutationType"] + ", VAF " + bm["vaf"].fillna("?") + ")"
    per_gene = bm.groupby(["patient_id", "gene"])["_txt"].agg(SEP.join).unstack()
    per_gene = per_gene.reindex(columns=BIOMARKER_GENES)
    per_gene.columns = [f"mut_{g}" for g in per_gene.columns]
    out = prof.merge(out, on="patient_id", how="outer").merge(
        per_gene.reset_index(), on="patient_id", how="left")

    # 검사를 받았는데 변이가 없으면 0 / "변이 없음", 검사를 안 받았으면 빈칸으로 둔다
    seq = out["mut_sequenced"].fillna(False).astype(bool)
    out.loc[seq & out["mut_n_total"].isna(), "mut_n_total"] = 0
    for g in BIOMARKER_GENES:
        out.loc[seq & out[f"mut_{g}"].isna(), f"mut_{g}"] = "변이 없음"
    return out


def cna_table():
    c = read_cbio("cna_biomarker_genes").rename(columns={"patientId": "patient_id"})
    c = c.drop(columns=["sampleId"])
    return c.rename(columns={g: f"cna_{g}" for g in BIOMARKER_GENES if g in c.columns})


# ---------- 열 설명표 ----------

def describe_columns(df):
    gdc_desc = {}
    # GDC 머리글 세 줄: 열 이름, 대체 이름, CDE ID (caDSR 데이터 사전 번호)
    head = pd.read_csv(GDC_DIR / "nationwidechildrens.org_clinical_patient_brca.txt",
                       sep="\t", nrows=3, header=None, dtype=str)
    for name, alt_name, cde in zip(head.iloc[0], head.iloc[1], head.iloc[2]):
        notes = []
        if name != alt_name:
            notes.append(f"다른 이름: {alt_name}")
        if isinstance(cde, str) and cde.strip() != "CDE_ID:":
            notes.append(cde)
        gdc_desc[name] = ", ".join(notes)
    attrs = read_cbio("clinical_attributes").set_index("clinicalAttributeId")

    rows = []
    for c in df.columns:
        src = next((v for k, v in SOURCES.items() if c.startswith(k)), "키")
        if c.startswith("has_"):
            src = "출처별 기록 유무 (True면 해당 출처에 이 환자 기록이 있음)"
        if c == "cna_profiled":
            src = "cBioPortal sample list (복제수 검사 여부)"
        desc = ""
        if c.startswith("gdc_"):
            desc = gdc_desc.get(c[4:], "")
        elif c.startswith("cbio_"):
            raw = c.replace("cbio_sample_", "").replace("cbio_", "")
            if raw in attrs.index:
                desc = f"{attrs.at[raw, 'displayName']}: {attrs.at[raw, 'description']}"
        s = df[c].astype("string")
        filled = real(s.dropna())
        rows.append({
            "column": c, "source": src, "description": desc,
            "filled_%": round(100 * len(filled) / len(df), 1),
            "n_unique": filled.nunique(),
            "examples": SEP.join(str(v)[:40] for v in filled.value_counts().head(3).index),
        })
    return pd.DataFrame(rows)


def main():
    if not (CBIO_DIR / "profiled_samples.tsv").exists():
        raise SystemExit("profiled_samples.tsv가 없습니다. 먼저 data/script/tcga_brca_download.py를 다시 실행하세요.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    parts = [
        ("GDC 환자 임상", gdc_patient()),
        ("cBioPortal 환자 임상", cbio_patient()),
        ("cBioPortal 샘플 임상", cbio_sample()),
        ("투약 요약", drug_summary()),
        ("방사선 요약", radiation_summary()),
        ("재발·새 종양 요약", nte_summary()),
        ("추적 관찰 요약", followup_summary()),
        ("다른 암 병력 요약", omf_summary()),
        ("변이 요약", mutation_summary()),
        ("복제수", cna_table()),
    ]

    # 모든 출처의 환자 ID 합집합을 기준으로 붙인다
    ids = sorted(set().union(*(set(p["patient_id"]) for _, p in parts)))
    merged = pd.DataFrame({"patient_id": ids})
    print(f"{'테이블':<20}{'환자 수':>8}{'추가 열':>8}")
    for name, p in parts:
        assert p["patient_id"].is_unique, f"{name}: 환자 ID가 중복됩니다"
        merged = merged.merge(p, on="patient_id", how="left")
        print(f"{name:<20}{len(p):>8,}{p.shape[1] - 1:>8}")

    # 어느 출처에 기록이 있는지 표시 (앞쪽에 둔다)
    flags = {
        "has_gdc_clinical": "gdc_bcr_patient_uuid",
        "has_cbio_clinical": "cbio_SUBTYPE",
        "has_drug": "drug_n_records",
        "has_mutation_data": "mut_sequenced",
    }
    for i, (flag, col) in enumerate(flags.items(), start=1):
        if flag == "has_mutation_data":
            merged.insert(i, flag, merged[col].fillna(False).astype(bool))
        elif flag == "has_cbio_clinical":
            merged.insert(i, flag, merged["patient_id"].isin(set(parts[1][1]["patient_id"])))
        else:
            merged.insert(i, flag, merged[col].notna())

    # 개수·일수 열은 정수로 저장 (빈칸은 빈칸 그대로)
    for c in merged.columns:
        if c.endswith(("_n_records", "_n_total", "_days")):
            merged[c] = pd.to_numeric(merged[c], errors="coerce").round().astype("Int64")

    csv_path = OUT_DIR / "tcga_brca_merged.csv"
    cols_path = OUT_DIR / "tcga_brca_merged_columns.csv"
    merged.to_csv(csv_path, index=False, encoding="utf-8-sig")
    describe_columns(merged).to_csv(cols_path, index=False, encoding="utf-8-sig")

    print(f"\n합친 결과: 환자 {len(merged):,}명 × {merged.shape[1]}열")
    print(f"  {csv_path}")
    print(f"  {cols_path}")


if __name__ == "__main__":
    main()
