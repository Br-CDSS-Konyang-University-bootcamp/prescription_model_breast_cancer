"""§8 날짜 비교 규칙 (책자 우선 방식으로 수정한 버전).

B = 지금 반영된 공고책자의 파일명 날짜.
책자는 공고 시행일마다 새로 올라온다고 보고(2026-10-13 확인), 공고 내용을 책자에 덧씌우지 않는다.
공고 게시판은 '예정' 표시와 '책자 지연' 경고에만 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

REFLECTED = "반영됨"   # 시행일 <= B: 이미 책자에 들어 있음
SCHEDULED = "예정"     # 시행일 > 오늘
DELAYED = "지연"       # B < 시행일 <= 오늘: 시행됐는데 새 책자가 아직 없음 -> 경고
IN_REVIEW = "진행중"   # 공고예고 의견조회 기간 중
NOTICED = "공고됨"     # 공고예고에 대응하는 공고가 올라옴 -> 공고 규칙을 따름


def is_new_booklet(file_date: date, current_b: date | None) -> bool:
    """규칙 1: 파일명 날짜 > B 이면 새 책자."""
    return current_b is None or file_date > current_b


def notice_status(effective_date: date, b: date, today: date) -> str:
    """규칙 2·3: 공고는 공고일이 아니라 시행일로 비교한다."""
    if effective_date <= b:
        return REFLECTED
    if effective_date > today:
        return SCHEDULED
    return DELAYED


def preview_status(period_end: date, today: date, has_notice: bool) -> str:
    """규칙 4: 공고예고는 판정에 쓰지 않는다."""
    if has_notice:
        return NOTICED
    return IN_REVIEW if today <= period_end else SCHEDULED


@dataclass
class Summary:
    booklet_date: date
    booklet_doc_no: str
    scheduled: int
    in_review: int
    warnings: list[str]

    def index_status(self) -> dict:
        """schemas/recommendation.json의 index_status. 책자 우선 방식이라 덧씌운 공고는 없다."""
        return {"booklet_date": self.booklet_date.isoformat(), "overlay_notices": [],
                "scheduled_count": self.scheduled, "in_progress_count": self.in_review}

    def line(self) -> str:
        """화면 하단 한 줄 요약."""
        s = (f"현재 반영: 공고책자 {self.booklet_date.isoformat()} (제{self.booklet_doc_no}호)"
             f" / 예정 {self.scheduled}건 / 진행중 {self.in_review}건")
        return s + "".join(f" / 경고: {w}" for w in self.warnings)


def summarize(b: date, b_doc_no: str, notices: list[tuple[str, date]],
              previews: list[tuple[date, bool]], today: date) -> Summary:
    """notices: [(공고번호, 시행일)], previews: [(예고기간 종료일, 대응 공고 있음)]"""
    statuses = [(no, notice_status(eff, b, today)) for no, eff in notices]
    warnings = [f"제{no}호 시행됐으나 새 공고책자 미반영" for no, s in statuses if s == DELAYED]
    p = [preview_status(end, today, has) for end, has in previews]
    return Summary(
        booklet_date=b,
        booklet_doc_no=b_doc_no,
        scheduled=sum(s == SCHEDULED for _, s in statuses) + p.count(SCHEDULED),
        in_review=p.count(IN_REVIEW),
        warnings=warnings,
    )
