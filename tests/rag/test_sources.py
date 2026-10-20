# tests/rag/test_sources.py
# 지침 원문 출처 기록(data/guidelines/sources.csv)이 청커의 문서 목록과 맞는지, 지문 확인이 맞게 되는지 본다
import csv
from pathlib import Path

from src.rag.chunker_esmo import DOCS
from src.rag.convert_pdf_to_md import SOURCES_CSV, check_source


def _rows():
    with open(SOURCES_CSV, encoding="utf-8-sig", newline="") as f:
        return {r["file"]: r for r in csv.DictReader(f)}


def test_every_chunked_document_has_a_source_record():
    rows = _rows()
    for stem, doc in DOCS.items():
        row = rows.get(f"{stem}.pdf")
        assert row, stem
        assert row["version"] == doc["version"] and doc["url"].endswith(row["doi"]), stem
        assert len(row["sha256"]) == 64 and row["license_basis"], stem


def test_check_source(tmp_path):
    pdf = tmp_path / "esmo_mbc_2026-05.pdf"
    pdf.write_bytes(b"not the real pdf")
    assert check_source(pdf) == "mismatch"
    other = tmp_path / "esmo_other_2026-01.pdf"
    other.write_bytes(b"x")
    assert check_source(other) == "unlisted"
    assert check_source(pdf, sources_csv=Path(tmp_path / "none.csv")) == "unlisted"
