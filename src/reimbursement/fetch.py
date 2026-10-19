"""심평원 게시판 수집 (§8 처리 흐름 2–4).

게시판 (모두 https://www.hira.or.kr, 로그인 없이 GET으로 열린다. 2026-10-14 확인):
  항암화학요법  /bbsDummy.do?pgmid=HIRAA030023030000
                글 2개(공고내용 전문 = 공고책자, 허가초과 항암요법)를 덮어쓰는 방식이라 주소가 고정이고
                목록에 날짜가 없다. 응답 헤더에도 Last-Modified·ETag·크기가 없다.
                -> HEAD 요청의 Content-Disposition 파일명 날짜로 새 파일인지 판단한다.
  공고          /bbsDummy.do?pgmid=HIRAA030023010000
                목록에 공고번호와 제·개정일(시행일)이 있다. 상세 쪽에서 공고전문 PDF를 받는다.
  공고예고      /rc/drug/anticancer/antiCncrAnnceList.do?pgmid=HIRAA030023020000
                첨부가 HWP뿐이라 받지 않는다. 목록의 상태와 공고예고기간만 쓴다 (규칙 4).

첨부 다운로드: /bbs/bbsCDownLoad.do?apndNo=&apndBrdBltNo=&apndBrdTyNo=&apndBltNo=
  (페이지의 downLoadBbs('apndNo','apndBrdBltNo','apndBrdTyNo','apndBltNo') 인자 순서 그대로)
파일명은 UTF-8 바이트가 latin-1로 들어오므로 되돌려 읽는다.

요청은 실행 한 번에 MAX_REQUESTS건까지, 요청 사이 REQUEST_GAP초를 둔다.
받은 원문은 data/reimbursement/raw/에만 두고 외부에 공개하지 않는다.

사용 (team_project 폴더에서):
    python -m src.reimbursement.fetch            # 확인만 (HEAD·목록), 내려받지 않음
    python -m src.reimbursement.fetch --download # 새 파일만 내려받기
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .dates import date_from_filename, parse_date, today_kst
from .registry import Registry
from .status import REFLECTED, is_new_booklet, notice_status, preview_status

BASE = "https://www.hira.or.kr"
BOARD_ANTICANCER = "/bbsDummy.do?pgmid=HIRAA030023030000"
BOARD_NOTICE = "/bbsDummy.do?pgmid=HIRAA030023010000"
BOARD_PREVIEW = "/rc/drug/anticancer/antiCncrAnnceList.do?pgmid=HIRAA030023020000"
DOWNLOAD = "/bbs/bbsCDownLoad.do"

# 항암화학요법 게시판 글 제목 -> 레지스트리 source
ANTICANCER_TITLES = {"공고내용 전문": "booklet", "허가초과": "offlabel"}

MAX_REQUESTS = 15
REQUEST_GAP = 1.0
USER_AGENT = "prescription_model_breast_cancer (non-profit research; reimbursement module)"

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "reimbursement"

_DOWN_ARGS = re.compile(r"downLoadBbs\(\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'(\d+)'\s*,\s*'(\d+)'\s*\)")
_TAG = re.compile(r"<[^>]+>")


# ---------- HTTP ----------

class Http:
    """요청 수 제한과 간격을 지키는 얇은 HTTP 클라이언트. 테스트에서는 같은 메서드를 가진 가짜로 바꾼다."""

    def __init__(self, base: str = BASE, max_requests: int = MAX_REQUESTS, gap: float = REQUEST_GAP):
        self.base, self.max_requests, self.gap = base, max_requests, gap
        self.count = 0
        self._last = 0.0

    def _open(self, path: str, method: str):
        if self.count >= self.max_requests:
            raise RuntimeError(f"요청 한도 {self.max_requests}건 초과")
        wait = self._last + self.gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.count += 1
        self._last = time.monotonic()
        req = urllib.request.Request(self.base + path, method=method,
                                     headers={"User-Agent": USER_AGENT})
        return urllib.request.urlopen(req, timeout=30)

    def get_text(self, path: str) -> str:
        with self._open(path, "GET") as r:
            return r.read().decode("utf-8", "replace")

    def head_filename(self, path: str) -> str:
        with self._open(path, "HEAD") as r:
            return filename_from_disposition(r.headers.get("Content-Disposition", ""))

    def download(self, path: str, dest_dir: Path) -> Path:
        """임시 파일로 받은 뒤 이름을 바꾼다. 중간에 끊겨도 반쪽 파일이 남지 않는다."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        with self._open(path, "GET") as r:
            name = filename_from_disposition(r.headers.get("Content-Disposition", ""))
            if not name:
                raise RuntimeError(f"파일명 없는 응답: {path}")
            target = dest_dir / safe_name(name)
            tmp = target.with_suffix(target.suffix + ".part")
            with open(tmp, "wb") as f:
                while chunk := r.read(1 << 16):
                    f.write(chunk)
        tmp.replace(target)
        return target


def filename_from_disposition(cd: str) -> str:
    """'attachment; filename="ê³µê³ ...pdf"' -> '공고책자_20261001.pdf'."""
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I)
    if m:
        return urllib.parse.unquote(m.group(1))
    m = re.search(r'filename="?([^";]+)"?', cd, re.I)
    if not m:
        return ""
    raw = m.group(1)
    try:
        return raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return raw


def safe_name(name: str) -> str:
    """경로 구분자 등을 지워 data/reimbursement/raw 밖으로 나가지 않게 한다."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    return name or "unnamed"


def download_path(a: "Attachment") -> str:
    return DOWNLOAD + "?" + urllib.parse.urlencode({
        "apndNo": a.apnd_no, "apndBrdBltNo": a.brd_blt_no,
        "apndBrdTyNo": a.brd_ty_no, "apndBltNo": a.blt_no})


# ---------- 페이지 파싱 ----------

def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", fragment))).strip()


def _rows(page: str) -> list[str]:
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", page, re.S)
    return re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S) if body else []


def _cells(row: str) -> list[str]:
    return re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)


@dataclass
class Attachment:
    apnd_no: str
    brd_blt_no: str
    brd_ty_no: str
    blt_no: str
    label: str = ""     # 페이지에 보이는 이름 (확장자 없을 수 있음)
    ext: str = ""       # 아이콘으로 표시된 형식: pdf / hwp / ...


def parse_anticancer_board(page: str) -> dict[str, Attachment]:
    """항암화학요법 게시판 -> {'booklet': ..., 'offlabel': ...}."""
    out = {}
    for row in _rows(page):
        m = _DOWN_ARGS.search(row)
        if not m:
            continue
        title = _text(row)
        for word, source in ANTICANCER_TITLES.items():
            if word in title:
                out[source] = Attachment(*m.groups(), label=title)
    return out


@dataclass
class NoticeRow:
    brd_blt_no: str
    doc_no: str             # '2026-210'
    title: str
    effective_date: date    # 제·개정일 (시행일)
    posted_date: date       # 작성일


def parse_notice_list(page: str) -> list[NoticeRow]:
    """공고 목록 열: 번호, 공고번호, 제목, 제·개정일, 작성일, 첨부."""
    out = []
    for row in _rows(page):
        cells = _cells(row)
        m = re.search(r"brdBltNo=(\d+)", row)
        if len(cells) < 5 or not m:
            continue
        no = re.search(r"(\d{4}\s*-\s*\d+)", _text(cells[1]))
        if not no:
            continue
        out.append(NoticeRow(brd_blt_no=m.group(1), doc_no=re.sub(r"\s", "", no.group(1)),
                             title=_text(cells[2]), effective_date=parse_date(_text(cells[3])),
                             posted_date=parse_date(_text(cells[4]))))
    return out


def parse_attachments(page: str) -> list[Attachment]:
    """상세 쪽 첨부 목록: <li><i class="icon-file-pdf"></i> 공고전문_20261001 <a onclick="downLoadBbs(...)">."""
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", page, re.S):
        m = _DOWN_ARGS.search(li)
        if not m:
            continue
        ext = re.search(r"icon-file-(\w+)", li)
        label = _text(re.sub(r"<a[^>]*>.*?</a>", "", li, flags=re.S))
        out.append(Attachment(*m.groups(), label=label, ext=ext.group(1) if ext else ""))
    return out


def pick_notice_pdf(atts: list[Attachment]) -> Attachment | None:
    for a in atts:
        if "공고전문" in a.label and a.ext == "pdf":
            return a
    return None


@dataclass
class PreviewRow:
    no: str
    title: str
    state: str              # 게시판 표기 ('공고예고완료' 등)
    period_start: date
    period_end: date


def parse_preview_list(page: str) -> list[PreviewRow]:
    """공고예고 목록 열: 번호, 제목, 첨부, 담당부서, 상태, 공고예고기간, 조회수."""
    out = []
    for row in _rows(page):
        cells = [_text(c) for c in _cells(row)]
        if len(cells) < 6:
            continue
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", cells[5])
        if len(dates) != 2:
            continue
        out.append(PreviewRow(no=cells[0], title=cells[1], state=cells[4],
                              period_start=date.fromisoformat(dates[0]),
                              period_end=date.fromisoformat(dates[1])))
    return out


# ---------- 판단 ----------

@dataclass
class Plan:
    """이번 실행에서 할 일. 내려받기 전에 화면에 보여 줄 수 있게 따로 만든다."""
    files: list[tuple[str, str, Attachment]] = field(default_factory=list)  # (source, 파일명, 첨부)
    notices: list[NoticeRow] = field(default_factory=list)                  # 새로 받을 공고
    skipped_notices: list[NoticeRow] = field(default_factory=list)          # 시행일 <= B
    previews: list[tuple[PreviewRow, str]] = field(default_factory=list)    # (행, 진행중/예정/종료)
    all_notices: list[NoticeRow] = field(default_factory=list)              # 공고 목록 1쪽 전체
    messages: list[str] = field(default_factory=list)


def _stored_date(reg: Registry, source: str) -> date | None:
    row = reg.latest_document(source)
    return date.fromisoformat(row["effective_date"]) if row and row["effective_date"] else None


def make_plan(http: Http, reg: Registry, today: date | None = None,
              sources: tuple[str, ...] = ("booklet", "offlabel")) -> Plan:
    """sources: 항암화학요법 게시판에서 확인할 파일. 허가초과가 범위 밖이면 ('booklet',)만 준다."""
    today = today or today_kst()
    plan = Plan()

    # 1. 항암화학요법 게시판: HEAD로 파일명 날짜만 확인
    board = parse_anticancer_board(http.get_text(BOARD_ANTICANCER))
    remote_booklet: date | None = None
    for source in sources:
        att = board.get(source)
        if att is None:
            plan.messages.append(f"[경고] 항암화학요법 게시판에서 '{source}' 글을 찾지 못함")
            continue
        name = http.head_filename(download_path(att))
        try:
            remote = date_from_filename(name)
        except ValueError:
            plan.messages.append(f"[경고] {source} 파일명에 날짜가 없음: {name!r}")
            continue
        stored = _stored_date(reg, source)
        stored_row = reg.latest_document(source)
        if source == "booklet":
            remote_booklet = remote
        if is_new_booklet(remote, stored):
            plan.files.append((source, name, att))
            plan.messages.append(f"{source}: 새 파일 {name} (저장된 날짜 {stored})")
        elif remote == stored and stored_row is not None and stored_row["file_name"] \
                and stored_row["file_name"] != safe_name(name):
            # 2026-10-15 실제 사례: 허가초과 파일이 같은 날짜로 다시 올라옴 (첨부 번호 1->2, 파일명 밑줄 빠짐)
            plan.files.append((source, name, att))
            plan.messages.append(f"[경고] {source}: 같은 날짜로 다시 올라온 파일 "
                                 f"({stored_row['file_name']} -> {name}). 받아서 내용을 비교한다")
        else:
            plan.messages.append(f"{source}: 최신 ({name})")

    # 2. 공고 게시판 1쪽: 시행일 > B 이고 레지스트리에 없는 글만.
    # 이번에 새 책자를 받는다면 그 날짜가 B다 (첫 실행에 지난 공고를 모두 받지 않게).
    b = max((d for d in (_stored_date(reg, "booklet"), remote_booklet) if d), default=None)
    notices = parse_notice_list(http.get_text(BOARD_NOTICE))
    plan.all_notices = notices
    for n in notices:
        if reg.has_board_id("notice", f"brdBltNo={n.brd_blt_no}"):
            continue
        if b is not None and notice_status(n.effective_date, b, today) == REFLECTED:
            plan.skipped_notices.append(n)
        else:
            plan.notices.append(n)
            if b is not None:
                plan.messages.append(
                    f"공고 제{n.doc_no}호 ({n.effective_date}): "
                    f"{notice_status(n.effective_date, b, today)}")

    # 3. 공고예고 게시판 1쪽: 받지 않고 상태만.
    # 예고와 공고를 잇는 번호가 없어서, 의견조회 마감 뒤에 작성된 공고가 있으면 대응 공고가 있다고 본다.
    for p in parse_preview_list(http.get_text(BOARD_PREVIEW)):
        has_notice = p.period_end < today and any(n.posted_date >= p.period_end for n in notices)
        plan.previews.append((p, preview_status(p.period_end, today, has_notice)))
    return plan


@dataclass
class Downloaded:
    source: str          # booklet / offlabel / notice
    path: Path
    file_hash: str
    doc_id: int
    reused: bool         # 같은 이름의 파일이 이미 있어 내려받지 않음
    report: "Report"     # qc.check_file 결과


def _get_file(http: Http, path: str, raw_dir: Path, expected_name: str | None) -> tuple[Path, bool]:
    """같은 이름의 파일이 raw_dir에 이미 있으면 다시 받지 않는다 (요청 수 절약)."""
    if expected_name:
        local = raw_dir / safe_name(expected_name)
        if local.exists():
            return local, True
    return http.download(path, raw_dir), False


def _register(reg: Registry, source: str, p: Path, reused: bool, expected: str | None,
              **fields) -> Downloaded:
    from .booklet import sha256
    from .qc import check_file

    rep = check_file(p, expected)
    h = sha256(p)
    doc_id = reg.add_document(source, file_hash=h, file_name=p.name, **fields)
    if not rep.ok:
        reg.set_status(doc_id, "failed", "; ".join(rep.errors))
    return Downloaded(source, p, h, doc_id, reused, rep)


def run_downloads(http: Http, reg: Registry, plan: Plan, raw_dir: Path) -> list[Downloaded]:
    """계획대로 내려받아 파일을 검사하고 레지스트리에 기록한다. 파싱·검증은 다음 단계에서 한다."""
    from .booklet import sha256

    out = []
    for source, name, att in plan.files:
        p, reused = _get_file(http, download_path(att), raw_dir, name)
        if not reused:
            # 이름만 바뀌고 내용이 같은 파일이면 새로 받은 것을 지우고 원래 파일을 쓴다
            same = reg.conn.execute("SELECT file_name FROM documents WHERE source=? AND file_hash=? "
                                    "AND file_name != ?", (source, sha256(p), p.name)).fetchone()
            if same is not None and (raw_dir / same["file_name"]).exists():
                p.unlink()
                p, reused = raw_dir / same["file_name"], True
                plan.messages.append(f"{source}: 다시 올라온 파일의 내용이 {same['file_name']}와 같음")
        out.append(_register(reg, source, p, reused, name, effective_date=date_from_filename(p.name)))
    for n in plan.notices:
        d = fetch_notice_pdf(http, reg, n, raw_dir)
        if d is None:
            plan.messages.append(f"[경고] 제{n.doc_no}호: 공고전문 PDF 첨부가 없음 (HWP만 있을 수 있음)")
        else:
            out.append(d)
    return out


def fetch_notice_pdf(http: Http, reg: Registry, n: NoticeRow, raw_dir: Path) -> Downloaded | None:
    """공고 하나의 공고전문 PDF. 파일명은 '공고전문_<시행일>.pdf'라서 이미 있으면 상세 쪽도 열지 않는다."""
    fields = dict(doc_no=n.doc_no, board_id=f"brdBltNo={n.brd_blt_no}", title=n.title,
                  posted_date=n.posted_date, effective_date=n.effective_date)
    guess = f"공고전문_{n.effective_date:%Y%m%d}.pdf"
    if (raw_dir / guess).exists():
        return _register(reg, "notice", raw_dir / guess, True, guess, **fields)
    page = http.get_text(f"{BOARD_NOTICE}&brdScnBltNo=4&brdBltNo={n.brd_blt_no}")
    att = pick_notice_pdf(parse_attachments(page))
    if att is None:
        return None
    p, reused = _get_file(http, download_path(att), raw_dir, None)
    return _register(reg, "notice", p, reused, None, **fields)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="새 파일을 실제로 내려받는다")
    ap.add_argument("--db", type=Path, default=DATA / "registry.db")
    ap.add_argument("--raw", type=Path, default=DATA / "raw")
    args = ap.parse_args(argv)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    reg = Registry(args.db)
    http = Http()
    try:
        plan = make_plan(http, reg)
        for m in plan.messages:
            print(m)
        for n in plan.skipped_notices:
            print(f"공고 제{n.doc_no}호 ({n.effective_date}): 책자에 반영됨, 건너뜀")
        for n in plan.notices:
            print(f"공고 제{n.doc_no}호 ({n.effective_date}): 공고전문 PDF를 받을 대상")
        for p, st in plan.previews[:3]:
            print(f"공고예고 {p.period_start}~{p.period_end} [{p.state}] -> {st}")
        if args.download:
            for d in run_downloads(http, reg, plan, args.raw):
                state = "있던 파일 사용" if d.reused else "저장"
                print(f"{state}: {d.path}  [{'정상' if d.report.ok else '오류: ' + '; '.join(d.report.errors)}]")
        elif plan.files or plan.notices:
            print("\n--download 를 붙이면 위 파일을 내려받는다.")
    finally:
        reg.close()
    print(f"(요청 {http.count}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
