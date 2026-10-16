"""사람이 직접 작성한 정답과 생성기 결과 비교.

tests/input/manual_truth/<patient_id>.json (직접 작성, 이름이 .todo.json이면 아직 작성 중이라 건너뜀)
→ 스키마 검사 → src/input/truth/tcga_truth.py 결과와 칸별 비교.

다른 칸이 나오면 셋 중 하나다: 내가 틀림 / 생성기 버그 / 규칙이 모호함 (tcga_mapping.md를 고침).
작업 안내: src/input/truth/manual_truth_worksheet.md

실행 (team_project 폴더에서): python -m pytest tests/input/test_manual_truth.py
"""
import json
from pathlib import Path

import pytest

from src.input.truth import tcga_truth as T

MANUAL = sorted(p for p in (Path(__file__).parent / "manual_truth").glob("*.json") if not p.name.endswith(".todo.json"))


def diff(a, b, path="") -> list[str]:
    """직접 작성(a)과 생성기(b)의 다른 칸 목록."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            p = f"{path}.{k}" if path else k
            if k not in b:
                out.append(f"{p}: 직접 작성에만 있음 = {json.dumps(a[k], ensure_ascii=False)}")
            elif k not in a:
                out.append(f"{p}: 생성기에만 있음 = {json.dumps(b[k], ensure_ascii=False)}")
            else:
                out += diff(a[k], b[k], p)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: 항목 수 직접 {len(a)} / 생성기 {len(b)}"]
        return [x for i, (p, q) in enumerate(zip(a, b)) for x in diff(p, q, f"{path}[{i}]")]
    if a == b:
        return []
    return [f"{path}: 직접 {json.dumps(a, ensure_ascii=False)} / 생성기 {json.dumps(b, ensure_ascii=False)}"]


@pytest.fixture(scope="module")
def rows():
    return T.load_rows().set_index("patient_id", drop=False)


@pytest.mark.skipif(not MANUAL, reason="tests/input/manual_truth/에 직접 작성한 정답(.json)이 아직 없음")
@pytest.mark.parametrize("path", MANUAL, ids=lambda p: p.stem)
def test_manual_truth_valid_and_matches_generator(path: Path, rows):
    manual = json.loads(path.read_text(encoding="utf-8"))
    errors = [f"{list(e.path)}: {e.message}" for e in T.validator().iter_errors(manual)]
    assert not errors, "스키마 오류:\n" + "\n".join(errors[:20])
    generated = T.build(rows.loc[manual["patient_ref"]])
    found = diff(manual["fields"], generated["fields"], "fields") + diff(manual["documents"], generated["documents"], "documents")
    assert not found, f"{path.stem}: 다른 칸 {len(found)}개\n" + "\n".join(found)
