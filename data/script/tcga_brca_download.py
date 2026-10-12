"""TCGA-BRCA 임상·변이 데이터 다운로드 (v0.1용, 슬라이드 제외).

받는 것
1. GDC BCR Biotab 임상 파일: 환자 임상(ER/PR/HER2 IHC 세부값, 폐경, 병기), 투약, 방사선, 추적 관찰, 재발(NTE)
2. cBioPortal TCGA PanCancer Atlas(brca_tcga_pan_can_atlas_2018):
   환자·샘플 임상 요약, 체세포 변이(MAF), 바이오마커 유전자의 복제수(GISTIC)

저장 위치: <프로젝트>/data/tcga_brca/  (git에 올리지 않음)
이미 받은 파일은 건너뛴다. 처음부터 다시 받으려면 해당 파일을 지우고 실행한다.

실행: conda team_project 환경에서
    python data/script/tcga_brca_download.py
"""
import json
from pathlib import Path

import pandas as pd
import requests

# 이 스크립트는 data/script/에 있다. DATA_ROOT = data/
DATA_ROOT = Path(__file__).resolve().parent.parent
OUT = DATA_ROOT / "tcga_brca"
GDC_DIR = OUT / "gdc_clinical"
CBIO_DIR = OUT / "cbioportal"

GDC_API = "https://api.gdc.cancer.gov"
CBIO_API = "https://www.cbioportal.org/api"
STUDY = "brca_tcga_pan_can_atlas_2018"

# BM-2 판정 기준표와 BM-4 검사 공백 규칙에 나오는 유전자
BIOMARKER_GENES = ["ERBB2", "ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]

TIMEOUT = 300


def download_gdc_clinical():
    """GDC의 TCGA-BRCA BCR Biotab 파일 중 임상(clinical_*) 파일을 받는다."""
    GDC_DIR.mkdir(parents=True, exist_ok=True)
    filters = {"op": "and", "content": [
        {"op": "=", "content": {"field": "cases.project.project_id", "value": "TCGA-BRCA"}},
        {"op": "=", "content": {"field": "data_format", "value": "BCR Biotab"}},
        {"op": "=", "content": {"field": "access", "value": "open"}}]}
    params = {"filters": json.dumps(filters), "fields": "file_id,file_name,file_size",
              "size": 200, "format": "json"}
    hits = requests.get(f"{GDC_API}/files", params=params, timeout=TIMEOUT).json()["data"]["hits"]
    hits = [h for h in hits if "_clinical_" in h["file_name"]]

    print(f"[GDC] 임상 파일 {len(hits)}개")
    for h in sorted(hits, key=lambda x: x["file_name"]):
        path = GDC_DIR / h["file_name"]
        if path.exists() and path.stat().st_size == h["file_size"]:
            print(f"  건너뜀  {h['file_name']}")
            continue
        r = requests.get(f"{GDC_API}/data/{h['file_id']}", timeout=TIMEOUT)
        r.raise_for_status()
        path.write_bytes(r.content)
        print(f"  받음    {h['file_name']} ({len(r.content) / 1e3:.0f} KB)")


def cbio_get(path, **params):
    r = requests.get(f"{CBIO_API}{path}", params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def cbio_post(path, body, **params):
    r = requests.post(f"{CBIO_API}{path}", params=params, json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def save(df, name):
    path = CBIO_DIR / name
    df.to_csv(path, sep="\t", index=False)
    print(f"  저장    {name} ({len(df):,}행 × {df.shape[1]}열)")


def download_cbioportal():
    CBIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[cBioPortal] {STUDY}")

    # 1) 임상 요약: API는 (ID, 속성, 값) 긴 형식으로 주므로 넓은 표로 바꾼다
    for level, id_col in [("PATIENT", "patientId"), ("SAMPLE", "sampleId")]:
        name = f"clinical_{level.lower()}.tsv"
        if (CBIO_DIR / name).exists():
            print(f"  건너뜀  {name}")
            continue
        rows = cbio_get(f"/studies/{STUDY}/clinical-data",
                        clinicalDataType=level, projection="SUMMARY", pageSize=10_000_000)
        long = pd.DataFrame(rows)
        index = ["patientId"] if level == "PATIENT" else ["patientId", "sampleId"]
        wide = long.pivot_table(index=index, columns="clinicalAttributeId",
                                values="value", aggfunc="first").reset_index()
        wide.columns.name = None
        save(wide, name)

    # 속성 설명표 (열 이름 → 뜻)
    if not (CBIO_DIR / "clinical_attributes.tsv").exists():
        attrs = pd.DataFrame(cbio_get(f"/studies/{STUDY}/clinical-attributes"))
        save(attrs[["clinicalAttributeId", "displayName", "description", "datatype", "patientAttribute"]],
             "clinical_attributes.tsv")
    else:
        print("  건너뜀  clinical_attributes.tsv")

    # 검사 대상 샘플 목록: 변이가 0개인 것과 검사를 안 한 것을 구분하는 데 쓴다
    if not (CBIO_DIR / "profiled_samples.tsv").exists():
        lists = {"sequenced": f"{STUDY}_sequenced", "cna": f"{STUDY}_cna"}
        rows = []
        for kind, list_id in lists.items():
            for sid in cbio_get(f"/sample-lists/{list_id}", projection="DETAILED")["sampleIds"]:
                rows.append({"sampleId": sid, "profile": kind})
        prof = (pd.DataFrame(rows).assign(v=True)
                .pivot_table(index="sampleId", columns="profile", values="v", aggfunc="first")
                .fillna(False).reset_index())
        prof.columns.name = None
        prof.insert(0, "patientId", prof["sampleId"].str[:12])
        save(prof, "profiled_samples.tsv")
    else:
        print("  건너뜀  profiled_samples.tsv")

    # 2) 체세포 변이: 변이 검사를 받은 전체 샘플
    if not (CBIO_DIR / "mutations.tsv").exists():
        # GET은 유전자 하나를 지정해야 해서, 전체 유전자는 POST /fetch로 받는다
        rows = cbio_post(f"/molecular-profiles/{STUDY}_mutations/mutations/fetch",
                         {"sampleListId": f"{STUDY}_all"},
                         projection="DETAILED", pageSize=10_000_000)
        mut = pd.json_normalize(rows)
        keep = {
            "patientId": "patientId", "sampleId": "sampleId",
            "gene.hugoGeneSymbol": "gene", "gene.entrezGeneId": "entrezGeneId",
            "proteinChange": "proteinChange", "mutationType": "mutationType",
            "variantType": "variantType", "ncbiBuild": "ncbiBuild",
            "refseqMrnaId": "refseqMrnaId", "chr": "chr",
            "startPosition": "startPosition", "endPosition": "endPosition",
            "referenceAllele": "referenceAllele", "variantAllele": "variantAllele",
            "tumorAltCount": "tumorAltCount", "tumorRefCount": "tumorRefCount",
            "mutationStatus": "mutationStatus", "validationStatus": "validationStatus",
        }
        mut = mut[[c for c in keep if c in mut.columns]].rename(columns=keep)
        if {"tumorAltCount", "tumorRefCount"} <= set(mut.columns):
            depth = mut["tumorAltCount"] + mut["tumorRefCount"]
            mut["vaf"] = (mut["tumorAltCount"] / depth.where(depth > 0)).round(3)
        save(mut, "mutations.tsv")
    else:
        print("  건너뜀  mutations.tsv")

    # 3) 복제수(GISTIC, -2 깊은 결실 ~ 2 증폭): 바이오마커 유전자만
    if not (CBIO_DIR / "cna_biomarker_genes.tsv").exists():
        genes = cbio_post("/genes/fetch", BIOMARKER_GENES, geneIdType="HUGO_GENE_SYMBOL")
        entrez = {g["entrezGeneId"]: g["hugoGeneSymbol"] for g in genes}
        rows = cbio_post(f"/molecular-profiles/{STUDY}_gistic/discrete-copy-number/fetch",
                         {"sampleListId": f"{STUDY}_all", "entrezGeneIds": list(entrez)},
                         discreteCopyNumberEventType="ALL", projection="SUMMARY")
        cna = pd.DataFrame(rows)
        cna["gene"] = cna["entrezGeneId"].map(entrez)
        wide = cna.pivot_table(index=["patientId", "sampleId"], columns="gene",
                               values="alteration", aggfunc="first").reset_index()
        wide.columns.name = None
        save(wide, "cna_biomarker_genes.tsv")
    else:
        print("  건너뜀  cna_biomarker_genes.tsv")


if __name__ == "__main__":
    download_gdc_clinical()
    download_cbioportal()
    print(f"\n완료: {OUT}")
