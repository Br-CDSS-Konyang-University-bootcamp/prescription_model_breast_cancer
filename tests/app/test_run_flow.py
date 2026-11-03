"""가상 차트 전체 흐름 표 (src/app/script/run_flow.py). LLM·색인 없이 저장된 결과 형식으로만 본다. team_project 폴더에서
python -m pytest tests/app
"""
import csv
import json

from src.app.script import run_flow as rf


def fake_result(options, retrieved):
    """화면 2 캐시(c1.json) 형식의 최소 결과."""
    return {"recommendation": {"options": options, "conflicts": ["x"]},
            "ranked": options, "chunks": {cid: {} for cid in retrieved}, "schema_errors": [], "seconds": 12}


def test_guideline_check():
    answer = {"expected_chunks": ["g1", "g2"], "not_expected": ["bad"], "status": "draft"}
    options = [{"therapy": "A", "citations": ["g2"]}, {"therapy": "B", "citations": ["bad"]}]
    got = rf.guideline_check(fake_result(options, ["g1", "g2", "bad"]), answer)
    assert got == {"guideline_answer": "draft", "retrieved": "2/2", "cited": "1/2", "top": "yes", "wrong": "bad"}
    got = rf.guideline_check(fake_result(options[::-1], ["g2", "bad"]), answer)
    assert got["retrieved"] == "1/2" and got["top"] == "no"


def test_summary(tmp_path):
    """VC-0103 결과는 표에 후보·대조가, 실패한 사례는 이유가, 돌리지 않은 사례는 '실행 안 됨'이 들어간다."""
    options = [{"therapy": "Fulvestrant—palbociclib", "reimbursement": "covered",
                "citations": ["esmo-mbc-2026-05-luminal-1l-0fd38a"]}]
    (tmp_path / "VC-0103").mkdir()
    (tmp_path / "VC-0103" / "c1.json").write_text(
        json.dumps(fake_result(options, ["esmo-mbc-2026-05-luminal-1l-0fd38a"])), encoding="utf-8")
    (tmp_path / "VC-0101").mkdir()
    (tmp_path / "VC-0101" / "error.json").write_text(json.dumps({"error": "ConnectionError: 터널 없음"}), encoding="utf-8")
    path = rf.write_summary(tmp_path, ["VC-0101", "VC-0102", "VC-0103"])
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = {r["case"]: r for r in csv.DictReader(f)}
    assert rows["VC-0103"]["options"] == "Fulvestrant—palbociclib [covered]"
    assert (rows["VC-0103"]["cited"], rows["VC-0103"]["top"], rows["VC-0103"]["conflicts"]) == ("1/1", "yes", "1")
    assert rows["VC-0103"]["decision"] == "내분비 1L / 항암 1L"
    assert rows["VC-0101"]["error"] == "ConnectionError: 터널 없음"
    assert rows["VC-0102"]["error"] == "실행 안 됨"


def test_cases_have_gold_confirmed_state():
    ids = rf.cases()
    assert "VC-0103" in ids and "VC-0129" not in ids and "VC-0106b" not in ids
    assert rf.main(["--out", "unused", "--ids", "VC-0129", "--summary"]) == 2
