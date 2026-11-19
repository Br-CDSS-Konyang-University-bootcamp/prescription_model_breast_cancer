"""가상 병원 환자 (src/virtual_hospital/) 검사: 규칙 표 ↔ 코드, 저장된 차트가 다시 만든 것과 같은지, mini check() 통과.

실행 (team_project 폴더): python -m pytest tests/virtual_hospital/test_virtual_hospital.py
다시 만들기 검사는 team_project_final(모듈 1 데이터)이 있어야 하고, BCNB 검사는 data/virtual_hospital/local/bcnb/가 있어야 한다.
없으면 건너뛴다.
"""
import json
import re

import pytest

from src.virtual_hospital.common import CODE, FINAL, LOCAL, OUT, ROOT, read_csv, rules

RULE_ID = re.compile(r"\b([SMDYNRIG]-\d\d)\b")
CHARTS = OUT / "tcga" / "charts"


def test_rule_ids_in_code_are_in_table():
    table = rules()
    used = {m for f in CODE.glob("*.py") for m in RULE_ID.findall(f.read_text(encoding="utf-8"))}
    refs = {r["ref_id"] for r in read_csv(ROOT / "rules" / "references.csv")}      # R-0n은 근거 표 id이기도 하다
    assert used - set(table) - refs == set()


def test_bcnb_outputs_stay_local():
    """BCNB 약관: BCNB에서 나온 산출물은 local/에만. 올라가는 차트 폴더(tcga, tcga_recur)에는 BCNB가 없어야 한다."""
    assert not any("BCNB" in f.read_text(encoding="utf-8", errors="ignore")
                   for base in (OUT / "tcga", OUT / "tcga_recur") for f in base.rglob("*")
                   if f.is_file() and f.suffix in (".csv", ".txt", ".json"))


def test_rule_ids_in_output_are_in_table():
    table = rules()
    used = {x for r in read_csv(OUT / "tcga" / "fields.csv") if r["rule_id"]
            for x in r["rule_id"].split(", ")}                     # 여러 규칙을 거친 칸은 "D-06, D-05"처럼 적는다
    assert used - set(table) == set()


def test_rules_have_basis_and_source():
    for r in rules().values():
        assert r["설명"] and r["출처"], r["rule_id"]


def test_synthetic_and_derived_rows_have_basis():
    for r in read_csv(OUT / "tcga" / "fields.csv"):
        if r["origin"] in ("synthetic", "derived"):
            assert r["basis"] and r["rule_id"], r


def test_no_source_ids_outside_local():
    """원본 ID(TCGA 바코드)는 local/에만 둔다. out/의 CSV·차트에 없어야 한다."""
    pat = re.compile(r"TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}(?!-\d\d[A-Z]-\d\d-DX)")
    for f in list((OUT / "tcga").rglob("*.csv")) + list(CHARTS.glob("*/chart.txt")):
        assert not pat.search(f.read_text(encoding="utf-8")), f


@pytest.fixture(scope="module")
def built():
    if not FINAL.exists():
        pytest.skip(f"{FINAL} 없음 (모듈 1 데이터)")
    from src.virtual_hospital.tcga import build_all
    pts, *_ = build_all()
    return {p.vp_id: p for p in pts}


def test_saved_charts_match_rebuild(built):
    """저장된 차트 중 앞·가운데·끝 3건을 다시 만들어 같은지 (같은 규칙 + 같은 원본 → 같은 글)."""
    from src.virtual_hospital.render import chart
    saved = sorted(d.name for d in CHARTS.iterdir())
    for vp in (saved[0], saved[len(saved) // 2], saved[-1]):
        text, ps, errs = chart(built[vp])
        assert errs == []
        assert text == (CHARTS / vp / "chart.txt").read_text(encoding="utf-8")
        assert ps == json.loads((CHARTS / vp / "expected" / "patient_state.json").read_text(encoding="utf-8"))



def test_saved_charts_pass_mini_check():
    from src.input.script.virtual.virtual_chart import check
    dirs = sorted(CHARTS.iterdir())
    assert dirs
    for d in dirs:
        ps = json.loads((d / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        assert check((d / "chart.txt").read_text(encoding="utf-8"), ps) == [], d.name


def test_image_tables_follow_spec():
    """모듈 결과 틀: 표 머리글이 rules/image_tables.csv와 같아야 한다 (TCGA에는 annotations 없음)."""
    spec = {}
    for r in read_csv(ROOT / "rules" / "image_tables.csv"):
        spec.setdefault(r["표"], []).append(r["열"])
    for base in (OUT / "tcga" / "images", LOCAL / "bcnb" / "images"):
        if not base.exists():
            continue                                                   # BCNB 자료가 없는 컴퓨터
        for table, cols in spec.items():
            if table == "annotations" and base.is_relative_to(OUT / "tcga"):
                continue
            with open(base / f"{table}.csv", encoding="utf-8-sig") as fh:
                assert fh.readline().strip().split(",") == cols, (base, table)

