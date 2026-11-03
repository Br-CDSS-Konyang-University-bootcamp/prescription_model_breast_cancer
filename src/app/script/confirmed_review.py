"""정답 confirmed_state 검증: 시나리오 기대값과 자동 대조하고, 사람이 볼 검토표를 쓴다. team_project 폴더에서:

    python -m src.app.script.confirmed_review            # 대조 결과를 보이고 검토표를 쓴다
    python -m src.app.script.confirmed_review --check    # 쓰지 않고 대조만 (어긋난 칸이 있으면 종료 코드 1)

- 기대값: tests/fixtures/virtual_charts/confirmed_expectations.csv. 사례 scenario.md의 "B" 줄과 결정 시점을 확정 칸 값으로 옮긴 것이다.
  규칙 코드와 따로 사람이 쓴 글이라 독립된 기준이 된다. 칸 이름 규칙:
  `deemed_lines.<규칙>` 간주 규칙 판정, `anthracycline_cumulative.<약>` mg/m2 값, `metastatic_sites~<부위>` 그 부위가 들어 있으면 yes.
  기대값과 다르지만 이유가 확인된 칸은 accepted에 이유를 적는다 (시나리오 문구, B 규칙 등).
- 검토표: tests/fixtures/virtual_charts/confirmed_review.csv. 사례마다 핵심 확정값, 대조 결과, 검토 상태(status)를 둔다.
  B·C가 검토하면 status를 reviewed로, reviewer·note를 채운다. 다시 써도 그 세 칸은 지키고 나머지만 새로 쓴다.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from src.input.script import confirmed as c

CHARTS = c.ROOT / "tests" / "fixtures" / "virtual_charts"
EXPECT = CHARTS / "confirmed_expectations.csv"
REVIEW = CHARTS / "confirmed_review.csv"
COLUMNS = ["case", "set", "subtype", "disease", "decision", "menopausal", "ER", "PR", "HER2", "Ki-67", "PD-L1", "gBRCA",
           "endocrine_relapse_12m", "high_risk_early", "dfi_days", "deemed_met", "metastatic_sites",
           "checks", "mismatches", "accepted", "status", "reviewer", "note"]
KEEP = ("status", "reviewer", "note")
SKIPPED = {"VC-0106b": "Ki-67 값 충돌 (외부 25% / 본원 재판독 15%), 의사가 고를 값",
           "VC-0129": "남성: 폐경 칸이 해당 없음인데 스키마가 HR+에 폐경(pre/post)을 필수로 둠 (팀 결정)"}
SCOPE = {"VC-0129": "범위 외 (남성)", "VC-0144": "범위 외 (임신). 확정 파일에는 범위 외 칸이 없음 (B 추천 단계에서 처리)"}


def case_sets() -> dict[str, str]:
    out = {}
    for name, label in (("cases.csv", "test"), ("holdout_cases.csv", "holdout")):
        with open(CHARTS / name, encoding="utf-8-sig", newline="") as f:
            out.update({r["case_id"]: label for r in csv.DictReader(f)})
    return out


def actual(items: dict, item: str):
    """기대값 표의 칸 이름 → 확정값 (문자열로 비교한다)."""
    if "~" in item:
        key, part = item.split("~", 1)
        return "yes" if part in (c.items_get(items, key) or {}).get("confirmed") or [] else "no"
    for prefix in ("deemed_lines.", "anthracycline_cumulative."):
        if item.startswith(prefix):
            v = ((items.get(prefix[:-1]) or {}).get("confirmed") or {}).get(item[len(prefix):])
            return v.get("value") if isinstance(v, dict) else v
    return (c.items_get(items, item) or {}).get("confirmed")


def same(want: str, got) -> bool:
    if isinstance(got, (int, float)) and not isinstance(got, bool):
        try:
            return float(want) == float(got)
        except ValueError:
            return False
    return want == str(got)


def compare() -> dict[str, list[dict]]:
    """사례 → [{item, expected, actual, ok, accepted}]."""
    with open(EXPECT, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, list[dict]] = {}
    for r in rows:
        path = CHARTS / r["case"] / "expected" / "confirmed_state.json"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            items = json.load(f)["items"]
        got = actual(items, r["item"])
        out.setdefault(r["case"], []).append({"item": r["item"], "expected": r["expected"], "actual": got,
                                              "ok": same(r["expected"], got), "accepted": r["accepted"]})
    return out


def summary_row(case: str, items: dict | None) -> dict:
    if items is None:
        return {"case": case}
    g = lambda k: (c.items_get(items, k) or {}).get("confirmed")   # noqa: E731
    dis = g("setting.disease")
    decision = (f"내분비 {g('setting.line_endocrine')} / 항암 {g('setting.line_chemo')}" if dis == "metastatic"
                else g("setting.phase"))
    deemed = [k.replace("DEEM-", "") for k, v in (g("deemed_lines") or {}).items() if v == "met"]
    hr = g("high_risk_early")
    return {"case": case, "subtype": g("subtype"), "disease": dis, "decision": decision, "menopausal": g("menopausal_status"),
            "ER": g("markers.ER"), "PR": g("markers.PR"), "HER2": g("markers.HER2"), "Ki-67": g("markers.Ki-67"),
            "PD-L1": g("markers.PD-L1"), "gBRCA": g("markers.gBRCA"), "endocrine_relapse_12m": g("endocrine_relapse_12m"),
            "high_risk_early": f"급여 {hr['hira']} / ESMO {hr['esmo']}" if hr else None, "dfi_days": g("dfi_days"),
            "deemed_met": ", ".join(deemed), "metastatic_sites": ", ".join(g("metastatic_sites") or [])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    results = compare()
    sets = case_sets()
    bad = 0
    for case, checks in results.items():
        for x in checks:
            if not x["ok"]:
                tag = "다름 (이유 있음)" if x["accepted"] else "다름"
                bad += not x["accepted"]
                print(f"{case} {x['item']}: 기대 {x['expected']} / 확정 {x['actual']} - {tag}"
                      + (f": {x['accepted']}" if x["accepted"] else ""))
    total = sum(len(v) for v in results.values())
    ok = sum(x["ok"] for v in results.values() for x in v)
    print(f"대조 {total}칸: 같음 {ok}, 다름(이유 있음) {sum(1 for v in results.values() for x in v if not x['ok'] and x['accepted'])}, "
          f"다름(확인 필요) {bad}")
    if args.check:
        return 1 if bad else 0

    old = {}
    if REVIEW.exists():
        with open(REVIEW, encoding="utf-8-sig", newline="") as f:
            old = {r["case"]: r for r in csv.DictReader(f)}
    cases = sorted(p.parents[1].name for p in CHARTS.glob("*/expected/patient_state.json"))
    with open(REVIEW, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for case in cases:
            path = CHARTS / case / "expected" / "confirmed_state.json"
            items = json.load(open(path, encoding="utf-8"))["items"] if path.exists() else None
            row = {k: "" for k in COLUMNS} | summary_row(case, items)
            checks = results.get(case, [])
            row["set"] = sets.get(case, "dev")
            row["checks"] = f"{sum(x['ok'] for x in checks)}/{len(checks)}" if checks else ""
            row["mismatches"] = "; ".join(f"{x['item']} 기대 {x['expected']} / 확정 {x['actual']}" for x in checks if not x["ok"])
            row["accepted"] = "; ".join(x["accepted"] for x in checks if not x["ok"] and x["accepted"])
            if items is None:
                row["mismatches"] = f"파일 없음: {SKIPPED.get(case, '')}"
            row["status"] = "draft"
            for k in KEEP:
                if old.get(case, {}).get(k):
                    row[k] = old[case][k]
            if case in SCOPE and not row["note"]:
                row["note"] = SCOPE[case]
            w.writerow({k: "" if row[k] is None else row[k] for k in COLUMNS})
    print(f"검토표: {REVIEW.relative_to(c.ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
