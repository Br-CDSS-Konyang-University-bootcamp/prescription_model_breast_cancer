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


VC0103 = json.loads((BASE_DIR / "tests" / "fixtures" / "virtual_charts" / "VC-0103" / "expected" /
                     "confirmed_state.json").read_text(encoding="utf-8"))


def test_from_confirmed_state_reads_only_confirmed_values():
    # VC-0103: 보조 anastrozole 복용 중 폐 전이, 폐경 후, PIK3CA·ESR1 음성, 고식적 내분비 1차 결정
    from src.rag.query import search_args
    from src.rag.retrieve import from_confirmed_state
    record, patient, lines = from_confirmed_state(VC0103)
    assert (record["subtype"], record["setting"]["disease"], record["setting"]["line"]) == ("HR+/HER2-", "metastatic", "1L")
    assert patient["metastatic_sites"] == ["lung"] and patient["menopausal_status"] == "postmenopausal"
    assert patient["prior_subclasses"] == ["AI_nonsteroidal"] and patient["endocrine_relapse_12m"] == "yes"
    assert patient["stage_at_diagnosis"] is None  # 재발 전이라 de novo가 아니다
    args = search_args(record, **patient)
    assert "recurring while receiving adjuvant ET" in args["query_text"]  # ESMO 1차 갈림길 (fulvestrant-CDK4/6 쪽)
    assert args["endocrine_relapse_12m"] == "yes"  # 반대 갈래(AI-CDK4/6) 권고 감점에 쓴다
    assert {"PIK3CA-mut", "ESR1-mut"} <= set(args["negative_tags"]) and args["biomarker_tags"] == []
    # 보조 내분비 중 재발(DEEM-ENDO-ADJ-1Y met)이면 급여는 '2차 이상' 내분비 행까지 찾는다 (공고 3.다.7·9)
    assert lines == {"guideline": ["1L"], "reimbursement": ["1L", "2L"]}


def test_decision_lines_by_subtype_and_setting():
    from src.rag.retrieve import decision_lines

    def item(value):
        return {"confirmed": value}
    hr = {"setting.disease": item("metastatic"), "subtype": item("HR+/HER2-"),
          "setting.line_endocrine": item(">=3L"), "setting.line_chemo": item("1L"), "deemed_lines": item({})}
    assert decision_lines(hr) == {"guideline": [">=3L", "1L"], "reimbursement": [">=3L", "1L"]}
    no_more_et = {**hr, "setting.line_endocrine": item("not_applicable")}
    assert decision_lines(no_more_et)["guideline"] == ["1L"]
    her2 = {**hr, "subtype": item("HR-/HER2+"), "setting.line_chemo": item("2L"),
            "deemed_lines": item({"DEEM-HER2ADC-6M": "met"})}
    assert decision_lines(her2) == {"guideline": ["2L"], "reimbursement": [">=3L", "2L"]}
    early = {"setting.disease": item("early"), "subtype": item("TNBC"), "setting.phase": item("neoadjuvant")}
    assert decision_lines(early) == {"guideline": ["neoadjuvant"], "reimbursement": ["neoadjuvant"]}


def test_retrieve_with_confirmed_state(index, monkeypatch):
    # 가짜 임베딩은 순위가 임의라, 지침 검색은 VC-0103의 정답 권고(fulvestrant-CDK4/6)를 돌려주게 고정하고
    # 급여 검색은 실제 함수로 가짜 급여 행(1L, 2L·>=3L)을 찾는다
    from src.rag import reimbursement_search, searcher
    from src.rag.chunk_store import get_chunk, get_parent
    from src.rag.retrieve import retrieve_for_recommend
    answer = get_chunk("esmo-mbc-2026-05-luminal-1l-0fd38a")
    searches, calls, real = [], [], reimbursement_search.search_reimbursement
    monkeypatch.setattr(searcher, "search_guidelines",
                        lambda **kw: searches.append(kw) or [{**answer, "score": 1.0, "parent": get_parent(answer)}])
    monkeypatch.setattr(reimbursement_search, "search_reimbursement",
                        lambda drugs, **kw: calls.append((drugs, kw)) or real(drugs, **kw))
    guideline, reimbursement = retrieve_for_recommend(VC0103, rerank=False)
    assert [c["chunk_id"] for c in guideline] == [answer["chunk_id"]] and guideline[0]["parent"]
    assert "recurring while receiving adjuvant ET" in searches[0]["query_text"]
    # 기준일은 확정 시각의 날짜, 급여 차수는 1L과 간주 규칙(DEEM-ENDO-ADJ-1Y)의 2L
    assert {kw["as_of"] for _, kw in calls} == {"2026-10-21"} and {kw["line"] for _, kw in calls} == {"1L", "2L"}
    assert {"r-fulv", "r-fulv-1l"} <= {r["chunk_id"] for r in reimbursement}  # '2차 이상' 행도 빠지지 않는다
    with pytest.raises(TypeError):
        retrieve_for_recommend({"subtype": "HR+/HER2-"})  # biomarker_record 없이 confirmed_state도 아니면 거부


def test_public_api():
    import src.rag as rag
    assert callable(rag.retrieve_for_recommend)


def test_check_case_validates_and_summarizes_without_text():
    from src.rag.check_case import summarize, validate
    assert validate(VC0103) == []  # A의 예시는 schemas/confirmed_state.json을 통과한다
    row = {"chunk_id": "r-1", "text": "공고 원문", "matched_drugs": ["fulvestrant"], "extra_drugs": ["palbociclib"],
           "setting": ["metastatic"], "line": ["2L"], "parents": [{"chunk_id": "r-l2"}],
           "reimbursement": {"notice_no": "제2026-1호"}}
    out = summarize([], [row])
    assert out["reimbursement"][0]["parents"] == ["r-l2"] and "text" not in out["reimbursement"][0]
