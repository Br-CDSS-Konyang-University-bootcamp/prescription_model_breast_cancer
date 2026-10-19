"""실제 공고책자·공고전문으로 하는 테스트의 공용 준비물.

준비: data/reimbursement/raw/공고책자_20261001.pdf, 공고전문_20261001.pdf
파일이 없으면 해당 테스트는 건너뛴다. 원본은 git에 올리지 않는다.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/reimbursement/raw"
CACHE = ROOT / "data/reimbursement/cache"
BOOKLET_PDF = RAW / "공고책자_20261001.pdf"
NOTICE_PDF = RAW / "공고전문_20261001.pdf"



@pytest.fixture(scope="session")
def booklet():
    """실제 공고책자. 파일이 없으면 이 준비물을 쓰는 테스트는 건너뛴다."""
    if not BOOKLET_PDF.exists():
        pytest.skip("공고책자 PDF 없음")
    from src.reimbursement.booklet import load_booklet
    return load_booklet(BOOKLET_PDF, CACHE)


@pytest.fixture(scope="session")
def notice():
    if not NOTICE_PDF.exists():
        pytest.skip("공고전문 PDF 없음")
    from src.reimbursement.notice import load_notice
    return load_notice(NOTICE_PDF)
