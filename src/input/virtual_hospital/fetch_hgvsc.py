"""M-03: TCGA 변이의 cDNA 표기(HGVSc, 정규 전사체)를 받아 data/tcga_hgvsc.csv에 저장한다.

mini 입력 모듈은 변이를 'GENE c.… (p.…)' 표기로만 읽는다 (pipeline.py VARIANT). 로컬 cBioPortal 변이 표에는
단백 변화(proteinChange)만 있어서, 차트에 쓰려면 cDNA 표기가 필요하다.

1) GDC 공개 API (ssm_occurrences): 환자·유전자로 찾고 정규 전사체 값을 쓴다
2) GDC에 그 환자의 변이 기록이 없으면 (cBioPortal과 GDC는 변이 호출이 달라 빠지는 경우가 있음, 2026-11-16 확인):
   cBioPortal 변이 표의 염색체 위치·염기(GRCh37)로 Genome Nexus 주석 API에 물어 정규 전사체 HGVSc를 받는다.
   돌려받은 단백 변화(hgvspShort)가 cBioPortal proteinChange와 같을 때만 쓴다.

실행: python -m src.input.virtual_hospital.fetch_hgvsc          (local/source_map.csv의 TCGA 환자 전부)
"""
from __future__ import annotations

import json
import re
import urllib.request

import pandas as pd

from src.input.virtual_hospital.common import LOCAL, MINI, ROOT, read_csv, write_csv

API = "https://api.gdc.cancer.gov/ssm_occurrences"
GN = "https://www.genomenexus.org/annotation/genomic?fields=annotation_summary"
GENES = ["ESR1", "PIK3CA", "AKT1", "PTEN", "BRCA1", "BRCA2", "PALB2"]
OUT = ROOT / "tcga_hgvsc.csv"
MUTATIONS = LOCAL / "mutations.tsv"                    # cBioPortal 변이 (tsv라 git 제외, mini data/tcga_brca에서 복사)


def post(url: str, body) -> object:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def fetch_gdc(cases: list[str]) -> list[dict]:
    body = {"filters": {"op": "and", "content": [
        {"op": "in", "content": {"field": "case.submitter_id", "value": cases}},
        {"op": "in", "content": {"field": "ssm.consequence.transcript.gene.symbol", "value": GENES}}]},
        "fields": "case.submitter_id,ssm.consequence.transcript.gene.symbol,ssm.consequence.transcript.aa_change,"
                  "ssm.consequence.transcript.annotation.hgvsc,ssm.consequence.transcript.is_canonical",
        "size": "5000"}
    rows = set()
    for h in post(API, body)["data"]["hits"]:
        for c in h["ssm"]["consequence"]:
            t = c["transcript"]
            if t.get("is_canonical") and t["gene"]["symbol"] in GENES and t.get("aa_change"):
                rows.add((h["case"]["submitter_id"], t["gene"]["symbol"], t["aa_change"], t["annotation"]["hgvsc"]))
    return [{"case": a, "gene": b, "protein_change": c, "hgvsc": d, "source": "GDC"} for a, b, c, d in sorted(rows)]


def same_splice(protein_change: str, hgvsp: str | None) -> bool:
    """cBioPortal 'X764_splice'와 Genome Nexus 'p.L764='처럼 같은 코돈의 스플라이스 부위 변이를 같은 것으로 본다."""
    m = re.fullmatch(r"X(\d+)_splice", protein_change or "")
    return bool(m and hgvsp and re.fullmatch(rf"p\.[A-Z]{m.group(1)}(=|_splice)", hgvsp))


def fetch_genome_nexus(missing: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """(받은 행, 못 받은 변이와 이유)."""
    locs = [{"chromosome": str(r.chr), "start": int(r.startPosition), "end": int(r.endPosition),
             "referenceAllele": r.referenceAllele, "variantAllele": r.variantAllele} for r in missing.itertuples()]
    got, miss = [], []
    for r, a in zip(missing.itertuples(), post(GN, locs)):
        t = (a.get("annotation_summary") or {}).get("transcriptConsequenceSummary") or {}
        hgvsc, hgvsp = t.get("hgvsc"), t.get("hgvspShort")
        if not hgvsc or t.get("hugoGeneSymbol") != r.gene:
            miss.append({"case": r.patientId, "gene": r.gene, "protein_change": r.proteinChange, "이유": "주석 없음"})
        elif hgvsp != f"p.{r.proteinChange}" and not same_splice(r.proteinChange, hgvsp):
            miss.append({"case": r.patientId, "gene": r.gene, "protein_change": r.proteinChange,
                         "이유": f"단백 변화가 다름 ({hgvsp})"})
        else:
            got.append({"case": r.patientId, "gene": r.gene, "protein_change": r.proteinChange,
                        "hgvsc": hgvsc.split(":", 1)[1], "source": "GenomeNexus"})
    return got, miss


def main() -> int:
    cases = sorted({r["source_id"] for r in read_csv(LOCAL / "source_map.csv") if r["dataset"] == "TCGA-BRCA"})
    gdc = fetch_gdc(cases)
    have = {(r["case"], r["gene"], r["protein_change"]) for r in gdc}
    mut = pd.read_csv(MUTATIONS, sep="\t", dtype=str)
    mut = mut[mut.patientId.isin(cases) & mut.gene.isin(GENES)].drop_duplicates(["patientId", "gene", "proteinChange"])
    missing = mut[[(r.patientId, r.gene, r.proteinChange) not in have for r in mut.itertuples()]]
    gn, miss = fetch_genome_nexus(missing) if len(missing) else ([], [])
    write_csv(OUT, gdc + gn, ["case", "gene", "protein_change", "hgvsc", "source"])
    write_csv(ROOT / "reports" / "hgvsc_missing.csv", miss, ["case", "gene", "protein_change", "이유"])
    print(f"{len(cases)}명: GDC {len(gdc)}건 + Genome Nexus {len(gn)}건, 못 받음 {len(miss)}건 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
