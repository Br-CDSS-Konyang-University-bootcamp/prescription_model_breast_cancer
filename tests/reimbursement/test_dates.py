from datetime import date

import pytest

from src.reimbursement.dates import date_from_filename, find_dates, parse_date


@pytest.mark.parametrize("text, expected", [
    ("2026.10.1.", date(2026, 10, 1)),
    ("2024.9.1 시행", date(2024, 9, 1)),          # 끝 점 없음 (실제 책자 표기)
    ("2026. 10. 1.", date(2026, 10, 1)),
    ("2026-06-29", date(2026, 6, 29)),
    ("20261001", date(2026, 10, 1)),
    ("2026년 9월 29일", date(2026, 9, 29)),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


def test_parse_date_fails_loudly():
    with pytest.raises(ValueError):
        parse_date("날짜 없음")


def test_find_dates_two_effective_dates():
    assert find_dates("2011.1.1. 시행, 2011.2.1. 시행") == [date(2011, 1, 1), date(2011, 2, 1)]


@pytest.mark.parametrize("name, expected", [
    ("공고책자_20261001.pdf", date(2026, 10, 1)),
    ("허가초과 항암요법_260827.xlsx", date(2026, 8, 27)),   # 연도 두 자리
])
def test_date_from_filename(name, expected):
    assert date_from_filename(name) == expected
