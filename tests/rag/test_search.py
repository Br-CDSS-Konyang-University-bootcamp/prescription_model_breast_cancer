# tests/rag/test_search.py
import pytest

pytest.importorskip("qdrant_client")
pytest.importorskip("sentence_transformers")

from src.rag.searcher import search_guidelines  # noqa: E402

def test_search_esmo_guideline():
    results = search_guidelines(
        query_text="adjuvant abemaciclib stage III early breast cancer",
        source="ESMO-EBC",
        setting="early",
        top_k=2
    )
    assert len(results) > 0
    assert results[0]["source"] == "ESMO-EBC"