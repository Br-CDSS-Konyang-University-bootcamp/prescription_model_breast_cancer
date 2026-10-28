"""표현 변형 사례: 개발 세트 가상 차트를 날짜 표기만 바꿔 다시 쓴다 (2026-10-28, 사례 목록 문서 10-23 §5 I03·I04).

환자 값은 그대로이고 차트 글의 날짜만 2021-03-05 / 2021년 3월 5일 / 21/03/05로 바뀐다. 정답 patient_state도 같은
사례 코드로 함께 만들어 값은 원래 사례와 같고 원문 표기(raw)와 인용 위치만 다르다. 정규화 규칙이 표기에 따라
깨지는지 보는 개발용 세트다 (규칙을 고칠 때 본다).

결과: tests/fixtures/virtual_charts/variants/<사례>-<형식>/chart.txt, expected/patient_state.json

usage (team_project 폴더에서):
    python -m src.input.script.virtual.build_variant_cases            # 모두
    python -m src.input.script.virtual.build_variant_cases --check    # 쓰지 않고, 저장된 파일과 같은지만 본다
"""
from __future__ import annotations

import argparse
import sys

from src.input.script.virtual.virtual_chart import check, date_style, dumps, load_case, out_dir

# 날짜를 kdate로 쓰는 개발 세트 사례 (VC-0103·0106b는 날짜를 글에 직접 써서 형식이 바뀌지 않아 뺐다)
BASES = ["VC-0101", "VC-0104", "VC-0105", "VC-0108", "VC-0109"]
STYLES = ["dash", "korean", "yy"]
VARIANTS = {f"{b}-{s}": (b, s) for b in BASES for s in STYLES}


def build(ref: str):
    base, style = VARIANTS[ref]
    with date_style(style):
        c = load_case(base)
        c.ref = ref
        return c.build()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ids", nargs="*", default=list(VARIANTS))
    ap.add_argument("--check", action="store_true", help="쓰지 않고 저장된 파일과 비교")
    args = ap.parse_args(argv)
    bad = 0
    for ref in args.ids:
        chart, ps = build(ref)
        errs = check(chart, ps)
        out = out_dir(ref)
        files = {out / "chart.txt": chart, out / "expected" / "patient_state.json": dumps(ps)}
        if args.check:
            errs += [f"저장된 {p.name}와 다름" for p, text in files.items()
                     if not p.exists() or p.read_text(encoding="utf-8") != text]
        elif not errs:
            for p, text in files.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8", newline="\n")
        print(f"{ref}: {'OK' if not errs else '; '.join(errs[:8])}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
