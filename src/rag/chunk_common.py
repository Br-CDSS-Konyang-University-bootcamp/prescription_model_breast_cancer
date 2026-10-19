# src/rag/chunk_common.py
# 청커(chunker_asco_all.py, chunker_esmo.py)가 같이 쓰는 경로, 텍스트 정제, 태깅 함수
import csv
import re
import unicodedata
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # team_project
PARSED_MD_DIR = BASE_DIR / "data" / "parsed_md"  # 각자 PDF에서 만든다 (convert_pdf_to_md.py). 저장소에 올리지 않는다
CHUNKS_DIR = BASE_DIR / "data" / "chunks"
DRUG_CLASSES_CSV = BASE_DIR / "data" / "dictionaries" / "drug_classes.csv"

# 지침 약어 → 일반명 (drug_classes.csv에 없는 표기)
DRUG_ALIASES = {
    "t-dxd": "trastuzumab deruxtecan",
    "t-dm1": "trastuzumab emtansine",
    "dato-dxd": "datopotamab deruxtecan",
    "sg": "sacituzumab govitecan",
    "nabpaclitaxel": "nab-paclitaxel",
    "protein-bound paclitaxel": "nab-paclitaxel",
}


def clean_text(text: str) -> str:
    """PDF 추출 텍스트 정제: 합자, 제어문자, 줄 끝 하이픈, 머리말(다운로드 정보), 마크다운 꾸밈 제거."""
    text = unicodedata.normalize("NFKC", text)
    # pymupdf4llm이 넣는 꾸밈: 인용 번호 위첨자, 굵게, 기울임, 밑줄, 표 안 줄바꿈
    text = re.sub(r"<sup>[^<]*</sup>", "", text)
    text = re.sub(r"</?u>", "", text).replace("<br>", " ").replace("**", "")
    text = re.sub(r"(?<![\w/])_([^_\n]+?)_\s?-\s?(?=\w)", r"\1-", text)  # _PIK3CA_ -mutated → PIK3CA-mutated
    text = re.sub(r"(?<![\w/])_([^_\n]+?)_(?![\w/])", r"\1", text)
    # PDF를 내려받은 사람의 정보가 담긴 줄은 청크에 넣지 않는다
    text = re.sub(r"^.*Downloaded from ascopubs\.org.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"[\x00-\x08\x0B-\x1F\x7F]", "", text)
    text = re.sub(r"(?<=[a-z])-\n\s*(?=[a-z])", "", text)
    text = text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    # 단어 사이 en dash는 하이픈으로 맞춘다 (receptor–positive → receptor-positive). 아형·태그 규칙이 하이픈을 찾는다
    text = re.sub(r"(?<=\w)–(?=\w)", "-", text)
    return text


def parse_version(file_stem: str) -> str:
    """파일 이름의 발행 연월. `_`는 단어 문자라 \\b 대신 숫자 경계를 쓴다."""
    match = re.search(r"(?<!\d)(20\d{2}-\d{2})(?!\d)", file_stem)
    if not match:
        raise ValueError(f"파일 이름에 발행 연월(YYYY-MM)이 없습니다: {file_stem}")
    return match.group(1)


def _load_drug_names() -> list[str]:
    names = set(DRUG_ALIASES)
    with open(DRUG_CLASSES_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = row["generic_name"].strip().lower()
            if name and "nos" not in name.split() and name != "unknown" and "vaccine" not in name:
                names.add(name)
    # 긴 이름부터 찾아야 trastuzumab deruxtecan이 trastuzumab으로 잡히지 않는다
    return sorted(names, key=len, reverse=True)


_DRUG_NAMES = None


def find_drugs(text: str) -> list[str]:
    global _DRUG_NAMES
    if _DRUG_NAMES is None:
        _DRUG_NAMES = _load_drug_names()
    remaining = text.lower()
    found = []
    for name in _DRUG_NAMES:
        pattern = rf"(?<![a-z]){re.escape(name)}(?![a-z])"
        if re.search(pattern, remaining):
            generic = DRUG_ALIASES.get(name, name)
            if generic not in found:
                found.append(generic)
            remaining = re.sub(pattern, " ", remaining)
    return found


def find_biomarker_tags(text: str) -> list[str]:
    # 태그 이름은 B(biomarker)와 맞추기 전 임시값이다 (리뷰 6번, B와 협의 후 공용 파일로 옮긴다)
    t = text.lower()
    tags = []
    if "her2-low" in t or "her2 low" in t or "ihc 1+" in t or "ihc 2+" in t:
        tags.append("HER2-low")
    if "her2-ultralow" in t or "ultralow" in t:
        tags.append("HER2-ultralow")
    if re.search(r"germline brca|gbrca|brca1/2m|brca1 or 2 mutation|brca1 or brca2", t):
        tags.append("gBRCA")
    if "pik3ca" in t:
        tags.append("PIK3CA-mut")
    if "esr1" in t:
        tags.append("ESR1-mut")
    if "pd-l1" in t or re.search(r"\bcps\b", t):
        tags.append("PD-L1+")
    if "akt1" in t:
        tags.append("AKT1-mut")
    if "pten" in t:
        tags.append("PTEN-alt")
    return tags


def make_chunk(*, chunk_id, source, version, section, url, chunk_kind, text, setting, subtype, line,
               evidence, copyright_notice, parent_id=None) -> dict:
    """schemas/chunk.json 형식의 지침 청크 하나."""
    return {
        "schema_version": "0.1-draft",
        "chunk_id": chunk_id,
        "doc_type": "guideline",
        "source": source,
        "version": version,
        "section": section,
        "page_start": None,
        "page_end": None,
        "url": url,
        "chunk_kind": chunk_kind,
        "parent_id": parent_id,
        "text": text,
        "setting": setting,
        "subtype": subtype,
        "line": line,
        "biomarker_tags": find_biomarker_tags(text),
        "drugs": find_drugs(text),
        "evidence": evidence,
        "superseded_by": None,
        "copyright_notice": copyright_notice,
    }
