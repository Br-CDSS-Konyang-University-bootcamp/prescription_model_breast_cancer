"""SQLite 레지스트리.

documents: 내려받은 문서 (책자, 허가초과 목록, 공고, 공고예고)
criteria : 급여 기준 항목의 버전 기록. effective_from ~ effective_to 로 유효 기간을 관리한다.
           effective_to 가 NULL 이면 지금 유효한 항목이다.
           이 기간은 D 안에서만 쓰고, C의 색인에는 '오늘 유효한 항목'만 넣는다.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .dates import KST

SOURCES = ("booklet", "offlabel", "notice", "preview")
STATUSES = ("downloaded", "parsed", "indexed", "failed", "superseded")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY,
    source         TEXT NOT NULL CHECK (source IN ('booklet','offlabel','notice','preview')),
    doc_no         TEXT,            -- 2026-210
    board_id       TEXT,            -- brdBltNo=45661
    title          TEXT,
    posted_date    TEXT,            -- ISO 날짜
    effective_date TEXT,            -- 시행일 (책자는 파일명 날짜)
    period_end     TEXT,            -- 공고예고 의견조회 마감일
    file_name      TEXT,
    file_hash      TEXT,
    status         TEXT NOT NULL DEFAULT 'downloaded'
                   CHECK (status IN ('downloaded','parsed','indexed','failed','superseded')),
    first_seen_at  TEXT NOT NULL,   -- 가정 검증용: 책자를 처음 본 시각 (KST)
    updated_at     TEXT NOT NULL,
    note           TEXT,
    validation_json TEXT,           -- validate.Report.to_dict() 결과
    UNIQUE (source, file_hash)
);
CREATE TABLE IF NOT EXISTS criteria (
    id             INTEGER PRIMARY KEY,
    item_key       TEXT NOT NULL,   -- 같은 항목을 판별하는 키 (예: breast|palliative|2L+|regimen)
    text           TEXT NOT NULL,   -- 원문 그대로
    content_hash   TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to   TEXT,            -- NULL = 현재 유효
    source_doc_id  INTEGER NOT NULL REFERENCES documents(id),
    source_page    INTEGER,
    meta_json      TEXT,            -- 구조화 결과 (약제, 투여단계, 조건 등)
    chunk_id       TEXT,            -- C의 색인에 넣었을 때의 id
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_criteria_key ON criteria(item_key);
CREATE INDEX IF NOT EXISTS idx_criteria_active ON criteria(effective_to);
"""


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _hash(text: str) -> str:
    # 공백 차이(줄바꿈 위치 등)로 '변경'이 잡히지 않게 공백을 지우고 비교한다
    return hashlib.sha256("".join(text.split()).encode()).hexdigest()


@dataclass
class CriterionItem:
    """책자에서 뽑은 기준 항목 하나."""
    item_key: str
    text: str
    effective_from: date | None = None   # 항목 변경 표시의 마지막 날짜. 없으면 책자 날짜
    source_page: int | None = None
    meta_json: str | None = None


@dataclass
class Diff:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.changed or self.removed)


class Registry:
    def __init__(self, db_path: str | Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---------- documents ----------

    def add_document(self, source: str, *, file_hash: str | None = None, **fields) -> int:
        """문서를 등록한다. 같은 (source, file_hash)가 있으면 기존 id를 돌려준다."""
        if source not in SOURCES:
            raise ValueError(source)
        if file_hash:
            row = self.conn.execute(
                "SELECT id FROM documents WHERE source=? AND file_hash=?", (source, file_hash)
            ).fetchone()
            if row:
                return row["id"]
        fields = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()}
        cols = ["source", "file_hash", "first_seen_at", "updated_at", *fields]
        vals = [source, file_hash, _now(), _now(), *fields.values()]
        cur = self.conn.execute(
            f"INSERT INTO documents ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals
        )
        self.conn.commit()
        return cur.lastrowid

    def update_document(self, doc_id: int, **fields) -> None:
        allowed = {"doc_no", "board_id", "title", "posted_date", "effective_date", "period_end", "note"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"바꿀 수 없는 필드: {bad}")
        fields = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in fields.items()}
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE documents SET {sets}, updated_at=? WHERE id=?",
                          (*fields.values(), _now(), doc_id))
        self.conn.commit()

    def set_status(self, doc_id: int, status: str, note: str | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(status)
        self.conn.execute(
            "UPDATE documents SET status=?, note=COALESCE(?, note), updated_at=? WHERE id=?",
            (status, note, _now(), doc_id),
        )
        self.conn.commit()

    def save_validation(self, doc_id: int, report: dict) -> None:
        """검증 결과를 저장하고, 오류가 있으면 failed로 표시한다 (§8 처리 흐름 9)."""
        status = "parsed" if report.get("ok") else "failed"
        self.conn.execute(
            "UPDATE documents SET validation_json=?, status=?, updated_at=? WHERE id=?",
            (json.dumps(report, ensure_ascii=False), status, _now(), doc_id),
        )
        self.conn.commit()

    def last_good_booklet(self, exclude_hash: str | None = None) -> sqlite3.Row | None:
        """검증을 통과한(parsed 또는 indexed) 가장 최근 책자. 새 책자와 대조할 때 쓴다."""
        return self.last_good("booklet", exclude_hash)

    def last_good(self, source: str, exclude_hash: str | None = None) -> sqlite3.Row | None:
        """그 source에서 검증을 통과한(parsed 또는 indexed) 가장 최근 문서."""
        return self.conn.execute(
            "SELECT * FROM documents WHERE source=? AND status IN ('parsed','indexed') "
            "AND (? IS NULL OR file_hash != ?) ORDER BY effective_date DESC LIMIT 1",
            (source, exclude_hash, exclude_hash),
        ).fetchone()

    def mark_indexed(self, source: str, effective_date: str) -> int | None:
        """공용 색인에 넣은 문서를 indexed로, 같은 source의 예전 indexed 문서를 superseded로 바꾼다.
        effective_date(책자 날짜)가 같은 문서 중 검증을 통과한 가장 최근 것. 없으면 None."""
        row = self.conn.execute(
            "SELECT id FROM documents WHERE source=? AND effective_date=? AND status IN ('parsed','indexed') "
            "ORDER BY id DESC LIMIT 1", (source, effective_date)).fetchone()
        if row is None:
            return None
        with self.conn:
            self.conn.execute(
                "UPDATE documents SET status='superseded', updated_at=? WHERE source=? AND status='indexed' AND id != ?",
                (_now(), source, row["id"]))
            self.conn.execute("UPDATE documents SET status='indexed', updated_at=? WHERE id=?", (_now(), row["id"]))
        return row["id"]

    def current_booklet(self) -> sqlite3.Row | None:
        """마지막으로 정상 반영(indexed)된 책자. 실패 시 이 버전을 계속 쓴다."""
        return self.conn.execute(
            "SELECT * FROM documents WHERE source='booklet' AND status='indexed' "
            "ORDER BY effective_date DESC LIMIT 1"
        ).fetchone()

    def latest_document(self, source: str) -> sqlite3.Row | None:
        """그 source에서 파일명 날짜(effective_date)가 가장 늦은 문서. 실패한 문서는 뺀다."""
        return self.conn.execute(
            "SELECT * FROM documents WHERE source=? AND status != 'failed' "
            "ORDER BY effective_date DESC, id DESC LIMIT 1", (source,)
        ).fetchone()

    def has_board_id(self, source: str, board_id: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM documents WHERE source=? AND board_id=?", (source, board_id)
        ).fetchone() is not None

    def booklet_lag_report(self) -> list[sqlite3.Row]:
        """가정 검증: 책자 파일명 날짜와 처음 본 날짜를 나란히 본다."""
        return self.conn.execute(
            "SELECT file_name, effective_date, first_seen_at, doc_no, status FROM documents "
            "WHERE source='booklet' ORDER BY effective_date"
        ).fetchall()

    # ---------- criteria ----------

    def apply_booklet(self, doc_id: int, booklet_date: date,
                      items: list[CriterionItem]) -> Diff:
        """새 책자(또는 허가초과 목록)의 항목 목록을 반영하고 신설·변경·삭제 목록을 만든다 (한 트랜잭션).

        비교 대상은 doc_id와 같은 source의 현재 항목뿐이다. 허가초과 목록을 반영해도
        책자 항목이 '삭제'로 잡히지 않는다.
        """
        diff = Diff()
        active = {r["item_key"]: r for r in self.conn.execute(
            "SELECT c.* FROM criteria c JOIN documents d ON d.id = c.source_doc_id "
            "WHERE c.effective_to IS NULL "
            "AND d.source = (SELECT source FROM documents WHERE id = ?)", (doc_id,))}
        seen: set[str] = set()
        with self.conn:
            for it in items:
                if it.item_key in seen:
                    raise ValueError(f"item_key 중복: {it.item_key}")
                seen.add(it.item_key)
                h = _hash(it.text)
                old = active.get(it.item_key)
                if old is not None and old["content_hash"] == h:
                    continue
                start = it.effective_from or booklet_date
                if old is not None:
                    # 변경 표시가 이전 버전보다 앞서면(표시 누락 등) 책자 날짜를 쓴다
                    if start.isoformat() <= old["effective_from"]:
                        start = booklet_date
                    self.conn.execute("UPDATE criteria SET effective_to=? WHERE id=?",
                                      (start.isoformat(), old["id"]))
                    diff.changed.append(it.item_key)
                else:
                    diff.added.append(it.item_key)
                self.conn.execute(
                    "INSERT INTO criteria (item_key, text, content_hash, effective_from,"
                    " source_doc_id, source_page, meta_json, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (it.item_key, it.text, h, start.isoformat(), doc_id,
                     it.source_page, it.meta_json, _now()),
                )
            for key, old in active.items():
                if key not in seen:
                    self.conn.execute("UPDATE criteria SET effective_to=? WHERE id=?",
                                      (booklet_date.isoformat(), old["id"]))
                    diff.removed.append(key)
        return diff

    def active_on(self, day: date) -> list[sqlite3.Row]:
        """그 날짜에 유효했던 항목. 오늘 날짜를 넣으면 색인에 넣을 항목이 된다."""
        d = day.isoformat()
        return self.conn.execute(
            "SELECT * FROM criteria WHERE effective_from <= ? "
            "AND (effective_to IS NULL OR effective_to > ?) ORDER BY item_key",
            (d, d),
        ).fetchall()
