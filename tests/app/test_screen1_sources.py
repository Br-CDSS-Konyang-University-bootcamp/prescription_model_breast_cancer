"""화면 1 차트 받는 곳: 가상 병원 DB (병원 쪽 요청 + 정답 따로), 입력 모듈 방식 (진행 표시, 가짜 LLM).

실행 (team_project 폴더): python -m pytest tests/app/test_screen1_sources.py
DB 검사는 각자 만든 data/virtual_hospital/local/virtual_hospital.db가 있어야 한다 (없으면 건너뜀).
"""
import time

import pytest

from src.app.script import screen1 as s
from src.app.script.sources import Extractor, HospitalDbSource

DB = s.ROOT / "data" / "virtual_hospital" / "local" / "virtual_hospital.db"


@pytest.fixture(scope="module")
def db_app(tmp_path_factory):
    if not DB.exists():
        pytest.skip("가상 병원 DB를 만들지 않은 컴퓨터 (python -m src.virtual_hospital.scripts.db build)")
    tmp = tmp_path_factory.mktemp("app")
    return s.App(HospitalDbSource(DB), tmp / "confirmed", tmp)


def test_db_find_and_visits(db_app):
    hits = db_app.find("10000043")
    assert [h["case"] for h in hits] == ["VH-T0043", "VH-T0043-R"] and hits[0]["set"].startswith("외래 ")
    assert "VH-T0043-R" in db_app.cases()


def test_db_chart_is_hospital_request(db_app):
    """차트는 request_chart로 받은 문서이고, 정답 방식은 정답 JSON을 따로 꺼낸다."""
    d = db_app.draft("VH-T0043-R")
    assert d["header"]["source"] == "hospital_db" and d["header"]["input"] == "answer"
    assert d["draft"]["patient_ref"] == "VH-T0043-R"
    assert d["documents"] and "김지경" in db_app.source.chart("VH-T0043-R")


def test_llm_mode_needs_reading_first(db_app):
    with pytest.raises(KeyError):
        db_app.draft("VH-T0043", input="llm")
    with pytest.raises(ValueError):
        db_app.patient_state("VH-T0043", input="other")


def test_extractor_reports_progress_and_saves(tmp_path):
    """가짜 LLM (문서마다 후보 없음): 문서 수를 세고, 끝나면 patient_state를 저장하고, 화면 1 초안을 만들 수 있다."""
    calls = []

    def fake(msgs, schema, cfg):
        calls.append(1)
        time.sleep(0.05)
        return {"candidates": []}

    app = s.App(s.DEFAULT_CASES, tmp_path / "confirmed", tmp_path)
    app.extractor = Extractor(tmp_path / "extracted", complete=fake)
    st = app.extract_start("VC-0103")
    assert st["stage"] in ("reading", "done")
    for _ in range(200):
        st = app.extractor.status("VC-0103")
        if st["stage"] != "reading":
            break
        time.sleep(0.05)
    assert st["stage"] == "done", st
    assert len(calls) >= 1
    ps = app.patient_state("VC-0103", input="llm")
    assert ps["patient_ref"] == "VC-0103"
    assert app.draft("VC-0103", input="llm")["header"]["input"] == "llm"
    n = len(calls)
    assert app.extract_start("VC-0103")["stage"] == "done" and len(calls) == n   # 이미 읽은 것은 다시 부르지 않는다
