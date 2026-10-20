"""공고책자 하나를 읽고, 검증하고, 레지스트리에 기록한다.

사용 (team_project 폴더에서):
    python -m src.reimbursement.check_booklet data/reimbursement/raw/공고책자_20261001.pdf \\
        --notice data/reimbursement/raw/공고전문_20261001.pdf --cross-check

  --notice       같은 번호의 공고 전문과 대조 (신설·변경·삭제가 책자에 들어갔는지)
  --cross-check  pdfplumber로 한 번 더 읽어 비교 (첫 실행 1분 남짓, 이후 캐시)

검증에 오류가 있으면 이 책자는 failed로 기록되고, 종료 코드 1로 끝난다.
그때는 레지스트리의 마지막 정상 책자를 계속 쓴다 (§8 처리 흐름 9).
매번 실행하면 '책자를 처음 본 시각'이 쌓여 '시행일 당일 게시' 가정을 확인할 수 있다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .booklet import load_booklet
from .notice import load_notice
from .registry import Registry
from .validate import validate_booklet

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reimbursement"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--notice", type=Path, help="같은 번호의 공고 전문 PDF")
    ap.add_argument("--cross-check", action="store_true", help="pdfplumber로 한 번 더 읽어 비교")
    ap.add_argument("--db", type=Path, default=DATA / "registry.db")
    args = ap.parse_args(argv)

    cache = DATA / "cache"
    b = load_booklet(args.pdf, cache)
    other = load_booklet(args.pdf, cache, engine="pdfplumber") if args.cross_check else None
    notice = load_notice(args.notice) if args.notice else None

    reg = Registry(args.db)
    prev = reg.last_good_booklet(exclude_hash=b.file_hash)
    report = validate_booklet(
        b, other=other, notice=notice,
        previous_doc_no=prev["doc_no"] if prev else None,
        previous_file_date=date.fromisoformat(prev["effective_date"]) if prev else None,
    )
    print(f"파일: {b.path.name}  (파일명 날짜 {b.file_date}, 제{b.doc_no}호)")
    if prev:
        print(f"이전 정상 책자: {prev['file_name']} (제{prev['doc_no']}호)")
    print(report.render())

    doc_id = reg.add_document("booklet", file_hash=b.file_hash, file_name=b.path.name,
                              doc_no=b.doc_no, effective_date=b.file_date)
    reg.save_validation(doc_id, report.to_dict())
    if notice:
        reg.add_document("notice", file_hash=None, file_name=notice.path.name,
                         doc_no=notice.doc_no, posted_date=notice.posted_date,
                         effective_date=min(notice.effective_dates))

    print("\n레지스트리의 책자 기록 (파일명 날짜 / 처음 본 시각 / 상태):")
    for r in reg.booklet_lag_report():
        print(f"  {r['effective_date']}  {r['first_seen_at']}  {r['status']:<8} {r['file_name']}")
    reg.close()
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
