"""개정 공고 전문(PDF) 읽기.

책자 우선 방식에서 공고는 책자에 덧씌우지 않는다. 대신
  1) '예정' 표시용 (번호, 공고일, 시행일)
  2) 검증용: 공고의 신설·변경·삭제 목록이 새 책자에 실제로 반영됐는지 대조
에 쓴다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .dates import parse_date
from .extract import extract_pages

KINDS = ("신설", "변경", "삭제")


@dataclass(frozen=True)
class Change:
    kind: str        # 신설 / 변경 / 삭제
    scope: str       # 'cancer' (주요 암종별 항암요법) / 'combination' (40. 기타 항암제 병용요법)
    cancer: str      # '비소세포폐암'
    regimen: str     # 'Tislelizumab + Pemetrexed + Platinum'


@dataclass
class NoticeDoc:
    path: Path
    doc_no: str
    posted_date: date
    effective_dates: list[date]
    changes: list[Change] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # 해석하지 않은 줄 (항구토제 목록 등)


_QUOTED = re.compile(r"[‘'](.+?)[’']")


def parse_notice_text(text: str, path: Path | None = None) -> NoticeDoc:
    m = re.search(r"공고\s*제\s*(\d{4}-\d+)\s*호", text)
    if not m:
        raise ValueError("공고번호를 찾지 못함")
    doc_no = m.group(1)

    # 부칙: '부 칙(2026.9.29.)' 다음 '(시행일) 이 공고는 2026년 10월 1일부터 시행한다. 다만, ...'
    b = re.search(r"부\s*칙\s*\(([^)]*)\)(.*?)(?:공고개정\s*내역|☐|$)", text, re.S)
    if not b:
        raise ValueError("부칙을 찾지 못함")
    posted = parse_date(b.group(1))
    eff = [parse_date(x) for x in re.findall(r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일", b.group(2))]
    if not eff:
        raise ValueError("시행일을 찾지 못함")

    doc = NoticeDoc(path=path or Path("-"), doc_no=doc_no, posted_date=posted,
                    effective_dates=eff)
    doc.changes, doc.skipped = _parse_changes(text)
    return doc


def _parse_changes(text: str) -> tuple[list[Change], list[str]]:
    """앞쪽 '공고개정 내역' 요약 목록을 읽는다 (뒤쪽 상세표는 읽지 않음)."""
    starts = [m.start() for m in re.finditer(r"공고개정\s*내역", text)]
    if not starts:
        return [], []
    end = starts[1] if len(starts) > 1 else len(text)
    block = text[starts[0]:end]
    # 줄바꿈으로 잘린 문장을 이어 붙인 뒤 '- ', 'ㆍ ', '<신설>' 단위로 나눈다
    flat = re.sub(r"\s*\n\s*", " ", block)
    tokens = re.split(r"(<(?:신설|변경|삭제)>|(?<!\S)-\s|ㆍ\s?)", flat)

    changes, skipped = [], []
    kind = scope = None
    bullet = None
    for tok in tokens:
        if not tok or not tok.strip():
            continue
        t = tok.strip()
        if t in ("<신설>", "<변경>", "<삭제>"):
            kind = t[1:-1]
            continue
        if t in ("-", "ㆍ"):
            bullet = t
            continue
        if kind is None:
            continue
        if bullet == "-":
            if t.startswith("기타 항암제 병용요법"):
                scope = "combination"
                continue
            scope = "cancer"
            cm = re.match(r"([가-힣/ ]+?)에\s", t)
            names = _QUOTED.findall(t)
            if cm and names:
                changes += [Change(kind, scope, cm.group(1).strip(), _clean(n)) for n in names]
            else:
                skipped.append(t)
        elif bullet == "ㆍ":
            cm = re.match(r"([가-힣/ ]+?)\s*\(\s*\d+\s*요법\s*\)\s*:", t)
            names = _QUOTED.findall(t)
            if scope == "combination" and cm and names:
                changes += [Change(kind, scope, cm.group(1).strip(), _clean(n)) for n in names]
            else:
                skipped.append(t)        # '항구토제 ... 목록 추가' 등
    return changes, skipped


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def load_notice(path: str | Path, engine: str = "pymupdf") -> NoticeDoc:
    path = Path(path)
    return parse_notice_text("\n".join(extract_pages(path, engine)), path)
