"""공용 LLM 인터페이스 (llm/README.md, notes/input_module_design.md §3).

모든 모듈은 complete_json 하나로 LLM을 부른다. 모델은 llm/config.toml의 작업 이름(예: "extract")으로 고른다.

    from llm import load_config, complete_json
    cfg = load_config("extract")
    out = complete_json([{"role": "user", "content": "..."}], schema, cfg)

환자 데이터 보호: patient_data=True 설정은 로컬 provider("ollama")만 허용하고, 그 밖이면 호출 전에 예외를 낸다.
"""
from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

import requests
from jsonschema import Draft202012Validator

CONFIG_PATH = Path(__file__).with_name("config.toml")
LOCAL_PROVIDERS = {"ollama"}


class PatientDataError(RuntimeError):
    """환자 데이터를 외부 provider로 보내려 할 때."""


class LLMOutputError(RuntimeError):
    """재시도 후에도 응답이 JSON 스키마에 맞지 않을 때."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str                 # "ollama" (지금 구현된 것) | "anthropic" (예정)
    model: str                    # 예: "qwen2.5:7b"
    patient_data: bool            # True면 로컬 provider만 허용
    temperature: float = 0.0
    device: str = "auto"          # auto: 실행기가 GPU를 스스로 찾음 / cpu: GPU를 쓰지 않음
    host: str = "http://127.0.0.1:11434"
    num_ctx: int = 8192           # 문맥 길이 (토큰)
    timeout: int = 600            # 초. CPU에서는 문서 하나에 수 분 걸릴 수 있음
    retries: int = 1              # 스키마에 맞지 않을 때 다시 요청하는 횟수
    think: bool = False           # 생각 모드 (Qwen3 계열). 켜면 CPU에서 답 전에 수 분씩 생각만 함 (2026-10-20 hari 시험)
    max_tokens: int = 4096        # 출력 길이 상한. 생각·반복이 끝없이 이어질 때 멈추게 함


def load_config(task: str, path: Path = CONFIG_PATH, **override) -> LLMConfig:
    """config.toml의 [task] 칸을 읽는다. override로 칸 하나를 바꿀 수 있다 (예: model="qwen2.5:7b")."""
    with open(path, "rb") as f:
        table = tomllib.load(f)
    if task not in table:
        raise KeyError(f"{path.name}에 [{task}] 설정이 없음 (있는 것: {', '.join(table)})")
    return replace(LLMConfig(**table[task]), **override)


def complete_json(messages: list[dict], schema: dict, config: LLMConfig) -> dict:
    """JSON 스키마에 맞는 응답 하나를 돌려준다. 맞지 않으면 오류를 붙여 config.retries번 다시 요청한다."""
    if config.patient_data and config.provider not in LOCAL_PROVIDERS:
        raise PatientDataError(f"환자 데이터는 로컬 모델만 쓴다: provider={config.provider!r}")
    validator = Draft202012Validator(schema)
    msgs = list(messages)
    for attempt in range(config.retries + 1):
        text = _call(msgs, schema, config)
        try:
            out = json.loads(text)
            errors = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(out)]
        except json.JSONDecodeError as e:
            out, errors = None, [f"JSON이 아님: {e}"]
        if not errors:
            return out
        msgs = msgs + [{"role": "assistant", "content": text},
                       {"role": "user", "content": "응답이 JSON 스키마에 맞지 않습니다. 오류를 고쳐 JSON만 다시 답하세요.\n"
                                                    + "\n".join(errors[:10])}]
    raise LLMOutputError(f"{config.retries + 1}번 요청했지만 스키마에 맞지 않음: {errors[:3]}")


def _call(messages: list[dict], schema: dict, config: LLMConfig) -> str:
    if config.provider == "ollama":
        return _ollama(messages, schema, config)
    raise NotImplementedError(f"provider {config.provider!r}는 아직 구현하지 않음 (llm/README.md)")


def _ollama(messages: list[dict], schema: dict, config: LLMConfig) -> str:
    options = {"temperature": config.temperature, "num_ctx": config.num_ctx, "num_predict": config.max_tokens}
    if config.device == "cpu":
        options["num_gpu"] = 0
    body = {"model": config.model, "messages": messages, "format": schema, "stream": False, "options": options,
            "think": config.think}
    r = requests.post(f"{config.host}/api/chat", json=body, timeout=config.timeout)
    if r.status_code == 404:
        raise RuntimeError(f"Ollama에 모델이 없음: {config.model} (ollama pull {config.model})")
    r.raise_for_status()
    return r.json()["message"]["content"]
