"""급여 청크를 C의 공용 색인(src/rag)에 넣는다.

색인 코드는 src/rag/에만 있다 (CLAUDE.md). 여기서는 C가 src/rag/__init__.py로 내놓은 함수를 부르기만 한다.
  - replace_doc_type("reimbursement", chunks)  새 청크를 먼저 넣고(같은 chunk_id는 덮어씀) 새 목록에 없는
                                               옛 급여 점만 지운다. 넣다가 실패하면 지우기까지 가지 않아 옛 점이 남는다
  - close_indexer()                            Qdrant 로컬 폴더 잠금을 푼다
지침 점(guideline)은 건드리지 않는다. 교체 방식은 팀 결정 안건 C1에서 b(새것 먼저, C가 함수 추가)로 정했다 (2026-10-20).
replace_doc_type이 없는 예전 src/rag에서는 delete_by_doc_type → index_chunks(지운 뒤 넣기)로 대신한다.
init_collection(force_recreate=True)는 지침 점까지 지우므로 여기서 부르지 않는다.

색인이 성공하면 기록 장부(registry.db)의 그 책자를 indexed로, 예전에 indexed였던 책자를 superseded로 바꾼다.

색인 주기 (회의 5 결정, 2026-10-21): 바뀌었을 때만 색인한다. 앱 시작 때 파이프라인(게시판 확인)을 돌리고,
색인할 청크가 마지막 색인 때와 다르면(신설·변경·삭제, 조건 수정 등) 이어서 색인한다. 같으면 하지 않는다.
DB도 함께 본다 (db_marker): DB를 새로 만들었거나 다른 폴더로 옮겼으면 청크가 같아도 다시 색인한다.
색인하는 1~2분 동안 검색이 막히므로 앱 시작 직후, 검색 전에 끝낸다. 검색과 색인은 src/rag의 Qdrant 연결
하나를 같이 쓰므로 같은 프로그램 안에서는 따로 닫지 않는다 (close_searcher를 부르면 진행 중인 검색이 끊길 수 있다).
앱이 켜져 있을 때 다른 프로그램(터미널 등)에서 색인을 따로 돌리지 않는다.

실행: python -m src.reimbursement.index              (기본: chunks/reimbursement_chunks_current.jsonl)
      python -m src.reimbursement.index --if-changed (마지막 색인 때와 같으면 건너뜀)
      python -m src.reimbursement.index --dry-run    (색인 없이 넣을 청크만 센다)
      python -m src.reimbursement.pipeline --index   (파이프라인이 정상이면 이어서 --if-changed 색인)
Qdrant 로컬 모드는 한 프로세스만 폴더를 열 수 있다. 검색(B)이나 run_indexing(C)과 동시에 돌리지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .chunks import DATA, check_chunks

DOC_TYPE = "reimbursement"
CURRENT = DATA / "chunks" / "reimbursement_chunks_current.jsonl"
STAMP = DATA / "reports" / "last_indexed.json"      # 마지막으로 색인한 청크의 해시와 DB (바뀌었을 때만 색인)
QDRANT_DIR = DATA.parent / "qdrant_db"              # 공용 색인 폴더 (CLAUDE.md, C). 파일만 보고 열지는 않는다
REPLACE = "replace_doc_type"                       # 새것 먼저 넣고 옛것만 지움 (C1 결정)
FALLBACK = ("index_chunks", "delete_by_doc_type")  # 예전 src/rag: 지운 뒤 넣기
L3_KINDS = ("reimbursement_condition", "offlabel_regimen")


class RagNotReady(RuntimeError):
    """C의 색인 함수를 부를 수 없음 (패키지 없음 또는 함수 없음)."""


@dataclass
class IndexReport:
    indexed: int = 0
    skipped: Counter = field(default_factory=Counter)   # 이유 -> 개수
    dry_run: bool = False
    removed: int | None = None       # replace_doc_type이 지운 옛 급여 점 수 (예전 방식이면 None)


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def select_for_index(chunks: list[dict], include_preview: bool = False) -> tuple[list[dict], Counter]:
    """색인할 청크와 뺀 이유.

    설계 문서 §0.1: 벡터는 L3 요법 행만 만든다. L1(원칙)·L2(소단원) 청크는 색인하지 않고, 판정할 때
    parent_id로 청크 파일에서 찾아 붙인다 (STEP 5). 검토중(preview) 요법은 판정에 쓰지 않으므로 기본으로 뺀다.
    """
    keep, skipped = [], Counter()
    for c in chunks:
        if c.get("doc_type") != DOC_TYPE:
            skipped["doc_type이 reimbursement가 아님"] += 1
        elif c["chunk_kind"] not in L3_KINDS:
            skipped["L1·L2 청크 (부모 문맥, 색인 안 함)"] += 1
        elif c["reimbursement"]["source_type"] == "preview" and not include_preview:
            skipped["검토중(preview)"] += 1
        else:
            keep.append(c)
    return keep, skipped


def load_rag() -> ModuleType:
    """C의 공개 함수 묶음 (src/rag/__init__.py). 내부 모듈(indexer 등)은 직접 고르지 않는다."""
    try:
        import src.rag as rag
    except ImportError as e:                      # qdrant_client·sentence_transformers 미설치 포함
        raise RagNotReady(f"src.rag를 불러오지 못함: {e}") from e
    return rag


def _close(rag: ModuleType) -> None:
    """Qdrant 로컬 폴더 잠금을 푼다 (공개 함수 close_indexer)."""
    close = getattr(rag, "close_indexer", None)
    if callable(close):
        close()


def digest(rows: list[dict]) -> str:
    """색인할 청크 목록의 해시. 내용이 하나라도 바뀌면 달라진다."""
    text = json.dumps(sorted(rows, key=lambda c: c["chunk_id"]), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def db_marker(qdrant_dir: Path = QDRANT_DIR) -> str | None:
    """색인한 DB를 가리키는 값: 폴더 경로 + meta.json 수정 시각. Qdrant 로컬 모드는 컬렉션을 만들거나 지울 때만
    meta.json을 고치므로, DB를 새로 만들었거나(다른 폴더로 옮김 포함) 컬렉션을 다시 만들면 값이 바뀐다.
    청크 해시만 보면 청크 파일을 다른 폴더로 복사했을 때 빈 DB인데도 '같음'으로 건너뛴다."""
    meta = qdrant_dir / "meta.json"
    try:
        return f"{qdrant_dir.resolve()}|{meta.stat().st_mtime_ns}"
    except FileNotFoundError:
        return None


def last_stamp(stamp: Path) -> dict:
    try:
        return json.loads(stamp.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def missing_functions(rag: ModuleType) -> list[str]:
    """replace_doc_type이 있으면 그것만, 없으면 예전 두 함수가 모두 있어야 한다."""
    if callable(getattr(rag, REPLACE, None)):
        return []
    return [n for n in FALLBACK if not callable(getattr(rag, n, None))]


def index_reimbursement(chunks: list[dict], rag: ModuleType | None = None, *,
                        include_preview: bool = False, dry_run: bool = False,
                        registry=None, stamp: Path | None = None, qdrant_dir: Path = QDRANT_DIR) -> IndexReport:
    """registry: 주면 성공한 뒤 청크의 책자(version = 책자 날짜)를 장부에 indexed로 표시한다.
    stamp: 주면 성공한 뒤 색인한 청크의 해시를 남긴다 (index_if_changed가 비교)."""
    errors = check_chunks(chunks)
    if errors:
        raise ValueError("청크 스키마 오류로 색인하지 않음:\n" + "\n".join(errors[:20]))
    rows, skipped = select_for_index(chunks, include_preview)
    if not rows:
        raise ValueError("색인할 급여 청크가 없음")
    report = IndexReport(len(rows), skipped, dry_run)
    if dry_run:
        return report

    rag = rag or load_rag()
    missing = missing_functions(rag)
    if missing:
        raise RagNotReady(
            "src/rag 공개 함수에 다음이 없어 색인하지 않음: " + ", ".join(missing)
            + ". 예전 급여 점을 지우지 못하면 새 책자를 넣을 때 옛 기준이 검색에 남는다.")
    try:
        if callable(getattr(rag, REPLACE, None)):
            result = rag.replace_doc_type(DOC_TYPE, rows) or {}   # 지침 점(guideline)은 건드리지 않는다
            report.removed = result.get("removed")
        else:
            rag.delete_by_doc_type(DOC_TYPE)
            rag.index_chunks(rows)
    finally:
        _close(rag)
    if registry is not None:
        versions = {c["version"] for c in rows if c["source"] == "HIRA-booklet"}
        for v in versions:
            registry.mark_indexed("booklet", v)
    if stamp is not None:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(json.dumps({"digest": digest(rows), "db": db_marker(qdrant_dir), "indexed": len(rows),
                                     "at": datetime.now().isoformat(timespec="seconds")},
                                    ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def index_if_changed(chunks: list[dict], rag: ModuleType | None = None, *, include_preview: bool = False,
                     registry=None, stamp: Path = STAMP, qdrant_dir: Path = QDRANT_DIR) -> IndexReport | None:
    """색인할 청크와 DB가 마지막 색인 때와 같으면 None (색인 안 함, 검색 DB도 잠그지 않음). 하나라도 다르면 색인한다."""
    rows, _ = select_for_index(chunks, include_preview)
    last = last_stamp(stamp)
    if rows and digest(rows) == last.get("digest") and last.get("db") and db_marker(qdrant_dir) == last["db"]:
        return None
    return index_reimbursement(chunks, rag, include_preview=include_preview, registry=registry, stamp=stamp,
                               qdrant_dir=qdrant_dir)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="급여 청크를 공용 색인(src/rag)에 넣는다")
    ap.add_argument("--chunks", type=Path, default=CURRENT)
    ap.add_argument("--include-preview", action="store_true", help="검토중 허가초과 요법도 넣는다")
    ap.add_argument("--dry-run", action="store_true", help="색인하지 않고 넣을 청크만 센다")
    ap.add_argument("--if-changed", action="store_true", help="마지막 색인 때와 청크가 같으면 건너뛴다")
    ap.add_argument("--db", type=Path, default=DATA / "registry.db", help="성공하면 indexed로 표시할 기록 장부")
    args = ap.parse_args(argv)
    return run_index(args.chunks, args.db, include_preview=args.include_preview, dry_run=args.dry_run,
                     if_changed=args.if_changed)


def run_index(chunks_path: Path = CURRENT, db: Path = DATA / "registry.db", *, include_preview: bool = False,
              dry_run: bool = False, if_changed: bool = False) -> int:
    """CLI와 pipeline --index가 같이 쓴다. 0 = 색인했거나 바뀐 게 없어 건너뜀, 1 = 색인 못 함."""
    from .registry import Registry
    reg = None if dry_run else Registry(db)
    try:
        chunks = load_jsonl(chunks_path)
        if if_changed and not dry_run:
            rep = index_if_changed(chunks, include_preview=include_preview, registry=reg)
            if rep is None:
                print("색인 안 함: 마지막 색인 때와 급여 청크가 같음")
                return 0
        else:
            rep = index_reimbursement(chunks, include_preview=include_preview, dry_run=dry_run, registry=reg,
                                      stamp=None if dry_run else STAMP)
    except (RagNotReady, ValueError, FileNotFoundError) as e:
        print(f"[색인 안 함] {e}", file=sys.stderr)
        return 1
    finally:
        if reg is not None:
            reg.close()
    what = "넣을" if rep.dry_run else "넣은"
    print(f"{what} 급여 청크 {rep.indexed}개" +
          (f", 지운 옛 급여 점 {rep.removed}개" if rep.removed is not None else "") +
          "".join(f", 뺀 청크 {n}개 ({why})" for why, n in rep.skipped.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
