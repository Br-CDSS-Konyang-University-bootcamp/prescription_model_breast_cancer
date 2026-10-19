from datetime import date

import pytest

from src.reimbursement.booklet import item_effective_from, item_tags



def test_header_and_file_date(booklet):
    assert booklet.doc_no == "2026-210"
    assert booklet.file_date == date(2026, 10, 1)


def test_history(booklet):
    assert len(booklet.history) == 227
    assert booklet.history[0].doc_no == "2006-1"
    last = booklet.last_notice
    assert (last.doc_no, last.posted_date, last.effective_date) == (
        "2026-210", date(2026, 9, 29), date(2026, 10, 1))
    multi = [n.doc_no for n in booklet.history if len(n.effective_dates) > 1]
    assert multi == ["2010-13", "2011-106", "2011-145", "2017-41", "2019-170"]


def test_assumption_file_date_equals_last_effective(booklet):
    """§8 가정: 책자 파일명 날짜 = 반영된 마지막 공고의 시행일."""
    assert booklet.file_date == booklet.last_notice.effective_date
    assert booklet.doc_no == booklet.last_notice.doc_no


def test_toc_cancers_all_found(booklet):
    assert len(booklet.toc_cancers) == 41          # 1~39번, 7-1·7-2·17-1·17-2 포함
    assert all(f"cancer:{n}" in booklet.sections for _, n in booklet.toc_cancers)


def test_toc_split_whole_booklet(booklet):
    """1단계: 목차(Ⅰ~Ⅳ, 별첨) 그대로 책자 전체를 나눈다. 간지가 없는 Ⅰ 말고는 모두 본문에서 찾는다."""
    assert [e.key for e in booklet.toc_missing] == ["part:항암요법"]
    keys = list(booklet.sections)
    assert keys[0] == "general" and keys[-1] == "appendix:삭제사항 정리"
    for k in ("immunotherapy", "part:항구토제", "antiemetic:항암제들의 구토 유발 가능성 정도",
              "pain:소아 암성 통증의 약물요법", "other:G-CSF 주사제", "other:dexrazoxane 주사제"):
        assert k in booklet.sections
    # 섹션은 목차 순서대로, 겹치지 않고 이어진다
    starts = [(s.start, s.offset) for s in booklet.sections.values()]
    assert starts == sorted(starts)
    # 예전에는 '항암면역요법제'가 책자 끝까지(보조 약제·별첨 포함) 한 덩어리였다
    assert "G-CSF" not in booklet.section_text("immunotherapy")


def test_section_records(booklet):
    from src.reimbursement.booklet import section_records
    recs = section_records(booklet)
    assert len(recs) == len(booklet.sections)
    breast = next(r for r in recs if r["key"] == "cancer:유방암")
    assert (breast["toc_page"], breast["page_start"], breast["page_end"]) == (47, 48, 64)
    assert breast["breast_mentions"] > 0 and breast["text"].startswith("9\n유방암")


@pytest.mark.parametrize("key, start, end", [
    ("general", 36, 46), ("cancer:유방암", 81, 97), ("combination", 193, 216),
    ("immunotherapy", 216, 218), ("other:zoledronic acid 주사제", 251, 252),
])
def test_section_pages(booklet, key, start, end):
    s = booklet.sections[key]
    assert (s.start, s.end) == (start, end)


def test_breast_section_text(booklet):
    text = booklet.section_text("유방암")
    assert text.startswith("9\n유방암(Breast Cancer)")
    assert "Ovarian" not in text and "abemaciclib" in text
    assert booklet.printed_page(81) == 48          # 출처 표시는 인쇄 쪽 번호로
    # 쌍점 표기 215개 + 쉼표 표기 21개 (제2024-188호, 제2024-264호 등). 2026-10-15 이전에는 215개만 읽었다
    assert len(item_tags(text)) == 236


def test_item_tags_tolerate_spaces_and_breaks():
    text = ("pembrolizumab + fluorouracil + cisplatin (제2025-272호: 2026.1.1.,\n"
            "개정 제2026- 88호:\n2026.4.2.,\n개정 제2026-210호: 2026.10.1.)")
    assert [no for no, _ in item_tags(text)] == ["2025-272", "2026-88", "2026-210"]
    assert item_effective_from(text) == date(2026, 10, 1)
    assert item_effective_from("표시 없음") is None


def test_item_tags_read_comma_form():
    """책자 1.가 연번 4의 실제 표기: 쌍점과 쉼표가 섞여 있고, '호'가 빠진 것도 있다."""
    text = ("(제2017-132호: 2017.6.1, 개정 제2019-158호: 2019.5.20.,\n"
            "개정 제2024-188호, 2024.8.1.\n개정 제2024-264호, 2024.12.1.)\n개정 제2024-188, 2024.8.1.")
    assert [no for no, _ in item_tags(text)] == ["2017-132", "2019-158", "2024-188", "2024-264", "2024-188"]
    assert item_effective_from(text) == date(2024, 12, 1)
    # 날짜 없는 번호 나열은 변경 표시가 아니다
    assert item_tags("제2024-188호, 제2024-264호 참고") == []
