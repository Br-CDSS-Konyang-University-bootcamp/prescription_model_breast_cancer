# tests/rag/test_chunks_schema.py
# 청크 JSON이 schemas/chunk.json을 통과하고 chunk_id가 겹치지 않는지 본다. qdrant·임베딩 모델 없이 돈다.
import json
import re
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
    assert "esmo_chunks.json" in names
    # ASCO 지침은 재사용 불가라 청크를 두지 않는다 (2026-10-20)
    assert not [n for n in names if n.startswith("asco")]


@pytest.mark.parametrize("path", CHUNK_FILES, ids=lambda p: p.name)
def test_chunks_match_schema(path):
    validator = Draft202012Validator(SCHEMA)
    errors = [(c.get("chunk_id"), e.message) for c in _load(path) for e in validator.iter_errors(c)]
    assert not errors, f"스키마 위반 {len(errors)}건: {errors[:5]}"


def test_chunk_ids_unique_across_files():
    counts = Counter(c["chunk_id"] for path in CHUNK_FILES for c in _load(path))
    duplicates = {cid: n for cid, n in counts.items() if n > 1}
    assert not duplicates, f"chunk_id 중복: {duplicates}"


def test_no_pdf_glyph_corruption():
    # PDF 기호 폰트가 그대로 남은 흔적: 제어문자 (ESMO EBC의 ≥·≤·•가 \x03~\x05로 나옴)
    patterns = {"제어문자": r"[\x00-\x08\x0b-\x1f]"}
    found = [(c["chunk_id"], name) for path in CHUNK_FILES for c in _load(path)
             for name, p in patterns.items() if re.search(p, c["text"])]
    assert not found, f"기호 깨짐: {found[:10]}"


def test_every_parent_id_points_to_a_section_chunk():
    by_id = {c["chunk_id"]: c for path in CHUNK_FILES for c in _load(path)}
    missing = [c["chunk_id"] for c in by_id.values() if c["parent_id"] and c["parent_id"] not in by_id]
    assert not missing, f"없는 부모를 가리킴: {missing[:5]}"
    for c in by_id.values():
        if c["parent_id"]:
            parent = by_id[c["parent_id"]]
            assert parent["chunk_kind"] == "section" and parent["parent_id"] is None


def test_parents_are_not_indexed_and_every_recommendation_has_a_parent():
    from src.rag.chunk_store import select_index_chunks
    chunks = [c for path in CHUNK_FILES for c in _load(path)]
    to_index = select_index_chunks(chunks)
    assert to_index and all(c["parent_id"] for c in to_index)


def test_every_chunk_has_page_numbers():
    # 출처 인용에 쪽이 필요하다 (CLAUDE.md: 모든 출력에 문서·쪽 또는 섹션·날짜)
    chunks = [c for path in CHUNK_FILES for c in _load(path)]
    missing = [c["chunk_id"] for c in chunks if c["page_start"] is None or c["page_end"] is None]
    assert not missing, f"쪽 번호 없음: {missing[:5]}"
    assert all(c["page_start"] <= c["page_end"] for c in chunks)
