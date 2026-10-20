"""CIViC 임상 근거 다운로드 (BM-3 근거 주석용).

받는 것
- CIViC nightly `ClinicalEvidenceSummaries.tsv` (약 4MB, CC0 공개).
- 남기는 것: PIK3CA, AKT1, PTEN의 근거 중 아래를 모두 만족하는 행
  - 분자 프로파일이 변이 하나를 정확히 지목함 (예: "PIK3CA N345K". "PIK3CA Mutation" 같은 묶음과 AND/OR 조합은 뺌)
  - 발암성·예측 근거 (src/input/handoff_to_B.md 5.4절): Predictive + Sensitivity/Response, 또는 Oncogenic + Oncogenicity
  - 근거 방향 Supports, 상태 accepted

저장 위치: <프로젝트>/data/civic/
- civic_bm3_evidence_<받은 날>.csv (예: civic_bm3_evidence_2026-10-19.csv. 전달 문서 5.6절 "파일명에 받은 날짜를
  넣는다". CC0라 git에 올린다. 다시 받으면 예전 날짜 파일은 지운다): gene, protein_change, evidence_level(A~E), evidence_type, significance, disease, therapies,
  evidence_id, citation, last_review_date
- civic_version.txt: 받은 날, 원본 주소

외부로 보내는 정보는 없다. 파일을 받아 로컬에서만 조회한다 (PROJECT.md 5절 BM-3).
인용: Griffith M et al., Nat Genet 2017;49:170-174 (CIViC). 데이터는 CC0 (로고 등 그림은 CC BY-ND 4.0이라 쓰지 않는다).
CIViC 면책 조항: 연구용 자료이며 응급 상황이나 의료적 조언에 쓰지 않는다. 결과는 참고 근거로만 표시한다.

실행: conda team_project 환경에서
    python data/script/civic_download.py
"""
import csv
import io
import re
from datetime import date
from pathlib import Path

import requests

# 이 스크립트는 data/script/에 있다. DATA_ROOT = data/
DATA_ROOT = Path(__file__).resolve().parent.parent
OUT = DATA_ROOT / "civic"
URL = "https://civicdb.org/downloads/nightly/nightly-ClinicalEvidenceSummaries.tsv"

GENES = {"PIK3CA", "AKT1", "PTEN"}
# 근거 종류와 의미 (발암성·예측 근거)
KEEP = {("Predictive", "Sensitivity/Response"), ("Oncogenic", "Oncogenicity")}
# "PIK3CA N345K"처럼 유전자 + 단백질 변화 하나
_PROFILE_RE = re.compile(r"^(\w+) ([A-Z]\d+[A-Z*]|[A-Z]\d+_[A-Z]\d+(?:del|ins[A-Z]+|delins[A-Z]+)|[A-Z]\d+del)$")

FIELDS = ["gene", "protein_change", "evidence_level", "evidence_type", "significance", "disease", "therapies",
          "evidence_id", "citation", "last_review_date"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, timeout=300)
    resp.raise_for_status()
    rows = csv.DictReader(io.StringIO(resp.content.decode("utf-8")), delimiter="\t")
    for old in OUT.glob("civic_bm3_evidence*.csv"):
        old.unlink()
    out_csv = OUT / f"civic_bm3_evidence_{date.today().isoformat()}.csv"
    kept = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=FIELDS)
        writer.writeheader()
        for r in sorted(rows, key=lambda r: (r["molecular_profile"], r["evidence_level"], int(r["evidence_id"]))):
            m = _PROFILE_RE.match(r["molecular_profile"])
            if not m or m.group(1) not in GENES:
                continue
            if ((r["evidence_type"], r["significance"]) not in KEEP or r["evidence_direction"] != "Supports"
                    or r["evidence_status"] != "accepted"):
                continue
            writer.writerow({
                "gene": m.group(1), "protein_change": m.group(2), "evidence_level": r["evidence_level"],
                "evidence_type": r["evidence_type"], "significance": r["significance"], "disease": r["disease"],
                "therapies": r["therapies"], "evidence_id": r["evidence_id"], "citation": r["citation"],
                "last_review_date": r["last_review_date"],
            })
            kept += 1
    (OUT / "civic_version.txt").write_text(
        f"source: {URL}\ndownloaded: {date.today().isoformat()}\ngenes: {', '.join(sorted(GENES))}\n"
        f"rows: {kept}\nlicense: CC0\ncitation: Griffith M et al., Nat Genet 2017;49:170-174\n", encoding="utf-8")
    print(f"{out_csv} {kept}행")


if __name__ == "__main__":
    main()
