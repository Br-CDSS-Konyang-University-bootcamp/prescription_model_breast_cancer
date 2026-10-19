"""공용 색인 연결. 실제 Qdrant·임베딩 모델은 쓰지 않는다 (가짜 rag 모듈)."""
from types import SimpleNamespace

import pytest

from src.reimbursement import index as ix
from src.reimbursement.chunks import _base


def _chunk(cid: str, source_type: str = "baseline") -> dict:
    return _base(cid, "HIRA-booklet", "2026-10-01", "9. 유방암 > 연번 1", "연번 1\n항암요법: anastrozole",
                 "reimbursement_condition", ["metastatic"], ["HR+/HER2-"], ["1L"], ["anastrozole"],
                 {"source_type": source_type, "notice_no": "제2026-210호", "effective_from": "2026-10-01"})


class FakeRag:
    def __init__(self, with_delete: bool = True):
        self.calls = []
        if with_delete:
            self.delete_by_doc_type = lambda t: self.calls.append(("delete", t))

    def index_chunks(self, chunks):
        self.calls.append(("index", [c["chunk_id"] for c in chunks]))

    def close_indexer(self):
        self.calls.append(("close",))


def test_deletes_old_reimbursement_points_then_indexes():
    rag = FakeRag()
    rep = ix.index_reimbursement([_chunk("a"), _chunk("b"), _chunk("p", "preview")], rag)
    assert rag.calls == [("delete", "reimbursement"), ("index", ["a", "b"]), ("close",)]
    assert rep.indexed == 2 and rep.skipped == {"검토중(preview)": 1}


def test_only_l3_rows_are_indexed():
    """설계 §0.1: 벡터는 L3 요법 행만. L1·L2(section)는 청크 파일에서 parent_id로 찾는다."""
    sec = _chunk("sec")
    sec["chunk_kind"] = "section"
    rag = FakeRag()
    rep = ix.index_reimbursement([_chunk("a"), sec], rag)
    assert ("index", ["a"]) in rag.calls and rep.skipped == {"L1·L2 청크 (부모 문맥, 색인 안 함)": 1}


def test_success_marks_registry(tmp_path):
    """색인이 성공하면 그 책자는 indexed, 예전 indexed 책자는 superseded."""
    from datetime import date
    from src.reimbursement.registry import Registry
    reg = Registry(tmp_path / "r.db")
    old = reg.add_document("booklet", file_hash="a", file_name="공고책자_20260901.pdf", effective_date=date(2026, 9, 1))
    new = reg.add_document("booklet", file_hash="b", file_name="공고책자_20261001.pdf", effective_date=date(2026, 10, 1))
    reg.set_status(old, "indexed")
    reg.set_status(new, "parsed")
    ix.index_reimbursement([_chunk("a")], FakeRag(), registry=reg)
    status = {r["id"]: r["status"] for r in reg.conn.execute("SELECT id, status FROM documents")}
    assert status == {old: "superseded", new: "indexed"}
    assert reg.current_booklet()["id"] == new
    reg.close()


def test_failure_leaves_registry(tmp_path):
    from datetime import date
    from src.reimbursement.registry import Registry
    reg = Registry(tmp_path / "r.db")
    doc = reg.add_document("booklet", file_hash="b", file_name="공고책자_20261001.pdf", effective_date=date(2026, 10, 1))
    reg.set_status(doc, "parsed")
    with pytest.raises(ix.RagNotReady):
        ix.index_reimbursement([_chunk("a")], FakeRag(with_delete=False), registry=reg)
    assert reg.conn.execute("SELECT status FROM documents").fetchone()["status"] == "parsed"
    reg.close()


def test_include_preview():
    rag = FakeRag()
    ix.index_reimbursement([_chunk("a"), _chunk("p", "preview")], rag, include_preview=True)
    assert ("index", ["a", "p"]) in rag.calls


def test_refuses_without_delete_function():
    """지우는 함수가 없으면 옛 기준이 남으므로 색인하지 않는다."""
    rag = FakeRag(with_delete=False)
    with pytest.raises(ix.RagNotReady, match="delete_by_doc_type"):
        ix.index_reimbursement([_chunk("a")], rag)
    assert rag.calls == []


def test_refuses_invalid_chunks():
    bad = _chunk("a")
    bad["subtype"] = ["HER2+"]                     # 스키마 허용값 아님
    with pytest.raises(ValueError, match="스키마"):
        ix.index_reimbursement([bad], FakeRag())


def test_closes_even_when_index_fails():
    rag = FakeRag()

    def boom(chunks):
        raise RuntimeError("lock")
    rag.index_chunks = boom
    with pytest.raises(RuntimeError):
        ix.index_reimbursement([_chunk("a")], rag)
    assert rag.calls[-1] == ("close",)


def test_dry_run_needs_no_rag():
    rep = ix.index_reimbursement([_chunk("a")], SimpleNamespace(), dry_run=True)
    assert rep.dry_run and rep.indexed == 1
