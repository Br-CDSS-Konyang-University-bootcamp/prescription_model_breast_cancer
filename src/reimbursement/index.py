"""급여 청크를 C의 공용 색인(src/rag)에 넣는다.

색인 코드는 src/rag/에만 있다 (CLAUDE.md). 여기서는 C가 src/rag/__init__.py로 내놓은 함수를 부르기만 한다.
  - index_chunks(chunks)            있음 (2026-10-17 공개: index_chunks, init_collection, search_guidelines)
  - delete_by_doc_type(doc_type)    C에 요청함, 아직 없음

색인이 성공하면 기록 장부(registry.db)의 그 책자를 indexed로, 예전에 indexed였던 책자를 superseded로 바꾼다.

새 책자가 나오면 예전 급여 점을 지운 뒤 새 청크를 넣어야 한다. 지금 index_chunks는 점 ID를 uuid4로 만들어
같은 청크를 다시 넣으면 중복이 쌓이므로, 지우는 함수가 없으면 색인하지 않고 멈춘다.

실행: python -m src.reimbursement.index            (기본: chunks/reimbursement_chunks_current.jsonl)
      python -m src.reimbursement.index --dry-run  (색인 없이 넣을 청크만 센다)
Qdrant 로컬 모드는 한 프로세스만 폴더를 열 수 있다. 검색(B)이나 run_indexing(C)과 동시에 돌리지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from .chunks import DATA, check_chunks

DOC_TYPE = "reimbursement"
CURRENT = DATA / "chunks" / "reimbursement_chunks_current.jsonl"
REQUIRED = ("index_chunks", "delete_by_doc_type")
L3_KINDS = ("reimbursement_condition", "offlabel_regimen")


class RagNotReady(RuntimeError):
    """C의 색인 함수를 부를 수 없음 (패키지 없음 또는 함수 없음)."""


@dataclass
class IndexReport:
    indexed: int = 0
    skipped: Counter = field(default_factory=Counter)   # 이유 -> 개수
    dry_run: bool = False


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
    """Qdrant 로컬 폴더 잠금을 푼다. 공개 함수에 없으면 indexer의 close_indexer를 쓴다."""
    close = getattr(rag, "close_indexer", None)
    if close is None:
        close = getattr(getattr(rag, "indexer", None), "close_indexer", None)
    if callable(close):
        close()


def missing_functions(rag: ModuleType) -> list[str]:
    return [n for n in REQUIRED if not callable(getattr(rag, n, None))]


def index_reimbursement(chunks: list[dict], rag: ModuleType | None = None, *,
                        include_preview: bool = False, dry_run: bool = False,
                        registry=None) -> IndexReport:
    """registry: 주면 성공한 뒤 청크의 책자(version = 책자 날짜)를 장부에 indexed로 표시한다."""
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
            "C의 src/rag/indexer.py에 다음 함수가 없어 색인하지 않음: " + ", ".join(missing)
            + ". 예전 급여 점을 지우지 못하면 새 책자를 넣을 때 옛 기준이 검색에 남는다.")
    try:
        rag.delete_by_doc_type(DOC_TYPE)          # 지침 점(guideline)은 건드리지 않는다
        rag.index_chunks(rows)
    finally:
        _close(rag)
    if registry is not None:
        versions = {c["version"] for c in rows if c["source"] == "HIRA-booklet"}
        for v in versions:
            registry.mark_indexed("booklet", v)
    return report


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="급여 청크를 공용 색인(src/rag)에 넣는다")
    ap.add_argument("--chunks", type=Path, default=CURRENT)
    ap.add_argument("--include-preview", action="store_true", help="검토중 허가초과 요법도 넣는다")
    ap.add_argument("--dry-run", action="store_true", help="색인하지 않고 넣을 청크만 센다")
    ap.add_argument("--db", type=Path, default=DATA / "registry.db", help="성공하면 indexed로 표시할 기록 장부")
    args = ap.parse_args(argv)

    from .registry import Registry
    reg = None if args.dry_run else Registry(args.db)
    try:
        rep = index_reimbursement(load_jsonl(args.chunks), include_preview=args.include_preview,
                                  dry_run=args.dry_run, registry=reg)
    except (RagNotReady, ValueError, FileNotFoundError) as e:
        print(f"[색인 안 함] {e}", file=sys.stderr)
        return 1
    finally:
        if reg is not None:
            reg.close()
    what = "넣을" if rep.dry_run else "넣은"
    print(f"{what} 급여 청크 {rep.indexed}개" +
          "".join(f", 뺀 청크 {n}개 ({why})" for why, n in rep.skipped.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
