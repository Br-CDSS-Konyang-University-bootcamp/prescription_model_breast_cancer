"""가상 차트마다 정답 confirmed_state (2단계 C·D·B 시험의 입력 정답). team_project 폴더에서:

    python -m src.app.script.confirmed_fixtures              # 쓰기 → tests/fixtures/virtual_charts/<사례>/expected/confirmed_state.json
    python -m src.app.script.confirmed_fixtures --check      # 쓰지 않고 저장된 파일과 비교
    python -m src.app.script.confirmed_fixtures --ids VC-0110 VC-0111

만드는 법: 정답 patient_state.json → B assess() → A build_draft() 기본값을 그대로 확정 (화면 1에서 아무것도 바꾸지 않고
[확정]한 것과 같다. 해당 없는 칸은 화면처럼 넣지 않는다, screen1.drop_not_applicable).
- 필수 칸이 비거나 스키마를 통과하지 못하면 파일을 쓰지 않고 이유를 적는다 (의사·팀이 정할 칸).
- 손으로 쓴 파일(HAND_MADE)은 덮어쓰지 않고, 기본값과 다른 칸만 보여 준다.
- 시각·확정자는 고정값이라 다시 만들어도 같은 파일이 나온다.
tests/fixtures는 공용 폴더라 바꾼 파일은 4명 검토 뒤에 올린다 (CLAUDE.md).
"""
from __future__ import annotations

import argparse
import json
import sys

from src.app.script import screen1 as s

c = s.c
CONFIRMED_AT = "2026-11-03T00:00:00+09:00"
CONFIRMED_BY = "virtual-gold"
# 손으로 쓴 정답 (2026-10-21). C·D 시험이 이 파일을 쓰므로 생성기로 덮지 않는다
HAND_MADE = {"VC-0103"}


def build(app: s.App, case: str) -> tuple[dict | None, list[str]]:
    """사례 하나 → (confirmed_state 또는 None, 쓰지 못한 이유)."""
    ps = app.patient_state(case)
    draft = s.drop_not_applicable(c.build_draft(ps, app.bm.assess(ps)))
    reasons = [f"{k}: 필수인데 기본값이 비어 있음 (의사 입력 필요)" for k in s.screen_missing(draft["items"])]
    doc, errors = c.to_confirmed_state(draft, CONFIRMED_BY, CONFIRMED_AT)
    reasons += [e for e in errors if e.split(":")[0] not in {r.split(":")[0] for r in reasons}]
    return (None, reasons) if reasons else (doc, [])


def diff(want: dict, got: dict) -> list[str]:
    """두 confirmed_state의 confirmed 값이 다른 칸."""
    out = []
    keys = sorted(set(c.item_keys(want["items"])) | set(c.item_keys(got["items"])))
    for k in keys:
        a, b = (c.items_get(x["items"], k) or {} for x in (want, got))
        if a.get("confirmed") != b.get("confirmed"):
            out.append(f"{k}: 파일 {json.dumps(a.get('confirmed'), ensure_ascii=False)} / 기본값 "
                       f"{json.dumps(b.get('confirmed'), ensure_ascii=False)}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="+")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 저장된 파일과 비교")
    args = ap.parse_args(argv)
    app = s.App(s.DEFAULT_CASES, c.SAVE_DIR)
    bad = 0
    for case in args.ids or app.cases():
        path = s.DEFAULT_CASES / case / "expected" / "confirmed_state.json"
        doc, reasons = build(app, case)
        if doc is None:
            print(f"{case}: 만들지 않음 - {'; '.join(reasons)}")
            continue
        if case in HAND_MADE:
            with open(path, encoding="utf-8") as f:
                hand = json.load(f)
            d = diff(hand, doc)
            print(f"{case}: 손으로 쓴 파일 유지" + (f", 기본값과 다른 칸 {len(d)}개" if d else ", 기본값과 같음"))
            for line in d:
                print(f"    {line}")
            continue
        text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if args.check:
            ok = path.exists() and path.read_text(encoding="utf-8") == text
            bad += not ok
            print(f"{case}: {'OK' if ok else '다름 (다시 만들 것)'}")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"{case}: 씀")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
