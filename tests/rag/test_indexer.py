# tests/rag/test_indexer.py
# 색인 함수를 메모리 Qdrant와 가짜 임베딩으로 시험한다. bge-m3(약 2GB)와 data/qdrant_db 없이 돈다.
import sys
import types

import pytest

pytest.importorskip("qdrant_client")

from qdrant_client import QdrantClient  # noqa: E402


class FakeModel:
    def encode(self, texts, show_progress_bar=False):
        import numpy as np
        return np.ones((len(texts), 1024)) if isinstance(texts, list) else np.ones(1024)


@pytest.fixture
def memory_index(monkeypatch):
    # client.py가 sentence_transformers를 불러오므로, 없으면 이 테스트 동안만 빈 모듈로 채운다
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=None))
    from src.rag import client as rag_client
    from src.rag import indexer

    monkeypatch.setattr(rag_client, "_client", QdrantClient(":memory:"))
    monkeypatch.setattr(rag_client, "_model", FakeModel())
    indexer.init_collection()
    yield rag_client, indexer
    rag_client._client = None


def _count(rag_client, doc_type=None):
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    flt = Filter(must=[FieldCondition(key="doc_type", match=MatchValue(value=doc_type))]) if doc_type else None
    return rag_client._client.count(rag_client.COLLECTION_NAME, count_filter=flt).count


GUIDE = [{"chunk_id": f"g-{i}", "doc_type": "guideline", "text": "g"} for i in range(3)]
REIMB = [{"chunk_id": f"r-{i}", "doc_type": "reimbursement", "text": "r"} for i in range(2)]


def test_reindex_same_chunks_does_not_duplicate(memory_index):
    rag_client, indexer = memory_index
    indexer.index_chunks(GUIDE)
    indexer.index_chunks(GUIDE)
    assert _count(rag_client) == 3


def test_delete_by_doc_type_keeps_other_type(memory_index):
    rag_client, indexer = memory_index
    indexer.index_chunks(GUIDE + REIMB)
    indexer.delete_by_doc_type("reimbursement")
    assert _count(rag_client, "reimbursement") == 0
    assert _count(rag_client, "guideline") == 3
    indexer.delete_guideline_chunks()
    assert _count(rag_client) == 0


def test_delete_by_doc_type_rejects_unknown(memory_index):
    _, indexer = memory_index
    with pytest.raises(ValueError):
        indexer.delete_by_doc_type("guidelines")


def test_search_returns_recommendations_with_parent(memory_index, monkeypatch):
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    results = searcher.search_guidelines("elacestrant ESR1", setting="metastatic", subtype="HR+/HER2-",
                                         line="2L", top_k=5, with_parent=True)
    assert results
    for r in results:
        assert r["parent_id"]  # 부모 청크(parent_id 없음)는 색인에 없다
        assert "metastatic" in r["setting"]
        assert "HR+/HER2-" in r["subtype"] or "any" in r["subtype"]
        assert r["parent"]["chunk_id"] == r["parent_id"]


def test_public_api_for_reimbursement_module():
    # D(src/reimbursement/index.py)가 src.rag에서 부르는 함수들
    import src.rag as rag
    for name in ("init_collection", "index_chunks", "delete_by_doc_type", "close_indexer"):
        assert callable(getattr(rag, name)), name
