"""입력 모듈 진입점: 차트 원문 → patient_state (notes/input_module_design.md §1).

    ps, issues = run(chart_text, extract, patient_ref="VC-0103", created_at="2026-10-23T00:00:00+09:00")

extract는 IN-2 자리다: 문서 목록을 받아 후보 목록(src/input/candidates.py 형식)을 돌려주는 함수.
LLM 추출기를 넣거나, 시험할 때는 정답에서 만든 후보를 그대로 돌려주는 함수를 넣는다.
extract는 IN-0으로 가린 문서만 받는다. 문서 나누기와 인용 확인은 원문 기준이다 (설계 §7 결정 5).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from src.input.assemble import assemble
from src.input.classify import Document, split
from src.input.deid import identifiers, mask


def run(chart_text: str, extract: Callable[[list[Document]], list[dict]], *, patient_ref: str,
        created_at: str) -> tuple[dict, list[dict]]:
    """patient_state와 issues (인용 못 찾음, 정규화 실패, 스키마 오류)."""
    docs = split(chart_text)
    mapping = identifiers(chart_text)
    masked = [replace(d, text=mask(d.text, mapping)) for d in docs]
    return assemble(docs, extract(masked), mapping=mapping, patient_ref=patient_ref, created_at=created_at)
