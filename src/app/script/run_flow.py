"""가상 차트 전체 흐름을 화면 없이 돌린다 (통합 순서 ⑤). team_project 폴더에서:

    python -m src.app.script.run_flow --out data/app/runs/<이름> --llm-host http://127.0.0.1:11435
    python -m src.app.script.run_flow --out data/app/runs/<이름> --ids VC-0103 VC-0111   # 일부만
    python -m src.app.script.run_flow --out data/app/runs/<이름> --summary               # 저장된 결과로 표만 다시

- 입력: 사례마다 정답 confirmed_state (tests/fixtures/virtual_charts/<case>/expected/confirmed_state.json,
  confirmed_fixtures.py가 만든 화면 1 기본값)와 정답 patient_state.
- 사례마다 화면 2와 같은 일을 한다 (screen2.Recommender): C retrieve_for_recommend → B recommend (llm/config.toml [recommend]).
  결과는 <out>/<case>/c1.json (화면 2 캐시와 같은 형식). 이미 있으면 건너뛴다 (--force로 다시). 실패는 <out>/<case>/error.json.
- 표: <out>/summary.csv (사례마다 한 줄). C 정답 expected/guideline.json이 있으면 대조한다:
  정답 지침 청크가 검색되었는지(retrieved), 후보가 인용했는지(cited), 1순위 후보가 인용했는지(top), 오답 청크를 인용했는지(wrong).
  급여 분류는 시나리오 표가 글이라 자동 대조하지 않고 후보마다 적어 둔다 (사람이 scenario.md D 표와 본다).
  급여 사유 글(reimbursement_reason)은 공고 문구가 들어 있을 수 있어 표에 넣지 않는다 (csv는 git에 올라갈 수 있음).
- Qdrant 로컬 모드는 한 프로세스만 연다. 화면 서버를 끄고 돌린다. GPU 서버는 SSH 터널로 (src/input/py_files.md).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from src.app.script import confirmed_review as cr
from src.app.script import screen1 as s1
from src.app.script import screen2 as s2

CHARTS = cr.CHARTS
VERSION = 1   # 정답 확정 파일은 v1로 본다 (결과 파일 이름 c1.json)
COLUMNS = ["case", "set", "subtype", "disease", "decision", "guideline_answer", "retrieved", "cited", "top", "wrong",
           "options", "conflicts", "schema_errors", "seconds", "error"]


def cases() -> list[str]:
    return sorted(p.parents[1].name for p in CHARTS.glob("*/expected/confirmed_state.json"))


def load(case: str, name: str) -> dict | None:
    path = CHARTS / case / "expected" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run_case(rec: s2.Recommender, case: str, out: Path) -> dict:
    """한 사례 실행. 화면 2와 같은 Recommender._run을 이 스레드에서 부른다."""
    err = out / case / "error.json"
    err.unlink(missing_ok=True)
    job = {"stage": "검색", "started": time.time(), "model": rec.model}
    rec._run(job, case, VERSION, load(case, "confirmed_state.json"), load(case, "patient_state.json"))
    if job["stage"] != "done":
        err.parent.mkdir(parents=True, exist_ok=True)
        err.write_text(json.dumps({k: job.get(k) for k in ("stage", "error", "trace")}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return job


def guideline_check(result: dict, answer: dict) -> dict:
    """C 정답(guideline.json)과 추천 결과 대조. 값은 '맞은 수/정답 수' 또는 yes/no."""
    want = answer.get("expected_chunks") or []
    options = result["recommendation"]["options"]
    cited = {cid for o in options for cid in o.get("citations") or []}
    top = set((result["ranked"][0].get("citations") or []) if result.get("ranked") else [])
    wrong = sorted(cited & set(answer.get("not_expected") or []))
    return {"guideline_answer": answer.get("status"),
            "retrieved": f"{sum(cid in result['chunks'] for cid in want)}/{len(want)}",
            "cited": f"{sum(cid in cited for cid in want)}/{len(want)}",
            "top": "yes" if top & set(want) else "no",
            "wrong": "; ".join(wrong)}


def summary_row(case: str, out: Path, sets: dict) -> dict:
    items = load(case, "confirmed_state.json")["items"]
    base = cr.summary_row(case, items)
    row = {k: "" for k in COLUMNS} | {k: base.get(k) for k in ("case", "subtype", "disease", "decision")}
    row["set"] = sets.get(case, "dev")
    err = out / case / "error.json"
    if err.exists():
        row["error"] = json.loads(err.read_text(encoding="utf-8")).get("error")
        return row
    path = out / case / f"c{VERSION}.json"
    if not path.exists():
        row["error"] = "실행 안 됨"
        return row
    result = json.loads(path.read_text(encoding="utf-8"))
    rec = result["recommendation"]
    row["options"] = "; ".join(f"{o.get('therapy')} [{o.get('reimbursement')}]" for o in result["ranked"])
    row["conflicts"] = len(rec.get("conflicts") or [])
    row["schema_errors"] = len(result.get("schema_errors") or [])
    row["seconds"] = result.get("seconds")
    answer = load(case, "guideline.json")
    if answer:
        row |= guideline_check(result, answer)
    return row


def write_summary(out: Path, ids: list[str]) -> Path:
    sets = cr.case_sets()
    path = out / "summary.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for case in ids:
            row = summary_row(case, out, sets)
            w.writerow({k: "" if row[k] is None else row[k] for k in COLUMNS})
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ids", nargs="+")
    ap.add_argument("--llm-host")
    ap.add_argument("--model", default=s2.DEFAULT_MODEL)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--summary", action="store_true", help="실행하지 않고 저장된 결과로 표만 쓴다")
    args = ap.parse_args(argv)
    ids = args.ids or cases()
    missing = [i for i in ids if load(i, "confirmed_state.json") is None]
    if missing:
        print(f"정답 confirmed_state 없음: {', '.join(missing)}")
        return 2
    if not args.summary:
        rec = s2.Recommender(s1.load_bm(), args.model, args.out, args.llm_host)
        for n, case in enumerate(ids, 1):
            if args.force:
                rec.path(case, VERSION).unlink(missing_ok=True)
            if rec.path(case, VERSION).exists():
                print(f"[{n}/{len(ids)}] {case}: 있음, 건너뜀")
                continue
            job = run_case(rec, case, args.out)
            print(f"[{n}/{len(ids)}] {case}: {job['stage']} {round(time.time() - job['started'])}초 {job.get('error') or ''}",
                  flush=True)
    path = write_summary(args.out, ids)
    print(f"표: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
