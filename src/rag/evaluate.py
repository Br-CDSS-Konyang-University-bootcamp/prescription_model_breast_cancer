# src/rag/evaluate.py
# 검색 평가: 문제집(data/eval/rag_eval_cases.csv)의 질의를 검색하고 3단계로 채점한다.
#   L0 문서: 1위 결과가 정답 문서(예: esmo-mbc-2026-05)에서 나왔나
#   L1 소단원: 상위 k개 결과의 부모(소단원) 중 정답 소단원이 있나
#   L2 권고: 정답 권고가 상위 k개에 몇 개 들어왔나(recall@k), 처음 나온 순위(MRR)
# 실행: team_project 폴더에서 python -m src.rag.evaluate [--k 5] [--no-rerank] [--candidates 20] [--reranker 모델] [--out 결과.csv]
# 질의마다 검색 시간도 잰다. 첫 질의는 모델을 불러오는 시간이 들어가 따로 보여 준다.
# 정답은 status=draft인 동안 초안이다. 원문과 대조해 확인한 문항은 status=reviewed로 바꾼다 (PROJECT.md §12).
import argparse
import csv
import sys
import time
from pathlib import Path

from .chunk_common import BASE_DIR

CASES_CSV = BASE_DIR / "data" / "eval" / "rag_eval_cases.csv"
LIST_FIELDS = ("biomarker_tags", "metastatic_sites", "expected_parents", "expected_chunks")


def load_cases(path: Path = CASES_CSV) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        cases = [dict(row) for row in csv.DictReader(f)]
    for case in cases:
        for field in LIST_FIELDS:
            case[field] = [v.strip() for v in (case.get(field) or "").split(";") if v.strip()]
    return cases


def doc_of(chunk: dict) -> str:
    """청크가 나온 문서(L0) 이름. 예: ESMO-MBC, 2026-05 → esmo-mbc-2026-05."""
    return f"{chunk['source'].lower()}-{chunk['version']}"


def score_case(case: dict, results: list[dict], k: int = 5) -> dict:
    top = results[:k]
    ids = [r["chunk_id"] for r in top]
    expected = case["expected_chunks"]
    found = [cid for cid in expected if cid in ids]
    first_rank = next((i + 1 for i, cid in enumerate(ids) if cid in expected), None)
    return {
        "case_id": case["case_id"],
        "l0_doc": int(bool(top) and doc_of(top[0]) == case["expected_doc"]),
        "l1_section": int(any(r.get("parent_id") in case["expected_parents"] for r in top)),
        "l2_hit": int(bool(found)),
        "l2_recall": len(found) / len(expected) if expected else 0.0,
        "mrr": 1 / first_rank if first_rank else 0.0,
        "top_ids": ids,
    }


def evaluate(cases: list[dict], search_fn, k: int = 5) -> tuple[list[dict], dict]:
    """search_fn(case) → 검색 결과 목록. 테스트에서는 가짜 검색 함수를 넘긴다."""
    rows = []
    for case in cases:
        start = time.perf_counter()
        results = search_fn(case)
        rows.append({**score_case(case, results, k), "seconds": time.perf_counter() - start})
    n = len(rows) or 1
    summary = {key: sum(r[key] for r in rows) / n for key in ("l0_doc", "l1_section", "l2_hit", "l2_recall", "mrr")}
    summary["cases"] = len(rows)
    rest = [r["seconds"] for r in rows[1:]] or [0.0]
    summary["first_seconds"] = rows[0]["seconds"] if rows else 0.0  # 모델 불러오기 포함
    summary["avg_seconds"] = sum(rest) / len(rest)
    summary["max_seconds"] = max(rest)
    return rows, summary


def search_case(case: dict, k: int = 5, rerank: bool = True) -> list[dict]:
    from .searcher import search_guidelines
    return search_guidelines(
        case["query"],
        setting=case["setting"] or None,
        subtype=case["subtype"] or None,
        line=case["line"] or None,
        biomarker_tags=case["biomarker_tags"],
        metastatic_sites=case["metastatic_sites"] or None,
        top_k=k,
        rerank=rerank,
    )


def client_name() -> str:
    from . import client
    return client.RERANKER_NAME.split("/")[-1]


def write_rows(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for r in rows:
            writer.writerow({**r, "top_ids": ";".join(r["top_ids"])})


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="지침 검색을 평가 문제집으로 채점한다")
    parser.add_argument("--cases", type=Path, default=CASES_CSV)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-rerank", dest="rerank", action="store_false", help="재정렬 모델을 끄고 뜻 검색만 쓴다 (비교용)")
    parser.add_argument("--reranker", help="재정렬 모델 이름 (기본 bge-reranker-v2-m3). 예: BAAI/bge-reranker-base")
    parser.add_argument("--candidates", type=int, help="재정렬할 후보 수 (기본 searcher.RERANK_CANDIDATES). 줄이면 빨라진다")
    parser.add_argument("--out", type=Path, help="문항별 결과를 저장할 CSV")
    args = parser.parse_args(argv)

    from . import searcher
    from .searcher import close_searcher
    if args.candidates:
        searcher.RERANK_CANDIDATES = args.candidates
    if args.reranker:
        from . import client
        client.RERANKER_NAME = args.reranker
    cases = load_cases(args.cases)
    try:
        rows, summary = evaluate(cases, lambda c: search_case(c, args.k, args.rerank), args.k)
    finally:
        close_searcher()

    print(f"{'문항':<5} L0 L1 L2  recall  MRR   상위 결과")
    for r in rows:
        print(f"{r['case_id']:<5} {r['l0_doc']:>2} {r['l1_section']:>2} {r['l2_hit']:>2}  {r['l2_recall']:>6.2f} "
              f"{r['mrr']:>5.2f}  {', '.join(cid.split('-', 4)[-1] for cid in r['top_ids'][:3])}")
    print(f"\n{summary['cases']}문항, k={args.k}, 재정렬 {'켬 (' + client_name() + ', 후보 ' + str(searcher.RERANK_CANDIDATES) + '개)' if args.rerank else '끔'}")
    print(f"L0 문서 선택 {summary['l0_doc']:.0%} | L1 소단원 {summary['l1_section']:.0%} | "
          f"L2 hit@{args.k} {summary['l2_hit']:.0%} | L2 recall@{args.k} {summary['l2_recall']:.2f} | MRR {summary['mrr']:.2f}")
    if args.rerank and searcher._reranker_failed:
        print("주의: 재정렬 모델을 불러오지 못해 뜻 검색 점수만 썼습니다 (위 경고 참고). 점수는 재정렬 끔과 같습니다.")
    print(f"검색 시간: 첫 질의 {summary['first_seconds']:.1f}초 (모델 불러오기 포함) | "
          f"나머지 평균 {summary['avg_seconds']:.2f}초, 최대 {summary['max_seconds']:.2f}초")
    if args.out:
        write_rows(rows, args.out)
        print(f"문항별 결과: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
