# tests/recommend/test_prompt_length.py
# 질문지 길이 (A 전달 src/input/handoff_recommend_prompt_to_B_2026-11-02.md): 소단원 반복 제거, 길이 제한, 빈 drugs·evidence 채우기.
# 청크 글은 모두 지어낸 테스트 문장이다 (지침·공고 원문을 옮기지 않는다).
import copy
import json

from src.recommend.llm_link import make_llm
from src.recommend.pipeline import recommend
from src.recommend.prompt import build_prompt, estimate_tokens, fit_prompt
from tests.recommend.test_recommend import GUIDE, INDEX_STATUS, REIMB, TODAY, bm, opt


def _with_parents():
    guide = copy.deepcopy(GUIDE)
    for g in guide:
        g["parent"] = {"chunk_id": "g-parent", "text": "지어낸 지침 소단원 시작. " + "본문 " * 20}
    reimb = copy.deepcopy(REIMB)
    for r in reimb:
        r["parent"] = {"chunk_id": "r-parent", "text": "지어낸 급여 소단원 본문 " * 50}
    return guide, reimb


def test_parent_text_once_and_no_reimbursement_parent():
    guide, reimb = _with_parents()
    text = build_prompt({}, bm(PIK3CA="positive"), guide, reimb)
    assert text.count("지어낸 지침 소단원 시작.") == 1           # 지침 소단원은 한 번만
    assert "지어낸 급여 소단원" not in text                             # 급여 소단원 본문은 넣지 않음
    assert text.count("소단원 [r-parent]") == 3 and text.count("소단원 [g-parent]") == 2   # ID는 남김


def test_estimate_tokens():
    assert estimate_tokens("가나다") == 3
    assert estimate_tokens("abcdef") == 2


def test_fit_prompt_drops_reimbursement_first_then_guideline():
    record = bm(PIK3CA="positive")
    full, g, r, log = fit_prompt({}, record, GUIDE, REIMB)
    assert (g, r, log) == (GUIDE, REIMB, [])
    size = estimate_tokens(full)
    _, g, r, log = fit_prompt({}, record, GUIDE, REIMB, budget=size + 256 - 1)
    assert g == GUIDE and len(r) == 2 and r[-1]["chunk_id"] == "r-pre" and "r-off" in log[0]
    _, g, r, log = fit_prompt({}, record, GUIDE, REIMB, budget=600)
    assert [c["chunk_id"] for c in g] == ["g-capi"] and r == []          # 지침 청크는 1개 남김
    assert log[-1].startswith("경고")


def test_pipeline_uses_budget_and_trimmed_chunks():
    seen = {}

    def llm(prompt):
        seen["prompt"] = prompt
        return {"options": [opt(reimbursement_citations=["r-off"])], "tests_needed": [], "out_of_scope": False,
                "conflicts": []}
    llm.prompt_budget = estimate_tokens(build_prompt({}, bm(PIK3CA="positive"), GUIDE, REIMB)) + 256 - 1
    rec, log, errors = recommend({}, bm(PIK3CA="positive"), GUIDE, REIMB, llm, INDEX_STATUS, "fake-local", TODAY)
    assert errors == [] and "[r-off]" not in seen["prompt"]
    assert any("청크 1개 뺌" in m for m in log)
    # 질문지에서 빠진 급여 청크도 후처리에는 넘긴다 (약이 맞는 행을 규칙으로 붙이도록, D 확인 VC-0101).
    # r-off는 olaparib 행이라 이 후보와 약이 달라 붙지 않고, 약이 맞는 r-fulv가 붙는다
    assert not any("받지 않은 청크 ID" in m for m in log)
    assert rec["options"][0]["reimbursement_citations"] == ["r-fulv"]


def test_make_llm_sets_budget():
    from llm import LLMConfig
    cfg = LLMConfig(provider="ollama", model="qwen3:14b", patient_data=True, num_ctx=16384, max_tokens=4096)
    assert make_llm(config=cfg, complete=lambda *a: {}).prompt_budget == 12288


def test_fill_empty_drugs_and_evidence():
    answer = json.dumps({"options": [opt(drugs=[], evidence="")], "tests_needed": [], "out_of_scope": False,
                         "conflicts": []})
    rec, log, errors = recommend({}, bm(PIK3CA="positive"), GUIDE, REIMB, lambda p: answer, INDEX_STATUS, "x", TODAY)
    o = rec["options"][0]
    assert errors == [] and o["drugs"] == ["fulvestrant", "capivasertib"] and o["evidence"] == "LoE I, GoR A"
    assert any("빈 칸을" in m for m in log)


def test_dropped_reimbursement_row_still_attached():
    """D 확인 (2026-11-04, VC-0101): 질문지 길이 제한으로 빠진 급여 행도 약이 맞으면 5번 규칙으로 붙는다."""
    def llm(prompt):
        return {"options": [opt(reimbursement_citations=[])], "tests_needed": [], "out_of_scope": False, "conflicts": []}
    # 급여 청크를 모두 뺄 만큼 작은 길이 제한 (지침 청크는 1개 남김)
    llm.prompt_budget = estimate_tokens(build_prompt({}, bm(PIK3CA="positive"), GUIDE[:1], [])) + 256
    rec, log, errors = recommend({}, bm(PIK3CA="positive"), GUIDE, REIMB, llm, INDEX_STATUS, "fake-local", TODAY)
    assert errors == [] and any("뺌" in m and "r-fulv" in m for m in log)
    assert rec["options"][0]["reimbursement_citations"] == ["r-fulv"]
