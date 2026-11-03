"""가상 차트 정답 confirmed_state (src/app/script/confirmed_fixtures.py). team_project 폴더에서
python -m pytest tests/app

저장된 expected/confirmed_state.json이 정답 patient_state의 기본값과 같은지 본다 (patient_state·규칙을 바꾸면 다시 만들 것:
python -m src.app.script.confirmed_fixtures).
"""
import json

import pytest

from src.app.script import confirmed_fixtures as cf
from src.app.script import screen1 as s

APP = s.App(s.DEFAULT_CASES, s.c.SAVE_DIR)
CASES = APP.cases()


@pytest.mark.parametrize("case", CASES)
def test_fixture_matches_generator(case):
    path = s.DEFAULT_CASES / case / "expected" / "confirmed_state.json"
    doc, reasons = cf.build(APP, case)
    if case in cf.HAND_MADE:
        assert path.exists()
        return
    if doc is None:
        assert not path.exists(), f"{case}: 기본값으로 만들 수 없는데 파일이 있음 ({reasons})"
        return
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == doc, f"{case}: 다시 만들 것 (python -m src.app.script.confirmed_fixtures)"


def test_skipped_cases():
    """정답을 정할 수 없는 사례: VC-0106b는 Ki-67 값 충돌(의사가 고를 값), VC-0129는 남성이라 폐경이 해당 없음인데
    스키마가 HR+에 폐경(pre/post)을 필수로 둔다."""
    skipped = [case for case in CASES if cf.build(APP, case)[0] is None]
    assert skipped == ["VC-0106b", "VC-0129"]


def test_fixtures_match_scenario_expectations():
    """confirmed_expectations.csv (시나리오 B 줄·결정 시점)와 다른 칸은 accepted에 이유가 있어야 한다."""
    from src.app.script import confirmed_review as cr
    unexplained = [f"{case} {x['item']}: 기대 {x['expected']} / 확정 {x['actual']}"
                   for case, checks in cr.compare().items() for x in checks if not x["ok"] and not x["accepted"]]
    assert unexplained == []
