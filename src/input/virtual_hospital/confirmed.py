"""가상환자마다 확정 상태(confirmed_state) 초안 = 처방 모듈 뒷단(C 지침 검색, B 추천, D 급여)의 입력.

mini의 가상 차트 정답과 같은 방법 (mini src/app/script/confirmed_fixtures.py, 고치지 않고 불러 씀):
정답 patient_state + 정답 biomarker_record → A build_draft() 기본값을 그대로 확정
(화면 1에서 아무것도 바꾸지 않고 [확정]한 것과 같다. 해당 없는 칸은 넣지 않는다).
- 값 충돌 칸은 의사가 고를 값이라 비운다
- 필수 칸이 비거나 schema를 통과하지 못하면 파일을 쓰지 않고 이유를 적는다 (의사가 정할 칸)
- 확정자·시각은 고정값 (같은 입력 → 같은 파일)

실행 (team_project 폴더, team_project 환경): python -m src.input.virtual_hospital.confirmed
결과: <차트>/expected/confirmed_state.json, reports/confirmed.md·confirmed_skipped.csv
      (BCNB는 local/bcnb/charts/…, local/reports/ — 약관)
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

from src.input.virtual_hospital.common import CREATED_AT, LOCAL, OUT, REPORTS, mini_on_path, read_csv, write_csv

CONFIRMED_BY = "virtual-hospital"
SETS = {"TCGA ①": (OUT / "tcga" / "charts", REPORTS), "TCGA ②": (OUT / "tcga_recur" / "charts", REPORTS),
        "BCNB": (LOCAL / "bcnb" / "charts", LOCAL / "reports")}


def build(s, ps: dict, br: dict) -> tuple[dict | None, list[str]]:
    """confirmed_fixtures.build과 같은 순서 (App 없이 저장된 정답 두 파일로)."""
    c = s.c
    draft = s.drop_not_applicable(c.build_draft(ps, br))
    for key, why in s.attention(draft["items"], ps).items():
        if why.startswith("값 충돌"):
            c.items_get(draft["items"], key)["confirmed"] = None
    reasons = [f"{k}: 필수인데 값이 없음 (의사 입력 필요)" for k in s.screen_missing(draft["items"])]
    doc, errors = c.to_confirmed_state(draft, CONFIRMED_BY, CREATED_AT)
    reasons += [e for e in errors if e.split(":")[0] not in {r.split(":")[0] for r in reasons}]
    return (None, reasons) if reasons else (doc, [])


def phase_line(doc: dict) -> str:
    """요약용: 치료 단계와 차수 (확정값)."""
    it = doc["items"]
    get = lambda k: (it.get(k) or {}).get("confirmed")   # noqa: E731
    setting = get("setting") or {}
    if isinstance(setting, dict):
        return f"{setting.get('phase') or setting.get('disease')} / {setting.get('line')}"
    return str(setting)


def main() -> int:
    mini_on_path()
    from src.app.script import screen1 as s
    lines = ["# 확정 상태(confirmed_state) 초안 — 생성 보고", "",
             "mini `confirmed_fixtures`와 같은 방법 (정답 patient_state + biomarker_record → build_draft 기본값 확정)", ""]
    for name, (root, rep) in SETS.items():
        if not root.exists():
            print(f"{name}: 차트 폴더 없음 ({root})")
            continue
        made, skipped, need = 0, [], collections.Counter()
        for d in sorted(p for p in root.iterdir() if (p / "expected" / "patient_state.json").exists()):
            ps = json.loads((d / "expected" / "patient_state.json").read_text(encoding="utf-8"))
            br = json.loads((d / "expected" / "biomarker_record.json").read_text(encoding="utf-8"))
            doc, reasons = build(s, ps, br)
            path = d / "expected" / "confirmed_state.json"
            if doc is None:
                path.unlink(missing_ok=True)
                skipped.append({"vp_id": d.name, "reason": "; ".join(reasons)})
                need.update(r.split(":")[0] for r in reasons)
                continue
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            made += 1
        write_csv(rep / f"confirmed_skipped_{name.split()[0].lower()}{'_r' if '②' in name else ''}.csv",
                  skipped, ["vp_id", "reason"])
        msg = f"{name}: 씀 {made}, 못 씀 {len(skipped)}" + (f" (칸: {dict(need)})" if need else "")
        print(msg)
        if name != "BCNB":
            lines.append(f"- {msg}")
        else:
            lines.append(f"- BCNB: 결과는 `local/`에만 (약관). 씀 {made}, 못 씀 {len(skipped)}")
    # TCGA ② 장면 차수(A 입력 모듈이 실제 전체 투약으로 센 차수)와 B 확정값(이번 결정 차수)이 다른 환자.
    # A는 끝난 이유를 모르면 다음 차수, B는 진행 기록이 있을 때만 다음 차수로 본다 (mini 규칙 차이, 이 폴더에서 고치지 않음)
    diff = []
    for r in read_csv(OUT / "tcga_recur" / "patients.csv"):
        path = OUT / "tcga_recur" / "charts" / r["vp_id"] / "expected" / "confirmed_state.json"
        if not path.exists():
            continue
        it = json.loads(path.read_text(encoding="utf-8"))["items"]
        key = "setting.line_endocrine" if r["scene_kind"] == "endocrine" else "setting.line_chemo"
        got = (it.get(key) or {}).get("confirmed")
        if got != f"{r['scene_line']}L":
            diff.append(f"  - {r['vp_id']}: 장면 {r['scene_kind']} {r['scene_line']}차, B 확정값 {key} = {got}")
    lines += ["", f"TCGA ② 장면 차수와 B 확정값이 다른 환자 {len(diff)}명 (A: 이유 모르면 다음 차수, B: 진행 기록 있을 때만)"] + diff
    (REPORTS / "confirmed.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
