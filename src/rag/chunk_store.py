# src/rag/chunk_store.py
# 지침 청크 JSON(data/chunks/)을 읽어 chunk_id로 찾는다. 부모 청크는 색인하지 않으므로 여기서 꺼낸다.
# 급여 청크(D)의 부모(L1 원칙·L2 단계)도 D의 청크 파일에서 꺼낸다 (D는 L3만 색인한다).
import json
from pathlib import Path

from .chunk_common import BASE_DIR, CHUNKS_DIR

GUIDELINE_CHUNK_FILES = ("esmo_chunks.json",)
# D가 만드는 급여 청크 파일 (src/reimbursement/index.py의 CURRENT). git에 올리지 않아 없을 수 있다
REIMBURSEMENT_CHUNKS = BASE_DIR / "data" / "reimbursement" / "chunks" / "reimbursement_chunks_current.jsonl"

_cache = {}


def load_guideline_chunks(chunks_dir: Path = CHUNKS_DIR) -> list[dict]:
    chunks = []
    for name in GUIDELINE_CHUNK_FILES:
        path = Path(chunks_dir) / name
        if path.exists():
            chunks.extend(json.loads(path.read_text(encoding="utf-8")))
    return chunks


def _by_id(chunks_dir: Path = CHUNKS_DIR) -> dict:
    key = str(chunks_dir)
    if key not in _cache:
        _cache[key] = {c["chunk_id"]: c for c in load_guideline_chunks(chunks_dir)}
    return _cache[key]


def get_chunk(chunk_id: str, chunks_dir: Path = CHUNKS_DIR):
    return _by_id(chunks_dir).get(chunk_id)


def get_parent(chunk: dict, chunks_dir: Path = CHUNKS_DIR):
    """권고 청크의 부모(소단원) 청크. 부모가 없으면 None."""
    parent_id = chunk.get("parent_id")
    return get_chunk(parent_id, chunks_dir) if parent_id else None


_reimb_cache = {}


def load_reimbursement_chunks(path: Path = REIMBURSEMENT_CHUNKS) -> list[dict]:
    """D의 급여 청크(JSONL). 파일이 없으면 빈 목록."""
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def get_reimbursement_parents(chunk: dict, path: Path = REIMBURSEMENT_CHUNKS) -> list[dict]:
    """급여 L3 청크의 부모들: 가까운 것부터 (L2 단계, L1 원칙). 파일이 없거나 부모가 없으면 빈 목록."""
    key = str(path)
    if key not in _reimb_cache:
        _reimb_cache[key] = {c["chunk_id"]: c for c in load_reimbursement_chunks(path)}
    by_id = _reimb_cache[key]
    parents, parent_id = [], chunk.get("parent_id")
    while parent_id and parent_id in by_id and len(parents) < 5:  # 고리 방지
        parents.append(by_id[parent_id])
        parent_id = by_id[parent_id].get("parent_id")
    return parents


def select_index_chunks(chunks: list[dict]) -> list[dict]:
    """색인할 청크: 다른 청크의 부모가 아닌 것 (권고 청크). 부모는 파일에만 두고 get_parent로 찾는다."""
    parent_ids = {c["parent_id"] for c in chunks if c.get("parent_id")}
    return [c for c in chunks if c["chunk_id"] not in parent_ids]
