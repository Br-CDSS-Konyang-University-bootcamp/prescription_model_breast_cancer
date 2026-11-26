"""화면 1 찾기: 환자 번호(등록번호·가상 번호)나 이름으로 사례를 찾는다. 여러 사례 폴더를 합친다.

실행 (team_project 폴더): python -m pytest tests/app/test_screen1_find.py
"""
import pytest

from src.app.script import screen1 as s

VH = s.ROOT / "data" / "virtual_hospital"
APP = s.App([s.DEFAULT_CASES, VH / "tcga" / "charts", VH / "tcga_recur" / "charts"], s.c.SAVE_DIR)


def test_scenes_of_one_patient_are_two_cases():
    """수술 후·재발 장면은 폴더 이름이 같아도 patient_ref로 갈린다 (D-12)."""
    cases = APP.cases()
    assert "VH-T0043" in cases and "VH-T0043-R" in cases
    assert APP.patient_state("VH-T0043-R")["patient_ref"] == "VH-T0043-R"


def test_find_by_registration_no_returns_both_scenes():
    hits = APP.find("10000043")
    assert [h["case"] for h in hits] == ["VH-T0043", "VH-T0043-R"]
    assert {h["set"] for h in hits} == {"tcga", "tcga_recur"}
    assert all(h["name"] == hits[0]["name"] for h in hits)


def test_find_by_virtual_id_and_name():
    assert [h["case"] for h in APP.find("vh-t0043")] == ["VH-T0043", "VH-T0043-R"]
    assert [h["case"] for h in APP.find("VC-0103")] == ["VC-0103"]
    name = APP.find("10000001")[0]["name"]
    assert [h["case"] for h in APP.find(name)] == ["VH-T0001"]          # 가상 병원 이름은 환자마다 다르다 (Y-08)
    assert len(APP.find("김가상")) > 1                                   # 가상 차트는 모두 같은 이름 → 목록에서 고름


def test_find_nothing():
    assert APP.find("") == [] and APP.find("99999999") == [] and APP.find("없는이름") == []


def test_draft_opens_found_case():
    case = APP.find("10000043")[1]["case"]
    assert APP.draft(case)["draft"]["patient_ref"] == "VH-T0043-R"
    with pytest.raises(KeyError):
        APP.draft("VH-T9999")
