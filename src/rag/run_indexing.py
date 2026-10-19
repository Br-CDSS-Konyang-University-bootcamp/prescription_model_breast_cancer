# src/rag/run_indexing.py
# 실행: team_project 폴더에서 python -m src.rag.run_indexing
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from src.rag.chunk_store import GUIDELINE_CHUNK_FILES, load_guideline_chunks, select_index_chunks
from src.rag.indexer import init_collection, index_chunks, delete_guideline_chunks, close_indexer


def main():
    base_dir = Path(__file__).resolve().parents[2]  # team_project
    chunks_dir = base_dir / "data" / "chunks"  # <- data/chunks/ 지정

    # 1. 컬렉션은 지우지 않는다 (D의 급여 청크 보존). 지침 청크만 지우고 다시 넣는다.
    init_collection(force_recreate=False)

    all_chunks = load_guideline_chunks(chunks_dir)
    print(f"[로드] 지침 청크 {len(all_chunks)}건 ({', '.join(GUIDELINE_CHUNK_FILES)})")

    # 2. 스키마 검증 후 색인 실행
    if all_chunks:
        schema = json.loads((base_dir / "schemas" / "chunk.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = [(c.get("chunk_id"), e.message) for c in all_chunks for e in validator.iter_errors(c)]
        if errors:
            raise ValueError(f"schemas/chunk.json 위반 {len(errors)}건: {errors[:5]}")
        to_index = select_index_chunks(all_chunks)
        print(f"[색인] 권고 청크 {len(to_index)}건 (부모 청크 {len(all_chunks) - len(to_index)}건은 파일에만 둠)")
        try:
            delete_guideline_chunks()
            index_chunks(to_index)
        finally:
            close_indexer()
    else:
        print("[에러] 색인할 청크 JSON 파일이 없습니다.")


if __name__ == "__main__":
    main()