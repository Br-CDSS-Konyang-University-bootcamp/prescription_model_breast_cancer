"""[4] 추천 결과 형식 검사 (PROJECT.md §15.5 출력 검증). schemas/recommendation.json으로만 검사한다."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "recommendation.json"


def _validator():
    if not hasattr(_validator, "cache"):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            _validator.cache = Draft202012Validator(json.load(fh), format_checker=Draft202012Validator.FORMAT_CHECKER)
    return _validator.cache


def validate(recommendation):
    """스키마 위반 목록. 비어 있으면 통과. 예: ['options/0/citations: [] should be non-empty']"""
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(최상위)'}: {e.message}"
            for e in sorted(_validator().iter_errors(recommendation), key=lambda e: list(e.absolute_path))]
