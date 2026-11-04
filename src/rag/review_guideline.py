# src/rag/review_guideline.py
# C 정답 파일(가상 차트 tests/fixtures/virtual_charts/<사례>/expected/guideline.json) 검수용 출력과 검수 기록.
# 사례마다 시나리오의 C 기대, 환자 조건(확정값으로 C가 만드는 검색 조건), 정답 권고 원문(쪽), 그림 경로, 오답으로 둔 권고,
# 판단 이유(note)를 한 화면에 보여 준다. check_case 결과 파일을 주면 이번 순위도 함께 보인다.
# 검수자는 ESMO PDF 옆에 두고 (1) 정답 권고가 이 환자에게 맞는지, (2) 오답으로 둔 권고가 정말 맞지 않는지,
# (3) note의 판단에 동의하는지 본다. 맞으면 --mark로 status를 reviewed로 바꾼다.
# 실행: team_project 폴더에서
#   python -m src.rag.review_guideline                               → 정답 파일이 있는 모든 사례
#   python -m src.rag.review_guideline VC-0103 VC-0124               → 고른 사례만
#   python -m src.rag.review_guideline --results check_전체.txt      → check_case 결과의 순위도 표시
#   python -m src.rag.review_guideline --out 검수.txt                → 파일로 저장 (UTF-8)
#   python -m src.rag.review_guideline --mark VC-0103 VC-0122 --reviewer 염승민   → 검수 완료 기록 (status reviewed)
# 출력은 읽기만 한다. --mark만 정답 파일의 status·reviewer·reviewed_on을 바꾼다. 색인·모델 없이 돈다.
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

from .chunk_store import load_guideline_chunks
from .check_case import compare_expected
from .query import search_args
from .retrieve import from_confirmed_state

ROOT = Path(__file__).resolve().parents[2]
CHARTS = ROOT / "tests" / "fixtures" / "virtual_charts"
SCENARIO_ROWS = ("이야기 핵심 값", "결정 시점", "C")


def answer_files(cases=None) -> list[Path]:
    files = sorted(CHARTS.glob("*/expected/guideline.json"))
    if cases:
        wanted = {c.upper() for c in cases}
        missing = wanted - {p.parts[-3].upper() for p in files}
        if missing:
            sys.exit(f"정답 파일이 없는 사례: {sorted(missing)}")
        files = [p for p in files if p.parts[-3].upper() in wanted]
    return files


def scenario_c(case: str) -> list[str]:
    """scenario.md에서 이야기 핵심 값·결정 시점·C 줄. 긴 형식(VC-0101~0109)은 '- **C (지침)**' 줄."""
    path = CHARTS / case / "scenario.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", text, re.M))
    out = [f"  {k}: {rows[k]}" for k in SCENARIO_ROWS if k in rows]
    out += ["  " + line.strip() for line in text.splitlines() if line.strip().startswith("- **C (지침)**")]
    return out


def parse_results(path: Path) -> dict:
    """check_case를 여러 사례 이어 붙인 결과 파일 → {사례: 지침 목록 [{chunk_id, chunk_kind}]}."""
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"^===== (VC-[\w-]+) =====.*$", text, flags=re.M)
    out = {}
    for case, part in zip(parts[1::2], parts[2::2]):
        out[case] = [{"chunk_id": m.group(2), "chunk_kind": "algorithm" if m.group(1) == "그림" else "recommendation"}
                     for m in re.finditer(r"^\s+\d+\s+[\d.]+\s+(권고|그림)\s+(\S+)", part, re.M)]
    return out


def _short(cid: str) -> str:
    """esmo-ebc-2024-02-tnbc-777c34 → EBC tnbc-777c34"""
    parts = cid.split("-")
    return f"{parts[1].upper()} " + "-".join(parts[4:]) if len(parts) > 4 else cid


def render_case(path: Path, chunks: dict, results: dict = None) -> str:
    case = path.parts[-3]
    exp = json.loads(path.read_text(encoding="utf-8"))
    state = json.loads((path.parent / "confirmed_state.json").read_text(encoding="utf-8"))
    record, patient, lines = from_confirmed_state(state)
    args = search_args(record, **patient)
    rank = {}
    if results and case in results:
        r = compare_expected(exp, results[case])
        rank = {**r["expected"], **r["algorithm"]}
        rank["_first"], rank["_wrong"] = r["first_rank"], r["wrong_above"]
    status = exp.get("status") or "draft"
    who = f", {exp.get('reviewer')} {exp.get('reviewed_on')}" if exp.get("reviewer") else ""
    out = [f"===== {case} (status: {status}{who}) =====", "[시나리오]"] + scenario_c(case)
    d = exp["decision"]
    out += ["", "[환자 조건: 확정값으로 C가 만드는 검색 조건]",
            f"  {d['setting']} · {d['subtype']} · 차수 {', '.join(lines['guideline'])} · 폐경 {args.get('menopausal_status') or '-'}",
            f"  마커 {', '.join(args.get('biomarker_tags') or []) or '-'} · 음성 {', '.join(args.get('negative_tags') or []) or '-'}"
            f" · 전이 부위 {', '.join(args.get('metastatic_sites') or []) or '-'}",
            f"  질의: {args['query_text']}"]
    if rank:
        out.append(f"  [이번 결과] 첫 정답 {rank['_first'] or '못 찾음'}위"
                   + (f" · 정답보다 위의 오답 {', '.join(_short(w) for w in rank['_wrong'])}" if rank["_wrong"] else ""))

    def chunk_line(cid, mark):
        c = chunks.get(cid)
        if c is None:
            return [f"  {mark} {cid}: 청크 파일에 없음"]
        r = f" · 이번 {rank[cid]}위" if cid in rank and rank[cid] else (" · 이번 못 찾음" if cid in rank else "")
        text = c["text"].split(" Footnotes: ")[0] if c.get("chunk_kind") == "algorithm" else c["text"]
        return [f"  {mark} {_short(cid)} (p{c.get('page_start')}{r})", f"      {text}"]

    out += ["", f"[정답 권고 {len(exp['expected_chunks'])}개: 이 환자에게 맞는가]"]
    for cid in exp["expected_chunks"]:
        out += chunk_line(cid, "*")
    out += ["", f"[그림 경로 {len(exp.get('expected_algorithm', []))}개]"]
    for cid in exp.get("expected_algorithm", []):
        out += chunk_line(cid, "*")
    out += ["", f"[오답으로 둔 권고 {len(exp.get('not_expected', []))}개: 정말 맞지 않는가]"]
    for cid in exp.get("not_expected", []):
        c = chunks.get(cid, {})
        out.append(f"  - {_short(cid)} (p{c.get('page_start')}): {c.get('text', '')[:220]}")
    out += ["", "[판단 이유 note]", f"  {exp.get('note')}"]
    return "\n".join(out) + "\n"


def mark_reviewed(paths, reviewer: str, today: str = None) -> list[str]:
    """정답 파일의 status를 reviewed로, reviewer·reviewed_on을 채운다. 바꾼 사례 목록."""
    today = today or datetime.date.today().isoformat()
    done = []
    for path in paths:
        exp = json.loads(path.read_text(encoding="utf-8"))
        exp.update(status="reviewed", reviewer=reviewer, reviewed_on=today)
        path.write_text(json.dumps(exp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done.append(path.parts[-3])
    return done


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서 한글·기호가 깨지지 않게
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="C 정답 파일(가상 차트 guideline.json) 검수용 출력과 검수 기록")
    ap.add_argument("cases", nargs="*", help="사례 (예: VC-0103). 비우면 정답 파일이 있는 전부")
    ap.add_argument("--results", type=Path, help="check_case 결과를 이어 붙인 파일 (===== VC-xxxx ===== 구분)")
    ap.add_argument("--out", type=Path, help="출력을 이 파일에 UTF-8로 저장")
    ap.add_argument("--mark", action="store_true", help="고른 사례를 검수 완료(reviewed)로 기록")
    ap.add_argument("--reviewer", help="--mark와 함께: 검수자 이름")
    args = ap.parse_args(argv)
    paths = answer_files(args.cases)
    if args.mark:
        if not args.cases or not args.reviewer:
            sys.exit("--mark는 사례와 --reviewer를 함께 주세요 (예: --mark VC-0103 --reviewer 염승민)")
        print("검수 완료로 기록:", ", ".join(mark_reviewed(paths, args.reviewer)))
        return
    chunks = {c["chunk_id"]: c for c in load_guideline_chunks()}
    results = parse_results(args.results) if args.results else None
    text = "\n".join(render_case(p, chunks, results) for p in paths)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"저장: {args.out} ({len(paths)}건)")
    else:
        print(text)


if __name__ == "__main__":
    main()
