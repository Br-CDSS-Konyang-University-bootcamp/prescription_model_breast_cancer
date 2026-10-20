# src/rag/chunk_common.py
# 청커(chunker_esmo.py)가 쓰는 경로, 텍스트 정제, 태깅 함수
import csv
import hashlib
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
    text = re.sub(r"[\x00-\x08\x0B-\x1F\x7F]", "", text)
    text = re.sub(r"(?<=[a-z])-\n\s*(?=[a-z])", "", text)
    text = text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")
    # 단어 사이 en dash는 하이픈으로 맞춘다 (receptor–positive → receptor-positive). 아형·태그 규칙이 하이픈을 찾는다
    text = re.sub(r"(?<=\w)–(?=\w)", "-", text)
    text = re.sub(r"(?<=\w)\s?[–—]\s(?=(positive|negative)\b)", "-", text)  # "receptor– positive" (줄바꿈 자리)
    text = re.sub(r"[ \t]+(?=[,;])", "", text)  # 기울임 표시를 지운 자리의 "PIK3CA , AKT1"
    text = re.sub(r"(?<=[<>≤≥])[ \t]+(?=\d)", "", text)  # "> 12 months" → ">12 months"
    return text


def parse_version(file_stem: str) -> str:
    """파일 이름의 발행 연월. `_`는 단어 문자라 \\b 대신 숫자 경계를 쓴다."""
    match = re.search(r"(?<!\d)(20\d{2}-\d{2})(?!\d)", file_stem)
    if not match:
        raise ValueError(f"파일 이름에 발행 연월(YYYY-MM)이 없습니다: {file_stem}")
    return match.group(1)


def stable_key(text: str, length: int = 6) -> str:
    """권고 문장으로 만드는 짧은 지문. 순서 번호(r01, r02) 대신 chunk_id에 쓴다.
    앞뒤 권고가 늘거나 줄어도, 대시·공백·마크다운 표기가 달라져도 같은 문장이면 같은 값이 나온다.
    평가셋 정답과 추천 결과의 인용이 chunk_id를 가리키므로, 다시 청킹해도 ID가 바뀌면 안 된다."""
    normalized = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", text).lower())[:200]
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:length]


def _load_drug_names() -> list[str]:
    names = set(DRUG_ALIASES)
    with open(DRUG_CLASSES_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = row["generic_name"].strip().lower()
            if name and "nos" not in name.split() and name != "unknown" and "vaccine" not in name:
                names.add(name)
    # 긴 이름부터 찾아야 trastuzumab deruxtecan이 trastuzumab으로 잡히지 않는다
    return sorted(names, key=lambda n: (-len(n), n))  # 길이가 같으면 이름 순 (실행마다 같은 순서)


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


# 표지자 뒤에 오면 "그 변이·발현이 없다"는 뜻인 표현. 예: PIK3CA-wild type, PD-L1-negative, BRCA1/2- wild type
_NEGATED_AFTER = re.compile(r"\s*-?\s*(wild[- ]?type|negative)\b")


def _mentioned(text: str, pattern: str) -> bool:
    """표지자가 양성(있음)의 뜻으로 한 번이라도 나오면 True. 바로 뒤가 wild type·negative인 언급은 세지 않는다."""
    return any(not _NEGATED_AFTER.match(text, m.end()) for m in re.finditer(pattern, text))


def find_biomarker_tags(text: str) -> list[str]:
    # 태그 이름은 B가 biomarker_record.records[].rag_tags에 붙이는 이름과 같다 (src/biomarker/README.md).
    # HER2-low, HER2-ultralow는 B가 아직 태그로 내지 않는다 (B는 HER2 상태값 low, ultralow로 낸다).
    # B의 태그는 양성일 때만 붙으므로, "PD-L1-negative", "germline BRCA1/2-wild type"처럼 없다는 언급에는 붙이지 않는다
    t = text.lower()
    tags = []
    if "her2-low" in t or "her2 low" in t or "ihc 1+" in t or "ihc 2+" in t:
        tags.append("HER2-low")
    if "her2-ultralow" in t or "ultralow" in t:
        tags.append("HER2-ultralow")
    if re.search(r"\ber-low|er-/pgr-low|\ber low\b|1%-9% er\b", t):
        tags.append("ER-low")
    if re.search(r"ki-?67 (score|index|level)?\s*(of )?≥\s?\d|high ki-?67", t):
        tags.append("Ki-67-high")
    if _mentioned(t, r"germline brca(1/2|1|2)?|gbrca(1/2)?|brca1/2m|brca1 or 2 mutation|brca1 or brca2"):
        tags.append("gBRCA")
    if re.search(r"somatic[^.]{0,40}brca|sbrca", t):
        tags.append("sBRCA")
    if _mentioned(t, r"palb2"):
        tags.append("gPALB2")
    if _mentioned(t, r"pik3ca"):
        tags.append("PIK3CA-mut")
    if _mentioned(t, r"esr1"):
        tags.append("ESR1-mut")
    if _mentioned(t, r"pd-l1|\bcps\b"):
        tags.append("PD-L1+")
    if _mentioned(t, r"akt1"):
        tags.append("AKT1-mut")
    if _mentioned(t, r"pten"):
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


def _union(values_lists: list[list[str]]) -> list[str]:
    out = []
    for values in values_lists:
        for v in values:
            if v not in out:
                out.append(v)
    return out


def attach_parent(children: list[dict], *, chunk_id: str, section: str, heading: str = "") -> dict:
    """권고 청크들의 부모(소단원) 청크를 만들고, 자식의 parent_id를 채운다.
    부모 본문은 소단원 제목(과 질문문) + 자식 권고 전체다. 검색은 자식으로 하고, LLM에는 부모를 함께 넘긴다.
    부모는 청크 JSON에만 두고 색인하지 않는다 (run_indexing.select_index_chunks). D의 급여 청크도 같은 방식이다."""
    first = children[0]
    text = "\n\n".join(([heading] if heading else []) + [c["text"] for c in children])
    parent = make_chunk(
        chunk_id=chunk_id,
        source=first["source"],
        version=first["version"],
        section=section,
        url=first["url"],
        chunk_kind="section",
        text=text,
        setting=_union([c["setting"] for c in children]),
        subtype=_union([c["subtype"] for c in children]),
        line=_union([c["line"] for c in children]),
        evidence=None,
        copyright_notice=first["copyright_notice"],
    )
    for child in children:
        child["parent_id"] = chunk_id
    return parent


# convert_pdf_to_md.page_marker가 쪽마다 넣는 표시
PAGE_MARKER = re.compile(r"<!-- page pdf=(\d+) printed=(\d+|-) -->")
# page_start·page_end에 넣을 쪽 번호: "printed"(학술지 인쇄 쪽, 인용에 쓰는 쪽) 또는 "pdf"(PDF 파일의 쪽).
# D의 급여 청크는 공고책자의 인쇄 쪽을 쓴다. 팀에서 다르게 정하면 이 값만 바꾼다.
PAGE_NUMBERING = "printed"


def strip_page_markers(text: str) -> str:
    return PAGE_MARKER.sub("", text)


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def fill_pages(chunks: list[dict], raw_markdown: str, numbering: str = PAGE_NUMBERING) -> None:
    """청크 본문이 md의 어느 쪽에 있는지 찾아 page_start·page_end를 채운다.
    본문 앞부분과 뒷부분을 쪽 표시가 든 md에서 찾는다 (영문자·숫자만 비교해서 정리 과정의 공백·기호 차이를 무시).
    부모 청크는 자식들의 첫 쪽~끝 쪽이다. 못 찾으면 null로 둔다."""
    flat, starts, pages = [], [], []  # 쪽마다 정규화한 본문과 그 시작 위치
    pos = 0
    parts = PAGE_MARKER.split(raw_markdown)
    # split 결과: [표시 앞 글, pdf, printed, 글, pdf, printed, 글, ...]
    for i in range(1, len(parts), 3):
        pdf_page, printed, body = int(parts[i]), parts[i + 1], parts[i + 2]
        norm = _alnum(clean_text(body))
        page_no = pdf_page if numbering == "pdf" else (int(printed) if printed != "-" else None)
        flat.append(norm)
        starts.append(pos)
        pages.append(page_no)
        pos += len(norm)
    if not flat:
        return
    haystack = "".join(flat)

    def page_at(offset: int):
        idx = 0
        for j, s in enumerate(starts):
            if s <= offset:
                idx = j
        return pages[idx]

    parent_ids = {c["parent_id"] for c in chunks if c.get("parent_id")}
    for c in chunks:
        if c["chunk_id"] in parent_ids:
            continue
        norm = _alnum(c["text"])
        head, tail = norm[:60], norm[-60:]
        start = haystack.find(head)
        if start < 0 and ": " in c["text"]:
            # ESMO의 "For patients ...: 권고"는 원문에서 문맥 줄과 권고 사이에 다른 권고가 끼어 있다. 권고 본문으로 찾는다
            head = _alnum(c["text"].split(": ", 1)[1])[:60]
            start = haystack.find(head)
        if start < 0:
            continue
        end = haystack.find(tail, start)
        c["page_start"] = page_at(start)
        c["page_end"] = page_at(end + len(tail) - 1) if end >= 0 else c["page_start"]
    for parent in (c for c in chunks if c["chunk_id"] in parent_ids):
        kids = [c for c in chunks if c.get("parent_id") == parent["chunk_id"]]
        starts_ = [k["page_start"] for k in kids if k["page_start"] is not None]
        ends_ = [k["page_end"] for k in kids if k["page_end"] is not None]
        parent["page_start"] = min(starts_) if starts_ else None
        parent["page_end"] = max(ends_) if ends_ else None
