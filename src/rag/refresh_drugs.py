# src/rag/refresh_drugs.py
# 실행: team_project 폴더에서 python -m src.rag.refresh_drugs  (--check: 바꾸지 않고 바뀔 청크 수만)
# 지침 청크 JSON의 drugs 칸을 저장된 본문으로 다시 계산한다. 약 사전(drug_names.csv·drug_classes.csv)이나 계열 풀기 규칙
# (chunk_common.CLASS_TERMS)을 바꾼 뒤, PDF 없이 청크 파일만 고칠 때 쓴다. chunker_esmo·algorithm_esmo를 다시 돌린 것과 같은 값이다:
# 권고·소단원 청크와 그림 부모는 본문 전체, 그림 경로는 경로 글(제목·각주 뺌, 요법 줄임말을 약 이름으로 펼침)로 찾는다.
import argparse
import json
import re

from .algorithm_esmo import OUTPUT_JSON as ALGORITHM_JSON, REGIMEN_ABBREVIATIONS, review_path_text
from .chunk_common import CHUNKS_DIR, find_drugs

ESMO_JSON = CHUNKS_DIR / "esmo_chunks.json"


def chunk_drugs(chunk: dict) -> list[str]:
    if chunk.get("chunk_kind") == "algorithm" and chunk.get("parent_id"):
        text = review_path_text(chunk)
        for pattern, names in REGIMEN_ABBREVIATIONS.items():
            text = re.sub(pattern, names, text)
        return find_drugs(text)
    return find_drugs(chunk["text"])


def refresh(chunks: list[dict]) -> int:
    """drugs를 다시 계산해 바꾼 청크 수를 돌려준다."""
    changed = 0
    for c in chunks:
        drugs = chunk_drugs(c)
        if drugs != c.get("drugs"):
            c["drugs"] = drugs
            changed += 1
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(description="지침 청크 JSON의 drugs 칸을 저장된 본문으로 다시 계산")
    ap.add_argument("--check", action="store_true", help="파일을 바꾸지 않고 바뀔 청크 수만 출력")
    args = ap.parse_args(argv)
    for path in (ESMO_JSON, ALGORITHM_JSON):
        chunks = json.loads(path.read_text(encoding="utf-8"))
        changed = refresh(chunks)
        if changed and not args.check:
            path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: 청크 {len(chunks)}개 중 drugs가 바뀌는 청크 {changed}개" + (" (저장 안 함)" if args.check else ""))


if __name__ == "__main__":
    main()
