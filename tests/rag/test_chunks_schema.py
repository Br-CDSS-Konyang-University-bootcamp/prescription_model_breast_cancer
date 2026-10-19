# tests/rag/test_chunks_schema.py
# 청크 JSON이 schemas/chunk.json을 통과하고 chunk_id가 겹치지 않는지 본다. qdrant·임베딩 모델 없이 돈다.
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

BASE_DIR = Path(__file__).resolve().parents[2]
CHUNK_FILES = sorted((BASE_DIR / "data" / "chunks").glob("*.json"))
SCHEMA = json.loads((BASE_DIR / "schemas" / "chunk.json").read_text(encoding="utf-8"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_chunk_files_exist():
    names = {p.name for p in CHUNK_FILES}
    assert {"asco_chunks_all.json", "esmo_chunks.json"} <= names


@pytest.mark.parametrize("path", CHUNK_FILES, ids=lambda p: p.name)
def test_chunks_match_schema(path):
    validator = Draft202012Validator(SCHEMA)
    errors = [(c.get("chunk_id"), e.message) for c in _load(path) for e in validator.iter_errors(c)]
    assert not errors, f"스키마 위반 {len(errors)}건: {errors[:5]}"


def test_chunk_ids_unique_across_files():
    counts = Counter(c["chunk_id"] for path in CHUNK_FILES for c in _load(path))
    duplicates = {cid: n for cid, n in counts.items() if n > 1}
    assert not duplicates, f"chunk_id 중복: {duplicates}"


def test_no_downloader_info_in_text():
    # ASCO PDF 머리말의 "Downloaded from ascopubs.org by ..."(내려받은 사람 정보)가 남으면 안 된다
    leaked = [c["chunk_id"] for path in CHUNK_FILES for c in _load(path) if "downloaded from" in c["text"].lower()]
    assert not leaked
