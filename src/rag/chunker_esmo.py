# src/rag/chunker_esmo.py
# 실행: team_project 폴더에서 python -m src.rag.chunker_esmo
# 입력: data/parsed_md/esmo/*.md (convert_pdf_to_md.py로 각자 만든다)
# 출력: data/chunks/esmo_chunks.json
import json
import re
from pathlib import Path

from .chunk_common import (PARSED_MD_DIR, CHUNKS_DIR, attach_parent, clean_text, fill_pages, make_chunk,
                           stable_key, strip_page_markers)

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

# 쪽 아래위 머리말 줄 (DOI와 쪽 번호, 권호, 저널 이름, 저자). 권고 문장 사이에 끼어 든다
RUNNING_FOOTER = re.compile(
    r"^\s*(\d+\s+)?https://doi\.org/10\.1016/j\.annonc\S*(\s+\d+)?\s*$"
    r"|^\s*Volume \d+ \S+ Issue \d+ \S+ \d{4}\s*$"
    r"|^\s*(E\. de Azambuja et al\.|S\. Loibl et al\.|#*\s*Annals of Oncology)\s*$",
    re.MULTILINE,
)

# 예전 변환(docling)에서 en dash가 e로 추출된 약제 조합 (설계 문서 §5). 새 변환에서는 기호 폰트 표로 고쳐진다
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
# 이 권고 뒤의 근거 없는 불릿은 약제 선택지 목록이다 ("Options include: ■ Fulvestrant—palbociclib ...")
SENTENCE_END = re.compile(r"[.:;!?)\]]\s*$")
OPTIONS_OPEN = re.compile(r":\s*$|Options include", re.IGNORECASE)


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


def _norm_title(title: str) -> str:
    """제목 비교용: 꾸밈 기호와 괄호 안쪽 공백을 지운다. 'Primary ( de novo ) stage IV BC' → 'Primary (de novo) stage IV BC'."""
    title = re.sub(r"[*_#]", "", title)
    title = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", title))
    return re.sub(r"\s+", " ", title).strip()


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


def _continue_sentence(item: list, piece: str):
    """끊긴 문장의 뒷부분을 본문과 ID용 문장 둘 다에 붙인다."""
    item[0] += " " + piece
    item[2] += " " + piece


def _section_items(lines: list[str]) -> list[tuple[str, str]]:
    """소단원 줄들을 권고 하나씩으로 묶는다. 그림·각주는 버리고, 하위 선택지와 끊긴 줄은 앞 권고에 붙인다.
    (ID용 첫 불릿 문장, 청크 본문) 목록을 돌려준다. ID용 문장에는 문맥 접두어와 뒤에 붙는 선택지가 들어가지 않는다."""
    items = []  # [첫 불릿 문장, 문맥, 본문]
    context = None  # "For patients who have previously received ChT:" 같은 문맥 불릿
    options_open = False  # 앞 권고가 "Options include:"처럼 ':'로 끝나 약제 목록을 받는 중
    sentence_open = False  # 앞 불릿이 마침표·괄호 없이 끝남 = PDF 줄바꿈에서 끊긴 문장 (변환기가 불릿 두 개로 냄)
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not line.startswith("- "):
            # 그림 사이에서 끊긴 권고의 뒷부분만 붙인다 (소문자로 시작, 각주 아님)
            if items and line[0].islower() and not FOOTNOTE.match(line):
                _continue_sentence(items[-1], line)
                sentence_open = not SENTENCE_END.search(line)
            continue

        body = line[2:].strip()
        is_sub = body.startswith(("■", "○", "o "))
        body = re.sub(r"^(■|○|o )\s*", "", body).strip()
        if not body:
            continue
        has_evidence = bool(EVIDENCE.search(body))

        if items and sentence_open and not is_sub:
            _continue_sentence(items[-1], body)
            sentence_open = not SENTENCE_END.search(body)
            continue
        sentence_open = not SENTENCE_END.search(body)
        if body.endswith(":") and not has_evidence and not is_sub and not body[0].islower():
            context, options_open = body, False
            continue
        if items and body[0].islower() and not is_sub and not items[-1][2].rstrip().endswith((".", "!", "?")):
            # 소문자로 시작하고 앞 권고가 마침표로 끝나지 않음 = 끊긴 문장.
            # 앞이 마침표로 끝났으면 "cT2-4 N0 ..."처럼 소문자로 시작하는 새 권고다
            _continue_sentence(items[-1], body)
            continue
        if items and (is_sub or (options_open and not has_evidence)
                      or (not has_evidence and body.startswith("Options include"))):
            # 하위 선택지(■, o)와 약제 목록은 앞 권고 본문에만 붙인다 (ID용 문장에는 넣지 않음)
            items[-1][2] += " " + body
            options_open = options_open or bool(OPTIONS_OPEN.search(items[-1][2]))
            continue

        if context and NEW_POPULATION.search(body):
            context = None
        items.append([body, context, body])
        options_open = bool(OPTIONS_OPEN.search(body))

    result = []
    for head, ctx, text in items:
        # ID용 문장은 첫 근거 등급 표시([I, A])까지만 쓴다. 그 뒤에 붙는 하위 선택지·인용 번호는 변환기마다 다르다
        first_evidence = EVIDENCE.search(head)
        if first_evidence:
            head = head[:first_evidence.end()]
        full = f"{ctx} {text}".strip() if ctx else text.strip()
        if len(full) >= 40:
            result.append((head, full))
    return result


def parse_esmo_chunks(md_path: Path) -> list[dict]:
    stem = md_path.stem
    doc = DOCS[stem]
    sections = SECTIONS[stem]
    raw = md_path.read_text(encoding="utf-8")
    text = clean_text(strip_page_markers(raw))
    for broken, fixed in DASH_FIXES.items():
        text = text.replace(broken, fixed)
    text = RUNNING_FOOTER.sub("", text)
    text = re.sub(r"\s*—\s*(?=\w)", "—", text)  # 줄바꿈으로 생긴 'taxane— bevacizumab'

    # 제목 줄로 소단원을 나눈다. 대문자 제목이 상위 제목, 그 밖은 소제목.
    # 변환기가 제목을 '#' 없이 굵은 글씨 줄로만 내는 경우가 있어, SECTIONS의 소제목과 같은 줄도 제목으로 본다.
    known_subs = {_norm_title(sub) for _, sub in sections}
    blocks = []  # (상위 제목, 소제목, 줄 목록)
    parent, sub, lines = None, None, []
    for line in text.splitlines():
        header = re.match(r"^#+\s*(.+?)\s*$", line)
        if header:
            title = _norm_title(header.group(1))
        elif _norm_title(line) in known_subs:
            title = _norm_title(line)
        else:
            lines.append(line)
            continue
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

        used = set()
        children = []
        for head, item in _section_items(block_lines):
            # 순서 번호 대신 권고 문장의 지문을 쓴다 (chunk_common.stable_key). 같은 소단원에 같은 문장이 또 있으면 -2를 붙인다
            chunk_id = f"esmo-{doc['slug']}-{doc['version']}-{sec_slug}-{stable_key(head)}"
            n = 2
            while chunk_id in used:
                chunk_id = f"esmo-{doc['slug']}-{doc['version']}-{sec_slug}-{stable_key(head)}-{n}"
                n += 1
            used.add(chunk_id)
            children.append(make_chunk(
                chunk_id=chunk_id,
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
        if children:
            # 부모 = 소단원 (예: esmo-mbc-2026-05-luminal-2l). 소단원 이름에서 만들어 바뀌지 않는다
            chunks.append(attach_parent(children, chunk_id=f"esmo-{doc['slug']}-{doc['version']}-{sec_slug}",
                                        section=section, heading=section))
            chunks.extend(children)
    fill_pages(chunks, raw)
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
