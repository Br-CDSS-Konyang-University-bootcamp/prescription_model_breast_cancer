"""화면 2 처방 선택 저장 (src/app/script/screen2.py save_decision)과 초안 스키마 src/app/prescription_decision.json.
LLM 없이 추천 결과 형식만 흉내 낸다. team_project 폴더에서 python -m pytest tests/app
"""
import json

import pytest
from jsonschema import Draft202012Validator

from src.app.script import screen2 as s2

CONFIRMED = json.loads((s2.ROOT / "tests" / "fixtures" / "virtual_charts" / "VC-0103" / "expected" / "confirmed_state.json")
                       .read_text(encoding="utf-8"))
OPTIONS = [{"therapy": "ET alone", "drugs": [], "evidence": "LoE V, GoR B", "reimbursement": "no_criteria"},
           {"therapy": "Fulvestrant—ribociclib", "drugs": ["fulvestrant", "ribociclib"], "evidence": "LoE I, GoR A",
            "reimbursement": "covered_conditions_unverified", "reimbursement_reason": "조건 충족 (r09)",
            "citations": ["esmo-mbc-2026-05-luminal-1l-0fd38a"],
            "reimbursement_citations": ["hira-booklet-20261101-bc-pal-endo-2lplus-r09"]}]
REC = {"recommendation": {"generated_at": "2026-11-03T09:13:00+09:00", "model": "qwen3:14b", "options": OPTIONS},
       "ranked": s2.ranked(OPTIONS)}


def save(tmp_path, **body):
    return s2.save_decision({"decided_by": "user-test", **body}, CONFIRMED, REC, tmp_path)


def test_accept_option_records_shown_rank(tmp_path):
    """options[1]은 근거 수준(I, A)이 높아 화면에서 1안으로 보인다. selected_rank가 1, 급여 분류와 근거 인용을 옮긴다."""
    path, doc, errors = save(tmp_path, action="accept_option", selected_option_index=1)
    assert errors == [] and path.name == "v1.json"
    assert (doc["selected_option_index"], doc["selected_rank"]) == (1, 1)
    assert doc["reimbursement"] == "covered_conditions_unverified"
    assert doc["reimbursement_reason"] == "조건 충족 (r09)"
    assert doc["citations"] == ["esmo-mbc-2026-05-luminal-1l-0fd38a"]
    assert doc["reimbursement_citations"] == ["hira-booklet-20261101-bc-pal-endo-2lplus-r09"]
    assert doc["setting"] == "palliative" and doc["line"] is None
    assert json.loads(path.read_text(encoding="utf-8")) == doc


def test_custom_and_defer(tmp_path):
    _, doc, errors = save(tmp_path, action="custom", drugs=["capecitabine"], setting="palliative", line="2L")
    assert errors == [] and doc["therapy"] == "capecitabine" and doc["reimbursement"] is None
    assert (doc["citations"], doc["reimbursement_citations"], doc["reimbursement_reason"]) == ([], [], None)
    path, doc, errors = save(tmp_path, action="defer", defer_reason="mdt")
    assert errors == [] and path.name == "v2.json" and doc["therapy"] is None


@pytest.mark.parametrize("body, msg", [
    ({"action": "defer", "defer_reason": "다학제 회의"}, "보류 이유"),   # 코드가 아닌 한국어 문장
    ({"action": "accept_option", "selected_option_index": 5}, "추천안"),
    ({"action": "custom", "drugs": [], "setting": "palliative"}, "약을 하나 이상"),
    ({"action": "custom", "drugs": ["capecitabine"], "setting": "maintenance"}, "setting"),   # 스키마가 막음
])
def test_refuses(tmp_path, body, msg):
    path, _, errors = save(tmp_path, **body)
    assert path is None and any(msg in e for e in errors)
    assert not any(tmp_path.iterdir())


def test_schema_action_rules(tmp_path):
    """action마다 비워야 할 칸: 보류인데 처방이 있으면 실패."""
    schema = json.loads(s2.DECISION_SCHEMA.read_text(encoding="utf-8"))
    _, doc, _ = save(tmp_path, action="defer", defer_reason="other")
    v = Draft202012Validator(schema)
    assert list(v.iter_errors(doc)) == []
    assert list(v.iter_errors({**doc, "therapy": "capecitabine"}))


# 현재 치료 유지와 보조 약물 (팀 안건 A src/input/team_agenda_A_2026-11-04.md, VC-0108)
VC0108 = json.loads((s2.ROOT / "tests" / "fixtures" / "virtual_charts" / "VC-0108" / "expected" / "confirmed_state.json")
                    .read_text(encoding="utf-8"))
SUPPORTIVE = [{"therapy": "denosumab", "drugs": ["denosumab"], "reimbursement": "covered",
               "reimbursement_reason": "조건 충족 (supp-denosumab-1)", "citations": ["esmo-mbc-2026-05-site-bone-087674"],
               "reimbursement_citations": ["hira-booklet-20261101-supp-denosumab-1"]},
              {"therapy": "zoledronic acid", "drugs": ["zoledronic acid"], "reimbursement": "covered_conditions_unverified",
               "reimbursement_reason": "확인 필요", "citations": ["esmo-mbc-2026-05-site-bone-087674"],
               "reimbursement_citations": ["hira-booklet-20261101-supp-zoledronic-b"]}]
REC_SUPP = {"recommendation": {**REC["recommendation"], "supportive_options": SUPPORTIVE}, "ranked": REC["ranked"]}


def test_continue_current_with_supportive(tmp_path):
    """VC-0108: 투약 중인 ribociclib + letrozole 유지 + denosumab 시작을 한 번에 저장한다."""
    path, doc, errors = s2.save_decision({"decided_by": "user-test", "action": "continue_current",
                                          "supportive_option_indexes": [0, 0]}, VC0108, REC_SUPP, tmp_path)
    assert errors == [] and path.name == "v1.json"
    assert (doc["therapy"], doc["drugs"]) == ("ribociclib + letrozole", ["ribociclib", "letrozole"])
    assert (doc["setting"], doc["line"], doc["reimbursement"], doc["citations"]) == ("palliative", None, None, [])
    assert doc["selected_option_index"] is None and doc["selected_rank"] is None
    assert [s["therapy"] for s in doc["supportive"]] == ["denosumab"]   # 같은 번호를 두 번 보내도 한 번
    assert doc["supportive"][0]["reimbursement_citations"] == ["hira-booklet-20261101-supp-denosumab-1"]


def test_supportive_with_accept_and_defer(tmp_path):
    """보조 약물은 추천안 채택·보류와도 함께 고를 수 있다."""
    _, doc, errors = s2.save_decision({"decided_by": "user-test", "action": "accept_option", "selected_option_index": 1,
                                       "supportive_option_indexes": [1]}, CONFIRMED, REC_SUPP, tmp_path)
    assert errors == [] and doc["therapy"] == "Fulvestrant—ribociclib"
    assert doc["supportive"][0]["option_index"] == 1 and doc["supportive"][0]["reimbursement"] == "covered_conditions_unverified"
    _, doc, errors = s2.save_decision({"decided_by": "user-test", "action": "defer", "defer_reason": "pending_test",
                                       "supportive_option_indexes": [0]}, CONFIRMED, REC_SUPP, tmp_path)
    assert errors == [] and doc["therapy"] is None and len(doc["supportive"]) == 1


@pytest.mark.parametrize("confirmed, body, msg", [
    (CONFIRMED, {"action": "continue_current"}, "투약 중인 치료가 없어"),   # VC-0103: anastrozole 진행 뒤 투약 중인 약 없음
    (VC0108, {"action": "continue_current", "supportive_option_indexes": [2]}, "보조 약물"),
    (VC0108, {"action": "continue_current", "supportive_option_indexes": ["0"]}, "보조 약물"),
])
def test_refuses_continue_and_supportive(tmp_path, confirmed, body, msg):
    path, _, errors = s2.save_decision({"decided_by": "user-test", **body}, confirmed, REC_SUPP, tmp_path)
    assert path is None and any(msg in e for e in errors)


def test_schema_continue_current_rules(tmp_path):
    """현재 치료 유지는 급여·근거 인용을 옮기지 않는다 (다시 판정하지 않음)."""
    v = Draft202012Validator(json.loads(s2.DECISION_SCHEMA.read_text(encoding="utf-8")))
    _, doc, _ = s2.save_decision({"decided_by": "user-test", "action": "continue_current"}, VC0108, REC_SUPP, tmp_path)
    assert list(v.iter_errors(doc)) == []
    assert list(v.iter_errors({**doc, "reimbursement": "covered"}))
    assert list(v.iter_errors({**doc, "drugs": []}))
