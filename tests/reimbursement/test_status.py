from datetime import date

from src.reimbursement import status as st

B = date(2026, 10, 1)
TODAY = date(2026, 10, 13)


def test_new_booklet():
    assert st.is_new_booklet(date(2026, 11, 1), B)
    assert not st.is_new_booklet(B, B)
    assert st.is_new_booklet(B, None)


def test_notice_status():
    assert st.notice_status(date(2026, 10, 1), B, TODAY) == st.REFLECTED
    assert st.notice_status(date(2026, 11, 1), B, TODAY) == st.SCHEDULED
    # 시행일이 지났는데 책자가 안 바뀜 -> 경고
    assert st.notice_status(date(2026, 10, 10), B, TODAY) == st.DELAYED


def test_preview_status():
    assert st.preview_status(date(2026, 10, 20), TODAY, False) == st.IN_REVIEW
    assert st.preview_status(date(2026, 10, 5), TODAY, False) == st.SCHEDULED
    assert st.preview_status(date(2026, 10, 5), TODAY, True) == st.NOTICED


def test_summary_line():
    s = st.summarize(B, "2026-210",
                     notices=[("2026-210", B), ("2026-230", date(2026, 11, 1))],
                     previews=[(date(2026, 10, 20), False)], today=TODAY)
    assert s.line() == "현재 반영: 공고책자 2026-10-01 (제2026-210호) / 예정 1건 / 진행중 1건"


def test_summary_warns_when_booklet_late():
    s = st.summarize(B, "2026-210", notices=[("2026-225", date(2026, 10, 10))],
                     previews=[], today=TODAY)
    assert s.warnings == ["제2026-225호 시행됐으나 새 공고책자 미반영"]
