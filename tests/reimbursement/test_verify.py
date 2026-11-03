"""로컬 모델 초안 확인 (팀 사전 대조, 숫자 대조, 빠진 조건). 모델 서버 없이 돈다."""
import copy
import json

import pytest

from src.reimbursement import conditions as cm
from src.reimbursement.verify import flag_for_review, uncovered, verify_conditions
from test_conditions import GOOD, TEXT, _empty


def test_good_conditions_pass():
    assert verify_conditions(GOOD, TEXT) == []


@pytest.mark.parametrize("where, change, msg", [
    (("all_of", 1), {"field": "age", "op": "lt", "value": 40}, "칸 age이 다름"),           # '폐경 전'을 나이 칸에
    (("all_of", 1), {"value": ["postmenopausal"]}, "사전 값"),                               # '폐경 전'을 폐경 후로
    (("any_of", 0), {"value": 35}, "숫자와 다름"),                                           # '40세 미만'인데 35
])
def test_wrong_field_value_number_are_flagged(where, change, msg):
    bad = copy.deepcopy(GOOD)
    it = bad["all_of"][where[1]] if where[0] == "all_of" else bad["any_of"][0]["items"][where[1]]
    it.update(change)
    issues = verify_conditions(bad, TEXT)
    assert issues and msg in issues[0][0] and issues[0][1] == it["text"]


def test_missing_condition_is_flagged():
    bad = copy.deepcopy(GOOD)
    bad["all_of"] = [x for x in bad["all_of"] if x["field"] != "menopause"]               # '폐경 전'을 빠뜨림
    assert any("폐경전" in run for run in uncovered(bad, TEXT))
    cond, msgs = flag_for_review(bad, TEXT)
    assert msgs and any("폐경전" in h for h in cond["human_review"]) and cm.check_grounding(cond, TEXT) == []


def test_numbers_in_names_and_units():
    cond = _empty(all_of=[
        {"id": "c1", "field": "pathologic_size_mm", "op": "gt", "value": 10, "text": "1cm를 초과"},
        {"id": "c2", "field": "days_end_to_recurrence", "op": "lte", "value": 183, "text": "6개월 이내"},
        {"id": "c3", "field": "palliative_chemo_lines", "op": "eq", "value": 0,
         "text": "CDK4/6 inhibitor 병용 시 고식적 항암화학요법을 투여하지 않은"},
        {"id": "c4", "field": "palliative_chemo_lines", "op": "gte", "value": 1, "text": "2차 이상"}])
    assert verify_conditions(cond, "1cm를 초과 6개월 이내") == []


def test_two_answers_that_differ_go_to_review():
    """다른 질문으로 만든 두 번째 답과 판정 항목이 다르면 다른 항목의 구절을 human_review에 넣는다."""
    from src.reimbursement.verify import disagreements
    other = copy.deepcopy(GOOD)
    other["any_of"][0]["items"].pop()                                     # 두 번째 답은 '종양분화도 2∼3'을 빠뜨림
    other["all_of"][0]["id"] = "x"                                        # id·글 차이는 같은 답
    assert disagreements(GOOD, copy.deepcopy(GOOD), TEXT) == []
    diff = disagreements(GOOD, other, TEXT)
    assert len(diff) == 1 and "grade" in diff[0][0] and diff[0][1] == "종양분화도 2∼3"
    cond, msgs = flag_for_review(GOOD, TEXT, diff)
    assert cond["human_review"] == ["종양분화도 2∼3"] and cm.check_grounding(cond, TEXT) == []
    # 구절을 알 수 없는 문제(두 번째 답 실패)도 첫 항목 구절로 행을 '알 수 없음'으로 만든다
    cond, _ = flag_for_review(GOOD, TEXT, [("두 번째 답을 받지 못함", None)])
    assert cond["human_review"] == [GOOD["all_of"][0]["text"]]


def test_second_opinion_uses_other_examples(monkeypatch):
    import types
    import requests
    import llm
    monkeypatch.setattr(requests, "get", lambda url, timeout: types.SimpleNamespace(
        json=lambda: {"models": [{"name": "m"}]}))
    seen = []
    monkeypatch.setattr(llm, "complete_json", lambda msgs, schema, config: seen.append(msgs) or GOOD)
    s = cm.OllamaStructurer(model="m", similar=1)
    pool = [{"chunk_id": f"r{i}", "text": t, "conditions": GOOD} for i, t in enumerate(["가 나 다", "가 나", "라"])]
    s.prepare({"chunk_id": "t", "text": "가 나 다 마", "drugs": []}, pool)
    first = s.messages("본문", "")
    s.second_opinion("본문", "")
    assert "가 나 다" in first[1]["content"] and "가 나\n" not in first[1]["content"]
    assert seen[-1][1]["content"].endswith("가 나") and s.messages("본문", "") == first     # 예시는 되돌린다


def test_reviewed_rows_are_not_flagged():
    """사람이 쓴 저장본 조건은 확인에 하나도 걸리지 않는다 (확인 규칙이 저장본 관례와 맞는지)."""
    cur = cm.DATA / "chunks" / "reimbursement_chunks_current.jsonl"
    if not cur.exists():
        pytest.skip("청크 파일 없음")
    n = 0
    for c in map(json.loads, open(cur, encoding="utf-8")):
        cond = cm._stored(c) if c["chunk_kind"] in cm.TARGET_KINDS else None
        if cond:
            n += 1
            assert verify_conditions(cond, c["text"]) == [], c["chunk_id"]
    assert n > 100
