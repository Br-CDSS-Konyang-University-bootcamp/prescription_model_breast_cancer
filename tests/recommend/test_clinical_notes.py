# tests/recommend/test_clinical_notes.py
# 참고란 (recommendation.json clinical_notes, proposal_clinical_notes_2026-10-29.md). 청크 text는 지어낸 테스트 문장이다.
import json
from pathlib import Path

from src.recommend.clinical_notes import clinical_notes
from src.recommend.pipeline import recommend

ROOT = Path(__file__).resolve().parents[2]
VC0108 = json.loads((ROOT / "tests/fixtures/virtual_charts/VC-0108/expected/patient_state.json").read_text(encoding="utf-8"))
CHUNK = {"chunk_id": "esmo-mbc-2026-05-luminal-1l-e03e88", "text": "TEST CHUNK (made up)"}
OPTIONS = [{"therapy": "palbociclib + letrozole", "drugs": ["palbociclib", "letrozole"]},
           {"therapy": "letrozole 단독", "drugs": ["letrozole"]}]


INDEX = {"booklet_date": "2026-11-01", "overlay_notices": [], "scheduled_count": 0, "in_progress_count": 0}


def confirmed(**items):
    return {"items": {k: {"confirmed": v} for k, v in items.items()}}


def test_comorbidity_and_contraindicated_classes():
    notes = clinical_notes(VC0108, OPTIONS, [CHUNK], confirmed(contraindicated_classes=["CDK4/6_inhibitor"]))
    by = {n["topic"]: n for n in notes}
    assert by["comorbidity"]["text"].startswith("동반질환: ")                     # VC-0108 CKD 3a
    assert by["comorbidity"]["citations"] == [CHUNK["chunk_id"]]
    ci = by["contraindicated_classes"]
    assert ci["applies_to"] == ["palbociclib + letrozole"]                       # 후보는 빼지 않고 표시만
    assert ci["source_fields"] == ["confirmed_state.items.contraindicated_classes"]


def test_citations_only_from_given_chunks():
    notes = clinical_notes(VC0108, OPTIONS, [], confirmed(contraindicated_classes=["CDK4/6_inhibitor"]))
    assert all("citations" not in n for n in notes)                              # 넘어오지 않은 청크 ID는 붙이지 않는다


def test_visceral_crisis_confirmed_over_chart():
    ps = json.loads(json.dumps(VC0108))
    ps["fields"]["patient"]["visceral_crisis"] = {"status": "present", "value": "yes"}
    assert any("차트 기록" in n["text"] for n in clinical_notes(ps, [], []))
    assert not any(n["topic"] == "visceral_crisis" for n in clinical_notes(ps, [], [], confirmed(visceral_crisis="no")))
    assert any("의사 확정" in n["text"] for n in clinical_notes(ps, [], [], confirmed(visceral_crisis="yes")))


def test_recommend_output_passes_schema():
    record = {"patient_ref": "VC-0108", "subtype": "HR+/HER2-", "setting": {"disease": "metastatic"},
              "records": [], "tests_needed": []}
    answer = {"options": [], "out_of_scope": True, "out_of_scope_reason": "TEST", "conflicts": []}
    out, _, errors = recommend(VC0108, record, [CHUNK], [], lambda prompt: answer, INDEX, "test",
                               confirmed_state=confirmed(contraindicated_classes=["CDK4/6_inhibitor"]))
    assert not errors
    assert {n["topic"] for n in out["clinical_notes"]} >= {"comorbidity", "contraindicated_classes"}
