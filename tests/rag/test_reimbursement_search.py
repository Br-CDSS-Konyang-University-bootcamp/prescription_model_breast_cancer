# tests/rag/test_reimbursement_search.py
# 급여 검색(search_reimbursement)을 메모리 Qdrant와 가짜 급여 청크로 본다. 규칙은 D와 정한 것 (2026-10-20)
import json
import sys
import types

import pytest

pytest.importorskip("qdrant_client")

from qdrant_client import QdrantClient  # noqa: E402


class FakeModel:
    def encode(self, texts, show_progress_bar=False):
        import numpy as np
        return np.ones((len(texts), 1024)) if isinstance(texts, list) else np.ones(1024)


def _chunk(cid, drugs, setting, line, source_type="baseline", effective_from="2026-10-01", kind="reimbursement_condition",
           parent_id="hira-booklet-20261001-bc-l2", superseded_by=None):
    return {"chunk_id": cid, "doc_type": "reimbursement", "chunk_kind": kind, "text": cid, "drugs": drugs,
            "setting": setting, "line": line, "subtype": ["any"], "parent_id": parent_id,
            "superseded_by": superseded_by, "source": "HIRA-booklet", "version": "2026-10-01",
            "reimbursement": {"source_type": source_type, "notice_no": "제2026-1호", "effective_from": effective_from}}


EARLY = ["early", "locally_advanced"]
CHUNKS = [
    _chunk("ac-adjuvant", ["doxorubicin", "cyclophosphamide"], EARLY, ["adjuvant"]),
    _chunk("ac-neoadjuvant", ["doxorubicin", "cyclophosphamide"], EARLY, ["neoadjuvant"]),
    _chunk("ac-palliative", ["doxorubicin", "cyclophosphamide"], ["metastatic"], ["1L", "2L", ">=3L"]),
    _chunk("ana-lhrh", ["anastrozole", "goserelin", "leuprolide"], ["metastatic"], ["1L"]),
    _chunk("fec-then-ptd", ["fluorouracil", "epirubicin", "cyclophosphamide", "pertuzumab", "trastuzumab",
                            "docetaxel"], EARLY, ["neoadjuvant"]),
    _chunk("preview-row", ["doxorubicin", "cyclophosphamide"], ["metastatic"], ["1L"], source_type="preview"),
    _chunk("old-row", ["doxorubicin", "cyclophosphamide"], ["metastatic"], ["1L"], superseded_by="ac-palliative"),
    _chunk("future-row", ["doxorubicin", "cyclophosphamide"], ["metastatic"], ["1L"], effective_from="2027-01-01"),
]
PARENTS = [
    _chunk("hira-booklet-20261001-bc-l2", [], ["any"], ["any"], kind="section", parent_id="hira-booklet-20261001-bc-l1"),
    _chunk("hira-booklet-20261001-bc-l1", [], ["any"], ["any"], kind="section", parent_id=None),
]


@pytest.fixture
def reimb(monkeypatch, tmp_path):
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        monkeypatch.setitem(sys.modules, "sentence_transformers",
                            types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import client as rag_client
    from src.rag import chunk_store, indexer, reimbursement_search

    monkeypatch.setattr(rag_client, "_client", QdrantClient(":memory:"))
    monkeypatch.setattr(rag_client, "_model", FakeModel())
    indexer.init_collection()
    indexer.index_chunks(CHUNKS)  # D처럼 L3만 색인한다
    jsonl = tmp_path / "reimbursement_chunks_current.jsonl"
    jsonl.write_text("\n".join(json.dumps(c) for c in CHUNKS + PARENTS), encoding="utf-8")
    real = chunk_store.get_reimbursement_parents
    monkeypatch.setattr(reimbursement_search, "get_reimbursement_parents", lambda c: real(c, path=jsonl))
    yield reimbursement_search
    rag_client._client = None


def _ids(results):
    return [r["chunk_id"] for r in results]


def test_all_rows_with_the_drugs_are_returned_and_filtered_by_setting_and_line(reimb):
    # 같은 약 조합이 여러 행(선행·보조·고식적)에 있다. 거르지 않으면 모두, setting·line을 주면 맞는 행만
    rows = reimb.search_reimbursement(["Doxorubicin", "cyclophosphamide"], as_of="2026-10-20")
    assert set(_ids(rows)) == {"ac-adjuvant", "ac-neoadjuvant", "ac-palliative"}
    assert _ids(reimb.search_reimbursement(["doxorubicin", "cyclophosphamide"], setting="early", line="adjuvant",
                                           as_of="2026-10-20")) == ["ac-adjuvant"]
    assert _ids(reimb.search_reimbursement(["doxorubicin", "cyclophosphamide"], setting="metastatic", line="2L",
                                           as_of="2026-10-20")) == ["ac-palliative"]


def test_candidate_drugs_only_need_to_be_contained(reimb):
    # 계열 펼침(LHRH agonist → goserelin, leuprolide)과 순차 요법 때문에 청크 drugs가 후보보다 많다
    rows = reimb.search_reimbursement(["anastrozole", "Zoladex"], as_of="2026-10-20")
    assert _ids(rows) == ["ana-lhrh"] and rows[0]["extra_drugs"] == ["leuprolide"]
    assert rows[0]["matched_drugs"] == ["anastrozole", "goserelin"]
    assert _ids(reimb.search_reimbursement(["pertuzumab", "trastuzumab", "docetaxel"], as_of="2026-10-20")) == \
        ["fec-then-ptd"]
    assert reimb.search_reimbursement(["anastrozole", "palbociclib"], as_of="2026-10-20") == []  # 기준 없음


def test_preview_superseded_and_not_yet_effective_rows_are_left_out(reimb):
    ids = _ids(reimb.search_reimbursement(["doxorubicin", "cyclophosphamide"], setting="metastatic", line="1L",
                                          as_of="2026-10-20"))
    assert ids == ["ac-palliative"]
    later = _ids(reimb.search_reimbursement(["doxorubicin", "cyclophosphamide"], setting="metastatic", line="1L",
                                            as_of="2027-02-01"))
    assert set(later) == {"ac-palliative", "future-row"}
    # effective_from은 책자 날짜가 아니라 그 행의 마지막 공고 시행일이다 (실제 청크는 2020-06-01 등).
    # 가짜 청크는 모두 2026-10-01로 두었으므로, 기준일이 그보다 앞이면 어느 행도 아직 시행 전이다
    assert reimb.search_reimbursement(["doxorubicin", "cyclophosphamide"], as_of="2026-09-30") == []


def test_parents_come_from_the_reimbursement_chunk_file(reimb):
    row = reimb.search_reimbursement(["anastrozole"], as_of="2026-10-20")[0]
    assert [p["chunk_id"] for p in row["parents"]] == ["hira-booklet-20261001-bc-l2", "hira-booklet-20261001-bc-l1"]
    assert row["parent"]["chunk_id"] == "hira-booklet-20261001-bc-l2"
    assert "parent" not in reimb.search_reimbursement(["anastrozole"], as_of="2026-10-20", with_parent=False)[0]


def test_guideline_points_are_never_returned(reimb):
    from src.rag import indexer
    indexer.index_chunks([{"chunk_id": "g-1", "doc_type": "guideline", "text": "g", "drugs": ["anastrozole"],
                           "setting": ["metastatic"], "line": ["1L"]}])
    assert _ids(reimb.search_reimbursement(["anastrozole"], as_of="2026-10-20")) == ["ana-lhrh"]


def test_same_score_rows_newest_first(reimb, monkeypatch):
    from src.rag import indexer
    indexer.index_chunks([_chunk("ac-old", ["doxorubicin", "cyclophosphamide"], EARLY, ["adjuvant"],
                                 effective_from="2014-01-01")])
    rows = reimb.search_reimbursement(["doxorubicin", "cyclophosphamide"], setting="early", line="adjuvant",
                                      as_of="2026-10-20")
    assert _ids(rows) == ["ac-adjuvant", "ac-old"]


def test_with_real_reimbursement_chunk_file(monkeypatch):
    # D의 실제 청크 파일이 있는 컴퓨터에서만 돈다 (git에 올리지 않는 파일). 청크마다 자기 약으로 찾히는지 본다
    from src.rag import chunk_store
    chunks = chunk_store.load_reimbursement_chunks()
    if not chunks:
        pytest.skip("급여 청크 파일 없음 (data/reimbursement/chunks/reimbursement_chunks_current.jsonl)")
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        monkeypatch.setitem(sys.modules, "sentence_transformers",
                            types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import client as rag_client
    from src.rag import indexer, reimbursement_search

    monkeypatch.setattr(rag_client, "_client", QdrantClient(":memory:"))
    monkeypatch.setattr(rag_client, "_model", FakeModel())
    l3 = [c for c in chunks if c["chunk_kind"] != "section"]
    indexer.init_collection()
    indexer.index_chunks(l3)
    for c in l3:
        rb = c["reimbursement"]
        if rb["source_type"] == "preview" or c.get("superseded_by"):
            continue
        rows = reimbursement_search.search_reimbursement(c["drugs"], setting=c["setting"][0], line=c["line"][0],
                                                         as_of=rb["effective_from"])
        found = next((r for r in rows if r["chunk_id"] == c["chunk_id"]), None)
        assert found and found["extra_drugs"] == [], c["chunk_id"]
        assert not c.get("parent_id") or found["parents"], c["chunk_id"]  # 부모를 파일에서 찾는다
    rag_client._client = None


def test_public_api():
    import src.rag as rag
    assert callable(rag.search_reimbursement) and callable(rag.close_searcher)


def test_client_closes_at_exit(monkeypatch, tmp_path):
    # 처음 열 때 종료 시 닫기를 한 번만 등록하고, 닫으면 다시 열 수 있다 (로컬 폴더 잠금)
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        monkeypatch.setitem(sys.modules, "sentence_transformers",
                            types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import client as rag_client
    registered = []
    monkeypatch.setattr(rag_client.atexit, "register", registered.append)
    monkeypatch.setattr(rag_client, "_atexit_registered", False)
    monkeypatch.setattr(rag_client, "_client", None)
    monkeypatch.setattr(rag_client, "DB_PATH", tmp_path / "qdrant_db")
    rag_client.get_qdrant_client()
    rag_client.close_client()
    rag_client.get_qdrant_client()
    rag_client.close_client()
    assert registered == [rag_client.close_client] and rag_client._client is None


def test_rows_without_drug_names_filtered_by_setting_line_subtype(reimb):
    # ESMO 권고는 없고 급여만 있는 요법: 약 이름 없이 병기·차수·아형으로 찾는다 (A 요청 2026-10-21)
    from src.rag import indexer
    indexer.index_chunks([
        _chunk("megestrol-2l", ["megestrol"], ["metastatic"], ["2L", ">=3L"]),
        {**_chunk("gcsf", ["filgrastim"], ["early", "locally_advanced", "metastatic"], ["any"])},
        {**_chunk("tnbc-only", ["eribulin"], ["metastatic"], ["2L"]), "subtype": ["TNBC"]},
        {**_chunk("offlabel", ["olaparib"], ["metastatic"], ["any"], kind="offlabel_regimen")},
    ])
    rows = reimb.search_reimbursement_rows(setting="metastatic", lines=["2L"], subtype="HR+/HER2-", as_of="2026-10-20",
                                           exclude_ids={"ac-palliative"})
    ids = [r["chunk_id"] for r in rows]
    assert ids == ["megestrol-2l", "gcsf"]  # 치료 요법 먼저, 보조약(G-CSF) 뒤. 아형·제외·허가초과·예고·대체·시행 전 행은 없음
    assert rows[0]["drug_classes"] == ["Hormone Therapy"] and rows[0]["matched_drugs"] == []
    assert rows[1]["supportive"] and rows[0]["parents"]
    assert "offlabel" in [r["chunk_id"] for r in reimb.search_reimbursement_rows(
        setting="metastatic", lines=["2L"], subtype="HR+/HER2-", as_of="2026-10-20", include_offlabel=True)]
    # 차수를 안 주면 거르지 않는다 (조기는 setting.phase가 없을 때)
    assert "ac-adjuvant" in [r["chunk_id"] for r in reimb.search_reimbursement_rows(setting="early", as_of="2026-10-20")]
