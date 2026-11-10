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


def test_replace_doc_type_swaps_only_that_type(memory_index):
    # 새 급여 청크를 넣고, 새 목록에 없는 옛 급여 점(r-1)만 지운다. 지침 점은 그대로
    rag_client, indexer = memory_index
    indexer.index_chunks(GUIDE + REIMB)
    new = [REIMB[0], {"chunk_id": "r-new", "doc_type": "reimbursement", "text": "r"}]
    assert indexer.replace_doc_type("reimbursement", new) == {"indexed": 2, "removed": 1}
    ids = {p.payload["chunk_id"] for p in rag_client._client.scroll(rag_client.COLLECTION_NAME, limit=100)[0]}
    assert ids == {"g-0", "g-1", "g-2", "r-0", "r-new"}


def test_replace_doc_type_keeps_old_points_when_indexing_fails(memory_index, monkeypatch):
    # 지우고 넣는 방식은 넣다가 실패하면 급여 점이 0개가 됐다 (D 안건 C1). 바꿔 끼우기는 옛 점을 남긴다
    rag_client, indexer = memory_index
    indexer.index_chunks(GUIDE + REIMB)

    class Broken:
        def encode(self, *a, **k):
            raise OSError("model download blocked")
    monkeypatch.setattr(rag_client, "_model", Broken())
    with pytest.raises(OSError):
        indexer.replace_doc_type("reimbursement", [{"chunk_id": "r-new", "doc_type": "reimbursement", "text": "r"}])
    assert _count(rag_client, "reimbursement") == 2 and _count(rag_client, "guideline") == 3


def test_replace_doc_type_rejects_empty_or_mixed_lists(memory_index):
    rag_client, indexer = memory_index
    indexer.index_chunks(GUIDE + REIMB)
    with pytest.raises(ValueError):
        indexer.replace_doc_type("reimbursement", [])  # 전부 지우게 되는 실수를 막는다
    with pytest.raises(ValueError):
        indexer.replace_doc_type("reimbursement", REIMB + GUIDE[:1])  # 다른 종류가 섞이면 넣지 않는다
    with pytest.raises(ValueError):
        indexer.replace_doc_type("guidelines", GUIDE)
    assert _count(rag_client) == 5


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
    for name in ("init_collection", "index_chunks", "delete_by_doc_type", "replace_doc_type", "close_indexer"):
        assert callable(getattr(rag, name)), name


def test_algorithm_paths_are_searched_separately(memory_index):
    # 알고리즘 그림 경로는 권고를 그림 순서로 다시 적은 것이라, 기본 검색에 섞이면 권고 자리를 차지한다 (평가 MRR 0.97 → 0.65)
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    chunks = select_index_chunks(load_guideline_chunks())
    if not any(c["chunk_kind"] == "algorithm" for c in chunks):
        pytest.skip("알고리즘 청크 파일 없음")
    indexer.index_chunks(chunks)
    args = dict(query_text="ESR1-mutated MBC", setting="metastatic", subtype="HR+/HER2-", top_k=50, rerank=False)
    assert {r["chunk_kind"] for r in searcher.search_guidelines(**args)} == {"recommendation"}
    assert {r["chunk_kind"] for r in searcher.search_guidelines(**args, chunk_kind="algorithm")} == {"algorithm"}
    assert len({r["chunk_kind"] for r in searcher.search_guidelines(**args, chunk_kind=None)}) == 2


def test_relapse_within_12_months_picks_the_fulvestrant_branch(memory_index):
    # ESMO MBC 1차: 보조 ET 중·12개월 이내 재발 → fulvestrant-CDK4/6, de novo·12개월 넘어 → AI-CDK4/6.
    # 두 권고가 이 구절만 달라 재정렬 모델이 못 갈랐다 (VC-0103). 확정값이 있으면 반대 갈래를 뒤로 보낸다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    args = dict(query_text="x", setting="metastatic", subtype="HR+/HER2-", line="1L", top_k=200, rerank=False,
                chunk_kind=None)
    fulv, ai = "esmo-mbc-2026-05-luminal-1l-0fd38a", "esmo-mbc-2026-05-luminal-1l-02649c"

    def rank(**kw):
        ids = [r["chunk_id"] for r in searcher.search_guidelines(**args, **kw)]
        return ids.index(fulv), ids.index(ai), ids.index("esmo-mbc-2026-05-fig2-a9baa4"), ids.index("esmo-mbc-2026-05-fig2-1ae139")

    f, a, fig_f, fig_a = rank(endocrine_relapse_12m="yes")
    assert f < a and fig_f < fig_a
    f, a, fig_f, fig_a = rank(endocrine_relapse_12m="no")
    assert a < f and fig_a < fig_f
    plain = {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args)}
    assert plain[fulv] == plain[ai]  # 값이 없으면 바꾸지 않는다


def test_menopausal_status_pushes_back_opposite_side_recommendations(memory_index):
    # 폐경 후 환자에게 폐경 전·이행기 OFS 권고가 상위에 왔다 (VC-0103 check_case, 2026-11-02). 확정 폐경 상태와 반대쪽만
    # 대상으로 하는 권고·그림 경로를 뒤로 보낸다. 두 쪽을 다 말하는 것과 그림 각주는 보지 않는다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    args = dict(query_text="x", setting="early", subtype="HR+/HER2-", top_k=200, rerank=False, chunk_kind=None)
    pre, post, both = ("esmo-ebc-2024-02-hrpos-6308eb", "esmo-ebc-2024-02-hrpos-0656d9",
                       "esmo-ebc-2024-02-fig2-74bcdc")  # 폐경 전 / 폐경 후 / "폐경 전 OFS와 폐경 후" 둘 다

    def scores(**kw):
        return {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args, **kw)}

    plain, after, before = scores(), scores(menopausal_status="postmenopausal"), scores(menopausal_status="premenopausal")
    assert after[pre] == plain[pre] - 1.0 and after[post] == plain[post]
    assert before[post] == plain[post] - 1.0 and before[pre] == plain[pre]
    assert scores(menopausal_status="perimenopausal")[post] == before[post]  # 이행기는 폐경 전으로 본다
    assert after[both] == before[both] == plain[both]
    # 전이성 그림 경로는 각주에 "pre- and perimenopausal women"이 있어도 감점하지 않는다
    meta = dict(args, setting="metastatic", line="1L")
    fig = "esmo-mbc-2026-05-fig2-a9baa4"
    plain_m = {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**meta)}
    after_m = {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**meta, menopausal_status="postmenopausal")}
    assert after_m[fig] == plain_m[fig] and after_m["esmo-mbc-2026-05-luminal-1l-c0c05b"] < plain_m["esmo-mbc-2026-05-luminal-1l-c0c05b"]


def test_menopause_rule_never_penalizes_an_eval_answer():
    # 평가 문제집의 정답 권고가 그 문항의 폐경 상태 때문에 감점되면 안 된다
    import sys, types
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag.chunk_store import load_guideline_chunks
    from src.rag.evaluate import load_cases
    from src.rag.searcher import _menopause_adjust
    text = {c["chunk_id"]: c["text"] for c in load_guideline_chunks()}
    bad = [(c["case_id"], cid) for c in load_cases() for cid in c["expected_chunks"]
           if _menopause_adjust(text[cid], c.get("menopausal_status"))]
    assert bad == []


def test_superseded_guideline_chunks_are_not_searched(memory_index):
    # 개정으로 대체된 청크는 색인에 남아 있어도 찾지 않는다 (PROJECT.md §6)
    rag_client, indexer = memory_index
    from src.rag import searcher
    base = {"doc_type": "guideline", "chunk_kind": "recommendation", "setting": ["metastatic"], "subtype": ["any"],
            "line": ["any"], "text": "x", "version": "2026-05"}
    indexer.index_chunks([{**base, "chunk_id": "new", "superseded_by": None},
                          {**base, "chunk_id": "old", "superseded_by": "new"}])
    assert [r["chunk_id"] for r in searcher.search_guidelines("x", setting="metastatic", top_k=5, rerank=False)] == ["new"]


def test_visceral_crisis_pushes_back_endocrine_only_recommendations(memory_index):
    # 장기 위기 환자에게 AI-CDK4/6이 1위, 장기 부전 임박 ChT 권고가 2위였다 (VC-0126 check_case, 2026-11-03).
    # 장기 위기가 yes면 내분비 기반 치료만 권하는 권고·그림 경로를 뒤로 보낸다. ChT 권고, 그림 각주, 내분비 부적합 경로는 그대로
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    args = dict(query_text="x", setting="metastatic", subtype="HR+/HER2-", line="1L", top_k=300, rerank=False,
                chunk_kind=None)
    p = "esmo-mbc-2026-05-"
    plain = {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args)}
    crisis = {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args, visceral_crisis="yes")}
    for cid in ("luminal-1l-02649c", "luminal-1l-0fd38a", "luminal-1l-e03e88", "fig2-1ae139"):
        assert crisis[p + cid] == pytest.approx(plain[p + cid] - 1.0), cid
    for cid in ("luminal-1l-5c55b4", "luminal-3l-044c33", "luminal-2l-160064", "fig4-ddbc18"):
        assert crisis[p + cid] == plain[p + cid], cid
    no = {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args, visceral_crisis="no")}
    assert no == plain  # yes일 때만 바꾼다


def test_visceral_crisis_rule_never_penalizes_a_virtual_chart_answer():
    # 가상 차트 C 정답 중 장기 위기 환자의 정답 권고·그림 경로는 감점되면 안 된다
    import json, sys, types
    from pathlib import Path
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag.chunk_store import load_guideline_chunks
    from src.rag.retrieve import from_confirmed_state
    from src.rag.searcher import _crisis_adjust
    text = {c["chunk_id"]: c["text"] for c in load_guideline_chunks()}
    base = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "virtual_charts"
    checked = 0
    for path in base.glob("*/expected/guideline.json"):
        exp = json.loads(path.read_text(encoding="utf-8"))
        _, patient, _ = from_confirmed_state(json.loads((path.parent / "confirmed_state.json").read_text(encoding="utf-8")))
        if patient.get("visceral_crisis") != "yes":
            continue
        checked += 1
        assert not [cid for cid in exp["expected_chunks"] + exp.get("expected_algorithm", [])
                    if _crisis_adjust(text[cid], "yes")], path
    assert checked  # VC-0126


def test_prior_metastatic_chemo_pushes_back_opposite_branch(memory_index):
    # 고식 항암이 없는 환자에게 "ChT 1차례 이상 뒤" T-DXd·SG 권고가 정답보다 위에 왔다 (VC-0113 check_case, 2026-11-03).
    # 확정 고식 항암 차수로 그림 4의 'No previous ChT' / 'Previous ChT' 갈래 중 반대쪽만 가리키는 권고·경로를 뒤로 보낸다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    args = dict(query_text="x", setting="metastatic", subtype="HR+/HER2-", line=">=3L", top_k=300, rerank=False,
                chunk_kind=None)
    p = "esmo-mbc-2026-05-"

    def scores(**kw):
        return {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args, **kw)}

    plain, naive, treated = scores(), scores(prior_metastatic_chemo="no"), scores(prior_metastatic_chemo="yes")
    needs, none, neither = ("luminal-3l-5f9ed9", "fig4-a7b5ac"), ("luminal-3l-b023e3", "fig4-ddbc18"), "luminal-3l-044c33"
    for cid in needs:
        assert naive[p + cid] == pytest.approx(plain[p + cid] - 1.0) and treated[p + cid] == plain[p + cid], cid
    for cid in none:
        assert treated[p + cid] == pytest.approx(plain[p + cid] - 1.0) and naive[p + cid] == plain[p + cid], cid
    assert naive[p + neither] == treated[p + neither] == plain[p + neither]


def test_prior_chemo_rule_never_penalizes_a_virtual_chart_answer():
    import json, sys, types
    from pathlib import Path
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag.chunk_store import load_guideline_chunks
    from src.rag.retrieve import from_confirmed_state
    from src.rag.searcher import _prior_chemo_adjust
    text = {c["chunk_id"]: c["text"] for c in load_guideline_chunks()}
    base = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "virtual_charts"
    for path in base.glob("*/expected/guideline.json"):
        exp = json.loads(path.read_text(encoding="utf-8"))
        _, patient, _ = from_confirmed_state(json.loads((path.parent / "confirmed_state.json").read_text(encoding="utf-8")))
        assert not [cid for cid in exp["expected_chunks"] + exp.get("expected_algorithm", [])
                    if _prior_chemo_adjust(text[cid], patient.get("prior_metastatic_chemo"))], path


def test_early_history_pushes_back_opposite_branch(memory_index):
    # 선행 뒤 환자에게 '수술 먼저 stage I' 권고가, 선행 pembrolizumab 환자에게 'ICI를 받지 않은 잔존 capecitabine'이 1위로 왔다
    # (VC-0105·0117·0118·0120 check_case, 2026-11-03). 확정 이력으로 반대 갈래만 가리키는 권고·그림 경로를 뒤로 보낸다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    p = "esmo-ebc-2024-02-"

    def scores(subtype, **kw):
        args = dict(query_text="x", setting="early", subtype=subtype, line="adjuvant", top_k=300, rerank=False,
                    chunk_kind=None)
        return {r["chunk_id"]: r["score"] for r in searcher.search_guidelines(**args, **kw)}

    her2, tnbc = "HR-/HER2+", "TNBC"
    plain_h, plain_t = scores(her2), scores(tnbc)
    after = scores(her2, neoadjuvant_received="yes", ici_received="no", pcr="no")  # VC-0105: 선행 뒤 잔존
    assert after[p + "her2pos-d04f07"] == pytest.approx(plain_h[p + "her2pos-d04f07"] - 1.0)
    assert after[p + "fig6-163f7d"] == pytest.approx(plain_h[p + "fig6-163f7d"] - 1.0)  # pCR 갈래
    assert after[p + "her2pos-ae367a"] == plain_h[p + "her2pos-ae367a"]
    pcr = scores(her2, neoadjuvant_received="yes", ici_received="no", pcr="yes")  # VC-0120: 선행 뒤 pCR
    assert pcr[p + "her2pos-ae367a"] == pytest.approx(plain_h[p + "her2pos-ae367a"] - 1.0)
    assert pcr[p + "fig6-163f7d"] == plain_h[p + "fig6-163f7d"]
    ici = scores(tnbc, neoadjuvant_received="yes", ici_received="yes", pcr="no")  # VC-0117: 선행 pembrolizumab 뒤 잔존
    assert ici[p + "tnbc-cd090b"] == pytest.approx(plain_t[p + "tnbc-cd090b"] - 1.0)
    assert ici[p + "tnbc-d13ffd"] == plain_t[p + "tnbc-d13ffd"]
    first = scores(tnbc, neoadjuvant_received="no")  # VC-0118: 수술 먼저
    assert first[p + "tnbc-cd090b"] == pytest.approx(plain_t[p + "tnbc-cd090b"] - 1.0)
    assert first[p + "fig7-8ccb0b"] == plain_t[p + "fig7-8ccb0b"] and first[p + "tnbc-725b0b"] == plain_t[p + "tnbc-725b0b"]
    both = "hrpos-7568e8"  # '수술 뒤 림프절 다수 또는 선행 뒤 잔존' 두 갈래를 다 말함
    plain_hr = scores("HR+/HER2-")
    for kw in ({"neoadjuvant_received": "yes"}, {"neoadjuvant_received": "no"}):
        assert scores("HR+/HER2-", **kw)[p + both] == plain_hr[p + both]


def test_rules_never_penalize_a_virtual_chart_answer():
    # 확정값에서 나온 감점 규칙(폐경·재발 시점·장기 위기·이전 항암·조기 이력)이 가상 차트 C 정답을 감점하면 안 된다
    import json, sys, types
    from pathlib import Path
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag.chunk_store import load_guideline_chunks
    from src.rag.query import search_args
    from src.rag.retrieve import from_confirmed_state
    from src.rag import searcher as s
    text = {c["chunk_id"]: c["text"] for c in load_guideline_chunks()}
    base = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "virtual_charts"
    bad = []
    for path in base.glob("*/expected/guideline.json"):
        exp = json.loads(path.read_text(encoding="utf-8"))
        record, patient, _ = from_confirmed_state(json.loads((path.parent / "confirmed_state.json").read_text(encoding="utf-8")))
        a = search_args(record, **patient)
        for cid in exp["expected_chunks"] + exp.get("expected_algorithm", []):
            t = text[cid]
            penalty = (s._relapse_adjust(t, a.get("endocrine_relapse_12m")) + s._menopause_adjust(t, a.get("menopausal_status"))
                       + s._crisis_adjust(t, a.get("visceral_crisis")) + s._prior_chemo_adjust(t, a.get("prior_metastatic_chemo"))
                       + s._early_adjust(t, a.get("neoadjuvant_received"), a.get("ici_received"), a.get("pcr"))
                       + s._er_adjust(t, a.get("subtype"))
                       + s._targetable_adjust(t, a.get("biomarker_tags")) + s._third_line_adjust(t, a.get("line"))
                       + s._phase_adjust(t, a.get("line")) + s._high_risk_adjust(t, a.get("high_risk_early"))
                       + s._marker_scope_adjust(t, a.get("biomarker_tags"))
                       + (1.0 if a.get("her2_adjuvant_relapse") == "no" and s.HER2_EARLY_RELAPSE.search(t.split(" Footnotes: ")[0]) else 0.0))
            if penalty:
                bad.append((path.parts[-3], cid))
    assert bad == []


def test_her2_er_scope_and_adjuvant_relapse(memory_index):
    # ER 음성 HER2 양성 환자에게 ER 양성 유지요법 권고가 1~4위를 차지했고(VC-0112), 보조 trastuzumab을 5년 전에 끝낸 환자에게
    # '보조 종료 6-12개월 안 재발' 권고가 1위였다(VC-0110). 아형의 HR 상태와 확정 간주 규칙으로 뒤로 보낸다
    rag_client, indexer = memory_index
    from src.rag import searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    p = "esmo-mbc-2026-05-her2-1l-"

    def scores(subtype, **kw):
        args = dict(query_text="x", setting="metastatic", subtype=subtype, line="1L", top_k=300, rerank=False)
        return {r["chunk_id"][len("esmo-mbc-2026-05-her2-1l-"):]: r["score"]
                for r in searcher.search_guidelines(**args, **kw) if r["chunk_id"].startswith(p)}

    neg, pos = scores("HR-/HER2+"), scores("HR+/HER2+")
    for cid in ("eab0c1", "4be7b0", "406dd2", "2cded5", "fc59a0"):  # ER 양성 전용
        assert neg[cid] == pytest.approx(pos[cid] - 1.0), cid
    for cid in ("5a1ce0", "f39214"):  # ER 음성 전용
        assert pos[cid] == pytest.approx(neg[cid] - 1.0), cid
    for cid in ("8cddda", "6a166b", "9ebcd3"):  # ER 상태와 무관
        assert pos[cid] == neg[cid], cid
    late = scores("HR+/HER2+", her2_adjuvant_relapse="no")
    assert late["b8e579"] == pytest.approx(pos["b8e579"] - 1.0) and late["8cddda"] == pos["8cddda"]
    assert scores("HR+/HER2+", her2_adjuvant_relapse="yes")["b8e579"] == pos["b8e579"]


def test_targetable_and_third_line_rules():
    # '표적 변이가 없을 때' 권고는 표적 변이가 있는 환자에게(VC-0101 ESR1, VC-0123 AKT1), 'third-line' 권고는 1·2차 환자에게(VC-0127) 감점
    import sys, types
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import searcher as s
    no_target = "Fulvestrant-CDK4/6 inhibitor switch may be considered in the absence of targetable alterations."
    assert s._targetable_adjust(no_target, ["ESR1-mut"]) == 1.0
    assert s._targetable_adjust(no_target, ["HER2-low"]) == 0.0
    assert s._targetable_adjust(no_target, []) == 0.0
    path = "Figure 3. (algorithm path): ER+ → ESR1m → elacestrant Footnotes: no targetable alterations: everolimus"
    assert s._targetable_adjust(path, ["ESR1-mut"]) == 0.0  # 각주는 보지 않는다
    third = "All ChT recommendations can also be recommended for third-line treatment of mTNBC"
    assert s._third_line_adjust(third, "2L") == 1.0
    assert s._third_line_adjust(third, ">=3L") == 0.0
    assert s._third_line_adjust("For gBRCA wild type mTNBC: all ChT recommendations", "2L") == 0.0
    assert s._third_line_adjust("Figure 3. (algorithm path): PIK3CA → capivasertib → [PD] → Third-line treatment", "2L") == 0.0


def test_rules_reach_the_chunks_run_flow_flagged():
    # A run_flow 2026-11-05 C-5·C-6·B-11: 각 사례에서 '나오면 안 됨'으로 인용된 청크가 새 규칙으로 감점되는지 (실제 확정값으로)
    import json, sys, types
    from pathlib import Path
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag.chunk_store import load_guideline_chunks
    from src.rag.query import search_args
    from src.rag.retrieve import from_confirmed_state
    from src.rag import searcher as s
    text = {c["chunk_id"]: c["text"] for c in load_guideline_chunks()}
    base = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "virtual_charts"

    def penalty(case, short):
        state = json.loads((base / case / "expected" / "confirmed_state.json").read_text(encoding="utf-8"))
        record, patient, _ = from_confirmed_state(state)
        a = search_args(record, **patient)
        t = next(v for k, v in text.items() if k.endswith(short))
        return (s._phase_adjust(t, a.get("line")) + s._high_risk_adjust(t, a.get("high_risk_early"))
                + s._marker_scope_adjust(t, a.get("biomarker_tags"))
                + s._prior_chemo_adjust(t, a.get("prior_metastatic_chemo")))

    flagged = [("VC-0124", "hrpos-fca2a7"), ("VC-0121", "hrpos-fca2a7"), ("VC-0121", "hrpos-7568e8"),
               ("VC-0107", "hrpos-1f97a2"), ("VC-0107", "hrpos-cca75c"), ("VC-0104", "tnbc-1l-a2bd8f"),
               ("VC-0104", "tnbc-1l-2d012a"), ("VC-0116", "tnbc-1l-a2bd8f"), ("VC-0116", "tnbc-1l-2d012a")]
    assert [f for f in flagged if not penalty(*f)] == []


def test_overfit_review_rules_2026_11_10():
    # 과적합 점검(src/rag/rule_review_2026-11-10.md): 선행 결정의 잔존암 권고는 아형과 관계없이 감점, de novo의 DFI 규칙과
    # 'beyond third-line'을 고식 항암 뒤로 보던 규칙은 뺐다 (atezolizumab 6280b3는 de novo PD-L1 양성 환자에게도 맞다)
    import sys, types
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import searcher as s
    for residual in ("For patients with residual invasive disease after neoadjuvant ChT, T-DM1 is recommended",
                     "In patients with TNBC and residual disease who did not receive ICIs, capecitabine"):
        assert s._phase_adjust(residual, "neoadjuvant") == 1.0
        assert s._phase_adjust(residual, "adjuvant") == 0.0
    assert not hasattr(s, "_dfi_adjust")
    rechallenge = "Rechallenge with anthracyclines or taxanes can be recommended beyond third-line treatment"
    assert s._prior_chemo_adjust(rechallenge, "no") == 0.0
    assert s._high_risk_adjust("Extended ET beyond 5 years should be considered in high-risk EBC", "no") == 1.0
    assert s._high_risk_adjust("Bisphosphonates ... especially if at high risk of relapse", "no") == 0.0


def test_rules_never_penalize_an_eval_set_answer():
    # 28건 정답만으로 확인하면 그 답지에 맞춘 규칙을 못 거른다. 평가 문제집(10-20, 가상 차트보다 먼저 따로 만듦)의 정답도
    # 감점 규칙에 걸리지 않아야 한다 (과적합 점검 2026-11-10)
    import csv, re, sys, types
    sys.modules.setdefault("sentence_transformers", types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag.chunk_store import load_guideline_chunks
    from src.rag.chunk_common import BASE_DIR
    from src.rag import searcher as s
    text = {c["chunk_id"]: c["text"] for c in load_guideline_chunks()}
    bad = []
    with open(BASE_DIR / "data" / "eval" / "rag_eval_cases.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            tags = [t for t in re.split(r"[;,| ]+", row.get("biomarker_tags") or "") if t]
            for cid in re.findall(r"esmo-[\w-]+", row.get("expected_chunks") or ""):
                t = text.get(cid, "")
                penalty = (s._menopause_adjust(t, row.get("menopausal_status")) + s._targetable_adjust(t, tags)
                           + s._third_line_adjust(t, row.get("line")) + s._phase_adjust(t, row.get("line"))
                           + s._high_risk_adjust(t, row.get("high_risk_early")) + s._marker_scope_adjust(t, tags)
                           + s._er_adjust(t, row.get("subtype")))
                if penalty:
                    bad.append((row["case_id"], cid))
    assert bad == []
