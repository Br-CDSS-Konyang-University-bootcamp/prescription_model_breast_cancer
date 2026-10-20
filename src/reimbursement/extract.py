"""PDF -> 쪽별 텍스트.

엔진 (PROJECT.md §9):
  pymupdf    기본. §9 대체 후보. 277쪽 책자 약 1초
  pdfplumber 검증용 두 번째 엔진. 같은 책자 약 70초. 두 엔진 결과를 비교해 추출 오류를 잡는다
  docling    §9 1차 조합. 표 구조가 필요한 다음 단계(항목 분리)에서 쓴다.
             레이아웃 모델을 내려받아야 해서 이 저장소의 테스트에서는 돌리지 않는다
"""
from __future__ import annotations

import re
from pathlib import Path

ENGINES = ("pymupdf", "pdfplumber", "docling")

# 모든 쪽 위에 붙는 머리말
RUNNING_HEADER = "암환자에게 처방･투여하는 약제에 대한 요양급여의 적용기준 및 방법에 관한 세부사항"
# 쪽 옆의 세로 탭 글자 ('Ⅰ', '항', '암', '요', '법'이 한 줄씩)
_SIDE_TAB = re.compile(r"^\s*(?:Ⅰ|Ⅱ|Ⅲ|항|암|요|법|구|토|제)\s*$")
_PAGE_NO = re.compile(r"^\s*(\d{1,3})\s*$")


def extract_pages(path: str | Path, engine: str = "pymupdf") -> list[str]:
    path = Path(path)
    if engine == "pymupdf":
        import pymupdf

        with pymupdf.open(path) as doc:
            return [p.get_text() for p in doc]
    if engine == "pdfplumber":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return [p.extract_text() or "" for p in pdf.pages]
    if engine == "docling":
        return _docling_pages(path)
    raise ValueError(f"알 수 없는 엔진: {engine} (가능: {ENGINES})")


def _docling_pages(path: Path) -> list[str]:  # pragma: no cover - 로컬에서만 실행
    from docling.document_converter import DocumentConverter

    doc = DocumentConverter().convert(str(path)).document
    n = doc.num_pages()
    return [doc.export_to_markdown(page_no=i) for i in range(1, n + 1)]


def printed_page_no(raw: str) -> int | None:
    """책자에 인쇄된 쪽 번호. PyMuPDF는 첫 줄, pdfplumber는 마지막 줄에 나온다."""
    lines = [l for l in raw.splitlines() if l.strip()]
    for line in (lines[:1] + lines[-1:]):
        m = _PAGE_NO.match(line)
        if m:
            return int(m.group(1))
    return None


def clean_page(raw: str) -> str:
    """머리말, 쪽 번호, 세로 탭 글자를 지운다. 본문 글자는 건드리지 않는다."""
    lines = raw.splitlines()
    nonempty = [i for i, l in enumerate(lines) if l.strip()]
    edges = {nonempty[0], nonempty[-1]} if nonempty else set()
    out = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s == RUNNING_HEADER or _SIDE_TAB.match(line):
            continue
        if i in edges and _PAGE_NO.match(line):
            continue
        out.append(line.rstrip())
    return "\n".join(out).strip()
