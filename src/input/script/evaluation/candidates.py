"""IN-2 후보 형식과, 정답 patient_state에서 "완벽한 후보 목록"을 만드는 함수 (notes/input_module_design.md §2 IN-2).

후보 하나는 LLM이 문서 하나에서 찾은 "이 칸의 값이 적힌 구절"이다. 값은 담지 않는다 (정규화는 IN-3 규칙).

    {"doc_id": "D4", "field": "receptors.er_percent", "quote": "ER positive (Allred 8, 5+3)",
     "specimen": "metastasis", "observed_date": "2023-04-16"}

- field: patient_state의 칸 경로. 이력·충돌 값도 같은 칸 이름 (고르는 것은 IN-4·IN-5).
  목록 칸은 항목 하나가 후보 하나다: treatment_history, imaging_findings, anthracycline_drug_dose.drugs.
- quote: 문서 원문 그대로의 구절. 위치(char_start·char_end)는 인용 확인 단계에서 코드가 계산한다.
- specimen, observed_date: 구절에 딸린 검체·관찰 날짜. 없으면 null.

정답에서 만든 후보를 IN-2 자리에 넣어 끝까지 돌리면 규칙 쪽을 LLM 없이 시험할 수 있다
(notes/input_llm_principles_priorities_2026-10-23.md §2 2번).
"""
from __future__ import annotations

KEYS = ("doc_id", "field", "quote", "specimen", "observed_date")


def from_expected(patient_state: dict) -> list[dict]:
    """정답 patient_state의 source가 있는 값마다 후보 하나. 순서는 정답 JSON에 나오는 순서."""
    out: list[dict] = []
    _walk(patient_state["fields"], [], out)
    for c in patient_state.get("conflicts", []):
        for e in c["candidates"]:
            out.append(_candidate(c["field"], e))
    return out


def _walk(x, path: list[str], out: list[dict]) -> None:
    if isinstance(x, dict):
        if isinstance(x.get("source"), dict):
            out.append(_candidate(".".join(path), x))
        for k, v in x.items():
            if k != "source":
                _walk(v, path if k == "history" else path + [k], out)
    elif isinstance(x, list):
        for v in x:
            _walk(v, path, out)


def _candidate(field: str, entry: dict) -> dict:
    s = entry["source"]
    return {"doc_id": s["doc_id"], "field": field, "quote": s["quote"],
            "specimen": entry.get("specimen"), "observed_date": entry.get("observed_date")}
