"""IN-1 문서 나누기·분류 [규칙] (notes/input_module_design.md §2 IN-1).

차트 원문(비식별화 전)을 문서로 나누고 doc_type, doc_date를 붙인다. 위치는 원문 기준이라 인용 위치가 그대로 맞는다.

- 문서 시작: 머리글 줄(`[...]`, `<...>`, `■ ...`) 또는 빈 줄 2개 이상 뒤의 첫 줄 (`BONE SCAN REPORT` 같은 머리글)
- 종류: 머리글 단어 사전. 사전에 없으면 progress_note
- 날짜: medication은 null. 그 밖에는 머리글 줄의 날짜, 없으면 보고일·검사일·작성일 같은 이름 붙은 날짜, 없으면 본문 첫 날짜
"""
from __future__ import annotations

import re
from dataclasses import dataclass

HEADER = re.compile(r"^(\[[^\]]+\]|<[^>]+>|■)")
DATE = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})")
NAMED_DATE = re.compile(r"(보고일|Reported|검사일|수술일|작성일)\s*:\s*" + DATE.pattern)
# 앞에서부터 처음 맞는 종류 (분자병리를 병리보다 먼저 본다)
TYPE_WORDS = [
    ("molecular", ("분자병리", "NGS", "유전자")),
    ("pathology", ("병리", "PATHOLOGY")),
    ("medication", ("투약", "처방")),
    ("radiology", ("영상", "판독", "CT", "MRI", "PET", "BONE SCAN", "초음파")),
]


@dataclass
class Document:
    doc_id: str
    doc_type: str
    doc_date: str | None
    start: int          # 차트 원문에서 문서가 시작하는 위치
    text: str           # 문서 원문 (끝 빈 줄 제외)

    @property
    def end(self) -> int:
        return self.start + len(self.text)

    def entry(self) -> dict:
        """patient_state documents[] 항목."""
        return {"doc_id": self.doc_id, "doc_type": self.doc_type, "doc_date": self.doc_date}


def split(chart: str) -> list[Document]:
    starts, pos, blanks = [], 0, 2
    for line in chart.splitlines(keepends=True):
        s = line.strip()
        if s and (blanks >= 2 or HEADER.match(s)):
            starts.append(pos)
        blanks = 0 if s else blanks + 1
        pos += len(line)
    docs = []
    for i, start in enumerate(starts):
        text = chart[start:starts[i + 1] if i + 1 < len(starts) else len(chart)].rstrip()
        header = text.split("\n", 1)[0]
        doc_type = classify(header)
        docs.append(Document(f"D{i + 1}", doc_type, None if doc_type == "medication" else _date(header, text),
                             start, text))
    return docs


def classify(header: str) -> str:
    h = header.upper()
    for doc_type, words in TYPE_WORDS:
        if any(w.upper() in h for w in words):
            return doc_type
    return "progress_note"


def _date(header: str, text: str) -> str | None:
    m = DATE.search(header) or NAMED_DATE.search(text) or DATE.search(text)
    if not m:
        return None
    y, mo, d = (int(g) for g in m.groups()[-3:])
    return f"{y:04d}-{mo:02d}-{d:02d}"
