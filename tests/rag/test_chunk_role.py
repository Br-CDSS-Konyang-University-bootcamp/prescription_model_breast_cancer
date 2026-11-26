# 지침 청크 역할(role) 시험 (B #158 요청, 2026-11-18). 청크 JSON의 role이 검토표·규칙과 같은지, 대표 청크의 역할이 맞는지
import json

from src.rag import chunk_role as cr
from src.rag.chunk_common import CHUNKS_DIR


def _chunks():
    return [c for name in ("esmo_chunks.json", "esmo_algorithm_chunks.json")
            for c in json.loads((CHUNKS_DIR / name).read_text(encoding="utf-8"))]


def test_every_recommendation_and_path_has_a_role_that_matches_the_review_sheet():
    review = cr.load_review()
    chunks = _chunks()
    targets = [c for c in chunks if cr.needs_role(c)]
    assert targets and all(c.get("role") in cr.ROLES for c in targets)
    assert all("role" not in c for c in chunks if not cr.needs_role(c))   # 소단원·그림 부모에는 없다
    assert {c["chunk_id"] for c in targets} == set(review)                # 검토표가 모든 대상을 담는다
    assert [c["chunk_id"] for c in targets if c["role"] != cr.final_role(c, review)] == []  # python -m src.rag.chunk_role 반영됨
    assert all(r["role"] in ("",) + cr.ROLES for r in review.values())


def test_representative_roles():
    role = {c["chunk_id"].split("-", 4)[-1]: c["role"] for c in _chunks() if cr.needs_role(c)}
    assert role["hrpos-5b21e4"] == "caution"          # olaparib·abemaciclib 병용 금지
    assert role["hrpos-941c55"] == "judgment"         # Luminal A 대부분 항암 불필요
    assert role["hrpos-6d44cc"] == "judgment"         # 유전자 검사로 항암 여부
    assert role["hrpos-ca0c8d"] == "prescribe_class"  # ChT followed by ET (약 목록이 빔)
    assert role["luminal-1l-02649c"] == "prescribe"   # AI—CDK4/6 inhibitor, 선택지로 AI—ribociclib 등 약 이름이 적혀 있다
    assert role["luminal-1l-e03e88"] == "prescribe_class"   # ET alone
    assert role["luminal-2l-49918b"] == "prescribe"   # fulvestrant—capivasertib
    assert role["her2-1l-58a1c0"] == "prescribe"      # taxane 금기면 capecitabine·vinorelbine (사람이 고침)


def test_auto_role_rules():
    assert cr.auto_role({"chunk_kind": "recommendation", "text": "X and Y should not be combined [V, A]."}) == "caution"
    assert cr.auto_role({"chunk_kind": "recommendation", "text": "Olaparib is recommended [I, A]."}) == "prescribe"
    assert cr.auto_role({"chunk_kind": "recommendation", "text": "ET alone can be recommended [V, B]."}) == "prescribe_class"
    assert cr.auto_role({"chunk_kind": "recommendation", "text": "MDT discussion is recommended [V, A]."}) == "judgment"
    path = {"chunk_kind": "algorithm", "parent_id": "p", "text": "Figure 1. (algorithm path): A → Olaparib Footnotes: x"}
    assert cr.auto_role(path) == "prescribe"
