"""공고책자를 제대로 읽었는지 검증한다.

오류(error)가 하나라도 있으면 이 책자는 반영하지 않고 마지막 정상 버전을 유지한다 (§8 처리 흐름 9).
경고(warning)는 반영은 하되 화면과 로그에 남긴다.

검사 묶음
  A. 추출: 빈 쪽, 깨진 글자, 인쇄 쪽 번호 연속성
  B. 머리말·개정 이력: 공고번호 일치, 날짜 순서, 파일명 날짜 가정
  C. 섹션: 목차의 암종이 본문에서 모두, 순서대로 발견되는지
  D. 항목 변경 표시: 이력에 있는 공고인지, 날짜가 맞는지, 책자 날짜 이후가 아닌지
  E. 두 엔진 비교 (선택): PyMuPDF와 pdfplumber의 쪽별 단어 비교
  F. 공고 대조 (선택): 공고 전문의 신설·변경·삭제가 책자에 반영됐는지
  G. 이전 책자 대조 (선택): 이전 책자의 마지막 공고가 새 이력에 있는지
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .booklet import Booklet, item_tags
from .notice import NoticeDoc

# 원래 비어 있는 쪽 비율 상한. 이번 책자는 277쪽 중 7쪽(간지)이 비어 있다
MAX_EMPTY_RATIO = 0.05
# 반드시 있어야 하는 섹션 (없으면 오류)
REQUIRED_SECTIONS = ("general", "cancer:유방암", "combination")
# 유방암 섹션에 반드시 나와야 하는 낱말 (구조가 크게 바뀌거나 잘렸는지 확인)
BREAST_ANCHORS = ("선행화학요법", "수술후보조요법", "고식적요법", "trastuzumab", "tamoxifen")
TAG_WINDOW = 1500
# 변경 표시의 머리 ('제2021-150호:' 또는 쉼표 표기 '제2024-188호, 2024'). ITEM_TAG와 같은 두 표기를 센다.
# 쉼표 뒤에 연도가 와야 머리로 본다 ('제2024-188호, 제2024-264호' 같은 나열은 빼려고)
TAG_HEAD = re.compile(r"제\s*(\d{4}\s*-\s*\d+)\s*호?\s*(?::|,(?=\s*\d{4}\s*\.))")
MAX_UNREAD_TAG_RATIO = 0.02   # PyMuPDF는 1604/1605, pdfplumber는 1412/1600   # 공고 대조 때 요법 이름 뒤에서 변경 표시를 찾는 범위 (글자 수)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "info": self.info}

    def render(self) -> str:
        lines = [f"검증 결과: {'통과' if self.ok else '실패'} "
                 f"(오류 {len(self.errors)}, 경고 {len(self.warnings)})"]
        lines += [f"  [오류] {m}" for m in self.errors]
        lines += [f"  [경고] {m}" for m in self.warnings]
        lines += [f"  [정보] {m}" for m in self.info]
        return "\n".join(lines)


def validate_booklet(b: Booklet, *, other: Booklet | None = None,
                     notice: NoticeDoc | None = None,
                     previous_doc_no: str | None = None,
                     previous_file_date: date | None = None) -> Report:
    r = Report()
    _check_extraction(b, r)
    _check_history(b, r)
    _check_sections(b, r)
    _check_tags(b, r)
    if other is not None:
        _compare_engines(b, other, r)
    if notice is not None:
        _check_notice(b, notice, r)
    if previous_doc_no is not None:
        _check_previous(b, previous_doc_no, previous_file_date, r)
    return r


# ---------- A. 추출 ----------

def _check_extraction(b: Booklet, r: Report) -> None:
    n = len(b.raw_pages)
    empty = [i + 1 for i, p in enumerate(b.raw_pages) if len(p.strip()) < 20]
    r.info.append(f"{n}쪽, 빈 쪽 {len(empty)}개 {empty}")
    if n == 0 or len(empty) / n > MAX_EMPTY_RATIO:
        r.error(f"빈 쪽이 너무 많음 ({len(empty)}/{n}). 스캔본이거나 추출 실패")
    bad = [i + 1 for i, p in enumerate(b.raw_pages) if "(cid:" in p or "\ufffd" in p]
    if bad:
        r.error(f"깨진 글자가 있는 쪽: {bad[:20]}")

    # 인쇄 쪽 번호는 본문에서 1씩 늘어야 한다 (빠진 쪽, 순서가 섞인 쪽 확인)
    nums = [(i + 1, b.printed_page(i + 1)) for i in range(n)]
    nums = [(pdf, pr) for pdf, pr in nums if pr is not None]
    jumps = [(a, b2) for (a, pa), (b2, pb) in zip(nums, nums[1:])
             if pb - pa != b2 - a]
    if jumps:
        r.warn(f"인쇄 쪽 번호가 PDF 쪽과 어긋나는 곳 {len(jumps)}곳 (PDF 쪽 기준): {jumps[:10]}")


# ---------- B. 머리말·개정 이력 ----------

def _check_history(b: Booklet, r: Report) -> None:
    h = b.history
    if not h:
        r.error("개정 이력을 읽지 못함")
        return
    last = b.last_notice
    r.info.append(f"개정 이력 {len(h)}건, 마지막 제{last.doc_no}호 "
                  f"(공고 {last.posted_date}, 시행 {last.effective_date})")
    if b.doc_no != last.doc_no:
        r.error(f"첫 줄 공고번호 제{b.doc_no}호 ≠ 이력의 마지막 제{last.doc_no}호")
    if b.file_date != last.effective_date:
        r.warn(f"가정 불일치: 파일명 날짜 {b.file_date} ≠ 마지막 공고 시행일 {last.effective_date}")
    if last.effective_date > b.file_date:
        r.error(f"이력의 마지막 시행일 {last.effective_date}이 파일명 날짜 {b.file_date}보다 늦음")

    years = Counter(n.doc_no.split("-")[0] for n in h)
    if any(int(n.doc_no.split("-")[0]) != n.posted_date.year for n in h):
        odd = [n.doc_no for n in h if int(n.doc_no.split("-")[0]) != n.posted_date.year]
        r.warn(f"공고번호 연도와 공고일 연도가 다른 이력: {odd}")
    for a, c in zip(h, h[1:]):
        if c.posted_date < a.posted_date:
            r.warn(f"이력 순서가 뒤바뀜: 제{a.doc_no}호 → 제{c.doc_no}호")
    early = [n.doc_no for n in h if n.effective_date < n.posted_date]
    if early:
        r.warn(f"시행일이 공고일보다 빠른 이력 (소급 시행): {early}")
    multi = [n.doc_no for n in h if len(n.effective_dates) > 1]
    if multi:
        r.info.append(f"시행일이 두 개 이상인 공고: {multi} (부칙 확인 필요)")
    r.info.append(f"연도별 공고 수(최근 3년): "
                  f"{ {y: years[y] for y in sorted(years)[-3:]} }")


# ---------- C. 섹션 ----------

def _check_sections(b: Booklet, r: Report) -> None:
    for key in REQUIRED_SECTIONS:
        if key not in b.sections:
            r.error(f"필수 섹션을 찾지 못함: {key}")
    if not b.toc_cancers:
        r.error("목차에서 암종 목록을 읽지 못함")
        return
    missing = [name for _, name in b.toc_cancers if f"cancer:{name}" not in b.sections]
    if missing:
        r.warn(f"목차에는 있으나 본문에서 못 찾은 암종: {missing}")
    starts = [b.sections[f"cancer:{n}"].start for _, n in b.toc_cancers
              if f"cancer:{n}" in b.sections]
    if starts != sorted(starts):
        r.error("암종 섹션 순서가 목차 순서와 다름 (제목 인식 오류 가능)")
    r.info.append(f"목차 암종 {len(b.toc_cancers)}개 중 {len(b.toc_cancers) - len(missing)}개 발견")
    _check_toc_split(b, r)

    if "cancer:유방암" in b.sections:
        s = b.sections["cancer:유방암"]
        text = b.section_text("유방암")
        r.info.append(f"유방암 섹션: PDF {s.start}~{s.end}쪽 "
                      f"(인쇄 {b.printed_page(s.start)}~{b.printed_page(s.end)}쪽), {len(text)}자")
        lacking = [w for w in BREAST_ANCHORS if w not in text]
        if lacking:
            r.error(f"유방암 섹션에 있어야 할 낱말이 없음: {lacking}")
        if "Ovarian" in text or "난소암 / 난관암" in text:
            r.error("유방암 섹션에 다음 섹션(난소암) 내용이 섞임")


def _check_toc_split(b: Booklet, r: Report) -> None:
    """목차 전체(Ⅰ~Ⅳ, 별첨) 단위로 나눈 결과 검사.

    - 목차 항목이 본문에서 모두 발견되는지 (대단원 간지는 없어도 됨: Ⅰ은 간지가 없다)
    - 본문 시작 쪽이 목차에 적힌 쪽과 가까운지 (인쇄 쪽 번호 읽기가 ±1쪽 흔들려 2쪽까지 허용)
    - 섹션 밖에 남은 본문 글자 (첫 섹션 앞, 암종 묶음 제목)
    """
    if not b.toc:
        r.error("목차를 읽지 못함")
        return
    items = [e for e in b.toc if not e.is_part and e.key != "cancers"]
    lost = [e.title for e in b.toc_missing if not e.is_part and e.key != "cancers"]
    if lost:
        r.warn(f"목차 항목을 본문에서 못 찾음 (앞 섹션에 합쳐짐): {lost}")
    parts = [e.title for e in b.toc_missing if e.is_part]
    if parts:
        r.info.append(f"간지가 없는 대단원: {parts}")
    far = []
    for e in items:
        s = b.sections.get(e.key)
        p = b.printed_page(s.start) if s else None
        if s and e.toc_page and p and abs(p - e.toc_page) > 2:
            far.append(f"{e.title} (목차 {e.toc_page}쪽, 본문 {p}쪽)")
    if far:
        r.warn(f"목차 쪽 번호와 본문 위치가 2쪽 넘게 다름 (제목 인식 오류 가능): {far}")
    def size(t: str) -> int:
        return len(re.sub(r"\s", "", t))
    covered = sum(size(b.section_text(k)) for k in b.sections)
    outside = sum(size(p) for p in b.pages[b.body_from - 1:]) - covered
    r.info.append(f"목차 단위 섹션 {len(b.sections)}개 (목차 항목 {len(items)}개 중 "
                  f"{len(items) - len(lost)}개 발견), 섹션 밖 본문 {outside}자")
    if outside > 200:
        r.warn(f"어느 섹션에도 들어가지 않은 본문이 {outside}자 (섹션 경계 확인 필요)")


# ---------- D. 항목 변경 표시 ----------

# 표가 쪽을 넘어가면 새 쪽 맨 위에 표 머리글이 다시 나온다 (유방암 표 3칸, 병용요법 표 8칸)
REPEATED_HEADER_LINES = {"연번", "항암요법", "투여대상", "주요", "암종", "항암제 병용요법",
                         "허가사항", "급여 요법", "급여기준", "비고"}


def _strip_repeated_headers(page: str) -> str:
    """쪽 맨 위의 반복된 표 머리글 줄을 뺀다. 앞 쪽 끝 '(제2025-133호:'와
    이 쪽 첫 줄 '2025.6.5.)'처럼 쪽 경계에서 나뉜 변경 표시를 이어 읽기 위해서다."""
    lines = page.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() in REPEATED_HEADER_LINES:
        i += 1
    return "\n".join(lines[i:])


def _check_tags(b: Booklet, r: Report) -> None:
    body_from = min((s.start for s in b.sections.values()), default=1)
    body = "\f".join(_strip_repeated_headers(p) for p in b.pages[body_from - 1:])
    tags = item_tags(body)
    hist = {n.doc_no: n for n in b.history}
    r.info.append(f"본문 변경 표시 {len(tags)}개")

    future = sorted({f"제{no}호 {d}" for no, d in tags if d > b.file_date})
    if future:
        r.error(f"책자 날짜보다 늦은 변경 표시: {future[:10]}")
    unknown = Counter(no for no, _ in tags if no not in hist)
    if unknown:
        r.warn(f"이력에 없는 공고번호를 가리키는 변경 표시 {sum(unknown.values())}개 "
               f"(복지부 고시 번호이거나 원문 오기): {dict(unknown)}")
    mismatch = Counter((no, d) for no, d in tags
                       if no in hist and d not in hist[no].effective_dates
                       and d != hist[no].posted_date)
    if mismatch:
        r.warn(f"변경 표시 날짜가 이력의 시행일·공고일과 다른 경우 {sum(mismatch.values())}개: "
               f"{[f'제{no}호 {d}' for no, d in list(mismatch)[:8]]}")

    # 자기 검사: '제XXXX-NN호:' 머리는 있는데 날짜를 못 읽은 표시.
    # 표의 칸 순서가 섞여 추출되면(엔진 문제) 이 비율이 크게 늘어난다
    heads = TAG_HEAD.findall(body)
    unread = len(heads) - len(tags)
    if heads and unread / len(heads) > MAX_UNREAD_TAG_RATIO:
        r.error(f"변경 표시 {len(heads)}개 중 {unread}개의 날짜를 읽지 못함 (표 칸 순서가 섞였을 가능성)")
    elif unread > 0:
        r.warn(f"날짜를 읽지 못한 변경 표시 {unread}개 (쪽 경계에서 잘린 경우 등)")

    if "cancer:유방암" in b.sections:
        n = len(item_tags(b.section_text("유방암")))
        if n == 0:
            r.error("유방암 섹션에서 변경 표시를 하나도 찾지 못함")
        r.info.append(f"유방암 섹션 변경 표시 {n}개")


# ---------- E. 두 엔진 비교 ----------

def _words(text: str) -> Counter:
    return Counter(re.findall(r"[0-9A-Za-z가-힣]+", text))


def _compare_engines(b: Booklet, o: Booklet, r: Report, threshold: float = 0.97) -> None:
    if len(b.pages) != len(o.pages):
        r.error(f"엔진별 쪽 수가 다름: {b.engine} {len(b.pages)} / {o.engine} {len(o.pages)}")
        return
    low = []
    for i, (x, y) in enumerate(zip(b.pages, o.pages)):
        wx, wy = _words(x), _words(y)
        total = sum((wx | wy).values())
        if total and sum((wx & wy).values()) / total < threshold:
            low.append(i + 1)
    if low:
        r.warn(f"{b.engine}와 {o.engine}의 단어 일치율이 {threshold:.0%} 미만인 쪽: {low[:20]}")
    if [n.doc_no for n in b.history] != [n.doc_no for n in o.history]:
        r.error("엔진별 개정 이력이 다름")
    for key in REQUIRED_SECTIONS:
        if key in b.sections and key in o.sections and \
                b.sections[key].start != o.sections[key].start:
            r.error(f"엔진별 섹션 시작 쪽이 다름: {key}")
    # 날짜까지 비교하면 칸 순서가 섞이는 엔진에서 차이가 나므로, 공고번호 머리만 비교한다
    hb = Counter(re.sub(r"\s", "", x) for x in TAG_HEAD.findall("\f".join(b.pages)))
    ho = Counter(re.sub(r"\s", "", x) for x in TAG_HEAD.findall("\f".join(o.pages)))
    diff = (hb - ho) + (ho - hb)
    if sum(diff.values()) > 0.01 * max(1, sum(hb.values())):
        r.error(f"엔진별 변경 표시 공고번호 차이가 1%를 넘음: {dict(list(diff.items())[:10])}")
    elif diff:
        r.warn(f"엔진별 변경 표시 공고번호 차이 {sum(diff.values())}개: {dict(diff)}")
    r.info.append(f"두 엔진 비교 완료 ({b.engine} vs {o.engine}), 차이 쪽 {len(low)}개")


# ---------- F. 공고 대조 ----------

def norm_regimen(s: str) -> str:
    """요법 이름 비교용: 소문자, 공백 제거, 각주 표시('주1')와 '(비급여)' 제거."""
    s = s.lower()
    s = re.sub(r"주\d+", "", s)
    s = s.replace("(비급여)", "")
    return re.sub(r"\s+", "", s)


def _check_notice(b: Booklet, n: NoticeDoc, r: Report) -> None:
    if n.doc_no != b.doc_no:
        r.info.append(f"공고 제{n.doc_no}호는 이 책자(제{b.doc_no}호)의 마지막 공고가 아니라 대조 생략")
        return
    hist = {x.doc_no: x for x in b.history}
    h = hist.get(n.doc_no)
    if h and (h.posted_date != n.posted_date or min(n.effective_dates) != h.effective_date):
        r.error(f"공고 전문의 날짜(공고 {n.posted_date}, 시행 {n.effective_dates})가 "
                f"책자 이력(공고 {h.posted_date}, 시행 {h.effective_date})과 다름")
    tag = norm_regimen(f"제{n.doc_no}호")
    checked = 0
    for c in n.changes:
        key = "combination" if c.scope == "combination" else c.cancer
        try:
            text = norm_regimen(b.section_text(key))
        except LookupError:
            r.error(f"공고의 {c.kind} 항목 섹션을 책자에서 못 찾음: {key}")
            continue
        reg = norm_regimen(c.regimen)
        hits = [m.start() for m in re.finditer(re.escape(reg), text)]
        label = f"{c.kind} [{key}] {c.regimen}"
        if c.kind == "삭제":
            if hits:
                r.error(f"삭제된 요법이 책자에 남아 있음: {label}")
        elif not hits:
            r.error(f"공고의 요법이 책자에 없음: {label}")
        elif not any(tag in text[p:p + TAG_WINDOW] for p in hits):
            r.warn(f"요법은 있으나 근처에 제{n.doc_no}호 변경 표시가 없음: {label}")
        checked += 1
    r.info.append(f"공고 제{n.doc_no}호 대조: 항목 {checked}개 확인, 해석 안 한 줄 {len(n.skipped)}개")


# ---------- G. 이전 책자 대조 ----------

def _check_previous(b: Booklet, prev_doc_no: str, prev_date: date | None, r: Report) -> None:
    if prev_doc_no not in {n.doc_no for n in b.history}:
        r.error(f"이전 책자의 마지막 공고 제{prev_doc_no}호가 새 책자 이력에 없음")
    if prev_date is not None and b.file_date < prev_date:
        r.error(f"새 책자 날짜 {b.file_date}가 이전 책자 {prev_date}보다 이름")
