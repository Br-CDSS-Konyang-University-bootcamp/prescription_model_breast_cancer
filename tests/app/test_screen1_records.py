"""화면 1 확정값 저장: 병원 기록 DB (records.DbStore)와 파일 (FileStore). 버전을 쌓고, 입력값을 버전마다 남긴다.

실행 (team_project 폴더): python -m pytest tests/app/test_screen1_records.py
"""
import sqlite3

import pytest

from src.app.script import screen1 as s
from src.app.script.records import DbStore, FileStore

CASE = "VC-0103"


def _draft(app):
    """화면 1에서 아무것도 고치지 않고 확정할 초안 (빈 필수 칸은 정답 확정 파일 값으로 채움)."""
    d = app.draft(CASE)["draft"]
    return s.drop_not_applicable(d)


def _confirmable(app):
    """필수 칸이 빈 사례도 있어, 이미 만든 정답 확정 파일(gold confirmed_state)의 items로 초안을 채운다."""
    gold = app.source.answer(CASE, "confirmed_state")
    d = _draft(app)
    d["items"] = gold["items"]
    return d


@pytest.fixture(params=["db", "files"])
def app(request, tmp_path):
    store = DbStore(tmp_path / "records.db") if request.param == "db" else FileStore(tmp_path / "confirmed")
    return s.App(s.DEFAULT_CASES, store, tmp_path)


def test_versions_stack_and_keep_input(app):
    path1, doc1, err1 = app.finalize(_confirmable(app), "user-test", "answer")
    assert err1 == [] and path1 and doc1["version"] == 1
    path2, doc2, _ = app.finalize(_confirmable(app), "user-test", "llm")
    assert doc2["version"] == 2 and doc2["supersedes"]["version"] == 1
    assert app.saved(CASE) == ["v1.json", "v2.json"]
    assert app.store.load(CASE, 1) == doc1
    assert (app.store.input_of(CASE, 1), app.store.input_of(CASE, 2)) == ("answer", "llm")
    assert app.screen2(CASE, 2)["input"] == "llm"
    with pytest.raises(KeyError):
        app.store.load(CASE, 3)
    with pytest.raises(ValueError):
        app.finalize(_confirmable(app), "user-test", "other")


def test_recommend_uses_input_saved_with_version(app, monkeypatch):
    """정답으로 확정한 버전은 주소에 input=llm이 와도 정답 patient_state로 추천한다."""
    app.finalize(_confirmable(app), "user-test", "answer")
    got = {}
    monkeypatch.setattr(app.recommender, "start", lambda ref, v, doc, ps, force: got.update(ps=ps) or {"stage": "검색"})
    app.rec_start(CASE, 1, input="llm")                          # 입력 모듈 결과가 없어도 실패하지 않는다
    assert got["ps"] == app.patient_state(CASE, "answer")


def test_db_store_leaves_no_files_and_never_overwrites(tmp_path):
    store = DbStore(tmp_path / "records.db")
    app = s.App(s.DEFAULT_CASES, store, tmp_path)
    app.finalize(_confirmable(app), "user-test", "answer")
    assert not (tmp_path / "confirmed").exists() and not list(tmp_path.rglob("v1.json"))
    with sqlite3.connect(store.path) as con:
        with pytest.raises(sqlite3.IntegrityError):              # 같은 버전은 다시 넣을 수 없다
            con.execute("INSERT INTO confirmed_states SELECT * FROM confirmed_states WHERE version = 1")
