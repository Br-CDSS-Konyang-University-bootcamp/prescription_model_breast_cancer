# src/rag/run_indexing.py
# 실행: team_project 폴더에서 python -m src.rag.run_indexing
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from src.rag.indexer import init_collection, index_chunks, delete_guideline_chunks, close_indexer


def main():
    base_dir = Path(__file__).resolve().parents[2]  # team_project
    chunks_dir = base_dir / "data" / "chunks"  # <- data/chunks/ 지정

    # 1. 컬렉션은 지우지 않는다 (D의 급여 청크 보존). 지침 청크만 지우고 다시 넣는다.
    init_collection(force_recreate=False)

    all_chunks = []

    # ASCO 청크 파일 로드
    asco_json = chunks_dir / "asco_chunks_all.json"
    if asco_json.exists():
        with open(asco_json, "r", encoding="utf-8") as f:
            asco_data = json.load(f)
            all_chunks.extend(asco_data)
            print(f"[로드] ASCO 청크 {len(asco_data)}건")
    else:
        print(f"[주의] {asco_json} 파일이 없습니다.")

    # ESMO 청크 파일 로드
    esmo_json = chunks_dir / "esmo_chunks.json"
    if esmo_json.exists():
        with open(esmo_json, "r", encoding="utf-8") as f:
            esmo_data = json.load(f)
            all_chunks.extend(esmo_data)
            print(f"[로드] ESMO 청크 {len(esmo_data)}건")
    else:
        print(f"[주의] {esmo_json} 파일이 없습니다.")

    # 2. 스키마 검증 후 색인 실행
    if all_chunks:
        schema = json.loads((base_dir / "schemas" / "chunk.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = [(c.get("chunk_id"), e.message) for c in all_chunks for e in validator.iter_errors(c)]
        if errors:
            raise ValueError(f"schemas/chunk.json 위반 {len(errors)}건: {errors[:5]}")
        try:
            delete_guideline_chunks()
            index_chunks(all_chunks)
        finally:
            close_indexer()
    else:
        print("[에러] 색인할 청크 JSON 파일이 없습니다.")


if __name__ == "__main__":
    main()