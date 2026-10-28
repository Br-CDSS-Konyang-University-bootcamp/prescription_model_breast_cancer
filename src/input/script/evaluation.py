"""정답 후보(candidates)와 채점(score). 가상 차트 정답과 출력을 칸 단위로 비교한다.

실행: python -m src.input.script.evaluation (아래 score 절의 usage)

이 파일은 아래 순서의 절로 되어 있다 (2026-10-26, 옛 script/evaluation/ 폴더의 파일을 합침).
절마다 맨 위 주석이 옛 파일의 설명이다.
- candidates
- score
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from src.input.script.pipeline import run
from src.input.script.virtual.cases.pairs import PAIRS
from src.input.script.virtual.virtual_chart import CASES, out_dir


# ====================================================================================================
# candidates (옛 src/input/script/evaluation/candidates.py)
# ====================================================================================================
# IN-2 후보 형식과, 정답 patient_state에서 "완벽한 후보 목록"을 만드는 함수 (notes/input_module_design.md §2 IN-2).
#
# 후보 하나는 LLM이 문서 하나에서 찾은 "이 칸의 값이 적힌 구절"이다. 값은 담지 않는다 (정규화는 IN-3 규칙).
#
#     {"doc_id": "D4", "field": "receptors.er_percent", "quote": "ER positive (Allred 8, 5+3)",
#      "specimen": "metastasis", "observed_date": "2023-04-16"}
#
# - field: patient_state의 칸 경로. 이력·충돌 값도 같은 칸 이름 (고르는 것은 IN-4·IN-5).
#   목록 칸은 항목 하나가 후보 하나다: treatment_history, imaging_findings, anthracycline_drug_dose.drugs.
# - quote: 문서 원문 그대로의 구절. 위치(char_start·char_end)는 인용 확인 단계에서 코드가 계산한다.
# - specimen, observed_date: 구절에 딸린 검체·관찰 날짜. 없으면 null.
#
# 정답에서 만든 후보를 IN-2 자리에 넣어 끝까지 돌리면 규칙 쪽을 LLM 없이 시험할 수 있다
# (notes/input_llm_principles_priorities_2026-10-23.md §2 2번).

KEYS = ("doc_id", "field", "quote", "specimen", "observed_date")


def from_expected(patient_state: dict) -> list[dict]:
    """정답 patient_state의 source가 있는 값마다 후보 하나. 순서는 정답 JSON에 나오는 순서."""
    out: list[dict] = []
    _walk(patient_state["fields"], [], out)
    for c in patient_state.get("conflicts", []):
        for e in c["candidates"]:
            out.append(_candidate(c["field"], e))
    return out


def _walk(x, path: list[str], out: list[dict]) -> None:
    if isinstance(x, dict):
        if isinstance(x.get("source"), dict):
            out.append(_candidate(".".join(path), x))
        for k, v in x.items():
            if k != "source":
                _walk(v, path if k == "history" else path + [k], out)
    elif isinstance(x, list):
        for v in x:
            _walk(v, path, out)


def _candidate(field: str, entry: dict) -> dict:
    s = entry["source"]
    return {"doc_id": s["doc_id"], "field": field, "quote": s["quote"],
            "specimen": entry.get("specimen"), "observed_date": entry.get("observed_date")}


# ====================================================================================================
# score (옛 src/input/script/evaluation/score.py)
# ====================================================================================================
# 입력 모듈 채점 (notes/input_module_design.md §5, notes/evaluation_plan_2026-10-23.md §3 A 추출).
#
# 출력 patient_state를 가상 차트 정답과 칸 단위로 비교한다.
#
# - 칸: 값 칸 하나(예: receptors.er_percent, molecular.mutations.ESR1), 투약 한 줄, 영상 판독 하나, 충돌 칸 하나.
#   한쪽에만 있는 칸은 그쪽을 not_recorded로 본다. 값 칸은 status와 값(value·result·variants)이 같으면 맞음,
#   투약·영상은 항목 전체(source·raw 제외)가 같으면 맞음. 변이의 raw는 빼고, 전이 부위 목록은 순서 없이 비교한다
# - 필드 정확도: 맞은 칸 / 전체 칸. 정답이 present인 칸만 센 정확도도 같이 낸다 (not_recorded 칸이 많아 높게 보이므로)
# - 상태 혼동표: 정답 status × 출력 status (present / not_done / not_recorded / conflict)
# - 근거 위치: 정답에 source가 있는 칸에서 위치가 똑같은 비율과 평균 겹침 (겹친 글자 / 합친 범위)
# - 인용 준수율: 원문에서 찾은 인용 / 낸 인용 (run의 issues 중 quote_not_found)
# - 정밀도: 출력이 값을 낸 칸(not_recorded가 아님) 중 맞은 칸. 낮으면 없는 값을 만든다
# - 재현율: 정답에 값이 있는 칸(not_recorded가 아님) 중 맞은 칸. 낮으면 있는 값을 놓친다
#
# 사례 묶음 (--set): dev = 가상 차트 10건 (규칙·프롬프트를 고칠 때 본 사례), pairs = 짝 사례 19건,
# test = 새 사례 20건 VC-0110 ~ VC-0129 (규칙을 고정한 뒤에만 잰다, notes 과적합 주의),
# holdout = 보류 세트 18건 VC-0130 ~ VC-0144 + 짝 G20·G21 (규칙을 고칠 때 보지 않는다, virtual_patient_cases_2026-10-27.md §5)
#
# usage (team_project 폴더에서):
#     python -m src.input.script.evaluation --gold [--set test]   # 정답 후보로 파이프라인을 돌려 채점 (규칙 쪽 점검)
#     python -m src.input.script.evaluation <출력 폴더>            # <폴더>/<사례>/patient_state.json (+ issues.json)을 채점

ALL = CASES + [p.id for p in PAIRS]
STATUSES = ["present", "not_done", "not_recorded", "conflict"]


def case_set(name: str) -> list[str]:
    """dev (10건) / pairs (짝 19건) / test (새 20건) / holdout (보류 18건) / all (dev + pairs)."""
    if name == "test":
        from src.input.script.virtual.build_virtual_cases import BUILDERS
        return list(BUILDERS)
    if name == "holdout":
        from src.input.script.virtual.build_holdout_cases import BUILDERS
        return list(BUILDERS)
    if name == "variants":
        from src.input.script.virtual.build_variant_cases import VARIANTS
        return list(VARIANTS)
    return {"dev": CASES, "pairs": [p.id for p in PAIRS], "all": ALL}[name]


NOT_RECORDED = {"status": "not_recorded"}
# 순서에 뜻이 없는 전이 부위 목록은 정렬해서 비교한다 (2026-10-26 0단계, 정답은 글 순서·출력은 표준 순서라 달랐다)
SITE_FIELDS = {"stage.metastatic_sites", "recurrence.metastatic_sites"}


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
                out[f"{group}.{key}"] = _scalar(e, f"{group}.{key}")
    for t in f.get("treatment_history", []):
        out[f"treatment_history[{'+'.join(t['drugs'])} {t['start_date']}]"] = _item(t)
    for i in f.get("imaging_findings", []):
        out[f"imaging_findings[{i['modality']} {i['date']}]"] = _item(i)
    for c in ps.get("conflicts", []):
        values = sorted(json.dumps(_scalar(e)["cmp"], sort_keys=True, ensure_ascii=False) for e in c["candidates"])
        out[c["field"]] = {"cmp": {"status": "conflict", "values": values}, "status": "conflict", "source": None}
    return out


def _scalar(e: dict, name: str | None = None) -> dict:
    cmp = {k: e[k] for k in ("status", "value", "result", "variants") if k in e}
    if "variants" in cmp:
        cmp["variants"] = _strip(cmp["variants"])       # 변이 원문(raw)은 다른 칸의 raw처럼 비교에서 뺀다 (0단계)
    if name in SITE_FIELDS and isinstance(cmp.get("value"), list):
        cmp["value"] = sorted(cmp["value"])
    return {"cmp": cmp, "status": e["status"], "source": e.get("source")}


def _item(x: dict) -> dict:
    cmp = _strip(x)
    if isinstance(cmp.get("sites"), list):
        cmp["sites"] = sorted(cmp["sites"])              # 영상 판독의 전이 부위도 순서 없이 (0단계)
    return {"cmp": cmp, "status": "present", "source": x.get("source")}


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
         "pred": Counter(), "gold": Counter(), "hit": Counter(), "wrong": []}
    blank = {"cmp": NOT_RECORDED, "status": "not_recorded", "source": None}
    for name in sorted(want.keys() | got.keys()):
        w, g = want.get(name, blank), got.get(name, blank)
        ok = w["cmp"] == g["cmp"]
        family = name.split("[", 1)[0]
        r["slots"] += 1
        r["correct"] += ok
        r["by_field"][family] += 1
        r["by_field_wrong"][family] += not ok
        # 정밀도·재현율: 값이 있는 칸만 (not_recorded끼리 맞은 칸은 세지 않는다)
        r["pred"][family] += g["status"] != "not_recorded"
        r["gold"][family] += w["status"] != "not_recorded"
        r["hit"][family] += ok and w["status"] != "not_recorded"
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
    pr = {k: sum((r[k] for r in results.values()), Counter()) for k in ("pred", "gold", "hit")}
    hit, pred, gold = (sum(pr[k].values()) for k in ("hit", "pred", "gold"))
    out.update({"precision": hit / pred if pred else None, "recall": hit / gold if gold else None,
                "counts": {"hit": hit, "pred": pred, "gold": gold},
                "pr_by_field": {f: (pr["hit"][f], pr["pred"][f], pr["gold"][f]) for f in sorted(pr["gold"] | pr["pred"])}})
    if issues:
        n = sum(v["candidates"] for v in issues.values())
        lost = sum(1 for v in issues.values() for i in v["issues"] if i["reason"] == "quote_not_found")
        out["quote_rate"] = (n - lost) / n if n else None
    return out


def report(results: dict[str, dict], issues: dict[str, dict] | None = None, show_wrong: int = 30) -> str:
    t = total(results, issues)

    def pct(x):
        return "—" if x is None else f"{x:.1%}"

    c = t["counts"]
    lines = [f"사례 {t['cases']}건",
             f"필드 정확도 {pct(t['field_accuracy'])} (정답 present 칸만 {pct(t['present_accuracy'])})",
             f"정밀도 {pct(t['precision'])} (출력한 값 {c['pred']}칸 중 맞음 {c['hit']}), "
             f"재현율 {pct(t['recall'])} (정답 값 {c['gold']}칸 중 찾음 {c['hit']})",
             f"근거 위치 정확 일치 {pct(t['source_exact'])}, 평균 겹침 {pct(t['source_overlap'])}",
             f"인용 준수율 {pct(t['quote_rate'])}", "", "상태 혼동표 (행 = 정답, 열 = 출력)",
             "| 정답 \\ 출력 | " + " | ".join(STATUSES) + " |", "|---" * (len(STATUSES) + 1) + "|"]
    for w in STATUSES:
        lines.append(f"| {w} | " + " | ".join(str(t["confusion"][(w, g)]) for g in STATUSES) + " |")
    bad = [(f, ok, n) for f, (ok, n) in t["by_field"].items() if ok < n]
    if bad:
        lines += ["", "틀린 칸이 있는 필드 (맞음 / 전체, 정밀도 = 맞은 값 / 출력한 값, 재현율 = 맞은 값 / 정답 값)"]
        for f, ok, n in bad:
            hit, pred, gold = t["pr_by_field"].get(f, (0, 0, 0))
            lines.append(f"  {f}: {ok}/{n}  정밀도 {hit}/{pred}  재현율 {hit}/{gold}")
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
    ap.add_argument("--ids", nargs="*", help="사례 (기본: --gold는 --set, 출력 폴더는 그 안에 있는 사례)")
    ap.add_argument("--set", default="all", choices=["dev", "pairs", "test", "holdout", "variants", "all"], help="--gold의 사례 묶음 (기본 all = dev + pairs)")
    ap.add_argument("--show-wrong", type=int, default=30)
    args = ap.parse_args(argv)
    if not args.gold and args.pred_dir is None:
        ap.error("출력 폴더 또는 --gold")
    results, issues = {}, {}
    ids = args.ids or (case_set(args.set) if args.gold else
                       sorted(p.name for p in args.pred_dir.iterdir() if (p / "patient_state.json").exists()))
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
