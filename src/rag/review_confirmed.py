# src/rag/review_confirmed.py
# 정답 confirmed_state 검토용 출력 (C): 사례마다 시나리오 요약, A 검토표(confirmed_review.csv)의 값, 그 확정값으로 C가 만드는
# 검색 조건(필터·질의·추가 검색·급여 차수)을 한 화면에 보여 준다. 검토자는 시나리오와 C 검색 조건이 맞는지 보고,
# 맞으면 confirmed_review.csv의 status를 reviewed로, reviewer·note를 채운다 (파일은 A의 src/app/script/confirmed_review.py가 쓴다).
# 실행: team_project 폴더에서
#   python -m src.rag.review_confirmed                    → 검토표의 모든 사례
#   python -m src.rag.review_confirmed VC-0126 VC-0108    → 고른 사례만
#   python -m src.rag.review_confirmed --out 결과.txt      → 파일로 저장 (UTF-8)
# 읽기만 한다. 색인·모델 없이 확정 파일, 시나리오, 검토표만 읽는다.
import argparse
import csv
import json
import re
import sys
from pathlib import Path

from .query import extra_search_args, search_args
from .retrieve import from_confirmed_state

ROOT = Path(__file__).resolve().parents[2]
CHARTS = ROOT / "tests" / "fixtures" / "virtual_charts"
REVIEW = CHARTS / "confirmed_review.csv"

REVIEW_FIELDS = (("set", "세트"), ("subtype", "아형"), ("disease", "병기 범주"), ("decision", "결정"),
                 ("menopausal", "폐경"), ("ER", "ER"), ("PR", "PR"), ("HER2", "HER2"), ("Ki-67", "Ki-67"),
                 ("PD-L1", "PD-L1"), ("gBRCA", "gBRCA"), ("endocrine_relapse_12m", "내분비 12개월 내 재발"),
                 ("high_risk_early", "조기 고위험"), ("metastatic_sites", "전이 부위"))
PATIENT_FIELDS = (("stage_at_diagnosis", "진단 시 병기"), ("pcr", "pCR"), ("prior_subclasses", "이전 치료"),
                  ("prior_classes", "이전 치료 계열"), ("endocrine_relapse_12m", "내분비 12개월 내 재발"),
                  ("high_risk_early", "조기 고위험"), ("visceral_crisis", "내장 위기"),
                  ("contraindicated", "금기 계열"))
SCENARIO_ROWS = ("이야기 핵심 값", "결정 시점", "B", "C")   # 짧은 시나리오(표 형식)에서 보여 줄 줄
LONG_SECTIONS = ("## 1.", "## 4.", "## 5.")                   # 긴 시나리오(VC-0101~0109)에서 보여 줄 절


def _join(value) -> str:
    if isinstance(value, list):
        return ", ".join(value) if value else "-"
    return "-" if value in (None, "") else str(value)


def scenario_summary(text: str) -> list[str]:
    """scenario.md에서 검토에 필요한 부분만. 표 형식이면 SCENARIO_ROWS 줄, 절 형식이면 LONG_SECTIONS 절 (D 표는 뺀다)."""
    lines = text.splitlines()
    title = next((l for l in lines if l.startswith("# ")), "")
    out = [title]
    rows = {}
    for l in lines:
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", l)
        if m:
            rows[m.group(1)] = m.group(2)
    picked = [f"  {k}: {rows[k]}" for k in SCENARIO_ROWS if k in rows]
    if picked:
        return out + picked
    keep = in_d = False
    for l in lines:
        if l.startswith("## "):
            keep = l.startswith(LONG_SECTIONS)
        if "**D" in l:             # D 급여 기대 표는 C 검토에 필요 없다
            in_d = True
            continue
        if in_d and l.strip() and not l.startswith("|"):
            in_d = False
        if keep and l.strip() and not in_d:
            out.append("  " + l)
    return out


def search_summary(confirmed_state: dict) -> list[str]:
    record, patient, lines = from_confirmed_state(confirmed_state)
    main = search_args(record, **patient)
    out = [f"  필터: 병기 {main.get('setting')} · 아형 {main.get('subtype')} · 차수 {main.get('line')} · "
           f"폐경 {_join(main.get('menopausal_status'))}",
           f"  마커 가산: {_join(main.get('biomarker_tags'))} · 음성(감점): {_join(main.get('negative_tags'))} · "
           f"전이 부위: {_join(main.get('metastatic_sites'))}",
           "  환자 정보: " + " · ".join(f"{label} {_join(patient.get(key))}" for key, label in PATIENT_FIELDS
                                     if patient.get(key) not in (None, "", [])),
           f"  주 검색 질의: {main.get('query_text')}"]
    for extra in extra_search_args(record, top_k=3, **patient):
        out.append(f"  추가 검색: {extra.get('query_text')}")
    for line in lines["guideline"][1:]:
        out.append(f"  추가 차수 검색: {line}")
    out.append(f"  급여 차수: {_join(lines['reimbursement'])} · 이번 결정 계열: {_join(lines.get('classes'))}")
    return out


def render_case(row: dict) -> str:
    case = row["case"]
    folder = CHARTS / case
    lines = [f"===== {case} (검토 status: {row.get('status') or 'draft'}"
             f"{', 보류 세트: 검색 규칙을 바꿀 때 결과를 보지 말 것' if row.get('set') == 'holdout' else ''}) ====="]
    scenario = folder / "scenario.md"
    lines += ["[시나리오]"] + (scenario_summary(scenario.read_text(encoding="utf-8")) if scenario.exists()
                               else ["  (scenario.md 없음)"])
    lines += ["", "[검토표 확정값]",
              "  " + " · ".join(f"{label} {row.get(key) or '-'}" for key, label in REVIEW_FIELDS),
              f"  A 대조: {row.get('checks') or '-'} 같음"
              + (f" · 다른 칸: {row['mismatches']}" if row.get("mismatches") else "")
              + (f" · 이유: {row['accepted']}" if row.get("accepted") else "")]
    path = folder / "expected" / "confirmed_state.json"
    lines += ["", "[C 검색 조건]"]
    if path.exists():
        with open(path, encoding="utf-8") as f:
            lines += search_summary(json.load(f))
    else:
        lines.append("  (confirmed_state.json 없음)")
    if row.get("reviewer") or row.get("note"):
        lines += ["", f"[검토 기록] {row.get('reviewer') or '-'}: {row.get('note') or '-'}"]
    return "\n".join(lines) + "\n"


def load_review() -> list[dict]:
    with open(REVIEW, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서 한글·기호가 깨지지 않게
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="정답 confirmed_state 검토용 출력 (시나리오, 검토표 값, C 검색 조건)")
    ap.add_argument("cases", nargs="*", help="보여 줄 사례 (예: VC-0126). 비우면 검토표 전부")
    ap.add_argument("--out", help="출력을 이 파일에 UTF-8로 저장")
    args = ap.parse_args(argv)
    rows = load_review()
    wanted = {c.upper() for c in args.cases}
    known = {r["case"].upper() for r in rows}
    if wanted - known:
        sys.exit(f"검토표에 없는 사례: {sorted(wanted - known)}")
    text = "\n".join(render_case(r) for r in rows if not wanted or r["case"].upper() in wanted)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"저장: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
