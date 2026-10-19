# src/rag/chunker_esmo.py
# 실행: team_project 폴더에서 python -m src.rag.chunker_esmo
# 입력: data/parsed_md/esmo/*.md (convert_pdf_to_md.py로 각자 만든다)
# 출력: data/chunks/esmo_chunks.json
import json
import re
from pathlib import Path

from .chunk_common import PARSED_MD_DIR, CHUNKS_DIR, clean_text, make_chunk

COPYRIGHT = "Copyright © European Society for Medical Oncology. All rights reserved"
HER2_POS = ["HR+/HER2+", "HR-/HER2+"]

# 파일 이름: 문서 정보. version은 발행 연월, url은 PDF 첫 쪽의 DOI.
DOCS = {
    "esmo_ebc_2024-02": {
        "source": "ESMO-EBC", "slug": "ebc", "version": "2024-02",
        "url": "https://doi.org/10.1016/j.annonc.2023.11.016",
        "setting": ["early", "locally_advanced"],
    },
    "esmo_mbc_2026-05": {
        "source": "ESMO-MBC", "slug": "mbc", "version": "2026-05",
        "url": "https://doi.org/10.1016/j.annonc.2026.05.707",
        "setting": ["metastatic"],
    },
}

# 권고를 읽을 소단원. (상위 제목, 소제목): (chunk_id용 이름, subtype, line)
# 상위 제목이 None이면 소제목만 본다. line이 None이면 문장에서 판단한다 (EBC).
SECTIONS = {
    "esmo_ebc_2024-02": {
        (None, "HR-positive, HER2-negative EBC"): ("hrpos", ["HR+/HER2-"], None),
        (None, "HER2-positive EBC"): ("her2pos", HER2_POS, None),
        (None, "TNBC"): ("tnbc", ["TNBC"], None),
    },
    "esmo_mbc_2026-05": {
        ("MANAGEMENT OF LUMINAL MBC", "First-line treatment"): ("luminal-1l", ["HR+/HER2-"], ["1L"]),
        ("MANAGEMENT OF LUMINAL MBC", "Second-line treatment"): ("luminal-2l", ["HR+/HER2-"], ["2L"]),
        ("MANAGEMENT OF LUMINAL MBC", "Third-line treatment and beyond"): ("luminal-3l", ["HR+/HER2-"], [">=3L"]),
        ("MANAGEMENT OF HER2-POSITIVE MBC", "First-line treatment"): ("her2-1l", HER2_POS, ["1L"]),
        ("MANAGEMENT OF HER2-POSITIVE MBC", "Second-line treatment"): ("her2-2l", HER2_POS, ["2L"]),
        ("MANAGEMENT OF HER2-POSITIVE MBC", "Third-line treatment"): ("her2-3l", HER2_POS, [">=3L"]),
        ("MANAGEMENT OF HER2-POSITIVE MBC", "Fourth-line treatment and beyond"): ("her2-4l", HER2_POS, [">=3L"]),
        ("MANAGEMENT OF METASTATIC TNBC", "First-line treatment"): ("tnbc-1l", ["TNBC"], ["1L"]),
        ("MANAGEMENT OF METASTATIC TNBC", "Second-line treatment and beyond"): ("tnbc-2l", ["TNBC"], ["2L", ">=3L"]),
        ("SITE-SPECIFIC MANAGEMENT", "Primary (de novo) stage IV BC"): ("site-denovo", ["any"], ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "OMD"): ("site-omd", ["any"], ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "Bone metastases and bone-modifying agents"): ("site-bone", ["any"], ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "BMs"): ("site-bm", ["any"], ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "LRT for BMs"): ("site-bm-lrt", ["any"], ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "HER2-positive BC with BMs"): ("site-bm-her2", HER2_POS, ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "ER-positive BC and TNBC with BMs"): ("site-bm-her2neg", ["HR+/HER2-", "TNBC"], ["any"]),
        ("SITE-SPECIFIC MANAGEMENT", "LMD"): ("site-lmd", ["any"], ["any"]),
    },
}

# 쪽마다 반복되는 머리말. 소단원을 끊지 않는다.
RUNNING_HEADERS = {"E. de Azambuja et al.", "S. Loibl et al.", "Annals of Oncology", "Recommendations"}

# ESMO EBC에서 en dash가 e로 추출된 약제 조합 (설계 문서 §5)
DASH_FIXES = {
    "OFSetamoxifen": "OFS-tamoxifen", "OFSeAI": "OFS-AI",
    "anthracyclinee taxane": "anthracycline-taxane", "taxaneecarboplatin": "taxane-carboplatin",
}

# [I, A; ESMO-MCBS v2.0 score: 3; ESCAT score: I-A]
EVIDENCE = re.compile(r"\[(I{1,3}|IV|V),\s*([A-E])([^\]]*)\]")
MCBS = re.compile(r"MCBS v[\d.]+ score:\s*([A-C1-5])")
ESCAT = re.compile(r"ESCAT(?: score)?:\s*([IVX]+-[A-C])")
# 새 환자군을 말하는 불릿이면 앞의 "For patients ...:" 문맥이 끝난 것으로 본다
NEW_POPULATION = re.compile(r"\bpatients with\b|\bwomen\b|^(If|After progression|In the absence)\b")
FOOTNOTE = re.compile(r"^[a-z] [A-Z]")


def _evidence(text: str):
    match = EVIDENCE.search(text)
    if not match:
        return None
    extra = match.group(3)
    mcbs = MCBS.search(extra)
    escat = ESCAT.search(extra)
    return {
        "loe": match.group(1),
        "gor": match.group(2),
        "esmo_mcbs": mcbs.group(1) if mcbs else None,
        "escat": escat.group(1) if escat else None,
    }


def _ebc_line(text: str) -> list:
    """EBC는 소제목에 차수가 없어 문장에서 선행/보조를 판단한다."""
    t = text.lower()
    found = []
    if "(neo)adjuvant" in t:
        return ["neoadjuvant", "adjuvant"]
    if re.search(r"neoadjuvant|preoperative|primary systemic therapy|\bpst\b", t):
        found.append("neoadjuvant")
    if re.search(r"(?<!neo)adjuvant|residual (invasive )?disease|non-?pcr|after (completion of )?(surgery|locoregional)", t):
        found.append("adjuvant")
    return found or ["any"]


def _section_items(lines: list[str]) -> list[str]:
    """소단원 줄들을 권고 하나씩으로 묶는다. 그림·각주는 버리고, 하위 선택지와 끊긴 줄은 앞 권고에 붙인다."""
    items = []
    context = None  # "For patients who have previously received ChT:" 같은 문맥 불릿
    options_open = False  # 앞 권고가 "Options include:"처럼 ':'로 끝나 약제 목록을 받는 중
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("- "):
            # 그림 사이에서 끊긴 권고의 뒷부분만 붙인다 (소문자로 시작, 각주 아님)
            if items and line[0].islower() and not FOOTNOTE.match(line):
                items[-1] += " " + line
            continue

        body = line[2:].strip()
        is_sub = body.startswith(("■", "○", "o "))
        body = re.sub(r"^(■|○|o )\s*", "", body).strip()
        if not body:
            continue
        has_evidence = bool(EVIDENCE.search(body))

        if body.endswith(":") and not has_evidence and not is_sub and not body[0].islower():
            context, options_open = body, False
            continue
        if items and (body[0].islower() or is_sub or (options_open and not has_evidence)
                      or (not has_evidence and body.startswith("Options include"))):
            # 끊긴 문장, 하위 선택지(■, o), 약제 목록은 앞 권고에 붙인다
            items[-1] += " " + body
            options_open = options_open or items[-1].endswith(":")
            continue

        if context and NEW_POPULATION.search(body):
            context = None
        items.append(f"{context} {body}" if context else body)
        options_open = body.endswith(":")
    return [item.strip() for item in items if len(item.strip()) >= 40]


def parse_esmo_chunks(md_path: Path) -> list[dict]:
    stem = md_path.stem
    doc = DOCS[stem]
    sections = SECTIONS[stem]
    text = clean_text(md_path.read_text(encoding="utf-8"))
    for broken, fixed in DASH_FIXES.items():
        text = text.replace(broken, fixed)

    # 제목 줄로 소단원을 나눈다. 대문자 제목이 상위 제목, 그 밖은 소제목.
    blocks = []  # (상위 제목, 소제목, 줄 목록)
    parent, sub, lines = None, None, []
    for line in text.splitlines():
        header = re.match(r"^#+\s*(.+?)\s*$", line)
        if not header:
            lines.append(line)
            continue
        title = header.group(1)
        if title in RUNNING_HEADERS:
            continue
        blocks.append((parent, sub, lines))
        lines = []
        if title.isupper() and " " in title:  # TNBC, LMD 같은 짧은 대문자 제목은 소제목
            parent, sub = title, None
        else:
            sub = title
    blocks.append((parent, sub, lines))

    chunks = []
    seen = set()
    for parent, sub, block_lines in blocks:
        spec = sections.get((parent, sub)) or sections.get((None, sub))
        if spec is None or (parent, sub) in seen:
            continue
        seen.add((parent, sub))
        sec_slug, subtype, line = spec
        section = f"{parent} > {sub}" if parent and (parent, sub) in sections else sub

        for idx, item in enumerate(_section_items(block_lines), 1):
            chunks.append(make_chunk(
                chunk_id=f"esmo-{doc['slug']}-{doc['version']}-{sec_slug}-r{idx:02d}",
                source=doc["source"],
                version=doc["version"],
                section=section,
                url=doc["url"],
                chunk_kind="recommendation",
                text=item,
                setting=doc["setting"],
                subtype=subtype,
                line=line or _ebc_line(item),
                evidence=_evidence(item),
                copyright_notice=COPYRIGHT,
            ))
    return chunks


def process_all_esmo() -> list[dict]:
    esmo_md_dir = PARSED_MD_DIR / "esmo"
    missing = [stem for stem in DOCS if not (esmo_md_dir / f"{stem}.md").exists()]
    if missing:
        raise FileNotFoundError(f"{esmo_md_dir}에 없는 파일: {missing}. convert_pdf_to_md.py로 먼저 만드세요.")

    all_chunks = []
    for stem in DOCS:
        all_chunks.extend(parse_esmo_chunks(esmo_md_dir / f"{stem}.md"))

    output_json = CHUNKS_DIR / "esmo_chunks.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ESMO 청크 {len(all_chunks)}개 저장 -> {output_json}")
    return all_chunks


if __name__ == "__main__":
    process_all_esmo()
