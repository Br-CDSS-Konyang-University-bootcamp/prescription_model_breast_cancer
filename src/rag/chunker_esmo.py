import json
import re
from pathlib import Path


def parse_esmo_chunks(md_path: Path) -> list[dict]:
    text = md_path.read_text(encoding="utf-8")
    chunks = []

    # 1. 파일 이름(EBC/MBC)에 따라 메타데이터(버전, URL, 세팅) 동적 분기
    filename = md_path.stem.lower()
    if "mbc" in filename:
        doc_source = "ESMO-MBC"
        version = "2021-12"
        url = "https://doi.org/10.1016/j.annonc.2021.09.015"
        default_setting = "metastatic"
        default_line = "1L"  # 재발/전이성 기본 차수
    else:
        doc_source = "ESMO-EBC"
        version = "2024-02"
        url = "https://doi.org/10.1016/j.annonc.2023.11.016"
        default_setting = "early"
        default_line = "adjuvant"

    # 제외 소단원 필터링
    cutoff_match = re.search(r"##\s+(METHODOLOGY|ACKNOWLEDGEMENTS|REFERENCES)", text, re.IGNORECASE)
    clean_text = text[:cutoff_match.start()] if cutoff_match else text

    # 2. 스키마에 맞게 subtype을 리스트 배열로 정의 (HER2+를 두 아형으로 분리)
    sections = [
        {"header": "HR-positive, HER2-negative EBC", "subtypes": ["HR+/HER2-"]},
        {"header": "HER2-positive EBC", "subtypes": ["HR+/HER2+", "HR-/HER2+"]},
        {"header": "TNBC", "subtypes": ["TNBC"]}
    ]

    for sec in sections:
        pattern = rf"##\s+{re.escape(sec['header'])}\s*\n(.*?)(?=\n##|\Z)"
        sec_match = re.search(pattern, clean_text, re.DOTALL)
        if not sec_match:
            continue

        sec_body = sec_match.group(1).strip()

        # 3. 텍스트 정제: 제어문자(\x03 등) 삭제 및 잘린 하이픈 연결
        sec_body = re.sub(r'[\x00-\x08\x0B-\x1F\x7F]', '', sec_body)
        sec_body = re.sub(r'-\n\s*', '', sec_body)

        raw_items = re.split(r"\n-\s*[\*\-]?\s*", sec_body)

        chunk_idx = 1
        for item in raw_items:
            clean_item = item.strip()
            if len(clean_item) < 40:
                continue

            # LoE, GoR 등 근거 파싱
            loe_val, gor_val = None, None
            evidence_match = re.search(r"\[([I|V|X]+),\s*([A-E])(?:\;[^\]]+)?\]", clean_item)
            if evidence_match:
                loe_val = evidence_match.group(1)
                gor_val = evidence_match.group(2)

            # 대표 약물 태그
            drugs = []
            for drug_name in ["abemaciclib", "olaparib", "trastuzumab", "pertuzumab", "t-dm1", "pembrolizumab",
                              "capecitabine"]:
                if drug_name in clean_item.lower():
                    drugs.append(drug_name)

            # 4. 바이오마커 태그 자동 삽입
            biomarker_tags = []
            if "olaparib" in drugs or "brca" in clean_item.lower():
                biomarker_tags.append("gBRCA")
            if "HR+/HER2-" in sec["subtypes"]:
                biomarker_tags.append("HR+")
            if "HER2+" in sec["header"]:
                biomarker_tags.append("HER2+")

            # 고유 chunk_id 생성
            subtype_str = sec["subtypes"][0].lower().replace('/', '').replace('+', 'pos').replace('-', 'neg')
            chunk_id = f"{doc_source.lower()}-{version}-{subtype_str}-r{chunk_idx:02d}"

            chunk = {
                "schema_version": "0.1-draft",
                "chunk_id": chunk_id,
                "doc_type": "guideline",
                "source": doc_source,
                "version": version,
                "section": sec["header"],
                "page_start": None,
                "page_end": None,
                "url": url,
                "chunk_kind": "recommendation",
                "parent_id": None,
                "text": clean_item,
                "setting": [default_setting],
                "subtype": sec["subtypes"],  # 수정됨: 스키마 호환 배열
                "line": [default_line],
                "biomarker_tags": biomarker_tags,
                "drugs": drugs,
                "evidence": {
                    "loe": loe_val,
                    "gor": gor_val,
                    "esmo_mcbs": "A" if "ESMO-MCBS" in clean_item else None,
                    "escat": "I-A" if "ESCAT" in clean_item else None
                },
                "superseded_by": None,
                "copyright_notice": "Copyright © European Society for Medical Oncology. All rights reserved"
            }
            chunks.append(chunk)
            chunk_idx += 1

    return chunks


if __name__ == "__main__":
    current_dir = Path(__file__).resolve().parent.parent.parent
    md_files = list((current_dir / "data" / "parsed_md" / "esmo").glob("*.md"))

    all_esmo_chunks = []
    for md_file in md_files:
        all_esmo_chunks.extend(parse_esmo_chunks(md_file))

    # 수정됨: 스크립트 실행 위치가 어디든 프로젝트 루트의 data/chunks/ 경로에 올바르게 저장되도록 보완
    output_json = current_dir / "data" / "chunks" / "esmo_chunks.json"

    # 만약 data/chunks 폴더가 없다면 생성
    output_json.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(all_esmo_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ESMO 청크 규격 변환 완료: 총 {len(all_esmo_chunks)}개 저장 -> {output_json}")