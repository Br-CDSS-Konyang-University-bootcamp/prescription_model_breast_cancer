"""검증이 '맞는 책자는 통과, 잘못 읽은 책자는 실패'시키는지 확인한다.

실제 책자 텍스트를 일부러 망가뜨려서(변조) 검증이 잡아내는지 본다.
"""
from datetime import date

import pytest

from src.reimbursement.booklet import build_booklet
from src.reimbursement.validate import validate_booklet


def _rebuild(b, raw):
    return build_booklet(raw, b.path, b.file_hash, b.engine)


def _page_of(b, needle):
    return next(i for i, p in enumerate(b.raw_pages) if needle in p)


def test_real_booklet_passes(booklet):
    r = validate_booklet(booklet, previous_doc_no="2026-190",
                         previous_file_date=date(2026, 9, 1))
    assert r.ok, r.render()


def test_real_notice_matches(booklet, notice):
    r = validate_booklet(booklet, notice=notice)
    assert r.ok, r.render()
    assert not [w for w in r.warnings if "변경 표시가 없음" in w]


def test_detects_missing_breast_section(booklet):
    raw = list(booklet.raw_pages)
    i = _page_of(booklet, "유방암(Breast Cancer)\n[유방암")
    raw[i] = raw[i].replace("유방암(Breast Cancer)", "유방(Breast)")
    r = validate_booklet(_rebuild(booklet, raw))
    assert any("유방암" in e for e in r.errors)


def test_detects_header_history_mismatch(booklet):
    raw = list(booklet.raw_pages)
    raw[0] = raw[0].replace("공고 제2026-210호", "공고 제2026-190호", 1)
    r = validate_booklet(_rebuild(booklet, raw))
    assert any("첫 줄 공고번호" in e for e in r.errors)


def test_detects_empty_pages(booklet):
    raw = [p if i % 5 else "" for i, p in enumerate(booklet.raw_pages)]
    raw[0] = booklet.raw_pages[0]
    r = validate_booklet(_rebuild(booklet, raw))
    assert any("빈 쪽" in e for e in r.errors)


def test_detects_future_tag(booklet):
    raw = list(booklet.raw_pages)
    i = _page_of(booklet, "제2026-210호: 2026.10.1.")
    raw[i] = raw[i].replace("제2026-210호: 2026.10.1.", "제2026-210호: 2026.12.1.", 1)
    r = validate_booklet(_rebuild(booklet, raw))
    assert any("책자 날짜보다 늦은" in e for e in r.errors)


def test_detects_unreadable_tags(booklet):
    # 표 칸 순서가 섞여 날짜가 떨어져 나간 상황을 흉내 낸다
    raw = [p.replace("호: 20", "호: ※ 20") for p in booklet.raw_pages]
    r = validate_booklet(_rebuild(booklet, raw))
    assert any("날짜를 읽지 못함" in e for e in r.errors)


def test_all_tags_read(booklet):
    """쪽 경계에서 나뉜 표시(병용요법 연번 46, 인쇄 177-178쪽)까지 모두 읽는다."""
    r = validate_booklet(booklet)
    assert not [w for w in r.warnings if "날짜를 읽지 못한" in w], r.render()
    assert "본문 변경 표시 1622개" in r.info


def test_strip_repeated_headers():
    from src.reimbursement.validate import _strip_repeated_headers
    page = "연번\n주요\n암종\n항암제 병용요법\n허가사항\n급여 요법\n급여기준\n비고\n2025.6.5.,개정\n47"
    assert _strip_repeated_headers(page) == "2025.6.5.,개정\n47"
    assert _strip_repeated_headers("본문\n연번") == "본문\n연번"     # 쪽 맨 위가 아니면 그대로


def test_detects_unreflected_notice(booklet, notice):
    raw = [p.replace("selpercatinib", "selpercatimib") for p in booklet.raw_pages]
    r = validate_booklet(_rebuild(booklet, raw), notice=notice)
    assert any("책자에 없음" in e and "Selpercatinib" in e for e in r.errors)


def test_detects_deleted_regimen_still_present(booklet, notice):
    raw = list(booklet.raw_pages)
    i = _page_of(booklet, "기타 항암제 병용요법 (기존")
    raw[i] += "\nzolbetuximab(비급여) + capecitabine + oxaliplatin"
    r = validate_booklet(_rebuild(booklet, raw), notice=notice)
    assert any("삭제된 요법이 책자에 남아" in e for e in r.errors)


@pytest.mark.parametrize("prev, ok", [("2026-190", True), ("2027-5", False)])
def test_previous_booklet(booklet, prev, ok):
    r = validate_booklet(booklet, previous_doc_no=prev)
    assert r.ok is ok
