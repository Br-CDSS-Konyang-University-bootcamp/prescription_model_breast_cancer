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


def test_only_male_case_is_skipped():
    """남성(VC-0129)은 폐경 칸이 해당 없음인데 스키마가 HR+에 폐경(pre/post)을 필수로 둬 만들 수 없다."""
    skipped = [case for case in CASES if cf.build(APP, case)[0] is None]
    assert skipped == ["VC-0129"]
