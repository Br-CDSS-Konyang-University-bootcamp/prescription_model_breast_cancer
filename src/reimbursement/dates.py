"""날짜 표기 통일 (§8 날짜 비교 규칙 5).

심평원 문서에 실제로 나오는 표기:
  2026.10.1.   2024.9.1 (끝 점 없음)   2026. 10. 1.   2026-06-29
  20261001 (공고책자 파일명)   260827 (허가초과 파일명, 연도 두 자리)
"""
from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_DOTTED = re.compile(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\.?")
_KOREAN = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")


def today_kst() -> date:
    """판정 기준일. 시행일 비교는 항상 한국 시간으로 한다."""
    return datetime.now(KST).date()


def parse_date(text: str) -> date:
    """문장 속 첫 날짜를 date로 바꾼다. 못 찾으면 ValueError."""
    s = text.strip()
    for pat in (_DOTTED, _KOREAN):
        m = pat.search(s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    raise ValueError(f"날짜를 읽을 수 없음: {text!r}")


def find_dates(text: str) -> list[date]:
    """문장 속 모든 날짜 (예: '2011.1.1. 시행, 2011.2.1. 시행')."""
    return [date(int(a), int(b), int(c)) for a, b, c in _DOTTED.findall(text)]


def date_from_filename(file_name: str) -> date:
    """파일명 끝의 날짜.

    공고책자_20261001.pdf      -> 2026-10-01 (8자리)
    허가초과 항암요법_260827.xlsx -> 2026-08-27 (6자리, 20YY로 해석)
    """
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", file_name)
    m = re.search(r"(\d{8}|\d{6})$", stem)
    if not m:
        raise ValueError(f"파일명에 날짜가 없음: {file_name!r}")
    digits = m.group(1)
    if len(digits) == 6:
        digits = "20" + digits
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
