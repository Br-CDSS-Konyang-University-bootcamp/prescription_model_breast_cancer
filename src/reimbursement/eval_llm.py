"""조건 구조화용 로컬 모델 비교 (PROJECT.md §14 '급여 조건 구조화용 로컬 LLM 선정').

지금 저장본의 조건(사람이 쓰고 검수한 131행)을 기준으로, 로컬 모델이 같은 행에서 만든 조건을 비교한다.
저장본·청크는 바꾸지 않는다. 결과는 data/reimbursement/reports/llm_eval_<모델>.json (공고 원문 없이 행 이름과 숫자만).

    python -m src.reimbursement.eval_llm --model qwen3:32b                  # 조건이 있는 행 전부
    python -m src.reimbursement.eval_llm --model qwen3:32b --limit 20       # 앞 20행만 (빨리 보기)
    python -m src.reimbursement.eval_llm --model qwen3:32b --similar 3 --fix                        # 파이프라인 방식 (새 행)
    python -m src.reimbursement.eval_llm --model qwen3:32b --similar 3 --fix --previous 옛청크.jsonl   # 바뀐 행

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
from .conditions import DATA, TARGET_KINDS, OllamaStructurer, _norm, _words, draft, problems_of, similar_rows
from .pipeline import _latest_local
from .verify import keyed_items

REPORTS = DATA / "reports"
# --shots N일 때 앞에서 N개를 예시로 넣는 검수된 행. 어려운 구조(단계 규칙·unless·묶음·예외·간주 규칙·병용)를 고루 담았다.
# 예시로 쓴 행은 채점에서 뺀다
EXAMPLE_ROWS = ["bc-pal-endo-1l-r01", "bc-pal-chemo-2lplus-r21", "bc-pal-endo-2lplus-r07", "combo-r22",
                "bc-pal-chemo-2lplus-r02", "bc-adj-r19"]


def item_keys(cond: dict) -> list[str]:
    """비교 열쇠 목록 (verify.keyed_items와 같은 열쇠: 묶음 위치 + field·op·value·of, 간주 규칙)."""
    return sorted(k for k, _ in keyed_items(cond))


def _skeleton(cond: dict) -> dict:
    """완전 일치 비교용: 항목 열쇠와 판정에 쓰지 않는 칸(notes 등)이 비었는지만 남긴다."""
    return {"items": item_keys(cond),
            **{k: bool(cond.get(k)) for k in ("human_review", "unmapped")}}


def compare(ref: dict, got: dict) -> dict:
    a, b = item_keys(ref), item_keys(got)
    common = sum(min(a.count(k), b.count(k)) for k in set(a))
    return {"ref_items": len(a), "got_items": len(b), "common": common,
            "exact": _skeleton(ref) == _skeleton(got)}


def run(model: str, limit: int | None = None, ids: list[str] | None = None, think: bool = False,
        shots: int = 0, similar: int = 0, fix: bool = False, previous: Path | None = None) -> dict:
    """similar: 행마다 원문이 가장 비슷한 검수 행 N개를 예시로 (자기 자신은 뺌. 새로 생긴 행을 만들 때와 같은 조건)
    fix: 파이프라인과 같이 규칙으로 고치고 검사에 걸리면 한 번 더 묻는다 (conditions.draft)
    previous: 이전 책자 청크 파일. 같은 행이 있으면 이전 판 원문·조건을 주고 바뀐 부분만 고치게 한다"""
    booklet = _latest_local(DATA / "raw", "공고책자_*.pdf")
    bc = booklet_chunks(load_booklet(booklet, DATA / "cache"))
    current = {c["chunk_id"]: c for c in map(json.loads, open(DATA / "chunks" / "reimbursement_chunks_current.jsonl",
                                                                   encoding="utf-8"))}
    rows = [c for c in bc.chunks if c["chunk_kind"] in TARGET_KINDS
            and (current.get(c["chunk_id"], {}).get("reimbursement", {}).get("conditions") or {}).keys() - {"line_rule"}]

    def reviewed(c):
        return {"chunk_id": c["chunk_id"], "text": c["text"], "context": bc.contexts.get(c["chunk_id"], ""),
                "drugs": c.get("drugs") or [],
                "conditions": {k: v for k, v in current[c["chunk_id"]]["reimbursement"]["conditions"].items()
                               if k != "line_rule"}}

    ex_ids = [c["chunk_id"] for e in EXAMPLE_ROWS[:shots] for c in rows if c["chunk_id"].endswith("-" + e)]
    examples = [(p["text"], p["context"], p["conditions"]) for p in map(reviewed, rows) if p["chunk_id"] in ex_ids]
    pool = [reviewed(c) for c in rows]       # 비슷한 행 예시를 찾는 곳 (prepare가 채점 행 자신은 뺌)
    old = []
    if previous:
        # 이전 책자 청크의 조건은 그때 저장본(사람이 넣은 조건)이라 그대로 이전 판으로 쓴다
        old = [{"chunk_id": c["chunk_id"], "text": c["text"], "context": "", "drugs": c.get("drugs") or [],
                "conditions": {k: v for k, v in c["reimbursement"]["conditions"].items() if k != "line_rule"}}
               for c in map(json.loads, open(previous, encoding="utf-8"))
               if c["chunk_kind"] in TARGET_KINDS and c["reimbursement"].get("conditions")]
    rows = [c for c in rows if c["chunk_id"] not in ex_ids]
    if ids:
        rows = [c for c in rows if any(c["chunk_id"].endswith(i) for i in ids)]
    rows = rows[:limit] if limit else rows

    s = OllamaStructurer(model=model, think=think, examples=examples, similar=similar)
    if not fix:
        s.assisted = False
    results = []
    for n, c in enumerate(rows, 1):
        cid, ctx = c["chunk_id"], bc.contexts.get(c["chunk_id"], "")
        s.prepare(c, pool, old)
        ref = reviewed(c)["conditions"]
        t0 = time.time()
        try:
            # --fix면 파이프라인과 같이 확인(두 번째 답 비교 포함)까지 하고, 채점은 확인 전 초안으로 한다
            flagged, usage = draft(s, c, ctx, verify=fix)
            got = usage.get("draft", flagged)
            err = None
        except Exception as e:          # 한 행 실패로 멈추지 않는다 (스키마 재시도 실패, 시간 초과 등)
            got, usage, err = None, {}, f"{type(e).__name__}: {str(e)[:200]}"
        sec = round(time.time() - t0, 1)
        r = {"chunk_id": cid, "seconds": sec, "error": err, "previous": s.hint.get("previous"),
             "similarity": s.hint.get("similarity"),
             "same_text": bool(s.previous_row) and _norm(s.previous_row["text"]) == _norm(c["text"]),
             "fixed": usage.get("fixed", []), "revised": usage.get("revised", False)}
        if got is not None:
            problems = problems_of(got, f"{ctx}\n{c['text']}")
            # 검사 결과는 어느 칸에서 걸렸는지만 남긴다. 모델 답(answer)은 원문 구절이 들어 있어
            # 확인 규칙(verify_conditions)을 맞춰 보는 데만 쓰고, 이 보고서는 git에 올리지 않는다 (data/reimbursement/의 .json)
            r.update(passed=not problems, problems=[p.split(":")[0] for p in problems], **compare(ref, got),
                     answer=got, verify=usage.get("verify", []), second_same=usage.get("second_same"))
        results.append(r)
        print(f"[{n}/{len(rows)}] {cid.split('-', 3)[3]}: {sec}s "
              + (r["error"] or f"검사 {'통과' if r['passed'] else '실패'}, 항목 {r['common']}/{r['ref_items']} 일치"
                 f"{' (완전 일치)' if r['exact'] else ''}{' [사람 검토]' if r.get('verify') else ''}"), flush=True)
    ok = [r for r in results if r.get("error") is None]
    ref_n, got_n, common = (sum(r[k] for r in ok) for k in ("ref_items", "got_items", "common"))
    summary = {
        "model": model, "think": think, "examples": [e.split("-", 3)[3] for e in ex_ids], "similar": similar,
        "fix": fix, "previous": previous.name if previous else None,
        "booklet": booklet.name, "rows": len(results),
        "with_previous": sum(bool(r["previous"]) for r in results),
        "revised": sum(r["revised"] for r in results),
        "fixed_rows": sum(bool(r["fixed"]) for r in results),
        # 확인(--fix): 검사를 통과한 초안 중 틀린 것을 사람 검토로 돌렸는지
        "wrong_flagged": sum(1 for r in results if r.get("passed") and not r["exact"] and r.get("verify")),
        "wrong_unflagged": sum(1 for r in results if r.get("passed") and not r["exact"] and not r.get("verify")),
        "right_flagged": sum(1 for r in results if r.get("passed") and r["exact"] and r.get("verify")),
        "errors": len(results) - len(ok),
        "passed": sum(r["passed"] for r in ok),
        "exact": sum(r["exact"] for r in ok),
        "item_precision": round(common / got_n, 3) if got_n else None,
        "item_recall": round(common / ref_n, 3) if ref_n else None,
        "seconds_per_row": round(sum(r["seconds"] for r in results) / len(results), 1) if results else None,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    tag = (re.sub(r"[^0-9A-Za-z._-]+", "_", model) + ("_think" if think else "") + (f"_{len(ex_ids)}shot" if ex_ids else "")
           + (f"_sim{similar}" if similar else "") + ("_fix" if fix else "") + ("_update" if previous else ""))
    out = REPORTS / f"llm_eval_{tag}.json"
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
    ap.add_argument("--think", action="store_true", help="생각 모드 (Qwen3 등). 느려짐")
    ap.add_argument("--shots", type=int, default=0, help=f"검수된 행을 예시로 넣는 수 (최대 {len(EXAMPLE_ROWS)}, 채점에서 뺌)")
    ap.add_argument("--similar", type=int, default=0,
                    help="행마다 원문이 가장 비슷한 검수된 행 N개를 예시로 넣음 (자기 자신은 뺌). 새로 생긴 행을 만들 때와 같은 조건")
    ap.add_argument("--fix", action="store_true", help="파이프라인처럼 규칙으로 고치고, 검사에 걸리면 한 번 더 묻기")
    ap.add_argument("--previous", type=Path,
                    help="이전 책자 청크 파일 (.jsonl). 같은 행이 있으면 이전 판 원문·조건을 주고 바뀐 부분만 고치게 함")
    args = ap.parse_args(argv)
    s = run(args.model, args.limit, args.ids, args.think, args.shots, args.similar, args.fix, args.previous)
    print(json.dumps(s, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
