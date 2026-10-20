"""약제명 목록과 이상한 낱말 찾기.

알려진 약제명 = data/dictionaries/drug_classes.csv의 일반명 (팀 공용 사전, 입력 모듈과 같은 표기)
             + 이 모듈에서 쓰는 유방암 약제 (사전에 아직 없는 최신 약제)
공용 사전은 고치지 않는다. 새 약제가 나오면 BREAST_EXTRA에 넣고, 공용 사전 추가는 팀에 요청한다.
"""
from __future__ import annotations

import csv
import difflib
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT_CSV = ROOT / "data" / "dictionaries" / "drug_classes.csv"

# 공용 사전에 없는 유방암 관련 약제 (2026-10 책자·허가초과 목록 기준)
BREAST_EXTRA = {
    "abemaciclib", "palbociclib", "ribociclib",
    "pertuzumab", "trastuzumab deruxtecan", "trastuzumab emtansine", "margetuximab",
    "sacituzumab govitecan", "datopotamab deruxtecan",
    "eribulin", "olaparib", "talazoparib",
    "pembrolizumab", "nivolumab", "atezolizumab",
    "neratinib", "tucatinib", "lapatinib",
    "alpelisib", "capivasertib", "inavolisib", "elacestrant",
    "filgrastim", "lenograstim", "dexrazoxane",
    "irinotecan", "oxaliplatin", "leucovorin", "mitomycin",
    # Ⅳ 기타 약제 (보조 약제, 설계 §10). G-CSF 지속형 제제, 골전이 약제
    "pegfilgrastim", "pegteograstim", "tripegfilgrastim", "lipegfilgrastim", "eflapegrastim",
    "zoledronic acid", "denosumab", "pamidronate", "sodium thiosulfate",
}
# 사전의 일반명이 아닌 항목 (분류용 표기)
_NOT_DRUG = re.compile(r"\bnos\b|unknown|vaccine")

# 일반 영어·의학 낱말 (약제명 오타 검사에서 뺀다)
COMMON_WORDS = {
    "neoadjuvant", "adjuvant", "palliative", "salvage", "agonist", "inhibitor", "inhibitors",
    "stage", "weekly", "receptor", "hormone", "releasing", "luteinizing", "epidermal", "growth",
    "factor", "human", "combination", "fixed", "dose", "dense", "therapy", "chemotherapy",
    "endocrine", "aromatase", "carcinoma", "cancer", "breast", "positive", "negative",
    "metastatic", "advanced", "first", "line", "intra", "peritoneal", "bound", "albumin",
    "acetate", "liposomal", "pegylated", "taxane", "anthracycline", "platinum", "bone",
    "metastases", "lesion", "regimen", "assay", "pharmdx", "tumors", "ejection", "point",
    "febrile", "neutropenia", "intensified", "corrected", "calcium", "bearing", "weight", "anthracenedion",
    "disease", "hodgkin",
    # 바이오마커·검사
    "gbrca", "sbrca", "brca", "pd-l", "pten", "akt", "pik3ca", "esr1", "her2", "hrd", "msi", "tmb",
}


@lru_cache(maxsize=1)
def known_drugs() -> frozenset[str]:
    names = set(BREAST_EXTRA)
    if DICT_CSV.exists():
        with open(DICT_CSV, encoding="utf-8-sig") as f:     # 사전 파일 앞에 BOM이 있다
            for row in csv.DictReader(f):
                g = (row.get("generic_name") or "").strip().lower()
                if g and not _NOT_DRUG.search(g):
                    names.add(g)
    return frozenset(names)


def _single_words() -> set[str]:
    return {w for d in known_drugs() for w in re.split(r"[\s\-]+", d) if len(w) >= 5}


def suggest_drug(token: str, cutoff: float = 0.85) -> str | None:
    """알려진 약제명과 거의 같지만 다른 낱말이면 가장 가까운 약제명을 돌려준다 (오타 의심)."""
    t = token.lower()
    words = _single_words()
    if t in words or t in COMMON_WORDS or len(t) < 6:
        return None
    m = difflib.get_close_matches(t, words, n=1, cutoff=cutoff)
    return m[0] if m else None


def typo_suspects(text: str) -> list[tuple[str, str]]:
    """본문에서 약제명 오타로 보이는 낱말 [(낱말, 추정 약제명)]. 같은 낱말은 한 번만."""
    out = {}
    for tok in re.findall(r"[A-Za-z][A-Za-z\-]{5,}", text):
        s = suggest_drug(tok)
        if s:
            out.setdefault(tok.lower(), s)
    return sorted(out.items())
