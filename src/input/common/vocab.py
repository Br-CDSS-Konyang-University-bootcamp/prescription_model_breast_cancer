"""표준값 사전 (data/dictionaries/field_vocab.csv).

같은 뜻의 표현을 필드별 표준값 하나로 바꾼다. TCGA 정답 생성기와 입력 모듈의 정규화(IN-3)가 같은 사전을 쓴다.
비교할 때는 앞뒤 공백을 지우고, 연속 공백을 하나로 줄이고, 대소문자를 무시한다.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

VOCAB_CSV = Path(__file__).resolve().parents[3] / "data" / "dictionaries" / "field_vocab.csv"


class UnknownExpression(KeyError):
    """사전에 없는 표현. 정답 생성기는 이 오류로 멈춘다 (사전에 표현을 추가할 것)."""


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip()).casefold()


class Vocab:
    def __init__(self, path: Path = VOCAB_CSV):
        self.path = Path(path)
        self._map: dict[str, dict[str, str]] = defaultdict(dict)
        self._expressions: dict[tuple[str, str], list[str]] = defaultdict(list)
        with open(self.path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                field, canonical, expr = row["field"].strip(), row["canonical"].strip(), row["expression"]
                old = self._map[field].get(_key(expr))
                if old is not None and old != canonical:
                    raise ValueError(f"{self.path.name}: {field} '{expr}'가 {old}와 {canonical} 두 값에 대응됨")
                self._map[field][_key(expr)] = canonical
                self._expressions[(field, canonical)].append(expr)

    def lookup(self, field: str, expression: str, strict: bool = True) -> str | None:
        """표현 → 표준값. strict이면 사전에 없을 때 UnknownExpression, 아니면 None."""
        if field not in self._map:
            raise KeyError(f"사전에 없는 필드: {field}")
        canonical = self._map[field].get(_key(expression))
        if canonical is None and strict:
            raise UnknownExpression(f"{self.path.name}에 없는 표현: {field} = '{expression}'")
        return canonical

    def mapping(self, field: str) -> dict[str, str]:
        """필드의 {정규화된 표현: 표준값} 사본."""
        return dict(self._map[field])

    def canonical_values(self, field: str) -> list[str]:
        return sorted(set(self._map[field].values()))

    def expressions(self, field: str, canonical: str) -> list[str]:
        """표준값 하나에 대응하는 표현들 (가상 차트 생성, LLM 프롬프트 예시용)."""
        return list(self._expressions[(field, canonical)])
