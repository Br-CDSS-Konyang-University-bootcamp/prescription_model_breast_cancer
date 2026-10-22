# src/rag/check_case.py
# 실행: team_project 폴더에서
#   python -m src.rag.check_case tests/fixtures/virtual_charts/VC-0103/expected/confirmed_state.json
#   python -m src.rag.check_case <confirmed_state.json> --out data/reimbursement/vc0103_candidates.json
# confirmed_state(의사 확정값) 하나로 retrieve_for_recommend를 실제 색인·모델로 돌려, B에게 넘어갈 지침 청크와
# 급여 청크, 급여만 있는 행(ESMO 권고는 없고 급여 기준만 있는 요법)을 보여 준다.
# 가상 차트의 기대 정답(scenario.md)과 눈으로 대조하고, D가 급여 판정을 시험할 후보 목록을 만든다.
# 먼저 색인이 있어야 한다: 지침 python -m src.rag.run_indexing, 급여 python -m src.reimbursement.index (D의 비공개 청크).
# --out 파일에는 급여 행 ID와 조건이 들어간다. 공고 원문에서 만든 자료라 git에 올리지 않는다
# (data/reimbursement/ 아래 .json은 .gitignore가 막는다).
import argparse
import json
import sys
from pathlib import Path

from .chunk_common import BASE_DIR
from .retrieve import from_confirmed_state, is_confirmed_state

SCHEMA = BASE_DIR / "schemas" / "confirmed_state.json"
SAFE_OUT_DIR = BASE_DIR / "data" / "reimbursement"


def validate(confirmed_state: dict) -> list[str]:
    """schemas/confirmed_state.json 위반 목록 (jsonschema가 없으면 검사하지 않는다)."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in Draft202012Validator(schema).iter_errors(confirmed_state)]


def _row(r: dict) -> dict:
    return {"chunk_id": r["chunk_id"], "matched_drugs": r.get("matched_drugs"), "extra_drugs": r.get("extra_drugs"),
            "setting": r.get("setting"), "line": r.get("line"), "drug_classes": r.get("drug_classes"),
            "supportive": r.get("supportive"), "parents": [p["chunk_id"] for p in r.get("parents") or []],
            "reimbursement": r.get("reimbursement")}


def summarize(guideline: list[dict], reimbursement: list[dict], reimbursement_only: list[dict] = ()) -> dict:
    """--out에 쓸 요약. 본문 대신 ID·약·차수·조건만 남긴다 (D가 판정에 쓰는 값).
    reimbursement_only: ESMO 권고의 약으로는 찾지 못했지만 같은 병기·차수·아형인 급여 행 (급여만 있는 요법)."""
    return {
        "guideline": [{"rank": i, "chunk_id": c["chunk_id"], "chunk_kind": c.get("chunk_kind"), "score": c.get("score"),
                       "line": c.get("line"), "drugs": c.get("drugs"), "page": c.get("page_start")}
                      for i, c in enumerate(guideline, 1)],
        "reimbursement": [_row(r) for r in reimbursement],
        "reimbursement_only": [_row(r) for r in reimbursement_only],
    }


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서 한글·기호가 깨지지 않게
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="confirmed_state 하나로 C 검색 결과(지침·급여 청크) 확인")
    ap.add_argument("path", type=Path, help="confirmed_state.json")
    ap.add_argument("--as-of", help="급여 판정 기준일 YYYY-MM-DD (기본: confirmed_at의 날짜)")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--out", type=Path, help="결과 요약 JSON (data/reimbursement/ 아래 권장, git에 올리지 않음)")
    args = ap.parse_args(argv)

    state = json.loads(args.path.read_text(encoding="utf-8"))
    if not is_confirmed_state(state):
        sys.exit(f"{args.path}는 confirmed_state가 아닙니다 (items, decision_context 칸이 없음).")
    errors = validate(state)
    if errors:
        print(f"[경고] schemas/confirmed_state.json 위반 {len(errors)}건: {errors[:3]}")

    from . import close_searcher, retrieve_for_recommend
    record, patient, lines = from_confirmed_state(state)
    print(f"환자 {state.get('patient_ref')} · {record['subtype']} · {record['setting']['disease']} · "
          f"지침 차수 {lines['guideline']} · 급여 차수 {lines['reimbursement']}")
    print(f"환자 정보 {patient}")
    try:
        guideline, reimbursement, only = retrieve_for_recommend(state, as_of=args.as_of, top_k=args.top_k,
                                                                rerank=not args.no_rerank, with_reimbursement_only=True)
    finally:
        close_searcher()

    print(f"\n[지침 청크 {len(guideline)}개]  순위  점수  종류  ID  쪽  본문 앞부분")
    for i, c in enumerate(guideline, 1):
        kind = "그림" if c.get("chunk_kind") == "algorithm" else "권고"
        print(f"{i:3d}  {c.get('score', 0):6.3f}  {kind}  {c['chunk_id']}  p{c.get('page_start')}  "
              f"{c['text'][:90].replace(chr(10), ' ')}")
    print(f"\n[급여 청크 {len(reimbursement)}개]  ID  찾은 약 / 행에만 있는 약  차수")
    for r in reimbursement:
        print(f"  {r['chunk_id']}  {r.get('matched_drugs')} / {r.get('extra_drugs')}  {r.get('line')}")
    if not reimbursement:
        print("  (없음: 급여 청크를 색인했는지 확인하세요. python -m src.reimbursement.index)")
    treat = [r for r in only if not r.get("supportive")]
    print(f"\n[급여만 있는 행 {len(only)}개: ESMO 권고의 약으로는 찾지 못한 같은 병기·차수·아형의 급여 행]"
          f"  치료 요법 {len(treat)}개 + 보조약 {len(only) - len(treat)}개")
    for r in only:
        mark = " (보조약)" if r.get("supportive") else ""
        print(f"  {r['chunk_id']}  {r.get('extra_drugs')}  {r.get('line')}  {r.get('drug_classes')}{mark}")

    if args.out:
        out = args.out.resolve()
        if SAFE_OUT_DIR not in out.parents:
            print(f"[주의] {args.out}: 급여 행 정보는 공고 원문에서 만든 자료라 git에 올리면 안 됩니다. "
                  f"data/reimbursement/ 아래에 저장하기를 권합니다.")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summarize(guideline, reimbursement, only), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(f"\n저장 -> {args.out}")


if __name__ == "__main__":
    main()
