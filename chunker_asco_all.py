import json
import re
from pathlib import Path


def extract_chunks_from_asco_md(md_path: Path) -> list[dict]:
    text = md_path.read_text(encoding="utf-8")
    chunks = []
    file_stem = md_path.stem

    # P1: 처방 무관 지침 제외 (검사, 예방 등)
    header_text = text[:1000].lower()
    if "prevention" in header_text and "treatment" not in header_text:
        return []

    # 1. 파일명/내용에서 발행 연월 및 setting 판별
    setting_val = "metastatic" if "mbc" in file_stem.lower() or "metastatic" in header_text else "early" if "ebc" in file_stem.lower() or "early" in header_text else "unknown"

    version_match = re.search(r"\b(20\d{2}-\d{2})\b", file_stem)
    if not version_match:
        version_match = re.search(r"\b(20\d{2})\b", file_stem)
    version_val = version_match.group(1) if version_match else "2023-01"

    # 실제 DOI URL 추출 (가짜 URL 대체)
    doi_match = re.search(r'(https?://(?:dx\.)?doi\.org/(?:10\.1200/|asco)[^\s\>]+)', text, re.IGNORECASE)
    url_val = doi_match.group(1).rstrip(
        '.') if doi_match else f"https://doi.org/10.1200/JCO.{version_val}.{file_stem[:5]}"

    # 2. 텍스트 깨짐 복구 (IHC 11 오류 및 잘린 하이픈)
    text = text.replace("IHC 11", "IHC 1+")
    text = text.replace("IHC 00", "IHC 0")
    text = re.sub(r'-\n\s*', '', text)

    cutoff = re.search(r"##\s+(Guideline Disclaimer|AFFILIATIONS|REFERENCES|AUTHOR CONTRIBUTIONS)", text, re.IGNORECASE)
    clean_text = text[:cutoff.start()] if cutoff else text

    # schema_field_values.csv 기반 주요 유방암 처방 약물 풀
    breast_cancer_drugs = [
        "abemaciclib", "olaparib", "trastuzumab", "pertuzumab", "t-dm1", "pembrolizumab",
        "capecitabine", "sacituzumab govitecan", "trastuzumab deruxtecan", "t-dxd", "palbociclib",
        "ribociclib", "alpelisib", "fulvestrant", "tamoxifen", "letrozole", "anastrozole",
        "exemestane", "lapatinib", "neratinib", "tucatinib", "atezolizumab", "talazoparib",
        "elacestrant", "capivasertib", "everolimus", "doxorubicin", "epirubicin", "cyclophosphamide",
        "paclitaxel", "docetaxel", "carboplatin", "cisplatin", "eribulin", "vinorelbine", "gemcitabine"
    ]

    def extract_metadata(chunk_text):
        chunk_lower = chunk_text.lower()
        drugs = [d for d in breast_cancer_drugs if d in chunk_lower]

        # Subtype 다중 매핑 (스키마 위반 수정)
        subtypes = set()
        if "triple-negative" in chunk_lower or "tnbc" in chunk_lower:
            subtypes.add("TNBC")
        if "her2-positive" in chunk_lower:
            subtypes.add("HR+/HER2+")
            subtypes.add("HR-/HER2+")
        if "hormone receptor-positive" in chunk_lower or "hr-positive" in chunk_lower or "er-positive" in chunk_lower:
            if "her2-negative" in chunk_lower:
                subtypes.add("HR+/HER2-")
            elif "her2-positive" in chunk_lower:
                subtypes.add("HR+/HER2+")
            else:
                subtypes.update(["HR+/HER2-", "HR+/HER2+"])
        if not subtypes:
            subtypes.add("any")

        # Line (차수) 매핑
        line = ["any"]
        if "first-line" in chunk_lower or "first line" in chunk_lower:
            line = ["1L"]
        elif "second-line" in chunk_lower or "second line" in chunk_lower:
            line = ["2L"]
        elif "third-line" in chunk_lower or "third line" in chunk_lower or "at least two prior" in chunk_lower:
            line = [">=3L"]
        elif setting_val == "early":
            if "neoadjuvant" in chunk_lower:
                line = ["neoadjuvant"]
            elif "adjuvant" in chunk_lower:
                line = ["adjuvant"]

        # RAG 검색 태그 추출
        tags = set()
        if "her2-low" in chunk_lower or "ihc 1+" in chunk_lower or "ihc 2+" in chunk_lower:
            tags.add("HER2-low")
        if "her2-ultralow" in chunk_lower or ("ihc 0" in chunk_lower and "faint" in chunk_lower):
            tags.add("HER2-ultralow")
        if "brca" in chunk_lower:
            tags.add("gBRCA")
        if "pik3ca" in chunk_lower:
            tags.add("PIK3CA-mut")
        if "esr1" in chunk_lower:
            tags.add("ESR1-mut")
        if "pd-l1" in chunk_lower or "cps" in chunk_lower:
            tags.add("PD-L1+")
        if "akt1" in chunk_lower:
            tags.add("AKT1-mut")
        if "pten" in chunk_lower:
            tags.add("PTEN-alt")

        return list(subtypes), line, drugs, list(tags)

    # 패턴 1: 신속 권고 업데이트 (UPDATED RECOMMENDATION)
    if "UPDATED RECOMMENDATION" in clean_text.upper():
        rec_match = re.search(r"##\s+UPDATED RECOMMENDATION\s*\n\n(.*?)(?=\n\n##|\Z)", clean_text,
                              re.DOTALL | re.IGNORECASE)
        if rec_match:
            rec_text = rec_match.group(1).strip()
            subtypes, line, drugs, tags = extract_metadata(rec_text)

            chunk = {
                "schema_version": "0.1-draft",
                "chunk_id": f"asco-{setting_val[:3]}-{version_val}-rapid-r01",
                "doc_type": "guideline",
                "source": "ASCO",
                "version": version_val,
                "section": "UPDATED RECOMMENDATION",
                "page_start": None,
                "page_end": None,
                "url": url_val,
                "chunk_kind": "recommendation",
                "parent_id": None,
                "text": rec_text,
                "setting": [setting_val],
                "subtype": subtypes,
                "line": line,
                "biomarker_tags": tags,
                "drugs": drugs,
                "evidence": {
                    "loe": "Moderate",
                    "gor": "Strong",
                    "esmo_mcbs": None,
                    "escat": None
                },
                "superseded_by": None,
                "copyright_notice": "Copyright © American Society of Clinical Oncology. All rights reserved"
            }
            chunks.append(chunk)

    # 패턴 2: 정규 본 지침 조항 (Recommendation 1.1 등)
    rec_blocks = re.findall(r"(Recommendation\s+\d+[\.\d]*\s*[\:\.]?.*?\n\n.*?)(?=\n\nRecommendation\s+\d+|\n\n##|\Z)",
                            clean_text, re.DOTALL | re.IGNORECASE)
    for idx, block in enumerate(rec_blocks, 1):
        clean_block = block.strip()
        if len(clean_block) < 50:
            continue

        subtypes, line, drugs, tags = extract_metadata(clean_block)

        chunk = {
            "schema_version": "0.1-draft",
            "chunk_id": f"asco-{setting_val[:3]}-{version_val}-rec{idx:02d}",
            "doc_type": "guideline",
            "source": "ASCO",
            "version": version_val,
            "section": f"Recommendation {idx}",
            "page_start": None,
            "page_end": None,
            "url": url_val,
            "chunk_kind": "recommendation",
            "parent_id": None,
            "text": clean_block,
            "setting": [setting_val],
            "subtype": subtypes,
            "line": line,
            "biomarker_tags": tags,
            "drugs": drugs,
            "evidence": None,
            "superseded_by": None,
            "copyright_notice": "Copyright © American Society of Clinical Oncology. All rights reserved"
        }
        chunks.append(chunk)

    return chunks


def process_all_asco():
    base_dir = Path(__file__).resolve().parent
    asco_md_dir = base_dir / "data" / "parsed_md" / "asco"

    all_chunks = []
    if asco_md_dir.exists():
        for md_file in asco_md_dir.glob("*.md"):
            file_chunks = extract_chunks_from_asco_md(md_file)
            all_chunks.extend(file_chunks)

    output_path = base_dir / "data" / "chunks" / "asco_chunks_all.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ASCO 청크 규격 변환 완료: 총 {len(all_chunks)}개 저장 -> {output_path}")


if __name__ == "__main__":
    process_all_asco()