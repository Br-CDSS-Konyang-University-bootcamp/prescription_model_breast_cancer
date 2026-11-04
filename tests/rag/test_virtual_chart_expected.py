# tests/rag/test_virtual_chart_expected.py
# 가상 차트의 C 정답 파일(tests/fixtures/virtual_charts/*/expected/guideline.json)이 청크와 맞는지 검사한다. 검색 모델 없이 돈다.
# 정답 ID가 청크에 있고, 권고는 그 환자 확정값의 필터(병기·아형)를 통과해야 한다. 청크 ID가 바뀌면 이 파일들도 고친다.
import json
from pathlib import Path

import pytest

from src.rag.check_case import compare_expected
from src.rag.chunk_store import load_guideline_chunks
from src.rag.retrieve import from_confirmed_state

BASE_DIR = Path(__file__).resolve().parents[2]
FILES = sorted((BASE_DIR / "tests" / "fixtures" / "virtual_charts").glob("*/expected/guideline.json"))
CHUNKS = {c["chunk_id"]: c for c in load_guideline_chunks()}
BONE_AGENTS = ("denosumab", "zoledronic acid", "pamidronate", "ibandronate", "clodronate")


@pytest.mark.parametrize("path", FILES, ids=[p.parts[-3] for p in FILES])
def test_expected_guideline_matches_chunks(path):
    exp = json.loads(path.read_text(encoding="utf-8"))
    assert exp["format"] == "C guideline expected v0.1" and exp["patient_ref"] == path.parts[-3]
    assert exp["status"] in ("draft", "reviewed") and exp["expected_chunks"]
    state = json.loads((path.parent / Path(exp["input"]).name).read_text(encoding="utf-8"))
    record, _, lines = from_confirmed_state(state)
    assert (record["setting"]["disease"], record["subtype"], lines["guideline"][0]) == (
        exp["decision"]["setting"], exp["decision"]["subtype"], exp["decision"]["line"])
    # ER 저발현(HR+/HER2- + ER-low 태그)은 TNBC 권고도 찾는다 (query.extra_search_args, 팀 안건 6-2)
    subtypes = {record["subtype"], "any"}
    if record["subtype"] == "HR+/HER2-" and any("ER-low" in r.get("rag_tags", []) for r in record["records"]):
        subtypes.add("TNBC")
    for cid in exp["expected_chunks"] + exp.get("not_expected", []):
        c = CHUNKS[cid]
        assert c["chunk_kind"] == "recommendation" and not c.get("superseded_by")
        assert record["setting"]["disease"] in c["setting"]
        assert subtypes & set(c["subtype"]), cid
    assert {CHUNKS[cid]["parent_id"] for cid in exp["expected_chunks"]} <= set(exp["expected_parents"])
    for cid in exp.get("expected_algorithm", []):
        assert CHUNKS[cid]["chunk_kind"] == "algorithm"
    assert not set(exp["expected_chunks"]) & set(exp.get("not_expected", []))
    # 보조 약물 정답(2026-11-04 팀 결정): 골 보호제 권고만, 주 처방 정답·오답과 겹치지 않음
    bone = set(BONE_AGENTS)
    for cid in exp.get("expected_supportive", []):
        c = CHUNKS[cid]
        assert c["chunk_kind"] == "recommendation" and (set(c.get("drugs") or []) & bone), cid
        assert cid not in exp["expected_chunks"] and cid not in exp.get("not_expected", []), cid


def test_compare_expected_ranks_and_wrong_above():
    exp = {"expected_chunks": ["a"], "expected_algorithm": ["f"], "not_expected": ["w", "x"]}
    guideline = [{"chunk_id": "w"}, {"chunk_id": "a"}, {"chunk_id": "x"}, {"chunk_id": "f", "chunk_kind": "algorithm"}]
    r = compare_expected(exp, guideline)
    assert r["first_rank"] == 2 and r["mrr"] == 0.5 and r["algorithm"] == {"f": 1} and r["wrong_above"] == ["w"]
    s = compare_expected({"expected_chunks": ["a"], "expected_supportive": ["x"]}, guideline)
    assert s["first_rank"] == 2 and s["supportive"] == {"x": 3}  # 보조 약물은 주 처방 순위에 넣지 않는다
    assert compare_expected({"expected_chunks": ["z"]}, guideline)["mrr"] == 0.0
