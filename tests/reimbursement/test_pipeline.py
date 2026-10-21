"""전체 흐름 (오프라인). 실제 공고책자가 data/reimbursement/raw/에 있을 때만 돈다."""
import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from src.reimbursement import pipeline
from src.reimbursement.registry import Registry

RAW = Path(__file__).resolve().parents[2] / "data/reimbursement/raw"
BOOKLET = RAW / "공고책자_20261001.pdf"
NOTICE = RAW / "공고전문_20261001.pdf"

pytestmark = pytest.mark.skipif(not BOOKLET.exists(), reason="공고책자 PDF 없음")


@pytest.fixture
def dirs(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(BOOKLET, raw)
    if NOTICE.exists():
        shutil.copy(NOTICE, raw)
    for x in RAW.glob("*_[0-9][0-9][0-9][0-9][0-9][0-9].xlsx"):
        shutil.copy(x, raw)
    return {"raw": raw, "db": tmp_path / "r.db", "out_dir": tmp_path / "chunks",
            "reports": tmp_path / "reports"}


def _run(dirs, **kw):
    kw.setdefault("use_llm", False)          # 테스트는 Claude API를 부르지 않는다
    return pipeline.run(offline=True, today=date(2026, 10, 15), **dirs, **kw)


EMPTY = {"all_of": [], "any_of": [], "any_of_exceptions": [], "stage_rules": [], "counts_as_prior_line": [],
         "notes": [], "human_review": [], "unmapped": []}


class FakeStructurer:
    """'호르몬 수용체 양성'이 있는 행에만 hr 조건을 붙이는 가짜 (설계 §3.5 형식). 부른 횟수를 센다."""
    def __init__(self):
        self.calls = 0

    def __call__(self, text, context):
        self.calls += 1
        q = "호르몬 수용체 양성"
        if q in text:
            return {**EMPTY, "all_of": [{"id": "c1", "field": "hr", "op": "eq", "value": "positive", "text": q}]}, {}
        return dict(EMPTY), {}


def test_conditions_stage_and_index_status(dirs):
    fake = FakeStructurer()
    res = _run(dirs, use_llm=True, structurer=fake)
    assert res.ok, res.render()
    chunks = [json.loads(x) for x in (dirs["out_dir"] / pipeline.CURRENT).read_text(encoding="utf-8").splitlines()]
    row = next(c for c in chunks if c["chunk_id"] == "hira-booklet-20261001-bc-pal-endo-1lplus-r06")   # fulvestrant
    cond = row["reimbursement"]["conditions"]
    assert cond["all_of"][0]["value"] == "positive"
    assert cond["line_rule"] == {"stage": "palliative_endocrine", "line": "1차 이상"}
    first_calls = fake.calls
    assert first_calls >= 121 + 8                               # 책자 행 + 병용요법 행 + Ⅳ 기타 약제 묶음
    assert not any(c["source"] == "HIRA-offlabel" for c in chunks)      # 허가초과는 기본으로 뺀다
    assert not any("offlabel" in m for m in res.stages[0].report.info)  # 받지도 검사하지도 않는다
    review = dirs["reports"] / "conditions_review_20261001.tsv"
    assert review.exists() and "\thr\t" in review.read_text(encoding="utf-8-sig")
    status = json.loads((dirs["out_dir"].parent / "index_status.json").read_text(encoding="utf-8"))
    assert status["index_status"]["booklet_date"] == "2026-10-01"
    assert status["index_status"]["overlay_notices"] == []
    assert any("가정 확인" in m for m in res.stages[1].report.info)

    again = _run(dirs, use_llm=True, structurer=fake)        # 저장본을 써서 다시 부르지 않는다
    assert again.ok and fake.calls == first_calls


def test_with_offlabel_option(dirs):
    if not list(dirs["raw"].glob("*.xlsx")):
        pytest.skip("허가초과 xlsx 없음")
    res = _run(dirs, with_offlabel=True)
    assert res.ok, res.render()
    chunks = [json.loads(x) for x in (dirs["out_dir"] / pipeline.CURRENT).read_text(encoding="utf-8").splitlines()]
    assert any(c["source"] == "HIRA-offlabel" for c in chunks)


def test_contexts_include_main_section_notes(dirs):
    from src.reimbursement.booklet import load_booklet
    from src.reimbursement.chunks import booklet_chunks

    bc = booklet_chunks(load_booklet(dirs["raw"] / BOOKLET.name, RAW.parent / "cache"))
    c = bc.contexts["hira-booklet-20261001-bc-pal-endo-1lplus-r06"]
    assert "3. 고식적 내분비요법" in c and "호르몬 수용체 양성인 유방암을 대상으로" in c
    assert "fulvestrant" not in c                               # 다른 행의 글은 넣지 않는다
    assert "CDK4/6 inhibitor" in bc.contexts["hira-booklet-20261001-bc-pal-endo-1l-r01"]   # 대단원 머리 규칙
    # 급여기준 칸이 위 행과 병합된 병용요법 행은 위 행 글을 맥락으로 받는다
    assert "① 40세 미만" in bc.contexts["hira-booklet-20261001-combo-r28"]
    assert "연번 27" in bc.contexts["hira-booklet-20261001-combo-r28"]
    assert "연번" not in bc.contexts["hira-booklet-20261001-combo-r27"]


def test_every_chunk_has_printed_page(dirs):
    """인용에 쪽이 빠지지 않게 모든 청크에 책자 인쇄 쪽이 있다 (지침 청크와 같은 형식, 정수)."""
    from src.reimbursement.booklet import load_booklet
    from src.reimbursement.chunks import booklet_chunks

    bc = booklet_chunks(load_booklet(dirs["raw"] / BOOKLET.name, RAW.parent / "cache"))
    missing = [c["chunk_id"] for c in bc.chunks if not isinstance(c.get("page_start"), int)
               or not isinstance(c.get("page_end"), int) or c["page_start"] > c["page_end"]]
    assert missing == []
    supp = next(c for c in bc.chunks if c["chunk_id"].endswith("-supp"))   # Ⅳ 기타 약제 목록: 자식들의 첫 쪽~끝 쪽
    kids = [c for c in bc.chunks if c["chunk_id"].startswith(supp["chunk_id"] + "-")]
    assert (supp["page_start"], supp["page_end"]) == (min(c["page_start"] for c in kids), max(c["page_end"] for c in kids))


def test_full_run_then_rerun(dirs):
    res = _run(dirs)
    assert res.ok, res.render()
    current = dirs["out_dir"] / pipeline.CURRENT
    chunks = [json.loads(x) for x in current.read_text(encoding="utf-8").splitlines()]
    ids = {c["chunk_id"] for c in chunks}
    assert "hira-booklet-20261001-bc-pal-chemo-2lplus-r22" in ids   # 4.라 마지막 행 (쪽 경계 뒤)
    assert "hira-booklet-20261001-combo-r30" in ids            # 병용요법 유방암 행
    assert "hira-booklet-20261001-supp-zoledronic-b" in ids    # Ⅳ 기타 약제 (골전이)
    assert res.diff["booklet"]["added"] and not res.diff["booklet"]["removed"]
    assert (dirs["reports"] / "last_good.json").exists()

    again = _run(dirs)                                          # 같은 파일 -> 변경 없음
    assert again.ok, again.render()
    assert again.diff["booklet"] == {"added": [], "changed": [], "removed": []}

    reg = Registry(dirs["db"])
    assert reg.latest_document("booklet")["status"] == "parsed"
    assert reg.latest_document("booklet")["doc_no"] == "2026-210"
    reg.close()


def test_bad_new_file_keeps_last_good(dirs):
    assert _run(dirs).ok
    current = dirs["out_dir"] / pipeline.CURRENT
    before = current.read_bytes()
    # 게시판이 오류 페이지를 내려준 상황: 더 새 날짜의 '책자'가 HTML
    (dirs["raw"] / "공고책자_20261101.pdf").write_bytes(b"<html>error</html>" + b" " * 60_000)
    res = _run(dirs)
    assert not res.ok
    assert res.stages[0].report.errors and all(s.skipped for s in res.stages[1:])
    assert current.read_bytes() == before                       # 마지막 정상 파일 유지


def test_truncated_section_is_caught(dirs, monkeypatch):
    """유방암 섹션 일부가 빠지면(추출 오류) 행 수 비교에서 멈춘다."""
    assert _run(dirs).ok
    real = pipeline.booklet_chunks

    def drop_rows(b):
        bc = real(b)
        sub = next(s for s in bc.table.subsections if s.key == "bc-pal-chemo-2lplus")
        del sub.rows[10:]
        bc.chunks = [c for c in bc.chunks
                     if not c["chunk_id"].startswith("hira-booklet-20261001-bc-pal-chemo-2lplus-r")
                     or int(c["chunk_id"][-2:]) <= 10]
        return bc

    monkeypatch.setattr(pipeline, "booklet_chunks", drop_rows)
    res = _run(dirs)
    assert not res.ok
    errs = " ".join(res.stages[4].report.errors)
    assert "줄어듦" in errs and "청크에 없음" in errs           # 행 수 감소 + 원문 낱말 누락


def test_invented_word_is_caught(dirs, monkeypatch):
    real = pipeline.booklet_chunks

    def add_word(b):
        bc = real(b)
        bc.chunks[5]["text"] += "\nzolbetuximab 추가 인정"
        return bc

    monkeypatch.setattr(pipeline, "booklet_chunks", add_word)
    res = _run(dirs)
    assert not res.ok
    assert any("원문에 없는 낱말" in e and "zolbetuximab" in e for e in res.stages[4].report.errors)
    assert not (dirs["out_dir"] / pipeline.CURRENT).exists()
