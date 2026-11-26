"""가상 병원 DB: 만들기와 읽기 함수. git에 있는 TCGA만으로도 돌아야 한다 (BCNB·슬라이드 벡터는 있으면 확인).

실행 (team_project 폴더): python -m pytest tests/virtual_hospital/test_db.py
"""
import json

import pytest

from src.virtual_hospital.scripts import db
from src.virtual_hospital.scripts.common import FEATURES, LOCAL, OUT, read_csv


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    path = tmp_path_factory.mktemp("vhdb") / "vh.db"
    db.build(path)
    c = db.connect(path)
    yield c
    c.close()


def test_tcga_patients_match_files(con):
    for branch, folder in (("tcga_postop", "tcga"), ("tcga_recur", "tcga_recur")):
        want = {r["vp_id"] for r in read_csv(OUT / folder / "patients.csv")}
        assert {r["vp_id"] for r in db.list_patients(con, branch=branch)} == want


def test_states_are_the_saved_json(con):
    vp = read_csv(OUT / "tcga" / "patients.csv")[0]["vp_id"]
    for kind in db.STATE_KINDS:
        saved = json.loads((OUT / "tcga" / "charts" / vp / "expected" / f"{kind}.json").read_text(encoding="utf-8"))
        assert db.get_state(con, vp, kind, branch="tcga_postop") == saved
    assert db.get_chart(con, vp, branch="tcga_postop") == (OUT / "tcga" / "charts" / vp / "chart.txt").read_text(encoding="utf-8")


def test_two_scenes_need_branch(con):
    vp = read_csv(OUT / "tcga_recur" / "patients.csv")[0]["vp_id"]       # 재발 갈래 환자는 수술 후 갈래에도 있다
    with pytest.raises(ValueError):
        db.get_chart(con, vp)
    assert "고식" in db.get_chart(con, vp, branch="tcga_recur")


def test_ident_per_patient_and_ref_per_scene(con):
    """R-08·Y-08: 등록번호·이름은 환자 단위로 하나 (두 장면은 같고, 환자끼리는 다름). D-12: patient_ref는 장면 단위."""
    rows = db.list_patients(con)
    by_vp: dict[str, set] = {}
    for r in rows:
        by_vp.setdefault(r["vp_id"], set()).add((r["registration_no"], r["patient_name"]))
        assert r["patient_ref"] == (r["vp_id"] + "-R" if r["branch"] == "tcga_recur" else r["vp_id"])
        assert r["registration_no"] == ("1" if r["vp_id"].startswith("VH-T") else "2") + r["vp_id"][4:].zfill(7)
    assert all(len(v) == 1 for v in by_vp.values())
    idents = [next(iter(v)) for v in by_vp.values()]
    assert len({i[0] for i in idents}) == len({i[1] for i in idents}) == len(idents)
    assert len({r["patient_ref"] for r in rows}) == len(rows)


def test_truth_needs_allow_future(con):
    vp = read_csv(OUT / "tcga" / "patients.csv")[0]["vp_id"]
    with pytest.raises(PermissionError):
        db.truth(con, vp, branch="tcga_postop")
    assert db.truth(con, vp, branch="tcga_postop", allow_future=True)


@pytest.mark.skipif(not (LOCAL / "bcnb" / "patients.csv").exists(), reason="BCNB를 만들지 않은 컴퓨터")
def test_bcnb_loaded(con):
    rows = db.list_patients(con, branch="bcnb_preop")
    assert len(rows) == len(read_csv(LOCAL / "bcnb" / "patients.csv"))
    assert all(r["phase"] == "neoadjuvant" for r in rows)


@pytest.mark.skipif(not (FEATURES / "tcga_hoptimus0.npz").exists(), reason="슬라이드 벡터를 받지 않은 컴퓨터")
def test_similar_excludes_self_and_same_feature_set(con):
    sid = con.execute("SELECT slide_id FROM slide_embeddings WHERE feature_set = 'tcga_hoptimus0' LIMIT 1").fetchone()[0]
    vp = con.execute("SELECT vp_id FROM slides WHERE slide_id = ?", (sid,)).fetchone()[0]
    hits = db.similar(con, sid, k=5)
    assert len(hits) == 5 and all(h["vp_id"] != vp for h in hits)
    assert all(h["slide_id"].startswith("VH-T") for h in hits)            # 묶음(TCGA·BCNB)을 섞지 않는다
    assert hits == sorted(hits, key=lambda h: -h["similarity"])
