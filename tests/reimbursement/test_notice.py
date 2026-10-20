from datetime import date

from src.reimbursement.notice import parse_notice_text


SAMPLE = """건강보험심사평가원 공고 제2026-999호
부 칙(2026.11.27.)
①(시행일) 이 공고는 2026년 12월 1일부터 시행한다.
공고개정 내역
<신설>
- 유방암에 ‘Datopotamab deruxtecan’ 단독요법(2차 이상, 고식적요법)
ㆍ 항구토제 [항암제들의 구토 유발 가능성 정도] 목록 추가
<삭제>
- 기타 항암제 병용요법 (기존 항암요법 본인일부부담)에 요법 삭제
ㆍ 유방암(1요법): ‘Trastuzumab + Tucatinib
+ Capecitabine’
☐ 공고개정 내역
"""


def test_parse_sample():
    n = parse_notice_text(SAMPLE)
    assert (n.doc_no, n.posted_date, n.effective_dates) == (
        "2026-999", date(2026, 11, 27), [date(2026, 12, 1)])
    assert [(c.kind, c.scope, c.cancer, c.regimen) for c in n.changes] == [
        ("신설", "cancer", "유방암", "Datopotamab deruxtecan"),
        ("삭제", "combination", "유방암", "Trastuzumab + Tucatinib + Capecitabine"),
    ]
    assert len(n.skipped) == 1                    # 항구토제 줄은 해석하지 않음


def test_real_notice(notice):
    assert notice.doc_no == "2026-210"
    assert notice.posted_date == date(2026, 9, 29)
    assert notice.effective_dates == [date(2026, 10, 1)]
    kinds = [c.kind for c in notice.changes]
    assert (kinds.count("신설"), kinds.count("변경"), kinds.count("삭제")) == (14, 5, 4)
