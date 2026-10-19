# src/rag/chunk_store.py
# 지침 청크 JSON(data/chunks/)을 읽어 chunk_id로 찾는다. 부모 청크는 색인하지 않으므로 여기서 꺼낸다.
import json
from pathlib import Path

from .chunk_common import CHUNKS_DIR

GUIDELINE_CHUNK_FILES = ("asco_chunks_all.json", "esmo_chunks.json")

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


def select_index_chunks(chunks: list[dict]) -> list[dict]:
    """색인할 청크: 다른 청크의 부모가 아닌 것 (권고 청크). 부모는 파일에만 두고 get_parent로 찾는다."""
    parent_ids = {c["parent_id"] for c in chunks if c.get("parent_id")}
    return [c for c in chunks if c["chunk_id"] not in parent_ids]
