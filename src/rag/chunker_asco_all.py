# src/rag/chunker_asco_all.py
# 실행: team_project 폴더에서 python -m src.rag.chunker_asco_all
# 입력: data/parsed_md/asco/*.md (convert_pdf_to_md.py로 각자 만든다)
# 출력: data/chunks/asco_chunks_all.json
import json
import re
from pathlib import Path

from .chunk_common import PARSED_MD_DIR, CHUNKS_DIR, clean_text, parse_version, make_chunk

COPYRIGHT = "Copyright © American Society of Clinical Oncology. All rights reserved"
EBC = ["early", "locally_advanced"]
MBC = ["metastatic"]
HR_POS = ["HR+/HER2-"]
HER2_POS = ["HR+/HER2+", "HR-/HER2+"]

# 처방 지침 11개만 청킹한다. 검사·예방·대체된 지침 8개는 src/rag/rag_non_prescription_docs.md 참고.
# 파일 이름: (chunk_id용 짧은 이름, setting, 기본 subtype, 기본 line, DOI)
# subtype이 None이면 권고 문장에서 아형을 판단한다.
DOCS = {
    "asco_ebc_2021-08_parp_olaparib": ("olaparib", EBC, ["HR+/HER2-", "TNBC"], ["adjuvant"], "10.1200/JCO.21.01532"),
    "asco_ebc_2022-01_bisphosphonates_bone": ("bma", EBC, ["any"], ["adjuvant"], "10.1200/JCO.21.02647"),
    "asco_ebc_2022-04_abemaciclib_qa": ("abema", EBC, HR_POS, ["adjuvant"], "10.1200/OP.22.00140"),
    "asco_ebc_2022-04_biomarkers_adjuvant": ("biomarkers", EBC, None, ["adjuvant"], "10.1200/JCO.22.00069"),
    "asco_ebc_2022-04_pembrolizumab_tnbc": ("pembro", EBC, ["TNBC"], ["neoadjuvant", "adjuvant"], "10.1200/JCO.22.00503"),
    "asco_mbc_2021-07_chemo_targeted_guideline": ("chemo", MBC, None, ["any"], "10.1200/JCO.21.01374"),
    "asco_mbc_2021-07_endocrine_targeted": ("endo", MBC, HR_POS, ["any"], "10.1200/JCO.21.01392"),
    "asco_mbc_2022-05_her2_positive_systemic": ("her2", MBC, HER2_POS, ["any"], "10.1200/JCO.22.00519"),
    "asco_mbc_2022-08_chemo_targeted_trastuzumab_deruxtecan": ("tdxd", MBC, ["HR+/HER2-", "TNBC"], ["any"], "10.1200/JCO.22.01533"),
    "asco_mbc_2023-01_chemo_targeted_sacituzumab_govitecan": ("sg", MBC, HR_POS, ["any"], "10.1200/JCO.22.02807"),
    "asco_mbc_2024-03_capivasertib_fulvestrant": ("capi", MBC, HR_POS, ["any"], "10.1200/JCO.24.00248"),
}

# 아형을 문장에서 판단하는 문서에서, 아형 표현이 없을 때 쓰는 값.
# biomarkers_adjuvant는 Clinical Question 1이 ER-positive, HER2-negative 대상이다.
SUBTYPE_FALLBACK = {"biomarkers": HR_POS}

# 처방 문서 안의 검사 권고 (rag_non_prescription_docs.md §2)
SKIP_RECS = {"asco_mbc_2021-07_endocrine_targeted": {"2.1", "2.2"}}

# her2_positive_systemic은 권고 번호의 첫 자리가 차수다 (4.x는 뇌 전이)
HER2_LINE_BY_QUESTION = {"1": ["1L"], "2": ["2L"], "3": [">=3L"]}

REC_START = re.compile(r"^Recommendation\s*(\d+(?:\.\d+)*)\.?\s", re.IGNORECASE)
REC_HEADER = re.compile(r"^#+\s*Recommendation\s+(\d+(?:\.\d+)*)\.?\s*$", re.IGNORECASE)
RAPID_HEADER = re.compile(r"^#+\s*(?:\d{4}\s+)?UPDATED RECOMMENDATIONS?\s*$", re.IGNORECASE)
QUALIFYING_HEADER = re.compile(r"^#+\s*Qualifying Statements?\b", re.IGNORECASE)
QUESTION_HEADER = re.compile(r"^#+\s*Question:\s*(.+)$", re.IGNORECASE)
# 권고 뒤에 이어 붙이는 문단
REC_CONTINUATION = re.compile(r"^(- |Practical information|Qualifying statement|Note\b)", re.IGNORECASE)
# 표, 그림 설명 등 권고가 아닌 문단
NOT_TEXT = re.compile(r"^(TABLE|FIG|\||NOTE\.|Abbreviations|\(continued)", re.IGNORECASE)
EVIDENCE = re.compile(r"Evidence quality:\s*([A-Za-z/\-]+).*?Strength of recommendation:\s*([A-Za-z/\-]+)",
                      re.IGNORECASE | re.DOTALL)


def _evidence(text: str):
    match = EVIDENCE.search(text)
    if not match:
        return None
    return {"loe": match.group(1).capitalize(), "gor": match.group(2).capitalize(), "esmo_mcbs": None, "escat": None}


def _subtype(text: str, default, fallback=("any",)):
    if default is not None:
        return default
    t = text.lower()
    found = []
    hr_her2_pos = re.search(r"(hr|er|hormone receptor)-positive,?\s*(but\s+)?(and\s+)?her2-positive", t)
    if hr_her2_pos:
        found.append("HR+/HER2+")
    elif "her2-positive" in t:
        found.extend(HER2_POS)
    if not hr_her2_pos and re.search(r"hr-positive|hormone receptor-positive|er-positive", t):
        found.append("HR+/HER2-")
    if re.search(r"triple-?\s?negative|tnbc", t):
        found.append("TNBC")
    return found or list(fallback)


def _line(text: str, setting: list, default: list) -> list:
    t = text.lower()
    if setting == EBC:
        found = []
        if "neoadjuvant" in t or "preoperative" in t:
            found.append("neoadjuvant")
        if re.search(r"(?<!neo)adjuvant|postoperative|after surgery", t):
            found.append("adjuvant")
        return found or default
    found = []
    if re.search(r"first-?\s?line", t):
        found.append("1L")
    if re.search(r"second-?\s?line", t):
        found.append("2L")
    if re.search(r"third-?\s?line|at least two prior|two or more prior", t):
        found.append(">=3L")
    return found or default


def _text_quality(body: list[str]) -> tuple:
    """중복 권고 중 고를 때 쓰는 점수: 표·약어 목록이 끼지 않고, 근거 수준이 있고, 단어가 붙지 않은 쪽."""
    text = " ".join(body)
    has_noise = "Abbreviations:" in text or "|" in text
    space_ratio = text.count(" ") / max(len(text), 1)
    return (not has_noise, bool(EVIDENCE.search(text)), round(space_ratio, 2), len(text))


def _paragraphs(text: str) -> list[str]:
    paras = []
    for p in re.split(r"\n\s*\n", text):
        # 요약 상자에서는 권고 여러 개가 빈 줄 없이 이어져 나온다. "Recommendation 1.3. "이 새로 시작하는 곳에서 나눈다
        paras.extend(re.split(r"(?<=[.)])\s+(?=Recommendation\s*\d+(?:\.\d+)+\.\s)", p.strip()))
    return [p.strip() for p in paras if p.strip()]


def extract_chunks_from_asco_md(md_path: Path) -> list[dict]:
    stem = md_path.stem
    slug, setting, default_subtype, default_line, doi = DOCS[stem]
    version = parse_version(stem)
    url = f"https://doi.org/{doi}"
    id_prefix = f"asco-{stem.split('_')[1]}-{version}-{slug}"

    text = clean_text(md_path.read_text(encoding="utf-8"))
    # ≥, IHC 1+ 같은 기호 깨짐은 convert_pdf_to_md.py의 기호 폰트 표가 변환 때 고친다.
    # 여기서 "$ 26"을 ≥로 바꾸면 비용 표의 진짜 달러 금액까지 바뀌므로 하지 않는다.
    # 권고·질문·단서 블록만 모으므로 문서 뒤쪽을 잘라 내지 않는다.
    # (Guideline Disclaimer, AFFILIATIONS 뒤에 본문 권고나 Qualifying Statement가 오는 파일이 있다)
    paras = _paragraphs(text)

    # 문단을 (종류, 번호/제목, 문단 목록) 블록으로 묶는다
    blocks = []
    current = None

    def close():
        nonlocal current
        if current and current[2]:
            blocks.append(current)
        current = None

    for para in paras:
        if para.startswith("#"):
            m_rec = REC_HEADER.match(para)
            m_q = QUESTION_HEADER.match(para)
            if m_rec:
                close()
                current = ("rec", m_rec.group(1), [])
            elif RAPID_HEADER.match(para):
                close()
                current = ("rapid", None, [])
            elif QUALIFYING_HEADER.match(para):
                close()
                current = ("qualifying", None, [])
            elif m_q:
                close()
                current = ("question", m_q.group(1).strip(), [])
            elif current and current[0] == "rec" and re.match(r"^#+\s*Options include", para, re.IGNORECASE):
                current[2].append(para.lstrip("# "))
            else:
                close()
            continue

        m_rec = REC_START.match(para)
        if m_rec:
            close()
            current = ("rec", m_rec.group(1), [para])
        elif current is None or NOT_TEXT.match(para):
            close()
        elif current[0] == "rec" and current[2] and not REC_CONTINUATION.match(para):
            close()
        else:
            current[2].append(para)
    close()

    # 같은 권고가 요약 상자와 본문에 반복된다. 텍스트가 덜 깨진 쪽 하나만 쓴다
    best_rec = {}
    for i, (kind, key, body) in enumerate(blocks):
        if kind == "rec" and key not in SKIP_RECS.get(stem, set()):
            if key not in best_rec or _text_quality(body) > _text_quality(blocks[best_rec[key]][2]):
                best_rec[key] = i

    chunks = []
    counters = {"rapid": 0, "qualifying": 0, "question": 0}
    for i, (kind, key, body) in enumerate(blocks):
        if kind == "rapid" and any(REC_START.match(p) for p in body):
            continue  # 번호 있는 권고는 rec 블록으로 이미 잡힘
        if kind == "rec" and best_rec.get(key) != i:
            continue
        chunk_text = "\n\n".join(body).strip()
        if len(chunk_text) < 50:
            continue

        if kind == "rec":
            chunk_id = f"{id_prefix}-r{key}"
            section = f"Recommendation {key}"
            chunk_kind = "recommendation"
        else:
            counters[kind] += 1
            n = counters[kind]
            if kind == "rapid":
                chunk_id, section, chunk_kind = f"{id_prefix}-rapid-r{n:02d}", "UPDATED RECOMMENDATION", "recommendation"
            elif kind == "qualifying":
                chunk_id, section, chunk_kind = f"{id_prefix}-qs{n:02d}", "QUALIFYING STATEMENT", "section"
            else:
                chunk_id, section, chunk_kind = f"{id_prefix}-q{n:02d}", f"Question: {key}", "section"
                chunk_text = f"Question: {key}\n\n{chunk_text}"

        line = _line(chunk_text, setting, default_line)
        if slug == "her2" and kind == "rec":
            line = HER2_LINE_BY_QUESTION.get(key.split(".")[0], ["any"])

        chunks.append(make_chunk(
            chunk_id=chunk_id,
            source="ASCO",
            version=version,
            section=section,
            url=url,
            chunk_kind=chunk_kind,
            text=chunk_text,
            setting=setting,
            subtype=_subtype(chunk_text, default_subtype, SUBTYPE_FALLBACK.get(slug, ("any",))),
            line=line,
            evidence=_evidence(chunk_text) if kind != "question" else None,
            copyright_notice=COPYRIGHT,
        ))
    return chunks


def process_all_asco() -> list[dict]:
    asco_md_dir = PARSED_MD_DIR / "asco"
    missing = [stem for stem in DOCS if not (asco_md_dir / f"{stem}.md").exists()]
    if missing:
        raise FileNotFoundError(f"{asco_md_dir}에 없는 파일: {missing}. convert_pdf_to_md.py로 먼저 만드세요.")

    all_chunks = []
    for stem in DOCS:
        all_chunks.extend(extract_chunks_from_asco_md(asco_md_dir / f"{stem}.md"))

    output_path = CHUNKS_DIR / "asco_chunks_all.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ASCO 청크 {len(all_chunks)}개 저장 -> {output_path}")
    return all_chunks


if __name__ == "__main__":
    process_all_asco()
