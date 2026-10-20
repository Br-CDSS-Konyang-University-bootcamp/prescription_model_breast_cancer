"""공고책자 PDF 읽기.

책자에서 바로 얻는 것:
  - 반영된 마지막 공고 번호 (첫 줄 '공고 제2026-210호')
  - 2006년부터의 전체 개정 이력 (공고번호, 공고일, 시행일)
  - 섹션 위치: 일반원칙, 암종별(목차 기준 40개), 기타 항암제 병용요법
  - 항목별 변경 표시 '(제2025-272호: 2026.1.1., 개정 제2026-210호: 2026.10.1.)'
    -> 항목의 effective_from = 가장 늦은 날짜
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .dates import date_from_filename, find_dates
from .extract import clean_page, extract_pages, printed_page_no

# 개정 이력 한 줄. 실제 표기가 제각각이다:
#   '개정 2022.2.25 공고 제2022-38호(2022.3.1. 시행)'
#   '개정 2025.11.25. 공고 제 2025-256호(2025.12.1. 시행)'
#   '개정 2011.9.29. 공고 제2011-106호(2011.10.1. 시행, 2011.12.1. 시행)'
_HISTORY = re.compile(
    r"(제정|전부개정|개정)\s*"
    r"(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?)\s*공고\s*제\s*(\d{4}-\d+)호"
    r"\s*\(([^)]*)\)"
)
_HEADER = re.compile(r"공고\s*제\s*(\d{4}-\d+)호")
# 항목 변경 표시. 줄바꿈·번호 속 공백('제2021- 129호')을 허용한다.
# 번호와 날짜 사이는 쌍점이 보통이지만 최근 공고는 쉼표로도 쓴다:
#   '제2021-150호: 2021.6.1.'  '개정 제2024-188호, 2024.8.1.'  '개정 제2024-188, 2024.8.1.' ('호' 빠짐)
ITEM_TAG = re.compile(
    r"제\s*(\d{4})\s*-\s*(\d+)\s*호?\s*[:,]\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})"
)
# 목차 둘째 쪽의 암종 줄: '9. 유방암 ······ 47', '38. 조혈모세포이식 전처치요법151'
_TOC_CANCER = re.compile(r"(\d{1,2}(?:-\d)?)\.\s*([가-힣/ ]+?)\s*(?:·{2,}\s*)?(\d{1,3})(?=\s|$)")
# 목차 첫째 쪽의 한 줄: 'Ⅱ. 항구토제·····184', '1. G-CSF 주사제·····212', '※ 별첨 1. 삭제사항 정리····222'
_TOC_LINE = re.compile(r"^\s*(?P<head>※\s*별첨|[ⅠⅡⅢⅣⅤ]\.)?\s*(?P<title>[^·\s].*?)\s*·{2,}\s*(?P<page>\d{1,3})\s*$")
# '40. 기타 항암제 병용요법\n(기존 항암요법 본인일부부담)\n159' (점선 없이 줄이 나뉨)
_TOC_COMBO = re.compile(r"40\.\s*기타 항암제\s*병용요법\D{0,40}?(\d{1,3})(?=\s|$)")

# 본문에서 섹션 시작을 찾는 표지 (목차 제목과 본문 제목이 다른 것만)
MARKERS = {
    "general": r"항암요법의 요양급여 적용 일반원칙",
    "cancers": r"주요 암종별 항암요법",
    "combination": r"40\s*기타 항암제\s*병용요법",
    "immunotherapy": r"항암면역요법제",
}
# 목차 제목 -> 섹션 키 (Ⅰ. 항암요법 아래)
_PART1_KEYS = {"항암요법의 요양급여 적용 일반원칙": "general", "주요 암종별 항암요법": "cancers",
               "항암면역요법제": "immunotherapy"}
# Ⅱ~Ⅳ, 별첨 항목의 키 머리 ('antiemetic:일반원칙', 'other:G-CSF 주사제', 'appendix:삭제사항 정리')
PART_SLUG = {"Ⅱ": "antiemetic", "Ⅲ": "pain", "Ⅳ": "other", "별첨": "appendix"}
# 섹션이 아닌 표지 (암종 묶음 제목). 본문 위치만 찾고 섹션으로 만들지 않는다
GROUP_KEYS = {"cancers"}
CACHE_VERSION = 2   # 추출·정리 방식을 바꾸면 올린다 (예전 캐시를 안 쓰게)


@dataclass(frozen=True)
class TocEntry:
    """목차 한 줄. 목차 순서 그대로 본문에서 찾는다."""
    key: str                  # 'general', 'cancer:유방암', 'combination', 'part:항구토제', 'other:G-CSF 주사제'
    title: str                # 목차에 적힌 제목
    part: str                 # 'Ⅰ'~'Ⅳ', '별첨'
    toc_page: int | None      # 목차에 적힌 쪽 번호 (인쇄 쪽)
    is_part: bool = False     # 'Ⅱ. 항구토제' 같은 대단원 (간지)


@dataclass(frozen=True)
class Notice:
    doc_no: str               # '2026-210'
    kind: str                 # 제정 / 개정 / 전부개정
    posted_date: date
    effective_dates: tuple[date, ...]   # 보통 1개, 드물게 2개

    @property
    def effective_date(self) -> date:
        """대표 시행일 = 가장 이른 날짜. 시행일이 두 개면 부칙 확인 필요."""
        return min(self.effective_dates)


@dataclass(frozen=True)
class Section:
    key: str           # 'general', 'combination', 'cancer:유방암'
    title: str
    start: int         # 시작 PDF 쪽 (1부터)
    end: int           # 끝 PDF 쪽 (포함). 다음 섹션이 같은 쪽에서 시작할 수 있음
    offset: int = 0    # 시작 쪽 안에서 제목이 나오는 글자 위치
    end_offset: int | None = None   # 끝 쪽에서 다음 섹션 제목 위치 (None = 쪽 끝까지)


@dataclass
class Booklet:
    path: Path
    file_hash: str
    file_date: date            # 파일명 날짜 (§8의 B)
    doc_no: str                # 반영된 마지막 공고
    history: list[Notice]
    engine: str
    raw_pages: list[str] = field(repr=False)
    pages: list[str] = field(repr=False)            # clean_page 적용
    toc_cancers: list[tuple[str, str]] = field(default_factory=list)   # [(번호, 이름)]
    sections: dict[str, Section] = field(default_factory=dict)
    toc: list[TocEntry] = field(default_factory=list)                  # 목차 전체 (순서대로)
    toc_missing: list[TocEntry] = field(default_factory=list)          # 본문에서 못 찾은 목차 항목
    body_from: int = 1                                                 # 본문 시작 PDF 쪽

    @property
    def last_notice(self) -> Notice:
        return max(self.history, key=lambda n: n.effective_date)

    def printed_page(self, pdf_page: int) -> int | None:
        """출처 표시용 인쇄 쪽 번호."""
        return printed_page_no(self.raw_pages[pdf_page - 1])

    def section(self, key: str) -> Section:
        for k in (key, f"cancer:{key}"):
            if k in self.sections:
                return self.sections[k]
        raise LookupError(f"섹션을 찾지 못함: {key}")

    def section_text(self, key: str) -> str:
        """섹션 본문만 (정리된 텍스트). 쪽 경계는 '\\f'로 남긴다."""
        s = self.section(key)
        parts = list(self.pages[s.start - 1:s.end])
        if s.end_offset is not None:
            parts[-1] = parts[-1][:s.end_offset]
        parts[0] = parts[0][s.offset:] if s.start != s.end or s.end_offset is None \
            else self.pages[s.start - 1][s.offset:s.end_offset]
        return "\f".join(parts).strip()


def _marker_re(pat: str) -> re.Pattern:
    return re.compile(rf"(?m)^[ \t]*(?:{pat})")


def _cancer_header_re(no: str, name: str) -> re.Pattern:
    """'9\n유방암(Breast Cancer)', '39\n기타 암' 등. 이름 속 공백·'/' 주변은 느슨하게."""
    loose = r"\s*".join(re.escape(c) for c in name.replace(" ", ""))
    return re.compile(rf"(?m)^[ \t]*{re.escape(no)}[ \t]*\n?[ \t]*{loose}[ \t]*(?:\(|$)")


def item_tags(text: str) -> list[tuple[str, date]]:
    """항목 변경 표시 [(공고번호, 날짜), ...]."""
    return [(f"{y}-{n}", date(int(a), int(b), int(c)))
            for y, n, a, b, c in ITEM_TAG.findall(text)]


def item_effective_from(text: str) -> date | None:
    """항목 텍스트의 변경 표시 중 가장 늦은 날짜. 표시가 없으면 None."""
    tags = item_tags(text)
    return max(d for _, d in tags) if tags else None


def parse_history(text: str) -> list[Notice]:
    notices: dict[str, Notice] = {}
    for kind, posted, doc_no, inner in _HISTORY.findall(text):
        eff = find_dates(inner)
        if eff:
            notices[doc_no] = Notice(doc_no, kind, find_dates(posted)[0], tuple(eff))
    return sorted(notices.values(), key=lambda n: (n.posted_date, n.doc_no))


def _loose(text: str) -> str:
    """글자 사이 공백·줄바꿈을 허용하는 패턴 ('항구토제 투여기준' -> '항\\s*구\\s*토...').
    조사 '의'는 없어도 된다 (목차 '항암제들의 구토 유발 가능성 정도', 본문 '항암제들 구토 유발 가능성 정도')."""
    return r"\s*".join("의?" if c == "의" else re.escape(c) for c in text.replace(" ", ""))


def _core_title(title: str) -> str:
    """목차 제목에서 번호와 품명 괄호를 뗀 본문 제목 ('2. zoledronic acid 주사제(품명: …)' -> 'zoledronic acid 주사제')."""
    return re.sub(r"^\d+\.\s*", "", title).split("(", 1)[0].strip()


def parse_toc(toc_pages: list[str]) -> tuple[list[TocEntry], list[tuple[str, str]]]:
    """목차 쪽 텍스트 -> (목차 전체, 암종 목록).

    첫째 쪽(‘Ⅰ.’이 있는 쪽)에 대단원 Ⅰ~Ⅳ와 그 아래 항목, 별첨이 있고,
    둘째 쪽에 '주요 암종별 항암요법'의 암종 1~40이 있다. 암종은 첫째 쪽의 그 줄 자리에 펼쳐 넣는다.
    """
    main = [p for p in toc_pages if re.search(r"(?m)^\s*Ⅰ\.", p)]
    detail = "\n".join(p for p in toc_pages if p not in main)
    cancers: dict[tuple[str, str], int] = {}
    for no, name, page in _TOC_CANCER.findall(detail):
        if "정리" not in name:                      # '별첨 1. 삭제사항 정리' 제외
            cancers.setdefault((no, name.strip()), int(page))
    combo = _TOC_COMBO.search(detail)

    entries: list[TocEntry] = []
    part = None
    for line in "\n".join(main).splitlines():
        m = _TOC_LINE.match(line)
        if not m:
            continue
        head, title, page = (m.group("head") or "").strip(), m.group("title").strip(), int(m.group("page"))
        if head == "※ 별첨" or head.startswith("※"):
            part = "별첨"
            entries.append(TocEntry(f"appendix:{_core_title(title)}", title, part, page))
        elif head:
            part = head[0]
            entries.append(TocEntry(f"part:{title}", title, part, page, is_part=True))
        elif part == "Ⅰ":
            key = _PART1_KEYS.get(title, f"chemo:{_core_title(title)}")
            entries.append(TocEntry(key, title, part, page))
            if key == "cancers":
                entries += [TocEntry(f"cancer:{name}", f"{no}. {name}", part, p)
                            for (no, name), p in cancers.items()]
                entries.append(TocEntry("combination", "40. 기타 항암제 병용요법", part,
                                        int(combo.group(1)) if combo else None))
        elif part in PART_SLUG:
            entries.append(TocEntry(f"{PART_SLUG[part]}:{_core_title(title)}", title, part, page))
    return entries, list(cancers)


def _entry_re(e: TocEntry, cancers: dict[str, str]) -> re.Pattern:
    """목차 항목의 본문 제목 패턴."""
    if e.key in MARKERS:
        return _marker_re(MARKERS[e.key])
    if e.key.startswith("cancer:"):
        name = e.key.split(":", 1)[1]
        return _cancer_header_re(cancers[name], name)
    if e.is_part:
        # 간지: 제목 다음 줄에 그 단원의 작은 목차('□ 일반원칙…' 또는 'Ⅳ' 다음 '1. G-CSF…')가 온다
        return re.compile(rf"(?m)^[ \t]*{_loose(e.title)}[ \t]*\n(?:[ \t]*[ⅠⅡⅢⅣ][ \t]*\n)?[ \t]*(?:□|1\.)")
    # 항목: '1\nG-CSF 주사제', '2\nzoledronic acid 주사제(품명…', '1. 삭제사항 정리'
    return re.compile(rf"(?m)^[ \t]*(?:\d+\.?[ \t]*\n?[ \t]*)?{_loose(_core_title(e.title))}[ \t]*(?:\(|$)")


def _find_sections(pages: list[str], toc: list[TocEntry],
                   body_from: int) -> tuple[dict[str, Section], list[TocEntry]]:
    """목차 순서대로 본문 제목을 찾는다. 앞 항목을 찾은 곳 뒤에서만 다음 항목을 찾으므로
    목차·간지·다른 섹션 안의 같은 낱말에 걸리지 않는다. 다음 항목 제목 직전까지가 그 섹션이다.

    body_from: 본문이 시작하는 쪽 번호 (목차·일러두기의 같은 제목을 피하려고)
    돌려주는 값: (섹션, 본문에서 못 찾은 목차 항목)
    """
    cancers = {e.key.split(":", 1)[1]: e.title.split(".", 1)[0] for e in toc if e.key.startswith("cancer:")}
    hits, missing = [], []
    pos = (body_from - 1, 0)                    # (쪽 0부터, 글자 위치)
    for e in toc:
        rx = _entry_re(e, cancers)
        found = None
        for i in range(pos[0], len(pages)):
            m = rx.search(pages[i], pos[1] if i == pos[0] else 0)
            if m:
                found = (i, m.start())
                break
        if found is None:
            missing.append(e)
            continue
        hits.append((found[0] + 1, found[1], e))
        pos = (found[0], found[1] + 1)
    out = {}
    for idx, (page, off, e) in enumerate(hits):
        if e.key in GROUP_KEYS:      # '주요 암종별 항암요법'은 암종 묶음의 표지일 뿐
            continue
        if e.key in MARKERS:
            title = e.key
        elif e.key.startswith("cancer:"):
            title = e.title.replace(". ", " ", 1)       # '9 유방암'
        else:
            title = e.title
        if idx + 1 == len(hits):
            out[e.key] = Section(e.key, title, page, len(pages), off, None)
        else:
            nxt = hits[idx + 1]
            out[e.key] = Section(e.key, title, page, nxt[0], off, nxt[1])
    return out, missing


def load_booklet(path: str | Path, cache_dir: str | Path | None = None,
                 engine: str = "pymupdf") -> Booklet:
    """책자 PDF를 읽는다.

    cache_dir를 주면 (파일 해시, 엔진)별로 쪽 텍스트를 JSON으로 저장해 재사용한다.
    캐시에는 공고 원문이 들어 있으니 git에 올리지 않는다 (§8 구현 주의).
    """
    path = Path(path)
    file_hash = sha256(path)
    cache = (Path(cache_dir) / f"booklet_{file_hash[:16]}_{engine}_v{CACHE_VERSION}.json"
             if cache_dir else None)
    if cache and cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
    else:
        raw = extract_pages(path, engine)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return build_booklet(raw, path, file_hash, engine)


def build_booklet(raw: list[str], path: str | Path, file_hash: str = "",
                  engine: str = "pymupdf") -> Booklet:
    """쪽 텍스트로 Booklet을 만든다. 테스트에서 텍스트를 일부러 고쳐 검증을 시험할 때도 쓴다."""
    path = Path(path)
    pages = [clean_page(p) for p in raw]
    m = _HEADER.search(pages[0] if pages else "")
    if not m:
        raise ValueError("첫 쪽에서 공고번호를 찾지 못함")
    # 개정 이력은 본문 시작('「국민건강보험') 전까지
    front = "\n".join(pages[:15]).split("「국민건강보험", 1)[0]
    toc_idx = [i for i, p in enumerate(pages[:60]) if p.count("···") >= 5]
    toc, cancers = parse_toc([pages[i] for i in toc_idx])
    body_from = (max(toc_idx) + 2) if toc_idx else 1
    sections, missing = _find_sections(pages, toc, body_from)
    return Booklet(
        path=path, file_hash=file_hash, file_date=date_from_filename(path.name),
        doc_no=m.group(1), history=parse_history(front), engine=engine,
        raw_pages=list(raw), pages=pages, toc_cancers=cancers,
        sections=sections, toc=toc, toc_missing=missing, body_from=body_from,
    )


def section_records(b: Booklet) -> list[dict]:
    """목차 단위로 나눈 책자 전체 (1단계 결과). 유방암 청크는 이 중 유방암·병용요법 섹션에서 만든다.

    공고 원문이 들어 있으므로 git에 올리지 않는다 (data/reimbursement/sections/).
    """
    out = []
    by_key = {e.key: e for e in b.toc}
    for key, s in sorted(b.sections.items(), key=lambda kv: (kv[1].start, kv[1].offset)):
        e = by_key.get(key)
        text = b.section_text(key)
        out.append({
            "key": key, "title": s.title, "part": e.part if e else None,
            "toc_page": e.toc_page if e else None,
            "pdf_start": s.start, "pdf_end": s.end,
            "page_start": b.printed_page(s.start), "page_end": b.printed_page(s.end),
            "chars": len(text), "breast_mentions": text.count("유방"),
            "text": text,
        })
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
