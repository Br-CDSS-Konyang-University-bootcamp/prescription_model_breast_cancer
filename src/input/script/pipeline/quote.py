"""인용 확인 [규칙] (notes/input_module_design.md §2 인용 확인, §7 결정 5).

LLM은 가린 문서를 보고 구절을 낸다. 구절의 가림 표시([이름1] 등)를 대응표로 되돌린 뒤 원문 문서에서 찾고,
위치는 차트 원문 기준으로 계산한다. 같은 구절이 여러 번 있으면 처음 나오는 곳.
그대로 없으면 공백·줄바꿈 차이만 허용해 다시 찾는다. 그래도 없으면 None (후보를 버리고 인용 준수율에 센다).
"""
from __future__ import annotations

import re

from src.input.script.pipeline.classify import Document


def locate(quote: str, doc: Document, mapping: dict[str, str] | None = None) -> dict | None:
    """원문 기준 source {doc_id, quote, char_start, char_end}. quote는 원문에서 잘라 온 글자."""
    for masked, original in (mapping or {}).items():
        quote = quote.replace(masked, original)
    i = doc.text.find(quote)
    if i >= 0:
        span = (i, i + len(quote))
    else:
        chars = [re.escape(ch) for ch in quote if not ch.isspace()]
        m = re.search(r"\s*".join(chars), doc.text) if chars else None
        if not m:
            return None
        span = m.span()
    return {"doc_id": doc.doc_id, "quote": doc.text[span[0]:span[1]],
            "char_start": doc.start + span[0], "char_end": doc.start + span[1]}
