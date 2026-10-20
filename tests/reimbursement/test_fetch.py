"""게시판 파싱과 수집 판단. 네트워크는 쓰지 않는다 (게시판 HTML 구조를 본뜬 짧은 조각)."""
from datetime import date

import pytest

from src.reimbursement import fetch
from src.reimbursement.fetch import (
    filename_from_disposition, make_plan, parse_anticancer_board, parse_attachments,
    parse_notice_list, parse_preview_list, pick_notice_pdf, run_downloads, safe_name,
)
from src.reimbursement.registry import Registry

ANTICANCER = """<table><tbody>
<tr><td>2</td><td>허가초과 항암요법</td>
<td><a href="#none" onclick="downLoadBbs('1','8','5','487');">다운로드</a></td></tr>
<tr><td>1</td><td>항암화학요법 등 공고내용 전문</td>
<td><a href="#none" onclick="downLoadBbs('1','7','5','487');">다운로드</a></td></tr>
</tbody></table>"""

NOTICE_LIST = """<table><thead><tr><th>번호</th></tr></thead><tbody>
<tr> <td class="col-num">229</td> <td class="col-num2">제2026-210호</td>
<td class="col-tit"><a href="?pgmid=HIRAA030023010000&amp;brdScnBltNo=4&amp;brdBltNo=45661&amp;pageIndex=1">암환자 공고 개정 안내</a></td>
<td class="col-depart">2026.10.1.</td> <td class="col-date">2026-09-30</td> <td class="col-file"></td> </tr>
<tr> <td class="col-num">230</td> <td class="col-num2">제2026-230호</td>
<td class="col-tit"><a href="?pgmid=HIRAA030023010000&amp;brdScnBltNo=4&amp;brdBltNo=45700&amp;pageIndex=1">암환자 공고 개정 안내</a></td>
<td class="col-depart">2026.11.1.</td> <td class="col-date">2026-10-13</td> <td class="col-file"></td> </tr>
</tbody></table>"""

NOTICE_DETAIL = """<div class="fileBox"><ul>
<li> <i class="icon-file-pdf" title="pdf"></i> 주요공고개정내역_20261101 <a href="#none" onclick="downLoadBbs('2','45700','6','49');" class="btn_file">첨부파일 다운로드</a> </li>
<li> <i class="icon-file-hwp" title="hwp"></i> 공고전문_20261101 <a href="#none" onclick="downLoadBbs('4','45700','6','49');" class="btn_file">첨부파일 다운로드</a> </li>
<li> <i class="icon-file-pdf" title="pdf"></i> 공고전문_20261101 <a href="#none" onclick="downLoadBbs('6','45700','6','49');" class="btn_file">첨부파일 다운로드</a> </li>
</ul></div>"""

PREVIEW_LIST = """<table><tbody>
<tr> <td class="col-num">9597</td> <td class="col-tit"><a href="#" onclick="goDetail('9597','9596'); return false;">공고 개정(안) 의견조회</a></td>
<td class="col-file"></td> <td class="col-depart">약제기준부</td> <td class="col-depart"> 공고예고중 </td>
<td class="col-date">2026-10-20 ~<br>2026-10-26</td> <td class="col-views">10</td> </tr>
<tr> <td class="col-num">9596</td> <td class="col-tit"><a href="#" onclick="goDetail('9596','9595'); return false;">공고 개정(안) 의견조회</a></td>
<td class="col-file"></td> <td class="col-depart">약제기준부</td> <td class="col-depart"> 공고예고완료 </td>
<td class="col-date">2026-09-22 ~<br>2026-09-28</td> <td class="col-views">890</td> </tr>
</tbody></table>"""


def test_filename_from_disposition():
    raw = "공고책자_20261001.pdf".encode("utf-8").decode("latin-1")
    assert filename_from_disposition(f'attachment; filename="{raw}"') == "공고책자_20261001.pdf"
    assert filename_from_disposition("attachment; filename*=UTF-8''%EA%B3%B5.pdf") == "공.pdf"
    assert filename_from_disposition("") == ""


def test_safe_name():
    assert safe_name("../../etc/공고책자_20261001.pdf") == "공고책자_20261001.pdf"
    assert safe_name('a:b?.pdf') == "a_b_.pdf"
    assert safe_name("..") == "unnamed"


def test_parse_anticancer_board():
    b = parse_anticancer_board(ANTICANCER)
    assert (b["booklet"].brd_blt_no, b["offlabel"].brd_blt_no) == ("7", "8")
    assert fetch.download_path(b["booklet"]) == \
        "/bbs/bbsCDownLoad.do?apndNo=1&apndBrdBltNo=7&apndBrdTyNo=5&apndBltNo=487"


def test_parse_notice_list():
    rows = parse_notice_list(NOTICE_LIST)
    assert [(r.doc_no, r.brd_blt_no, r.effective_date, r.posted_date) for r in rows] == [
        ("2026-210", "45661", date(2026, 10, 1), date(2026, 9, 30)),
        ("2026-230", "45700", date(2026, 11, 1), date(2026, 10, 13)),
    ]


def test_pick_notice_pdf():
    atts = parse_attachments(NOTICE_DETAIL)
    assert [(a.apnd_no, a.ext) for a in atts] == [("2", "pdf"), ("4", "hwp"), ("6", "pdf")]
    assert pick_notice_pdf(atts).apnd_no == "6"
    assert pick_notice_pdf(atts[:2]) is None


def test_parse_preview_list():
    rows = parse_preview_list(PREVIEW_LIST)
    assert [(r.state, r.period_start, r.period_end) for r in rows] == [
        ("공고예고중", date(2026, 10, 20), date(2026, 10, 26)),
        ("공고예고완료", date(2026, 9, 22), date(2026, 9, 28)),
    ]


class FakeHttp:
    def __init__(self, names: dict[str, str]):
        self.names = names      # apndBrdBltNo -> 파일명
        self.downloads = []
        self.count = 0

    def get_text(self, path):
        self.count += 1
        if path == fetch.BOARD_ANTICANCER:
            return ANTICANCER
        if path == fetch.BOARD_NOTICE:
            return NOTICE_LIST
        if path == fetch.BOARD_PREVIEW:
            return PREVIEW_LIST
        if "brdBltNo=45700" in path:
            return NOTICE_DETAIL
        raise AssertionError(path)

    def _name(self, path):
        import re
        return self.names[re.search(r"apndBrdBltNo=(\d+)", path).group(1)]

    def head_filename(self, path):
        self.count += 1
        return self._name(path)

    def download(self, path, dest_dir):
        self.downloads.append(path)
        dest_dir.mkdir(parents=True, exist_ok=True)
        p = dest_dir / self._name(path)
        p.write_bytes(fake_file(p.name, self.payload))
        return p

    payload = b"v1"


def fake_file(name, payload=b"v1"):
    """파일 검사(qc.check_file)를 통과하는 가짜 내용: 형식 서명 + 충분한 크기."""
    head = b"%PDF-1.7\n" if name.endswith(".pdf") else b"PK\x03\x04"
    return head + payload + b"0" * 60_000


NAMES = {"7": "공고책자_20261001.pdf", "8": "사전신청요법_(용법용량 포함)및 불승인요법_261012.xlsx",
         "45700": "공고전문_20261101.pdf"}


@pytest.fixture
def reg(tmp_path):
    r = Registry(tmp_path / "r.db")
    yield r
    r.close()


def test_plan_first_run_fetches_everything(reg):
    plan = make_plan(FakeHttp(NAMES), reg, today=date(2026, 10, 14))
    assert [s for s, _, _ in plan.files] == ["booklet", "offlabel"]
    # 레지스트리에 B가 없어도 이번에 받을 책자 날짜(2026-10-01)를 B로 쓴다
    assert [n.doc_no for n in plan.skipped_notices] == ["2026-210"]
    assert [n.doc_no for n in plan.notices] == ["2026-230"]


def test_plan_uses_filename_date_against_registry(reg):
    reg.add_document("booklet", file_hash="b", file_name=NAMES["7"], effective_date=date(2026, 10, 1))
    reg.add_document("offlabel", file_hash="o", file_name="허가초과 항암요법_260827.xlsx",
                     effective_date=date(2026, 8, 27))
    http = FakeHttp(NAMES)
    plan = make_plan(http, reg, today=date(2026, 10, 14))
    # 책자는 같은 날짜 -> 건너뜀, 허가초과는 260827 < 261012 -> 받음
    assert [(s, n) for s, n, _ in plan.files] == [("offlabel", NAMES["8"])]
    # 시행일 <= B 인 제2026-210호는 건너뛰고, 2026-11-01 시행 공고만 남는다 (오늘 기준 '예정')
    assert [n.doc_no for n in plan.skipped_notices] == ["2026-210"]
    assert [n.doc_no for n in plan.notices] == ["2026-230"]
    assert any("2026-230" in m and "예정" in m for m in plan.messages)
    # 예고: 10/26 마감은 진행중, 9/28 마감은 그 뒤에 작성된 공고(9/30)가 있어 공고됨
    assert [st for _, st in plan.previews] == ["진행중", "공고됨"]
    assert http.count == 5      # 목록 3 + HEAD 2, 파일은 받지 않음


def test_failed_document_is_not_current(reg):
    a = reg.add_document("booklet", file_hash="a", effective_date=date(2026, 9, 1))
    b = reg.add_document("booklet", file_hash="b", effective_date=date(2026, 10, 1))
    reg.set_status(b, "failed")
    assert reg.latest_document("booklet")["id"] == a


def test_run_downloads_records_registry(reg, tmp_path):
    reg.add_document("booklet", file_hash="b", effective_date=date(2026, 10, 1))
    reg.add_document("offlabel", file_hash="o", effective_date=date(2026, 10, 12))
    http = FakeHttp(NAMES)
    plan = make_plan(http, reg, today=date(2026, 10, 14))
    saved = run_downloads(http, reg, plan, tmp_path / "raw")
    assert [d.path.name for d in saved] == ["공고전문_20261101.pdf"]
    assert saved[0].report.ok and not saved[0].reused
    assert reg.has_board_id("notice", "brdBltNo=45700")
    # 다시 계획하면 이미 받은 공고는 빠진다
    assert make_plan(FakeHttp(NAMES), reg, today=date(2026, 10, 14)).notices == []


def test_existing_local_file_is_reused(reg, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / NAMES["7"]).write_bytes(fake_file(NAMES["7"]))
    http = FakeHttp(NAMES)
    plan = make_plan(http, reg, today=date(2026, 10, 14))
    saved = {d.source: d for d in run_downloads(http, reg, plan, raw)}
    assert saved["booklet"].reused and not saved["offlabel"].reused
    assert not any("apndBrdBltNo=7" in p for p in http.downloads)


def test_html_error_page_marks_failed(reg, tmp_path):
    class HtmlHttp(FakeHttp):
        def download(self, path, dest_dir):
            p = super().download(path, dest_dir)
            p.write_bytes(b"<html><body>error</body></html>" + b" " * 60_000)
            return p
    http = HtmlHttp(NAMES)
    plan = make_plan(http, reg, today=date(2026, 10, 14))
    saved = {d.source: d for d in run_downloads(http, reg, plan, tmp_path / "raw")}
    assert not saved["booklet"].report.ok
    assert reg.latest_document("booklet") is None          # failed는 현재 문서로 쓰지 않는다


def test_same_date_reupload(reg, tmp_path):
    """2026-10-15 실제 사례: 같은 날짜로 다시 올라오며 파일명이 바뀜."""
    raw = tmp_path / "raw"
    raw.mkdir()
    old = NAMES["8"]
    new = "사전신청요법(용법용량 포함)및 불승인요법_261012.xlsx"
    (raw / old).write_bytes(fake_file(old))
    from src.reimbursement.booklet import sha256
    reg.add_document("booklet", file_hash="b", file_name=NAMES["7"], effective_date=date(2026, 10, 1))
    reg.add_document("offlabel", file_hash=sha256(raw / old), file_name=old, effective_date=date(2026, 10, 12))

    http = FakeHttp({**NAMES, "8": new})
    plan = make_plan(http, reg, today=date(2026, 10, 14))
    assert [n for _, n, _ in plan.files] == [new]
    assert any("다시 올라온" in m for m in plan.messages)

    # 내용이 같으면 새로 받은 파일을 지우고 원래 파일을 쓴다
    saved = run_downloads(http, reg, plan, raw)
    assert saved[0].path.name == old and saved[0].reused and not (raw / new).exists()

    # 내용이 다르면 새 파일을 남긴다
    http2 = FakeHttp({**NAMES, "8": new})
    http2.payload = b"v2"
    saved = run_downloads(http2, reg, make_plan(http2, reg, today=date(2026, 10, 14)), raw)
    assert saved[0].path.name == new and (raw / new).exists()


def test_http_request_limit():
    h = fetch.Http(max_requests=0)
    with pytest.raises(RuntimeError):
        h.get_text("/x")
