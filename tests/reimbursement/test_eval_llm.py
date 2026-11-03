"""로컬 모델 비교(eval_llm)의 항목 비교 규칙. 모델 서버 없이 돈다."""
from src.reimbursement.eval_llm import compare, item_keys, similar_rows

REF = {
    "all_of": [{"id": "c1", "field": "her2", "op": "eq", "value": "positive", "text": "HER2 양성인"}],
    "any_of": [{"text": "하나", "items": [
        {"id": "a1", "field": "pn_status", "op": "eq", "value": "positive", "text": "림프절 양성"},
        {"id": "a2", "field": "pathologic_size_mm", "op": "gt", "value": 10, "text": "1cm를 초과"}]}],
    "counts_as_prior_line": [{"text": "간주", "setting": ["adjuvant"], "drugs": ["trastuzumab", "taxane"],
                              "rule_id": "DEEM-HER2ADC-6M"}],
    "human_review": [], "unmapped": [],
}


def test_same_conditions_with_other_text_and_ids_match():
    got = {**REF, "all_of": [{**REF["all_of"][0], "id": "x9", "text": "다른 글"}],
           "counts_as_prior_line": [{**REF["counts_as_prior_line"][0], "drugs": ["taxane", "trastuzumab"]}]}
    r = compare(REF, got)
    assert r == {"ref_items": 4, "got_items": 4, "common": 4, "exact": True}


def test_similar_rows_skip_self_and_rank_by_words():
    rows = [{"chunk_id": cid, "text": f"[머리]\n{t}"} for cid, t in [
        ("r01", "palbociclib + letrozole 호르몬 수용체 양성 HER2 음성 폐경 후 (제2020-155호: 2020.6.1.)"),
        ("r03", "abemaciclib + letrozole 호르몬 수용체 양성 HER2 음성 폐경 후 (제2021-1호: 2021.1.1.)"),
        ("r09", "trastuzumab deruxtecan HER2 양성 2차 이상")]]
    got = similar_rows(rows[0], rows, 2)
    assert [c["chunk_id"] for c in got] == ["r03", "r09"]          # 자기 자신은 빼고, 공고 번호·날짜는 비교하지 않음


def test_place_and_value_matter():
    moved = {**REF, "all_of": REF["all_of"] + REF["any_of"][0]["items"][:1]}         # any_of 항목을 all_of로
    assert compare(REF, moved)["common"] == 4 and not compare(REF, moved)["exact"]
    wrong = {**REF, "any_of": [{"text": "하나", "items": [REF["any_of"][0]["items"][0],
                                                       {**REF["any_of"][0]["items"][1], "op": "gte"}]}]}
    assert compare(REF, wrong)["common"] == 3
    assert not compare(REF, {**REF, "unmapped": ["못 옮김"]})["exact"]                  # 못 옮긴 조건이 있으면 다름
    assert len(item_keys(REF)) == 4
