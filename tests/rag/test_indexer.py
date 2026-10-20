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
        monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import client as rag_client
    from src.rag import indexer

    from src.rag import searcher

    monkeypatch.setattr(rag_client, "_client", QdrantClient(":memory:"))
    monkeypatch.setattr(rag_client, "_model", FakeModel())
    monkeypatch.setattr(searcher, "_reranker_failed", False)
    searcher.clear_search_cache()
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
                                         line="2L", top_k=5, with_parent=True, rerank=False)
    assert results
    for r in results:
        assert r["parent_id"]  # 부모 청크(parent_id 없음)는 색인에 없다
        assert "metastatic" in r["setting"]
        assert "HR+/HER2-" in r["subtype"] or "any" in r["subtype"]
        assert r["parent"]["chunk_id"] == r["parent_id"]


class FakeReranker:
    """본문에 'elacestrant'가 있으면 높은 원점수(logit)를 주는 가짜 재정렬 모델."""
    def predict(self, pairs):
        return [4.0 if "elacestrant" in text.lower() else -4.0 for _, text in pairs]


def test_rerank_reorders_candidates_and_keeps_score_scale(memory_index, monkeypatch):
    # 가짜 임베딩은 모든 청크 점수가 같아 순위가 임의다. 재정렬을 켜면 재정렬 점수로 순위가 정해져야 한다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    monkeypatch.setattr(searcher, "get_reranker", lambda: FakeReranker())
    monkeypatch.setattr(searcher, "RERANK_CANDIDATES", 200)  # 가짜 임베딩이라 후보를 모두 넣어야 정답이 후보에 든다
    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    results = searcher.search_guidelines("ESR1-mutated MBC after ET", setting="metastatic", subtype="HR+/HER2-",
                                         top_k=10, rerank=True)
    assert "elacestrant" in results[0]["text"].lower()
    assert 0.9 < results[0]["score"] <= 1.0  # logit 4 → sigmoid 0.982, 가점 없음
    # elacestrant가 든 청크(권고, 알고리즘 그림 경로)가 모두 앞에 오고, 나머지는 재정렬 점수가 낮다
    has = ["elacestrant" in r["text"].lower() for r in results]
    assert has == sorted(has, reverse=True) and not all(has)
    assert all(r["score"] < 0.1 for r, h in zip(results, has) if not h)


def test_search_falls_back_when_reranker_cannot_load(memory_index, monkeypatch):
    # 재정렬은 기본으로 켜져 있다. 모델을 못 불러오면(미설치, 내려받기 실패) 경고하고 뜻 검색 결과를 돌려준다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    def broken():
        raise OSError("model download blocked")
    monkeypatch.setattr(searcher, "get_reranker", broken)
    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    with pytest.warns(UserWarning, match="재정렬 모델"):
        results = searcher.search_guidelines("ESR1-mutated MBC", setting="metastatic", subtype="HR+/HER2-", top_k=3)
    assert len(results) == 3


def test_search_cache_returns_copies_and_clears_on_reindex(memory_index, monkeypatch):
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    calls = []
    real = searcher._search
    monkeypatch.setattr(searcher, "_search", lambda *a: calls.append(a) or real(*a))
    first = searcher.search_guidelines("ESR1", setting="metastatic", top_k=2, rerank=False)
    first[0]["text"] = "고친 값"  # 받은 쪽이 고쳐도
    second = searcher.search_guidelines("ESR1", setting="metastatic", top_k=2, rerank=False)
    assert len(calls) == 1 and second[0]["text"] != "고친 값"  # 두 번째는 기억해 둔 원래 결과
    indexer.delete_guideline_chunks()  # 색인이 바뀌면 기억을 비운다
    assert searcher.search_guidelines("ESR1", setting="metastatic", top_k=2, rerank=False) == []
    assert len(calls) == 2


def test_metastatic_sites_raise_matching_and_lower_other_site_recommendations(memory_index):
    # 가짜 임베딩이라 모든 청크의 뜻 검색 점수가 같다. 전이 부위 가점·감점만으로 순위가 갈린다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    # 가점·감점은 뜻 검색으로 뽑힌 후보 안에서 순위를 바꾼다. 가짜 임베딩은 후보가 임의라 전부 뽑아서 본다
    bone = searcher.search_guidelines("x", setting="metastatic", subtype="TNBC", top_k=200, rerank=False,
                                      metastatic_sites=["bone"])
    n_bone = sum(r["parent_id"].endswith("-site-bone") for r in bone)
    assert n_bone and all(r["parent_id"].endswith("-site-bone") for r in bone[:n_bone])
    # 부위를 알면 없는 부위의 부위별 권고는 후보에서 빠진다 (감점만 하면 그런 권고가 후보 자리를 채울 수 있다)
    no_cns = searcher.search_guidelines("x", setting="metastatic", subtype="TNBC", top_k=200, rerank=False,
                                        metastatic_sites=["liver"])
    site_parents = {"site-bone", "site-bm", "site-bm-lrt", "site-bm-her2neg", "site-lmd"}
    assert no_cns and not [r for r in no_cns if r["parent_id"].split("2026-05-")[-1] in site_parents]
    unknown_sites = searcher.search_guidelines("x", setting="metastatic", subtype="TNBC", top_k=200, rerank=False)
    assert [r for r in unknown_sites if r["parent_id"].split("2026-05-")[-1] in site_parents]  # 모르면 그대로
    unknown = searcher.search_guidelines("x", setting="metastatic", subtype="TNBC", top_k=3, rerank=False,
                                         metastatic_sites=["[Not Available]"][0])
    assert len({r["score"] for r in unknown}) == 1  # 부위를 모르면 점수를 바꾸지 않는다


def test_line_mismatch_is_pushed_down(memory_index):
    # 2차 질의에서 1차·3차만 가리키는 권고는 감점, any(부위별 등)는 소폭 가점, 2차는 가점
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    results = searcher.search_guidelines("x", setting="metastatic", subtype="HR+/HER2-", line="2L", top_k=200,
                                         rerank=False)
    ranks = [r["line"] for r in results]
    first_mismatch = next(i for i, ln in enumerate(ranks) if "2L" not in ln and "any" not in ln)
    assert all("2L" not in ln and "any" not in ln for ln in ranks[first_mismatch:])
    assert "2L" in ranks[0]


def test_matching_line_chunks_always_reach_the_candidates(memory_index):
    # 후보 수가 작아도(top_k=2 → 후보 6개) 절반은 차수가 맞거나 any인 권고에서 뽑으므로, 맞는 차수가 1·2위에 온다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    results = searcher.search_guidelines("x", setting="metastatic", subtype="HR-/HER2+", line=">=3L", top_k=2,
                                         rerank=False)
    assert len(results) == 2 and all(">=3L" in r["line"] or "any" in r["line"] for r in results)


def test_negative_marker_recommendations_are_pushed_down(memory_index):
    # gBRCA 음성 환자: gBRCA만 조건인 권고는 감점. "PIK3CA, AKT1 or PTEN" 권고는 PIK3CA만 음성이면 그대로
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    results = searcher.search_guidelines("x", setting="early", subtype="HR+/HER2-", top_k=200, rerank=False,
                                         negative_tags=["gBRCA"])
    tags = [set(r["biomarker_tags"]) for r in results]
    first = next(i for i, t in enumerate(tags) if t and t <= {"gBRCA"})
    assert all(t and t <= {"gBRCA"} for t in tags[first:])
    mixed = searcher.search_guidelines("x", setting="metastatic", subtype="HR+/HER2-", line="2L", top_k=200,
                                       rerank=False, negative_tags=["PIK3CA-mut"])
    capi = next(r for r in mixed if r["chunk_id"].endswith("luminal-2l-49918b"))
    alpe = next(r for r in mixed if r["chunk_id"].endswith("luminal-2l-8d7349"))
    assert capi["score"] > alpe["score"]  # alpelisib(PIK3CA만)은 감점, capivasertib(PIK3CA·AKT1·PTEN)은 그대로


def test_evaluate_with_extra_appends_site_and_de_novo_results(memory_index):
    rag_client, indexer = memory_index
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks
    from src.rag.evaluate import extra_results, load_cases, search_case

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    case = next(c for c in load_cases() if c["case_id"] == "M17")  # de novo
    main = search_case(case, k=5, rerank=False, auto_query=True)
    extras = extra_results(case, rerank=False)
    combined = search_case(case, k=5, rerank=False, auto_query=True, with_extra=True)
    assert extras and combined[:5] == main  # de novo 추가 검색이 돌고, 주 검색 결과가 앞에 온다
    assert {r["chunk_id"] for r in combined} == {r["chunk_id"] for r in main + extras}
    assert len({r["chunk_id"] for r in combined}) == len(combined)  # 겹치는 결과는 한 번만


def test_public_api_for_reimbursement_module():
    # D(src/reimbursement/index.py)가 src.rag에서 부르는 함수들
    import src.rag as rag
    for name in ("init_collection", "index_chunks", "delete_by_doc_type", "close_indexer"):
        assert callable(getattr(rag, name)), name
