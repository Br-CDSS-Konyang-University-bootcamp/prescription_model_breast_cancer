"""가상환자 차트를 입력 모듈 LLM으로 끝까지 돌리고 정답(expected/patient_state.json)으로 채점한다.

mini 입력 모듈(pipeline.run, make_extract)과 채점기(evaluation.compare·report)를 고치지 않고 불러 쓴다
(mini `python -m src.input.script.pipeline --out`과 같은 저장 형식). 결과는 local/llm_runs/<이름>/ (git 제외).

실행 (virtual_hospital 폴더, team_project 환경, GPU 터널을 연 뒤):
    python -m src.input.virtual_hospital.llm_run --name t1 --tcga 50 --recur          # TCGA ① 50명(고르게 뽑음) + ② 전체
    python -m src.input.virtual_hospital.llm_run --name t1 --score                    # 저장한 결과만 다시 채점
서버 주소는 코드에 쓰지 않는다. --host 기본값은 이 PC의 SSH 터널 (http://127.0.0.1:11435).
"""
from __future__ import annotations

import argparse
import json
import time

from src.input.virtual_hospital.common import LOCAL, OUT, mini_on_path

RUNS = LOCAL / "llm_runs"


def charts(n_tcga: int, recur: bool) -> list:
    tcga = sorted(p for p in (OUT / "tcga" / "charts").iterdir() if p.is_dir())
    step = max(1, len(tcga) // n_tcga) if n_tcga else 0
    pick = tcga[::step][:n_tcga] if n_tcga else []                 # 번호 순으로 고르게 (재현 가능)
    if recur:
        pick += sorted(p for p in (OUT / "tcga_recur" / "charts").iterdir() if p.is_dir())
    return pick


def key(d) -> str:
    return f"{d.parent.parent.name}-{d.name}"                       # tcga-VH-T0001, tcga_recur-VH-T0043


def run_all(out, dirs, host: str) -> None:
    import requests
    from llm import LLMOutputError, complete_json, load_config
    from src.input.script.pipeline import NO_QUOTE, make_extract, run
    cfg = load_config("extract", host=host)
    print(f"모델 {cfg.model}, 차트 {len(dirs)}건", flush=True)
    for d in dirs:
        o = out / key(d)
        if (o / "patient_state.json").exists():
            continue                                                 # 이어 돌리기
        chart = (d / "chart.txt").read_text(encoding="utf-8")
        want = json.loads((d / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        log = {"candidates": 0, "errors": [], "doc_seconds": {}}

        def complete(msgs, sch, config, _log=log):
            t = time.perf_counter()
            try:
                res = complete_json(msgs, sch, config)
            except (LLMOutputError, requests.RequestException) as e:  # 문서 하나가 실패해도 계속
                _log["errors"].append(str(e)[:300])
                res = {"candidates": []}
            _log["candidates"] += sum(c["quote"].strip().lower() not in NO_QUOTE for c in res["candidates"])
            _log["doc_seconds"][str(len(_log["doc_seconds"]) + 1)] = round(time.perf_counter() - t)
            return res

        cands: list[dict] = []
        llm = make_extract(cfg, complete)

        def extract(docs, _c=cands):
            _c.extend(llm(docs))
            return _c

        t0 = time.perf_counter()
        ps, issues = run(chart, extract, patient_ref=want["patient_ref"], created_at=want["created_at"])
        o.mkdir(parents=True, exist_ok=True)
        (o / "candidates.json").write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
        (o / "patient_state.json").write_text(json.dumps(ps, ensure_ascii=False, indent=2), encoding="utf-8")
        (o / "issues.json").write_text(json.dumps({**log, "model": cfg.model, "issues": issues,
                                                   "seconds": round(time.perf_counter() - t0)},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{key(d)}: {time.perf_counter() - t0:.0f}초, 후보 {log['candidates']}개, 문제 {len(issues)}개, "
              f"LLM 실패 {len(log['errors'])}개", flush=True)


def score(out) -> str:
    from src.input.script.evaluation import compare, report
    results, issues = {}, {}
    for o in sorted(p for p in out.iterdir() if (p / "patient_state.json").exists()):
        branch, vp = o.name.split("-", 1)
        want = json.loads((OUT / branch / "charts" / vp / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        results[o.name] = compare(want, json.loads((o / "patient_state.json").read_text(encoding="utf-8")))
        issues[o.name] = json.loads((o / "issues.json").read_text(encoding="utf-8"))
    text = report(results, issues, show_wrong=80)
    (out / "score.md").write_text(text + "\n", encoding="utf-8")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--tcga", type=int, default=0, help="TCGA ① 몇 명 (고르게)")
    ap.add_argument("--recur", action="store_true", help="TCGA ② 전체")
    ap.add_argument("--host", default="http://127.0.0.1:11435")
    ap.add_argument("--score", action="store_true", help="돌리지 않고 채점만")
    args = ap.parse_args(argv)
    mini_on_path()
    out = RUNS / args.name
    out.mkdir(parents=True, exist_ok=True)
    if not args.score:
        run_all(out, charts(args.tcga, args.recur), args.host)
    print(score(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
