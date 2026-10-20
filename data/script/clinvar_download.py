"""ClinVar 변이 판정 다운로드 (BM-3 근거 주석용).

받는 것
- NCBI ClinVar `variant_summary.txt.gz` (약 450MB). 내려받으면서 바로 걸러서 원본은 저장하지 않는다.
- 남기는 것: BRCA1, BRCA2, PALB2, PTEN의 GRCh38 변이 중 단백질 변화(p.)가 있는 행.
  유전자별로 BM-3가 ClinVar를 쓰는 곳은 src/input/handoff_to_B.md 5.4절 (gBRCA1/2, PALB2, PTEN 미스센스).

저장 위치: <프로젝트>/data/clinvar/  (git에 올리지 않음: 전달 문서 5.6절 "스크립트만 올린다".
  .tsv·.log는 .gitignore의 data/ 규칙으로 제외된다. 팀원은 각자 이 스크립트를 실행한다)
- clinvar_bm3_genes.tsv (탭 구분): gene, protein_change(한 글자 표기, 예 C61G), clinical_significance, review_status,
  stars(리뷰 등급 0~4), variation_id, last_evaluated, name(ClinVar 원래 이름)
- clinvar_version.log: 원본 파일의 날짜(Last-Modified)와 받은 날

외부로 보내는 정보는 없다. 파일을 통째로 받아 로컬에서만 조회한다 (PROJECT.md 5절 BM-3).
ClinVar 이용 조건: 미국 정부(NCBI) 자료로 퍼블릭 도메인이다. 배포·인용 시 ClinVar를 출처로 적는다(파일 날짜 포함).
  ClinVar에 연결된 OMIM 설명·논문 원문 등은 별도 저작권이 있어 가져오지 않는다(이 파일은 판정·리뷰 등급·번호·이름만 남긴다).
  NCBI는 정확성을 보증하지 않는다. 연구·참고용이며 진단·치료 결정에 바로 쓰지 않는다.

실행: conda team_project 환경에서
    python data/script/clinvar_download.py
"""
import csv
import gzip
import re
from datetime import date
from pathlib import Path

import requests

# 이 스크립트는 data/script/에 있다. DATA_ROOT = data/
DATA_ROOT = Path(__file__).resolve().parent.parent
OUT = DATA_ROOT / "clinvar"
URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"

GENES = {"BRCA1", "BRCA2", "PALB2", "PTEN"}
ASSEMBLY = "GRCh38"

# ClinVar 리뷰 등급(별 개수). https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/
STARS = {
    "practice guideline": 4,
    "reviewed by expert panel": 3,
    "criteria provided, multiple submitters, no conflicts": 2,
    "criteria provided, conflicting classifications": 1,
    "criteria provided, conflicting interpretations": 1,
    "criteria provided, single submitter": 1,
}

AA3 = {"Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E", "Gly": "G",
       "His": "H", "Ile": "I", "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S",
       "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V", "Ter": "*", "Sec": "U"}
_AA_RE = re.compile("|".join(AA3))
_P_RE = re.compile(r"\(p\.([^)]+)\)")

FIELDS = ["gene", "protein_change", "clinical_significance", "review_status", "stars",
          "variation_id", "last_evaluated", "name"]


def one_letter(p3):
    """세 글자 단백질 표기를 TCGA와 같은 한 글자 표기로. 예: Cys61Gly -> C61G, Arg130Ter -> R130*"""
    return _AA_RE.sub(lambda m: AA3[m.group(0)], p3)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    out_csv = OUT / "clinvar_bm3_genes.tsv"
    kept = 0
    with requests.get(URL, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        modified = resp.headers.get("Last-Modified", "")
        resp.raw.decode_content = True
        with gzip.open(resp.raw, "rt", encoding="utf-8") as src, \
                open(out_csv, "w", newline="", encoding="utf-8") as dst:
            writer = csv.DictWriter(dst, fieldnames=FIELDS, delimiter="\t")
            writer.writeheader()
            reader = csv.DictReader(src, delimiter="\t")
            for row in reader:
                if row["GeneSymbol"] not in GENES or row["Assembly"] != ASSEMBLY:
                    continue
                m = _P_RE.search(row["Name"])
                if not m:
                    continue
                writer.writerow({
                    "gene": row["GeneSymbol"],
                    "protein_change": one_letter(m.group(1)),
                    "clinical_significance": row["ClinicalSignificance"],
                    "review_status": row["ReviewStatus"],
                    "stars": STARS.get(row["ReviewStatus"], 0),
                    "variation_id": row["VariationID"],
                    "last_evaluated": row["LastEvaluated"],
                    "name": row["Name"],
                })
                kept += 1
    (OUT / "clinvar_version.log").write_text(
        f"source: {URL}\nlast_modified: {modified}\ndownloaded: {date.today().isoformat()}\n"
        f"genes: {', '.join(sorted(GENES))} ({ASSEMBLY})\nrows: {kept}\n", encoding="utf-8")
    print(f"{out_csv} {kept}행 (원본 날짜 {modified})")


if __name__ == "__main__":
    main()
