from datetime import date

import pytest

from src.reimbursement.registry import CriterionItem, Registry


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "registry.db")
    yield r
    r.close()


def _booklet(reg, d, h):
    return reg.add_document("booklet", file_hash=h, file_name=f"공고책자_{d:%Y%m%d}.pdf",
                            effective_date=d)


def test_same_file_registered_once(reg):
    assert _booklet(reg, date(2026, 10, 1), "h1") == _booklet(reg, date(2026, 10, 1), "h1")


def test_apply_booklet_versions(reg):
    d1, d2 = date(2026, 10, 1), date(2026, 11, 1)
    doc1 = _booklet(reg, d1, "h1")
    diff = reg.apply_booklet(doc1, d1, [
        CriterionItem("A", "abemaciclib 조건 v1", effective_from=date(2022, 3, 1)),
        CriterionItem("B", "olaparib 조건"),
        CriterionItem("C", "곧 삭제될 요법"),
    ])
    assert sorted(diff.added) == ["A", "B", "C"]

    doc2 = _booklet(reg, d2, "h2")
    diff = reg.apply_booklet(doc2, d2, [
        CriterionItem("A", "abemaciclib 조건 v2", effective_from=d2),
        CriterionItem("B", "olaparib   조건"),          # 공백만 다름 -> 변경 아님
        CriterionItem("D", "신설 요법", effective_from=d2),
    ])
    assert (diff.added, diff.changed, diff.removed) == (["D"], ["A"], ["C"])

    # 오늘(11월) 기준 유효 항목
    now = {r["item_key"]: r["text"] for r in reg.active_on(date(2026, 11, 13))}
    assert now == {"A": "abemaciclib 조건 v2", "B": "olaparib 조건", "D": "신설 요법"}
    # 과거 재현: 10월 기준
    past = {r["item_key"]: r["text"] for r in reg.active_on(date(2026, 10, 13))}
    assert past == {"A": "abemaciclib 조건 v1", "B": "olaparib 조건", "C": "곧 삭제될 요법"}


def test_unchanged_booklet_gives_empty_diff(reg):
    d = date(2026, 10, 1)
    items = [CriterionItem("A", "x")]
    reg.apply_booklet(_booklet(reg, d, "h1"), d, items)
    assert reg.apply_booklet(_booklet(reg, date(2026, 11, 1), "h2"), date(2026, 11, 1), items).is_empty()


def test_duplicate_key_rejected(reg):
    d = date(2026, 10, 1)
    with pytest.raises(ValueError):
        reg.apply_booklet(_booklet(reg, d, "h1"), d, [CriterionItem("A", "x"), CriterionItem("A", "y")])
    assert reg.active_on(d) == []     # 트랜잭션이라 아무것도 안 들어감


def test_validation_sets_status_and_last_good(reg):
    d1, d2 = date(2026, 9, 1), date(2026, 10, 1)
    a = _booklet(reg, d1, "h1")
    reg.save_validation(a, {"ok": True, "errors": []})
    b = _booklet(reg, d2, "h2")
    reg.save_validation(b, {"ok": False, "errors": ["x"]})
    # 실패한 새 책자 대신 마지막 정상 책자를 쓴다
    assert reg.last_good_booklet()["file_hash"] == "h1"
    assert reg.last_good_booklet(exclude_hash="h1") is None
