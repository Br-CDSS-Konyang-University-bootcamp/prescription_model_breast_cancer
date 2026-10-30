"""화면 1 확정값 (src/input/script/confirmed.py). team_project 폴더에서 python -m pytest tests/input/test_confirmed.py

가상 차트마다 A의 patient_state 정답 + B의 assess() 결과로 초안을 만들고,
빈 필수 칸을 채우면 schemas/confirmed_state.json을 통과하는지 본다.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from src.input.script import confirmed as c

ROOT = Path(__file__).resolve().parents[2]
CHARTS = ROOT / "tests" / "fixtures" / "virtual_charts"
CASES = sorted(p.parents[1].name for p in CHARTS.glob("*/expected/patient_state.json"))

# B 파일 이름에 쉼표가 있어 파일 경로로 불러온다 (tests/biomarker/test_bm.py와 같음)
_spec = importlib.util.spec_from_file_location("bm", ROOT / "src" / "biomarker" / "BM1_ER,PR,HER2,Ki_67,subtype.py")
bm = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("bm", bm)
_spec.loader.exec_module(bm)


def load(case, name):
    with open(CHARTS / case / "expected" / name, encoding="utf-8") as f:
        return json.load(f)


def draft_of(case):
    ps = load(case, "patient_state.json")
    return c.build_draft(ps, bm.assess(ps))


def fill_required(draft):
    """빈 필수 칸을 스키마의 첫 허용 값으로 채운다 (의사가 고른 것처럼)."""
    rules = c.item_rules()
    for key in draft["needs"]["required"]:
        draft = c.set_item(draft, key, rules[key]["enum"][0], reason="시험: 의사 선택")
    return draft


@pytest.mark.parametrize("case", CASES)
def test_draft_passes_schema_after_required(case):
    draft = fill_required(draft_of(case))
    assert draft["needs"]["required"] == []
    doc, errors = c.to_confirmed_state(draft, "user-test", "2026-10-30T09:00:00+09:00")
    assert errors == [], errors
    assert "needs" not in doc


def test_vc0103_matches_hand_made():
    """손으로 만든 VC-0103 확정 예시 (2026-10-21)의 confirmed 값과 같다. 요법은 그때 있던 칸만 비교."""
    doc, errors = c.to_confirmed_state(draft_of("VC-0103"), "user-test")
    assert errors == []
    hand = load("VC-0103", "confirmed_state.json")
    assert doc["decision_context"] == hand["decision_context"]
    assert doc["index_day"] == hand["index_day"]
    for key in c.item_keys(hand["items"]):
        mine = c.items_get(doc["items"], key)["confirmed"]
        want = c.items_get(hand["items"], key)["confirmed"]
        if key == "prior_regimens":
            mine = [{k: r[k] for k in want[0]} for r in mine]
        assert mine == want, key


def test_set_item_status_and_reason():
    draft = draft_of("VC-0103")
    changed = c.set_item(draft, "setting.line_endocrine", "2L")
    it = changed["items"]["setting.line_endocrine"]
    assert it["status"] == "changed"
    _, errors = c.to_confirmed_state(changed, "user-test")
    assert any("reason" in e for e in errors)

    with_reason = c.set_item(draft, "setting.line_endocrine", "2L", reason="외부 병원 내분비 1차 기록 확인")
    assert c.to_confirmed_state(with_reason, "user-test")[1] == []

    with pytest.raises(ValueError):
        c.set_item(draft, "setting.line_endocrine", "unknown")
    with pytest.raises(ValueError):
        c.set_item(draft, "high_risk_early", {"hira": "yes", "esmo": "bad"})

    back = c.set_item(changed, "setting.line_endocrine", "1L")
    assert back["items"]["setting.line_endocrine"]["status"] == "confirmed"
    assert draft["items"]["setting.line_endocrine"]["confirmed"] == "1L"   # 원본은 그대로


def test_required_follow_disease_and_subtype():
    draft = draft_of("VC-0103")
    early = c.set_item(draft, "setting.disease", "early", reason="시험")
    assert early["decision_context"] == "early"
    assert "setting.phase" in early["needs"]["required"]
    tnbc = c.set_item(draft, "subtype", "TNBC", reason="시험")
    assert {"dfi_days", "markers.PD-L1"} <= set(c.required_items(tnbc["items"]))
    assert "menopausal_status" not in c.required_items(tnbc["items"])


@pytest.mark.parametrize("statuses, want", [
    (["positive", "not_recorded"], "positive"),
    (["vus", "negative"], "vus"),
    (["negative", "negative"], "negative"),
    (["negative", None], None),
    (["negative", "not_recorded"], None),
    (["not_done", "not_done"], "not_done"),
    (["not_recorded", "not_recorded"], "not_recorded"),
    (["unknown", "negative"], None),
])
def test_merge_genes(statuses, want):
    assert c._merge_genes(statuses) == want


@pytest.mark.parametrize("t, ln, grade, ki67, want", [
    ("T2", 4, 2, 10, {"hira": "yes", "esmo": "yes"}),
    ("T3", 1, 2, 10, {"hira": "yes", "esmo": "yes"}),
    ("T2", 2, 3, 10, {"hira": "yes", "esmo": "yes"}),
    ("T2", 2, 2, 25, {"hira": "no", "esmo": "yes"}),
    ("T2", 2, 2, 10, {"hira": "no", "esmo": "no"}),
    ("T2", 0, 3, 40, {"hira": "no", "esmo": "no"}),
    ("T2", None, 3, 40, {"hira": "unknown", "esmo": "unknown"}),
    ("T2", 2, "not_recorded", None, {"hira": "unknown", "esmo": "unknown"}),
])
def test_high_risk(t, ln, grade, ki67, want):
    assert c._high_risk(t, ln, grade, ki67) == want


def test_finalize_versions(tmp_path):
    draft = draft_of("VC-0103")
    p1, doc1, err1 = c.finalize(draft, "user-test", "2026-10-30T09:00:00+09:00", save_dir=tmp_path)
    assert err1 == [] and p1.name == "v1.json"
    assert doc1["visit_type"] == "initial" and doc1["supersedes"] is None
    p2, doc2, _ = c.finalize(draft, "user-test", "2026-10-30T10:00:00+09:00", save_dir=tmp_path)
    assert p2.name == "v2.json"
    assert doc2["visit_type"] == "follow_up"
    assert doc2["supersedes"] == {"version": 1, "confirmed_at": "2026-10-30T09:00:00+09:00"}
    assert json.loads(p1.read_text(encoding="utf-8"))["version"] == 1   # 이전 버전은 그대로


def test_finalize_refuses_missing_required(tmp_path):
    draft = c.set_item(draft_of("VC-0103"), "subtype", None)
    path, _, errors = c.finalize(draft, "user-test", save_dir=tmp_path)
    assert path is None
    assert any(e.startswith("subtype") for e in errors)
    assert not any(tmp_path.iterdir())
