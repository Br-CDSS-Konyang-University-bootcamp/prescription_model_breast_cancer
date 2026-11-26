"""화면 1 확정값(confirmed_state)을 저장하는 곳. 형식은 schemas/confirmed_state.json 그대로, 버전을 쌓고 덮어쓰지 않는다.

- FileStore: <save_dir>/<patient_ref>/v<n>.json (원래 방식, confirmed.finalize). 입력값 표시는 v<n>.input.txt
- DbStore: 병원 기록 DB (SQLite 한 파일). 실제 병원처럼 확정값을 EMR DB에 다시 써 넣는 그림이라 파일을 남기지 않는다.
  가상 병원 DB(db build가 매번 새로 만듦)와 따로 둬서 다시 만들어도 확정 기록은 지워지지 않는다

두 곳 모두 버전마다 어느 입력값(answer 정답 / llm 입력 모듈)으로 확정했는지 남긴다. 화면 2 추천은 그 입력값의
patient_state를 쓴다 (주소의 input 값보다 앞선다).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from src.input.script import confirmed as c

INPUTS = ("answer", "llm")
SCHEMA = """
CREATE TABLE IF NOT EXISTS confirmed_states (
  patient_ref TEXT NOT NULL,
  version INTEGER NOT NULL,
  confirmed_by TEXT NOT NULL,          -- 확정자 가명 ID
  confirmed_at TEXT NOT NULL,
  input TEXT,                          -- answer (정답 patient_state) / llm (입력 모듈이 만든 것)
  json TEXT NOT NULL,                  -- schemas/confirmed_state.json 문서
  PRIMARY KEY (patient_ref, version)   -- 같은 버전은 다시 쓰지 않는다 (덮어쓰기 없음)
);
"""


def _check_input(input: str | None) -> None:
    if input is not None and input not in INPUTS:
        raise ValueError(f"입력값은 {INPUTS} 중 하나: {input}")


class FileStore:
    kind = "files"

    def __init__(self, save_dir: Path):
        self.save_dir = save_dir

    def versions(self, ref: str) -> list[int]:
        return [int(p.stem[1:]) for p in c._versions(ref, self.save_dir)]

    def load(self, ref: str, version: int) -> dict:
        p = self.save_dir / ref / f"v{version}.json"
        if not p.exists():
            raise KeyError(f"확정 파일 없음: {ref} v{version}")
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def input_of(self, ref: str, version: int) -> str | None:
        p = self.save_dir / ref / f"v{version}.input.txt"
        return p.read_text(encoding="utf-8").strip() if p.exists() else None

    def finalize(self, draft: dict, by: str, input: str | None = None) -> tuple[str | None, dict, list[str]]:
        _check_input(input)
        path, doc, errors = c.finalize(draft, by, save_dir=self.save_dir)
        if path and input:
            path.with_suffix(".input.txt").write_text(input, encoding="utf-8")
        return (str(path) if path else None), doc, errors


class DbStore:
    kind = "records_db"

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as con:
            con.executescript(SCHEMA)

    def _con(self):
        return closing(sqlite3.connect(self.path))

    def versions(self, ref: str) -> list[int]:
        with self._con() as con:
            return [r[0] for r in con.execute(
                "SELECT version FROM confirmed_states WHERE patient_ref = ? ORDER BY version", (ref,))]

    def load(self, ref: str, version: int) -> dict:
        with self._con() as con:
            r = con.execute("SELECT json FROM confirmed_states WHERE patient_ref = ? AND version = ?",
                            (ref, version)).fetchone()
        if r is None:
            raise KeyError(f"확정 기록 없음: {ref} v{version}")
        return json.loads(r[0])

    def input_of(self, ref: str, version: int) -> str | None:
        with self._con() as con:
            r = con.execute("SELECT input FROM confirmed_states WHERE patient_ref = ? AND version = ?",
                            (ref, version)).fetchone()
        return r[0] if r else None

    def finalize(self, draft: dict, by: str, input: str | None = None) -> tuple[str | None, dict, list[str]]:
        """confirmed.next_version으로 다음 버전을 만들어 한 거래 안에 넣는다 (같은 버전이 이미 있으면 실패)."""
        _check_input(input)
        ref = draft["patient_ref"]
        with self._con() as con, con:
            r = con.execute("SELECT json FROM confirmed_states WHERE patient_ref = ? ORDER BY version DESC LIMIT 1",
                            (ref,)).fetchone()
            doc, errors = c.next_version(draft, by, last=json.loads(r[0]) if r else None)
            if errors:
                return None, doc, errors
            con.execute("INSERT INTO confirmed_states VALUES (?,?,?,?,?,?)",
                        (ref, doc["version"], doc["confirmed_by"], doc["confirmed_at"], input,
                         json.dumps(doc, ensure_ascii=False)))
        return f"{self.path.name}: {ref} v{doc['version']}", doc, []
