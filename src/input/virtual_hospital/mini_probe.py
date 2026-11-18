"""mini 처방 모듈 점검 (읽기 전용): 만든 차트의 정답 patient_state를 mini B assess와 화면 1 초안(build_draft)에 넣어
어디서 unknown·빈 칸·검사 권고가 나오는지 센다. mini 파일은 고치지 않고 불러 쓰기만 한다.

실행 (team_project 폴더, team_project 환경): python -m src.input.virtual_hospital.mini_probe
결과: reports/mini_probe.md (TCGA), local/reports/mini_probe_bcnb.md (BCNB)
"""
from __future__ import annotations

import collections
import json

from src.input.virtual_hospital.common import LOCAL, OUT, REPORTS, mini_on_path
from src.input.virtual_hospital.gates import biomarker


def probe(charts) -> dict:
    mini_on_path()
    from src.input.script.confirmed import build_draft
    out = {k: collections.Counter() for k in ("marker", "subtype", "setting", "tests", "needs", "error")}
    examples = collections.defaultdict(list)
    n = 0
    for d in sorted(charts.iterdir()):
        ps = json.loads((d / "expected" / "patient_state.json").read_text(encoding="utf-8"))
        n += 1
        try:
            bm = biomarker().assess(ps)
        except Exception as ex:                                    # noqa: BLE001
            out["error"][f"assess {type(ex).__name__}: {ex}"[:120]] += 1
            continue
        for r in bm["records"]:
            out["marker"][(r["marker"], r["status"])] += 1
            if r["status"] == "unknown":
                examples[f"{r['marker']} unknown"].append((d.name, r["reason"][:80]))
        out["subtype"][json.dumps(bm.get("subtype"), ensure_ascii=False)[:80]] += 1
        out["setting"][json.dumps(bm.get("setting"), ensure_ascii=False)[:120]] += 1
        for t in bm.get("tests_needed") or []:
            out["tests"][json.dumps(t, ensure_ascii=False)[:100]] += 1
        try:
            draft = build_draft(ps, bm)
            for item in draft.get("needs") or []:
                key = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)[:80]
                out["needs"][key] += 1
                if len(examples[f"needs {key}"]) < 3:
                    examples[f"needs {key}"].append(d.name)
        except Exception as ex:                                    # noqa: BLE001
            out["error"][f"build_draft {type(ex).__name__}: {ex}"[:120]] += 1
    return {"n": n, **out, "examples": {k: v[:3] for k, v in examples.items()}}


def write(res: dict, path, title: str) -> None:
    lines = [f"# {title}", "", f"차트 {res['n']}건 · mini는 읽기만 함", ""]
    for k in ("error", "marker", "subtype", "setting", "tests", "needs"):
        lines += [f"## {k}", "", "| 값 | 수 |", "|---|---|"]
        lines += [f"| {str(v).replace('|', '/')} | {c} |" for v, c in res[k].most_common(30)]
        lines.append("")
    lines += ["## 예", "", "```", json.dumps(res["examples"], ensure_ascii=False, indent=1)[:4000], "```"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    write(probe(OUT / "tcga" / "charts"), REPORTS / "mini_probe.md", "mini 점검 — TCGA ① 차트")
    write(probe(LOCAL / "bcnb" / "charts"), LOCAL / "reports" / "mini_probe_bcnb.md", "mini 점검 — BCNB 차트 (공개 안 함)")
    print("reports/mini_probe.md, local/reports/mini_probe_bcnb.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
