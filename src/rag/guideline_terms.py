# src/rag/guideline_terms.py
# 지침 표현 사전 (data/dictionaries/guideline_terms.csv): 환자 JSON의 코드 값 → 지침 원문에 쓰이는 영어 표현.
# canonical은 B의 biomarker_record 값(과 A의 patient_state 값, 약 사전 값)으로 고정한다. C는 expression만 늘린다.
# 검색 질의문과 평가용 키워드를 만들 때 쓴다. 청크 태깅(chunk_common)도 같은 사전으로 옮겨 갈 예정이다.
# 실행: team_project 폴더에서 python -m src.rag.guideline_terms  → 표현마다 청크에 몇 번 나오는지 보여 준다
import csv
import re
from pathlib import Path

from .chunk_common import BASE_DIR

TERMS_CSV = BASE_DIR / "data" / "dictionaries" / "guideline_terms.csv"


def load_terms(path: Path = TERMS_CSV) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def expressions(field: str, canonical: str, terms: list[dict] = None) -> list[str]:
    """그 값의 지침 표현. 대표 표현(preferred=1)이 맨 앞."""
    rows = [t for t in (terms or load_terms()) if t["field"] == field and t["canonical"] == canonical]
    rows.sort(key=lambda t: t["preferred"] != "1")
    return [t["expression"] for t in rows]


def preferred(field: str, canonical: str, terms: list[dict] = None):
    found = expressions(field, canonical, terms)
    return found[0] if found else None


def query_terms(profile: dict, terms: list[dict] = None) -> list[str]:
    """환자 프로필(코드 값)을 지침 대표 표현 목록으로 바꾼다. 값이 없거나 unknown이면 뺀다.
    profile 예: {"subtype": "HR+/HER2-", "disease": "metastatic", "line": "2L",
                "markers": ["ESR1:positive"], "prior_subclasses": ["AI_nonsteroidal", "CDK4/6_inhibitor"],
                "menopausal_status": "postmenopausal"}"""
    terms = terms or load_terms()
    keys = [("biomarker_record.subtype", profile.get("subtype")),
            ("biomarker_record.setting.disease", profile.get("disease")),
            ("biomarker_record.setting.line", profile.get("line"))]
    keys += [("biomarker_record.records", m) for m in profile.get("markers", [])]
    keys += [("treatment_history.drug_subclass", s) for s in profile.get("prior_subclasses", [])]
    keys += [("treatment_history.drug_class", c) for c in profile.get("prior_classes", [])]
    keys += [("patient.menopausal_status", profile.get("menopausal_status")),
             ("neoadjuvant_response.pcr", profile.get("pcr"))]
    keys += [("metastatic_sites", s) for s in profile.get("metastatic_sites", [])]
    out = []
    for field, value in keys:
        if value and value != "unknown":
            phrase = preferred(field, value, terms)
            if phrase and phrase not in out:
                out.append(phrase)
    return out


def _norm(text: str) -> str:
    """대시·하이픈 종류와 공백 차이를 없앤 소문자."""
    text = re.sub(r"[‐-―−-]", "-", text.lower())
    return re.sub(r"\s+", " ", text)


def coverage(chunks: list[dict], terms: list[dict] = None) -> list[tuple[dict, int]]:
    """표현마다 그 표현이 들어 있는 청크 수. 0이면 지침에 없는 표현이라 질의에 써도 소용이 없다."""
    texts = [_norm(c["text"]) for c in chunks]
    result = []
    for t in terms or load_terms():
        expr = _norm(t["expression"])
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(expr) + r"(?![a-z0-9])")
        result.append((t, sum(1 for x in texts if pattern.search(x))))
    return result


def main():
    from .chunk_store import load_guideline_chunks, select_index_chunks
    chunks = select_index_chunks(load_guideline_chunks())
    rows = coverage(chunks)
    print(f"권고 청크 {len(chunks)}개 기준. 표현이 들어 있는 청크 수")
    for t, n in rows:
        mark = "  ← 청크에 없음" if n == 0 else ""
        star = "*" if t["preferred"] == "1" else " "
        print(f"{n:4d} {star} {t['field']:34s} {t['canonical']:22s} {t['expression']}{mark}")
    print("(* = 질의문에 쓰는 대표 표현)")


if __name__ == "__main__":
    main()
