"""llm/ 공용 인터페이스 테스트.

가짜 응답으로 도는 테스트는 Ollama 없이 돈다. 마지막 테스트만 실제 Ollama([extract] 모델, qwen3:14b)가 켜져 있을 때 돈다.
실행 (team_project 폴더에서): python -m pytest tests/llm
"""
import json

import pytest
import requests

import llm
from llm import LLMConfig, LLMOutputError, PatientDataError, complete_json, load_config

SCHEMA = {"type": "object", "required": ["er"], "additionalProperties": False,
          "properties": {"er": {"type": "string"}}}
MSG = [{"role": "user", "content": "ER : positive (80%)"}]


class FakeResponse:
    def __init__(self, content, status=200):
        self.status_code, self._content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(self.status_code)

    def json(self):
        return {"message": {"content": self._content}}


@pytest.fixture
def fake_ollama(monkeypatch):
    """requests.post를 가로채 미리 정한 응답을 차례로 돌려준다. 보낸 요청 본문은 calls에 쌓인다."""
    calls, replies = [], []

    def post(url, json=None, timeout=None):
        calls.append(json)
        return FakeResponse(replies.pop(0))

    monkeypatch.setattr(llm.requests, "post", post)
    return calls, replies


def cfg(**kw):
    return LLMConfig(**{"provider": "ollama", "model": "fake", "patient_data": True, **kw})


def test_config_sections():
    for task in ("extract", "extract_dev"):
        c = load_config(task)
        assert c.provider == "ollama" and c.patient_data and c.temperature == 0
    assert load_config("extract_dev", model="other").model == "other"
    with pytest.raises(KeyError):
        load_config("no_such_task")


def test_patient_data_blocks_external_provider(fake_ollama):
    calls, _ = fake_ollama
    with pytest.raises(PatientDataError):
        complete_json(MSG, SCHEMA, cfg(provider="anthropic"))
    assert calls == []  # 요청을 보내기 전에 막힘


def test_valid_reply_and_request_body(fake_ollama):
    calls, replies = fake_ollama
    replies.append('{"er": "80%"}')
    assert complete_json(MSG, SCHEMA, cfg()) == {"er": "80%"}
    body = calls[0]
    assert body["format"] == SCHEMA and body["stream"] is False
    assert body["options"]["temperature"] == 0 and "num_gpu" not in body["options"]
    assert body["think"] is False and body["options"]["num_predict"] == 4096


def test_cpu_device_turns_off_gpu(fake_ollama):
    calls, replies = fake_ollama
    replies.append('{"er": "80%"}')
    complete_json(MSG, SCHEMA, cfg(device="cpu"))
    assert calls[0]["options"]["num_gpu"] == 0


def test_retry_once_then_succeed(fake_ollama):
    calls, replies = fake_ollama
    replies += ['{"er": 80}', '{"er": "80%"}']  # 첫 응답은 타입이 틀림
    assert complete_json(MSG, SCHEMA, cfg()) == {"er": "80%"}
    assert len(calls) == 2
    assert "스키마에 맞지 않습니다" in calls[1]["messages"][-1]["content"]


def test_gives_up_after_retries(fake_ollama):
    _, replies = fake_ollama
    replies += ["not json", "still not json"]
    with pytest.raises(LLMOutputError):
        complete_json(MSG, SCHEMA, cfg())


def _ollama_up():
    try:
        return requests.get("http://127.0.0.1:11434/api/version", timeout=2).ok
    except requests.RequestException:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama 서버가 꺼져 있음")
def test_live_extract():
    c = load_config("extract")
    schema = {"type": "object", "required": ["er_quote", "pr_quote", "her2_quote"], "additionalProperties": False,
              "properties": {k: {"type": "string"} for k in ("er_quote", "pr_quote", "her2_quote")}}
    text = "ER : positive (80%)\nPR : 양성 60%\nHER2 (4B5): 1+"
    out = complete_json([{"role": "user", "content":
                          "다음 가상 병리 보고서에서 ER, PR, HER2가 적힌 구절을 원문 그대로 옮겨 JSON으로 답하라.\n" + text}],
                        schema, c)
    for v in out.values():
        assert v in text, f"원문에 없는 인용: {v!r} ({json.dumps(out, ensure_ascii=False)})"
