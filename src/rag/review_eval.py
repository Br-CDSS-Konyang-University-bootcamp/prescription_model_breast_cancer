# src/rag/review_eval.py
# 평가 문제집 검수용 출력: 문항마다 질문, 환자 조건, 원문 위치, 정답 권고 전문, 같은 소단원의 다른 권고를 한 화면에 보여 준다.
# 검수자는 이 출력을 ESMO PDF 옆에 두고 (1) 정답 권고가 그 쪽에 있고 질문의 답이 맞는지, (2) 같은 소단원에 이 환자에게
# 똑같이 맞는 권고가 더 있는지(있으면 expected_chunks에 ;로 추가)를 본다. 확인한 문항은 status를 reviewed로 바꾼다.
# 실행: team_project 폴더에서
#   python -m src.rag.review_eval            → 29문항 전부
#   python -m src.rag.review_eval E02 E05    → 고른 문항만
# 읽기만 하고 파일은 바꾸지 않는다. 색인·모델 없이 청크 JSON만 읽는다.
import argparse
import sys

from .chunk_store import load_guideline_chunks
from .evaluate import load_cases

CONDITIONS = (("setting", "병기"), ("subtype", "아형"), ("line", "차수"), ("biomarker_tags", "양성 마커"),
              ("negative_tags", "음성 마커"), ("metastatic_sites", "전이 부위"), ("menopausal_status", "폐경"),
              ("pcr", "pCR"), ("stage_at_diagnosis", "진단 시 병기"), ("high_risk_early", "조기 고위험"),
              ("prior_subclasses", "이전 치료"), ("prior_classes", "이전 치료 계열"))


def _short(chunk_id: str) -> str:
    """esmo-ebc-2024-02-hrpos-6308eb → hrpos-6308eb (평가 출력과 같은 줄임)."""
    return "-".join(chunk_id.split("-")[4:])


def _conditions(case: dict) -> str:
    parts = []
    for key, label in CONDITIONS:
        value = case.get(key)
        if isinstance(value, list):
            value = ", ".join(value)
        if value:
            parts.append(f"{label} {value}")
    return " · ".join(parts)


def render_case(case: dict, chunks: dict) -> str:
    """문항 하나의 검수용 글. chunks: {chunk_id: 청크} (권고 청크)."""
    expected = case["expected_chunks"]
    lines = [f"===== {case['case_id']} (status: {case.get('status') or 'draft'}) =====",
             f"질문: {case['query']}",
             f"환자 조건: {_conditions(case)}",
             f"원문 위치: {case.get('note') or '-'}",
             "",
             f"[정답 권고 {len(expected)}개]"]
    for cid in expected:
        c = chunks.get(cid)
        if c is None:
            lines.append(f"  ! {cid}: 청크 파일에 없음 (ID가 바뀌었는지 확인)")
            continue
        lines.append(f"  * {_short(cid)} (p{c.get('page_start')}, 차수 {', '.join(c.get('line') or [])})")
        lines.append(f"    {c['text']}")
    others = [c for c in chunks.values()
              if c.get("parent_id") in case["expected_parents"] and c["chunk_id"] not in expected]
    lines += ["", f"[같은 소단원의 다른 권고 {len(others)}개: 이 환자에게도 똑같이 맞으면 expected_chunks에 추가]"]
    for c in others:
        lines.append(f"  - {_short(c['chunk_id'])} (p{c.get('page_start')}, 차수 {', '.join(c.get('line') or [])}): "
                     f"{c['text']}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서 ≥·– 같은 기호가 깨지지 않게
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="평가 문제집 검수용 출력 (문항, 정답 권고, 같은 소단원의 다른 권고)")
    ap.add_argument("case_ids", nargs="*", help="보여 줄 문항 (예: E02 M14). 비우면 전부")
    args = ap.parse_args(argv)
    chunks = {c["chunk_id"]: c for c in load_guideline_chunks() if c.get("chunk_kind") == "recommendation"}
    cases = load_cases()
    wanted = {c.upper() for c in args.case_ids}
    if wanted - {c["case_id"] for c in cases}:
        sys.exit(f"문제집에 없는 문항: {sorted(wanted - {c['case_id'] for c in cases})}")
    for case in cases:
        if not wanted or case["case_id"] in wanted:
            print(render_case(case, chunks))


if __name__ == "__main__":
    main()
