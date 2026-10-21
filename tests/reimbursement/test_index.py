"""공용 색인 연결. 실제 Qdrant·임베딩 모델은 쓰지 않는다 (가짜 rag 모듈)."""
import json
from types import SimpleNamespace

import pytest

from src.reimbursement import index as ix
from src.reimbursement.chunks import _base


def _chunk(cid: str, source_type: str = "baseline") -> dict:
    return _base(cid, "HIRA-booklet", "2026-10-01", "9. 유방암 > 연번 1", "연번 1\n항암요법: anastrozole",
                 "reimbursement_condition", ["metastatic"], ["HR+/HER2-"], ["1L"], ["anastrozole"],
                 {"source_type": source_type, "notice_no": "제2026-210호", "effective_from": "2026-10-01"})


class FakeRag:
    """with_replace=False면 replace_doc_type이 없는 예전 src/rag."""
    def __init__(self, with_delete: bool = True, with_replace: bool = False, removed: int = 0):
        self.calls = []
        if with_delete:
            self.delete_by_doc_type = lambda t: self.calls.append(("delete", t))
        if with_replace:
            def replace(t, chunks):
                self.calls.append(("replace", t, [c["chunk_id"] for c in chunks]))
                return {"indexed": len(chunks), "removed": removed}
            self.replace_doc_type = replace

    def index_chunks(self, chunks):
        self.calls.append(("index", [c["chunk_id"] for c in chunks]))

    def close_indexer(self):
        self.calls.append(("close",))


def test_deletes_old_reimbursement_points_then_indexes():
    rag = FakeRag()
    rep = ix.index_reimbursement([_chunk("a"), _chunk("b"), _chunk("p", "preview")], rag)
    assert rag.calls == [("delete", "reimbursement"), ("index", ["a", "b"]), ("close",)]
    assert rep.indexed == 2 and rep.skipped == {"검토중(preview)": 1}


def test_uses_replace_doc_type_when_available():
    """C1 결정: 새것을 먼저 넣고 옛 급여 점만 지우는 replace_doc_type을 쓴다 (지운 뒤 넣기는 하지 않음)."""
    rag = FakeRag(with_replace=True, removed=3)
    rep = ix.index_reimbursement([_chunk("a"), _chunk("b"), _chunk("p", "preview")], rag)
    assert rag.calls == [("replace", "reimbursement", ["a", "b"]), ("close",)]
    assert rep.indexed == 2 and rep.removed == 3


def test_replace_alone_is_enough():
    """replace_doc_type만 있어도 된다 (delete_by_doc_type이 없어도). index_chunks는 따로 부르지 않는다."""
    rag = FakeRag(with_delete=False, with_replace=True)
    ix.index_reimbursement([_chunk("a")], rag)
    assert [c[0] for c in rag.calls] == ["replace", "close"]


def test_replace_failure_closes_and_leaves_registry(tmp_path):
    """넣다가 실패하면 C 쪽에서 옛 점이 남고, D는 잠금을 풀고 장부를 바꾸지 않는다."""
    from datetime import date
    from src.reimbursement.registry import Registry
    reg = Registry(tmp_path / "r.db")
    doc = reg.add_document("booklet", file_hash="b", file_name="공고책자_20261001.pdf", effective_date=date(2026, 10, 1))
    reg.set_status(doc, "parsed")
    rag = FakeRag(with_replace=True)

    def boom(t, chunks):
        raise RuntimeError("model download failed")
    rag.replace_doc_type = boom
    with pytest.raises(RuntimeError):
        ix.index_reimbursement([_chunk("a")], rag, registry=reg)
    assert rag.calls[-1] == ("close",)
    assert reg.conn.execute("SELECT status FROM documents").fetchone()["status"] == "parsed"
    reg.close()


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


def _db(tmp_path, name="qdrant_db"):
    d = tmp_path / name
    d.mkdir()
    (d / "meta.json").write_text("{}", encoding="utf-8")
    return d


def test_index_only_when_changed(tmp_path):
    """회의 5: 마지막 색인 때와 청크가 같으면 색인하지 않는다 (검색 DB를 잠그지 않음)."""
    stamp, db = tmp_path / "last_indexed.json", _db(tmp_path)
    rag = FakeRag(with_replace=True)
    assert ix.index_if_changed([_chunk("a"), _chunk("b")], rag, stamp=stamp, qdrant_dir=db).indexed == 2
    assert ix.index_if_changed([_chunk("b"), _chunk("a")], rag, stamp=stamp, qdrant_dir=db) is None  # 순서만 다름
    assert [c[0] for c in rag.calls] == ["replace", "close"]
    changed = _chunk("a")
    changed["text"] += "\n변경"
    assert ix.index_if_changed([changed, _chunk("b")], rag, stamp=stamp, qdrant_dir=db).indexed == 2
    assert [c[0] for c in rag.calls].count("replace") == 2


def test_new_db_reindexes_same_chunks(tmp_path):
    """청크 파일·기록을 다른 폴더로 복사했거나 DB를 새로 만들면, 청크가 같아도 빈 DB이므로 다시 색인한다."""
    stamp = tmp_path / "last_indexed.json"
    rag = FakeRag(with_replace=True)
    ix.index_if_changed([_chunk("a")], rag, stamp=stamp, qdrant_dir=_db(tmp_path, "db1"))
    assert ix.index_if_changed([_chunk("a")], rag, stamp=stamp, qdrant_dir=_db(tmp_path, "db2")).indexed == 1
    assert ix.index_if_changed([_chunk("a")], rag, stamp=stamp, qdrant_dir=tmp_path / "없는_db").indexed == 1
    old = {"digest": ix.digest([_chunk("a")]), "indexed": 1}                  # db 칸이 없는 예전 기록
    stamp.write_text(json.dumps(old), encoding="utf-8")
    assert ix.index_if_changed([_chunk("a")], rag, stamp=stamp, qdrant_dir=_db(tmp_path, "db3")).indexed == 1


def test_failed_index_keeps_old_stamp(tmp_path):
    """색인이 실패하면 해시를 남기지 않아 다음 실행 때 다시 색인한다."""
    stamp = tmp_path / "last_indexed.json"
    rag = FakeRag(with_replace=True)

    def boom(t, chunks):
        raise RuntimeError("model download failed")
    rag.replace_doc_type = boom
    with pytest.raises(RuntimeError):
        ix.index_if_changed([_chunk("a")], rag, stamp=stamp)
    assert not stamp.exists()


def test_does_not_close_search():
    """검색과 색인은 Qdrant 연결 하나를 같이 쓴다. 색인이 검색 연결을 닫으면 진행 중인 검색이 끊기므로 부르지 않는다."""
    rag = FakeRag(with_replace=True)
    rag.close_searcher = lambda: rag.calls.append(("close_search",))
    ix.index_reimbursement([_chunk("a")], rag)
    assert [c[0] for c in rag.calls] == ["replace", "close"]


def test_dry_run_needs_no_rag():
    rep = ix.index_reimbursement([_chunk("a")], SimpleNamespace(), dry_run=True)
    assert rep.dry_run and rep.indexed == 1
