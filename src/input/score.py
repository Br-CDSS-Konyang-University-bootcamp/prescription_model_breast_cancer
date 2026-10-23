"""입력 모듈 채점 (notes/input_module_design.md §5, notes/evaluation_plan_2026-10-23.md §3 A 추출).

출력 patient_state를 가상 차트 정답과 칸 단위로 비교한다.

- 칸: 값 칸 하나(예: receptors.er_percent, molecular.mutations.ESR1), 투약 한 줄, 영상 판독 하나, 충돌 칸 하나.
  한쪽에만 있는 칸은 그쪽을 not_recorded로 본다. 값 칸은 status와 값(value·result·variants)이 같으면 맞음,
  투약·영상은 항목 전체(source·raw 제외)가 같으면 맞음
- 필드 정확도: 맞은 칸 / 전체 칸. 정답이 present인 칸만 센 정확도도 같이 낸다 (not_recorded 칸이 많아 높게 보이므로)
- 상태 혼동표: 정답 status × 출력 status (present / not_done / not_recorded / conflict)
- 근거 위치: 정답에 source가 있는 칸에서 위치가 똑같은 비율과 평균 겹침 (겹친 글자 / 합친 범위)
- 인용 준수율: 원문에서 찾은 인용 / 낸 인용 (run의 issues 중 quote_not_found)

usage (team_project 폴더에서):
    python -m src.input.score --gold              # 정답 후보로 파이프라인을 돌려 채점 (규칙 쪽 점검, 100%여야 함)
    python -m src.input.score <출력 폴더>          # <폴더>/<사례>/patient_state.json (+ issues.json)을 채점
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from src.input.candidates import from_expected
from src.input.chart.cases.pairs import PAIRS
from src.input.chart.virtual_chart import CASES, out_dir
from src.input.pipeline import run

ALL = CASES + [p.id for p in PAIRS]
STATUSES = ["present", "not_done", "not_recorded", "conflict"]
NOT_RECORDED = {"status": "not_recorded"}


def slots(ps: dict) -> dict[str, dict]:
    """{칸 이름: {"cmp": 비교할 값, "status": ..., "source": 정답 위치 | None}}."""
    out: dict[str, dict] = {}
    f = ps["fields"]
    for group, entries in f.items():
        if group == "molecular":
            for kind, genes in entries.items():
                for gene, e in genes.items():
                    out[f"molecular.{kind}.{gene}"] = _scalar(e)
        elif isinstance(entries, dict) and all(isinstance(e, dict) and "status" in e for e in entries.values()):
            for key, e in entries.items():
                out[f"{group}.{key}"] = _scalar(e)
    for t in f.get("treatment_history", []):
        out[f"treatment_history[{'+'.join(t['drugs'])} {t['start_date']}]"] = _item(t)
    for i in f.get("imaging_findings", []):
        out[f"imaging_findings[{i['modality']} {i['date']}]"] = _item(i)
    for c in ps.get("conflicts", []):
        values = sorted(json.dumps(_scalar(e)["cmp"], sort_keys=True, ensure_ascii=False) for e in c["candidates"])
        out[c["field"]] = {"cmp": {"status": "conflict", "values": values}, "status": "conflict", "source": None}
    return out


def _scalar(e: dict) -> dict:
    return {"cmp": {k: e[k] for k in ("status", "value", "result", "variants") if k in e},
            "status": e["status"], "source": e.get("source")}


def _item(x: dict) -> dict:
    return {"cmp": _strip(x), "status": "present", "source": x.get("source")}


def _strip(x):
    if isinstance(x, dict):
        return {k: _strip(v) for k, v in x.items() if k not in ("source", "raw")}
    if isinstance(x, list):
        return [_strip(v) for v in x]
    return x


def _overlap(a: dict | None, b: dict | None) -> float:
    if not a or not b:
        return 0.0
    inter = min(a["char_end"], b["char_end"]) - max(a["char_start"], b["char_start"])
    union = max(a["char_end"], b["char_end"]) - min(a["char_start"], b["char_start"])
    return max(inter, 0) / union if union else 1.0


def compare(expected: dict, predicted: dict) -> dict:
    """사례 하나의 채점. 합칠 수 있도록 개수로 돌려준다."""
    want, got = slots(expected), slots(predicted)
    r = {"slots": 0, "correct": 0, "present": 0, "present_correct": 0, "confusion": Counter(),
         "source": 0, "source_exact": 0, "source_overlap": 0.0, "by_field": Counter(), "by_field_wrong": Counter(),
         "wrong": []}
    blank = {"cmp": NOT_RECORDED, "status": "not_recorded", "source": None}
    for name in sorted(want.keys() | got.keys()):
        w, g = want.get(name, blank), got.get(name, blank)
        ok = w["cmp"] == g["cmp"]
        family = name.split("[", 1)[0]
        r["slots"] += 1
        r["correct"] += ok
        r["by_field"][family] += 1
        r["by_field_wrong"][family] += not ok
        r["confusion"][(w["status"], g["status"])] += 1
        if w["status"] == "present":
            r["present"] += 1
            r["present_correct"] += ok
        if w["source"]:
            r["source"] += 1
            r["source_exact"] += bool(g["source"]) and all(
                w["source"][k] == g["source"][k] for k in ("doc_id", "char_start", "char_end"))
            r["source_overlap"] += _overlap(w["source"], g["source"])
        if not ok:
            r["wrong"].append((name, w["cmp"], g["cmp"]))
    return r


def total(results: dict[str, dict], issues: dict[str, dict] | None = None) -> dict:
    """사례별 compare 결과를 합친 지표. issues: {사례: {"candidates": 낸 인용 수, "issues": [...]}}."""
    s = {k: sum(r[k] for r in results.values()) for k in
         ("slots", "correct", "present", "present_correct", "source", "source_exact", "source_overlap")}
    out = {"cases": len(results),
           "field_accuracy": s["correct"] / s["slots"] if s["slots"] else None,
           "present_accuracy": s["present_correct"] / s["present"] if s["present"] else None,
           "source_exact": s["source_exact"] / s["source"] if s["source"] else None,
           "source_overlap": s["source_overlap"] / s["source"] if s["source"] else None,
           "confusion": sum((r["confusion"] for r in results.values()), Counter()),
           "by_field": {f: (sum(r["by_field"][f] - r["by_field_wrong"][f] for r in results.values()),
                            sum(r["by_field"][f] for r in results.values()))
                        for f in sorted({f for r in results.values() for f in r["by_field"]})},
           "quote_rate": None}
    if issues:
        n = sum(v["candidates"] for v in issues.values())
        lost = sum(1 for v in issues.values() for i in v["issues"] if i["reason"] == "quote_not_found")
        out["quote_rate"] = (n - lost) / n if n else None
    return out


def report(results: dict[str, dict], issues: dict[str, dict] | None = None, show_wrong: int = 30) -> str:
    t = total(results, issues)

    def pct(x):
        return "—" if x is None else f"{x:.1%}"

    lines = [f"사례 {t['cases']}건",
             f"필드 정확도 {pct(t['field_accuracy'])} (정답 present 칸만 {pct(t['present_accuracy'])})",
             f"근거 위치 정확 일치 {pct(t['source_exact'])}, 평균 겹침 {pct(t['source_overlap'])}",
             f"인용 준수율 {pct(t['quote_rate'])}", "", "상태 혼동표 (행 = 정답, 열 = 출력)",
             "| 정답 \\ 출력 | " + " | ".join(STATUSES) + " |", "|---" * (len(STATUSES) + 1) + "|"]
    for w in STATUSES:
        lines.append(f"| {w} | " + " | ".join(str(t["confusion"][(w, g)]) for g in STATUSES) + " |")
    bad = [(f, ok, n) for f, (ok, n) in t["by_field"].items() if ok < n]
    if bad:
        lines += ["", "틀린 칸이 있는 필드 (맞음 / 전체)"] + [f"  {f}: {ok}/{n}" for f, ok, n in bad]
    wrong = [(ref, *w) for ref, r in results.items() for w in r["wrong"]]
    if wrong:
        lines += ["", f"틀린 칸 {len(wrong)}개 (앞 {min(show_wrong, len(wrong))}개)"]
        lines += [f"  {ref} {name}\n    정답 {json.dumps(w, ensure_ascii=False)}\n    출력 {json.dumps(g, ensure_ascii=False)}"
                  for ref, name, w, g in wrong[:show_wrong]]
    return "\n".join(lines)


def expected(ref: str) -> dict:
    return json.loads((out_dir(ref) / "expected" / "patient_state.json").read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pred_dir", nargs="?", type=Path, help="<폴더>/<사례>/patient_state.json")
    ap.add_argument("--gold", action="store_true", help="정답 후보로 파이프라인을 돌려 채점")
    ap.add_argument("--ids", nargs="*", help="사례 (기본: --gold는 29건, 출력 폴더는 그 안에 있는 사례)")
    ap.add_argument("--show-wrong", type=int, default=30)
    args = ap.parse_args(argv)
    if not args.gold and args.pred_dir is None:
        ap.error("출력 폴더 또는 --gold")
    results, issues = {}, {}
    ids = args.ids or (ALL if args.gold else [r for r in ALL if (args.pred_dir / r).is_dir()])
    for ref in ids:
        want = expected(ref)
        if args.gold:
            chart = (out_dir(ref) / "chart.txt").read_text(encoding="utf-8")
            cands = from_expected(want)
            got, iss = run(chart, lambda docs: cands, patient_ref=ref, created_at=want["created_at"])
            issues[ref] = {"candidates": len(cands), "issues": iss}
        else:
            path = args.pred_dir / ref / "patient_state.json"
            if not path.exists():
                print(f"{ref}: 출력 없음 ({path})")
                continue
            got = json.loads(path.read_text(encoding="utf-8"))
            ipath = args.pred_dir / ref / "issues.json"
            if ipath.exists():
                issues[ref] = json.loads(ipath.read_text(encoding="utf-8"))
        results[ref] = compare(want, got)
    print(report(results, issues or None, args.show_wrong))
    return 0


if __name__ == "__main__":
    sys.exit(main())
