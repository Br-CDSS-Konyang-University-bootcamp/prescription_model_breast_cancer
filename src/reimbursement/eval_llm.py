"""조건 구조화용 로컬 모델 비교 (PROJECT.md §14 '급여 조건 구조화용 로컬 LLM 선정').

지금 저장본의 조건(사람이 쓰고 검수한 131행)을 기준으로, 로컬 모델이 같은 행에서 만든 조건을 비교한다.
저장본·청크는 바꾸지 않는다. 결과는 data/reimbursement/reports/llm_eval_<모델>.json (공고 원문 없이 행 이름과 숫자만).

    python -m src.reimbursement.eval_llm --model qwen3:32b                  # 조건이 있는 행 전부
    python -m src.reimbursement.eval_llm --model qwen3:32b --limit 20       # 앞 20행만 (빨리 보기)

모델 서버는 REIMB_OLLAMA_HOST (기본 http://127.0.0.1:11500, GPU 서버를 SSH 터널로 연 주소).

재는 것
  검사 통과   형식·어휘·원문 구절 검사(파이프라인과 같은 검사)를 통과한 행 비율. 실패한 행은 파이프라인에서 버려진다
  항목 일치   (field, op, value, of)를 묶음 위치(all_of / any_of / 예외 / stage_rules / unless)와 함께 비교한 정밀도·재현율
  완전 일치   글(text)·id를 뺀 조건 구조가 저장본과 똑같은 행 비율
  시간       행당 걸린 초
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from .booklet import load_booklet
from .chunks import booklet_chunks
from .conditions import (DATA, TARGET_KINDS, OllamaStructurer, check_grounding, check_schema, check_values,
                         iter_items)
from .pipeline import _latest_local

REPORTS = DATA / "reports"


def _key(where: str, it: dict) -> str:
    """항목을 비교할 열쇠: 묶음 위치(번호 없이) + field·op·value·of. 글과 id는 모델마다 달라도 된다."""
    place = re.sub(r"\[\d+\]", "", where)
    value = sorted(it["value"], key=str) if isinstance(it.get("value"), list) else it.get("value")
    of = {k: sorted(v) for k, v in (it.get("of") or {}).items()}
    return json.dumps([place, it.get("field"), it.get("op"), value, of], ensure_ascii=False, sort_keys=True)


def item_keys(cond: dict) -> list[str]:
    keys = []
    for where, it in iter_items(cond):
        keys.append(_key(where, it))
        if it.get("unless"):
            keys.append(_key(where + ".unless", it["unless"]))
    for g in cond.get("counts_as_prior_line") or []:
        keys.append(json.dumps(["counts_as_prior_line", sorted(g.get("setting") or []), sorted(g.get("drugs") or []),
                                g.get("within_days"), g.get("rule_id")], ensure_ascii=False))
    return sorted(keys)


def _skeleton(cond: dict) -> dict:
    """완전 일치 비교용: 항목 열쇠와 판정에 쓰지 않는 칸(notes 등)이 비었는지만 남긴다."""
    return {"items": item_keys(cond),
            **{k: bool(cond.get(k)) for k in ("human_review", "unmapped")}}


def compare(ref: dict, got: dict) -> dict:
    a, b = item_keys(ref), item_keys(got)
    common = sum(min(a.count(k), b.count(k)) for k in set(a))
    return {"ref_items": len(a), "got_items": len(b), "common": common,
            "exact": _skeleton(ref) == _skeleton(got)}


def run(model: str, limit: int | None = None, ids: list[str] | None = None) -> dict:
    booklet = _latest_local(DATA / "raw", "공고책자_*.pdf")
    bc = booklet_chunks(load_booklet(booklet, DATA / "cache"))
    current = {c["chunk_id"]: c for c in map(json.loads, open(DATA / "chunks" / "reimbursement_chunks_current.jsonl",
                                                                   encoding="utf-8"))}
    rows = [c for c in bc.chunks if c["chunk_kind"] in TARGET_KINDS
            and (current.get(c["chunk_id"], {}).get("reimbursement", {}).get("conditions") or {}).keys() - {"line_rule"}]
    if ids:
        rows = [c for c in rows if any(c["chunk_id"].endswith(i) for i in ids)]
    rows = rows[:limit] if limit else rows
    s = OllamaStructurer(model=model)
    results = []
    for n, c in enumerate(rows, 1):
        cid, ctx = c["chunk_id"], bc.contexts.get(c["chunk_id"], "")
        ref = {k: v for k, v in current[cid]["reimbursement"]["conditions"].items() if k != "line_rule"}
        t0 = time.time()
        try:
            got, _ = s(c["text"], ctx)
            err = None
        except Exception as e:          # 한 행 실패로 멈추지 않는다 (스키마 재시도 실패, 시간 초과 등)
            got, err = None, f"{type(e).__name__}: {str(e)[:200]}"
        sec = round(time.time() - t0, 1)
        r = {"chunk_id": cid, "seconds": sec, "error": err}
        if got is not None:
            problems = check_schema(got) + check_values(got) + check_grounding(got, f"{ctx}\n{c['text']}")
            # 원문 구절은 공고 글이라 보고서에 넣지 않고 어느 칸에서 걸렸는지만 남긴다
            r.update(passed=not problems, problems=[p.split(":")[0] for p in problems], **compare(ref, got))
        results.append(r)
        print(f"[{n}/{len(rows)}] {cid.split('-', 3)[3]}: {sec}s "
              + (r["error"] or f"검사 {'통과' if r['passed'] else '실패'}, 항목 {r['common']}/{r['ref_items']} 일치"
                 f"{' (완전 일치)' if r['exact'] else ''}"), flush=True)
    ok = [r for r in results if r.get("error") is None]
    ref_n, got_n, common = (sum(r[k] for r in ok) for k in ("ref_items", "got_items", "common"))
    summary = {
        "model": model, "booklet": booklet.name, "rows": len(results),
        "errors": len(results) - len(ok),
        "passed": sum(r["passed"] for r in ok),
        "exact": sum(r["exact"] for r in ok),
        "item_precision": round(common / got_n, 3) if got_n else None,
        "item_recall": round(common / ref_n, 3) if ref_n else None,
        "seconds_per_row": round(sum(r["seconds"] for r in results) / len(results), 1) if results else None,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"llm_eval_{re.sub(r'[^0-9A-Za-z._-]+', '_', model)}.json"
    out.write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    summary["report"] = str(out)
    return summary


def main(argv: list[str] | None = None) -> int:
    for st in (sys.stdout, sys.stderr):
        if hasattr(st, "reconfigure"):
            st.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="조건 구조화 로컬 모델을 저장본(사람이 쓴 조건)과 비교")
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", nargs="*", help="chunk_id 끝부분 (예: bc-adj-r17 combo-r22)")
    args = ap.parse_args(argv)
    s = run(args.model, args.limit, args.ids)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
