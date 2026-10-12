"""TCGA-BRCA 임상·변이 데이터 구조 파악.

tcga_brca_download.py로 받은 파일을 읽어서
1. 파일별 행·열 수, 한 행의 단위, 환자 수
2. 열별 채움 비율, GDC 결측 코드([Not Available] 등) 개수, 고유값 수, 예시 값
3. 출처 간 환자 ID 겹침
4. v0.1 추출 스키마·바이오마커 판정에 쓸 핵심 필드 분포
를 정리한다.

터미널에는 요약을 출력하고, 열 단위 상세 표는 data/tcga_brca/structure_report.md에 저장한다.

실행: conda team_project 환경에서
    python data/script/tcga_brca_explore.py
"""
import re
from pathlib import Path

import pandas as pd

# 이 스크립트는 data/script/에 있다. DATA_ROOT = data/
DATA_ROOT = Path(__file__).resolve().parent.parent
DATA = DATA_ROOT / "tcga_brca"
GDC_DIR = DATA / "gdc_clinical"
CBIO_DIR = DATA / "cbioportal"
REPORT = DATA / "structure_report.md"

# GDC Biotab 결측 코드. "[Not Evaluated]"는 미시행, "[Not Available]"은 기록 없음에 가깝다
GDC_CODE = re.compile(r"^\[.*\]$")

BIOMARKER_GENES = ["ERBB2", "ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]


# ---------- 읽기 ----------

def read_gdc(path):
    """GDC Biotab: 1행 열 이름, 2행 대체 이름, 3행 CDE ID, 4행부터 데이터."""
    return pd.read_csv(path, sep="\t", header=0, skiprows=[1, 2], dtype=str,
                       keep_default_na=False, na_values=[""])


def read_cbio(path):
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, na_values=["", "NA"])


def load_all():
    tables = {}
    for p in sorted(GDC_DIR.glob("*.txt")):
        short = p.name.replace("nationwidechildrens.org_", "gdc_").replace("_brca.txt", "")
        tables[short] = read_gdc(p)
    for p in sorted(CBIO_DIR.glob("*.tsv")):
        tables["cbio_" + p.stem] = read_cbio(p)
    return tables


def patient_col(df):
    for c in ("bcr_patient_barcode", "patientId"):
        if c in df.columns:
            return c
    return None


# ---------- 요약 ----------

def column_profile(df):
    rows = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        codes = s.dropna().str.match(GDC_CODE)
        real = s.dropna()[~codes]
        top = real.value_counts().head(3)
        rows.append({
            "column": c,
            "filled_%": round(100 * len(real) / n, 1) if n else 0,
            "gdc_codes": ", ".join(f"{k}:{v}" for k, v in s[s.str.match(GDC_CODE, na=False)]
                                   .value_counts().items()),
            "n_unique": real.nunique(),
            "examples": " | ".join(f"{str(k)[:30]} ({v})" for k, v in top.items()),
        })
    return pd.DataFrame(rows)


def row_unit(name, df):
    pc = patient_col(df)
    if pc is None:
        return "속성 설명"
    if df[pc].nunique() == len(df):
        return "환자 1명 = 1행"
    if "sampleId" in df.columns and df["sampleId"].nunique() == len(df):
        return "샘플 1개 = 1행"
    return f"환자당 여러 행 (평균 {len(df) / df[pc].nunique():.1f})"


def find_cols(df, *keywords):
    return [c for c in df.columns if any(k in c.lower() for k in keywords)]


def value_counts_block(df, cols, top=8):
    lines = []
    for c in cols:
        vc = df[c].fillna("(빈칸)").value_counts().head(top)
        lines.append(f"  {c}")
        lines.extend(f"      {k}: {v}" for k, v in vc.items())
    return "\n".join(lines)


def main():
    if not DATA.exists():
        raise SystemExit("data/tcga_brca가 없습니다. 먼저 data/script/tcga_brca_download.py를 실행하세요.")
    t = load_all()
    md = ["# TCGA-BRCA 임상·변이 데이터 구조", ""]

    # 1) 파일 목록
    print("=" * 80, "\n1. 파일 목록\n" + "=" * 80)
    inv = []
    for name, df in t.items():
        pc = patient_col(df)
        inv.append({"table": name, "rows": len(df), "cols": df.shape[1],
                    "patients": df[pc].nunique() if pc else "-", "unit": row_unit(name, df)})
    inv = pd.DataFrame(inv)
    print(inv.to_string(index=False))
    md += ["## 1. 파일 목록", "", inv.to_markdown(index=False), ""]

    # 2) 출처 간 환자 겹침
    print("\n" + "=" * 80, "\n2. 출처 간 환자 ID 겹침\n" + "=" * 80)
    gdc_p = set(t["gdc_clinical_patient"]["bcr_patient_barcode"])
    cbio_p = set(t["cbio_clinical_patient"]["patientId"])
    mut_p = set(t["cbio_mutations"]["patientId"])
    drug_p = set(t["gdc_clinical_drug"]["bcr_patient_barcode"])
    overlap = [
        ("GDC 임상 환자", len(gdc_p)),
        ("cBioPortal 임상 환자", len(cbio_p)),
        ("둘 다 있음", len(gdc_p & cbio_p)),
        ("변이 1개 이상 있는 환자", len(mut_p)),
        ("GDC 임상 ∩ 변이", len(gdc_p & mut_p)),
        ("투약 기록 있는 환자", len(drug_p)),
        ("GDC 임상 ∩ 변이 ∩ 투약", len(gdc_p & mut_p & drug_p)),
    ]
    for k, v in overlap:
        print(f"  {k:<28}{v:>6,}")
    md += ["## 2. 출처 간 환자 ID 겹침", "", "| 구분 | 환자 수 |", "|---|---|"]
    md += [f"| {k} | {v:,} |" for k, v in overlap] + [""]

    # 3) v0.1 핵심 필드
    pat = t["gdc_clinical_patient"]
    sections = {
        "수용체 (ER/PR/HER2)": find_cols(pat, "er_status", "pr_status", "her2", "_level_cell_percent"),
        "병기 (AJCC)": find_cols(pat, "ajcc_"),
        "환자 (나이, 폐경)": find_cols(pat, "menopause", "age_at_diagnosis"),
        "조직형": find_cols(pat, "histological_type", "histologic_diagnosis"),
    }
    print("\n" + "=" * 80, "\n3. v0.1 핵심 필드 분포 (GDC clinical_patient)\n" + "=" * 80)
    md += ["## 3. v0.1 핵심 필드 분포", ""]
    for title, cols in sections.items():
        block = value_counts_block(pat, cols)
        print(f"\n[{title}]\n{block}")
        md += [f"### {title}", "", "```", block, "```", ""]

    drug = t["gdc_clinical_drug"]
    dcols = find_cols(drug, "drug_name", "therapy_type", "regimen_indication", "response")
    block = value_counts_block(drug, dcols, top=10)
    print(f"\n[치료 이력 (GDC clinical_drug)]\n{block}")
    md += ["### 치료 이력 (GDC clinical_drug)", "", "```", block, "```", ""]

    nte = t["gdc_clinical_nte"]
    ncols = find_cols(nte, "new_tumor_event_type", "new_neoplasm_event_type", "site")
    block = value_counts_block(nte, ncols)
    print(f"\n[재발·새 종양 (GDC clinical_nte)]\n{block}")
    md += ["### 재발·새 종양 (GDC clinical_nte)", "", "```", block, "```", ""]

    # 4) 변이·복제수
    mut = t["cbio_mutations"]
    print("\n" + "=" * 80, "\n4. 체세포 변이·복제수 (cBioPortal)\n" + "=" * 80)
    n_sample = mut["sampleId"].nunique()
    bm = mut[mut["gene"].isin(BIOMARKER_GENES)]
    gene_tbl = (bm.groupby("gene")["patientId"].nunique()
                .reindex(BIOMARKER_GENES, fill_value=0).rename("환자 수").to_frame())
    gene_tbl["비율_%"] = (100 * gene_tbl["환자 수"] / n_sample).round(1)
    print(f"  변이 행 {len(mut):,}개, 샘플 {n_sample:,}개, 유전자 {mut['gene'].nunique():,}개")
    print("\n  [mutationType]\n" + mut["mutationType"].value_counts().head(10).to_string())
    print("\n  [바이오마커 유전자별 변이 환자 수]\n" + gene_tbl.to_string())
    hot = (mut[mut["gene"] == "PIK3CA"]["proteinChange"].value_counts().head(5))
    print("\n  [PIK3CA 상위 변이]\n" + hot.to_string())

    cna = t["cbio_cna_biomarker_genes"]
    cna_lines = []
    for g in [c for c in BIOMARKER_GENES if c in cna.columns]:
        vc = cna[g].value_counts().reindex(["-2", "-1", "0", "1", "2"], fill_value=0)
        cna_lines.append(f"  {g:<7} " + "  ".join(f"{k:>2}:{v:>4}" for k, v in vc.items()))
    print("\n  [복제수 GISTIC: -2 깊은 결실, -1 얕은 결실, 0 정상, 1 증가, 2 증폭]\n" + "\n".join(cna_lines))

    md += ["## 4. 체세포 변이·복제수", "",
           f"변이 행 {len(mut):,}개, 샘플 {n_sample:,}개, 유전자 {mut['gene'].nunique():,}개", "",
           "### 바이오마커 유전자별 변이 환자 수", "", gene_tbl.to_markdown(), "",
           "### PIK3CA 상위 변이", "", hot.to_frame("count").to_markdown(), "",
           "### 복제수 (GISTIC)", "", "```", "\n".join(cna_lines), "```", ""]

    # 5) HER2: IHC 결과와 ERBB2 증폭 교차표 (BM-2 테스트에 쓸 수 있는지 확인)
    her2_cols = [c for c in ("her2_status_by_ihc", "her2_ihc_score") if c in pat.columns]
    if her2_cols:
        x = pat[["bcr_patient_barcode"] + her2_cols].merge(
            cna[["patientId", "ERBB2"]], left_on="bcr_patient_barcode", right_on="patientId", how="inner")
        ct = pd.crosstab(x[her2_cols[-1]].fillna("(빈칸)"), x["ERBB2"].fillna("(없음)"))
        print("\n" + "=" * 80, f"\n5. {her2_cols[-1]} × ERBB2 복제수\n" + "=" * 80)
        print(ct.to_string())
        md += [f"## 5. {her2_cols[-1]} × ERBB2 복제수", "", ct.to_markdown(), ""]

    # 6) 열 단위 상세 (리포트에만)
    md += ["## 6. 테이블별 열 상세", "",
           "filled_%는 GDC 결측 코드와 빈칸을 뺀 실제 값 비율이다.", ""]
    for name, df in t.items():
        md += [f"### {name} ({len(df):,}행 × {df.shape[1]}열)", "",
               column_profile(df).to_markdown(index=False), ""]

    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"\n열 단위 상세 표: {REPORT}")


if __name__ == "__main__":
    main()
