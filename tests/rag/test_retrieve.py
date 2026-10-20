# tests/rag/test_retrieve.py
# retrieve_for_recommend: patient_state + biomarker_record → B의 recommend()에 넘길 (지침 청크, 급여 청크)
import json
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("qdrant_client")

from qdrant_client import QdrantClient  # noqa: E402

BASE_DIR = Path(__file__).resolve().parents[2]
PATIENT = json.loads((BASE_DIR / "tests" / "input" / "expected" /
                      "patient_state_metastatic_TCGA-A2-A0EW.json").read_text(encoding="utf-8"))
RECORD = {
    "subtype": "HR+/HER2-",
    "setting": {"disease": "metastatic", "line": "2L"},
    "records": [{"marker": "ESR1", "status": "positive", "rag_tags": ["ESR1-mut"]},
                {"marker": "gBRCA1", "status": "negative", "rag_tags": ["gBRCA"]},
                {"marker": "gBRCA2", "status": "negative", "rag_tags": ["gBRCA"]}],
}


class FakeModel:
    def encode(self, texts, show_progress_bar=False):
        import numpy as np
        return np.ones((len(texts), 1024)) if isinstance(texts, list) else np.ones(1024)


def _reimb(cid, drugs, line):
    return {"chunk_id": cid, "doc_type": "reimbursement", "chunk_kind": "reimbursement_condition", "text": cid,
            "drugs": drugs, "setting": ["locally_advanced", "metastatic"], "line": line, "subtype": ["any"],
            "parent_id": None, "superseded_by": None, "source": "HIRA-booklet", "version": "2026-10-01",
            "reimbursement": {"source_type": "baseline", "notice_no": "제2026-1호", "effective_from": "2024-01-01"}}


@pytest.fixture
def index(monkeypatch):
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        monkeypatch.setitem(sys.modules, "sentence_transformers",
                            types.SimpleNamespace(SentenceTransformer=None, CrossEncoder=None))
    from src.rag import client as rag_client
    from src.rag import indexer, searcher
    from src.rag.chunk_store import load_guideline_chunks, select_index_chunks

    monkeypatch.setattr(rag_client, "_client", QdrantClient(":memory:"))
    monkeypatch.setattr(rag_client, "_model", FakeModel())
    searcher.clear_search_cache()
    indexer.init_collection()
    indexer.index_chunks(select_index_chunks(load_guideline_chunks()))
    indexer.index_chunks([_reimb("r-fulv", ["fulvestrant"], ["2L", ">=3L"]),
                          _reimb("r-fulv-1l", ["fulvestrant"], ["1L"]),
                          _reimb("r-zol", ["zoledronic acid"], ["any"])])
    yield
    rag_client._client = None


def test_patient_from_state_reads_schema_fields():
    from src.rag.retrieve import patient_from_state
    p = patient_from_state(PATIENT, "metastatic")
    assert p["metastatic_sites"] == ["bone"] and p["menopausal_status"] == "postmenopausal"
    assert p["stage_at_diagnosis"] == "locally_advanced" and p["pcr"] is None
    assert {"AI_nonsteroidal", "SERD"} <= set(p["prior_subclasses"])  # 보조 AI와 전이 후 fulvestrant
    assert "Bone-modifying Agent" not in p["prior_classes"]  # 골 보호제는 이전 치료로 넣지 않는다
    assert patient_from_state(PATIENT, "early")["prior_subclasses"] == []  # 전이성일 때만


def test_retrieve_returns_guideline_with_parents_and_matching_reimbursement(index, monkeypatch):
    from src.rag import searcher
    from src.rag.retrieve import retrieve_for_recommend
    calls, real = [], searcher.search_guidelines
    monkeypatch.setattr(searcher, "search_guidelines", lambda **kw: calls.append(kw) or real(**kw))
    guideline, reimbursement = retrieve_for_recommend(PATIENT, RECORD, as_of="2026-10-20", rerank=False)
    # 주 검색 1번 + 뼈 전이 추가 검색 1번 (de novo 아님: 진단 시 국소 진행성) + 알고리즘 그림 경로 검색 1번 (주 검색과 같은 조건).
    # 모두 부모를 붙여 달라고 부른다
    assert [kw["query_text"].split()[0] for kw in calls] == ["second-line", "bone", "second-line"]
    assert [kw.get("chunk_kind", "recommendation") for kw in calls] == ["recommendation", "recommendation", "algorithm"]
    assert all(kw["with_parent"] and kw["negative_tags"] == ["gBRCA"] for kw in calls)
    assert guideline and all(c["doc_type"] == "guideline" and c["parent"] for c in guideline)
    assert len({c["chunk_id"] for c in guideline}) == len(guideline)
    kinds = [c["chunk_kind"] for c in guideline]
    assert "algorithm" in kinds and kinds == sorted(kinds, key=lambda k: k == "algorithm")  # 알고리즘 경로는 맨 뒤
    drugs = {d for c in guideline if c["chunk_kind"] != "algorithm" for d in c["drugs"]}
    assert all(r["doc_type"] == "reimbursement" and set(r["matched_drugs"]) <= drugs for r in reimbursement)
    ids = {r["chunk_id"] for r in reimbursement}
    if "fulvestrant" in drugs:
        assert "r-fulv" in ids and "r-fulv-1l" not in ids  # 2차 환자에게 1차 급여 행은 거른다
    if "zoledronic acid" in drugs:
        assert "r-zol" in ids


def test_public_api():
    import src.rag as rag
    assert callable(rag.retrieve_for_recommend)
