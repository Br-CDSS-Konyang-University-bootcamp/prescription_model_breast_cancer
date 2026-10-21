# tests/recommend/test_llm_link.py
# 추천 모듈 ↔ llm/ 연결 (llm_link.py). 실제 모델 없이 가짜 complete 함수로 시험한다.

import pytest
from jsonschema import Draft202012Validator

from llm import LLMConfig, LLMOutputError
from src.recommend.llm_link import NonLocalLLMError, answer_schema, check_local, make_llm
from src.recommend.pipeline import recommend
from tests.recommend.test_recommend import GUIDE, INDEX_STATUS, REIMB, TODAY, bm, opt

LOCAL = LLMConfig(provider="ollama", model="fake-local", patient_data=True)


def test_local_config_passes():
    check_local(LOCAL)
    check_local(LLMConfig(provider="ollama", model="m", patient_data=True, host="http://localhost:11434"))


@pytest.mark.parametrize("cfg", [
    LLMConfig(provider="ollama", model="m", patient_data=True, host="http://192.168.0.10:11434"),   # 다른 PC
    LLMConfig(provider="ollama", model="m", patient_data=True, host="https://example.com"),          # 외부 서버
    LLMConfig(provider="anthropic", model="m", patient_data=True),                                  # 외부 provider
    LLMConfig(provider="ollama", model="m", patient_data=False),                                    # 보호 모드 꺼짐
])
def test_non_local_config_stops_before_sending(cfg):
    sent = []
    with pytest.raises(NonLocalLLMError):
        make_llm(config=cfg, complete=lambda *a: sent.append(a))
    assert sent == []


def test_answer_schema_is_llm_part_of_recommendation():
    schema = answer_schema()
    assert set(schema["properties"]) == {"options", "tests_needed", "out_of_scope", "out_of_scope_reason", "conflicts"}
    Draft202012Validator.check_schema(schema)
    good = {"options": [opt()], "tests_needed": [], "out_of_scope": False, "conflicts": []}
    assert not list(Draft202012Validator(schema).iter_errors(good))
    assert list(Draft202012Validator(schema).iter_errors({**good, "patient_ref": "VC-1"}))   # LLM이 채우는 칸이 아님


def test_make_llm_sends_prompt_with_schema_and_returns_dict():
    seen = {}

    def fake_complete(messages, schema, config):
        seen.update(messages=messages, schema=schema, config=config)
        return {"options": [opt()], "tests_needed": [], "out_of_scope": False, "conflicts": []}
    ask = make_llm(config=LOCAL, complete=fake_complete)
    out = ask("질문지")
    assert seen["messages"] == [{"role": "user", "content": "질문지"}] and seen["schema"] == answer_schema()
    assert out["options"][0]["therapy"] == "fulvestrant + capivasertib"


def test_recommend_accepts_dict_answer_from_llm_link():
    ask = make_llm(config=LOCAL, complete=lambda m, s, c: {"options": [opt()], "tests_needed": [],
                                                           "out_of_scope": False, "conflicts": []})
    rec, log, errors = recommend({}, bm(PIK3CA="positive"), GUIDE, REIMB, ask, INDEX_STATUS, "fake-local", TODAY)
    assert errors == [], errors
    assert [o["therapy"] for o in rec["options"]] == ["fulvestrant + capivasertib"]


def test_recommend_out_of_scope_when_llm_never_fits_schema():
    def broken(m, s, c):
        raise LLMOutputError("스키마에 맞지 않음")
    rec, log, errors = recommend({}, bm(), GUIDE, REIMB, make_llm(config=LOCAL, complete=broken), INDEX_STATUS,
                                 "fake-local", TODAY)
    assert errors == [] and rec["out_of_scope"] is True and rec["options"] == []
    assert any("스키마" in line for line in log)
