"""[4] 추천 모듈과 공용 llm/ 인터페이스를 잇는다 (llm/README.md, A 전달 문서 handoff_confirmed_state_to_B.md §4 1번).

make_llm()이 돌려주는 함수를 recommend(..., llm=...)에 넣는다. 함수는 질문지 글을 받아 답 사전을 돌려준다.
환자 정보가 든 질문지는 이 PC의 로컬 모델에만 보낸다 (CLAUDE.md, PROJECT.md §2).
llm/의 patient_data 확인은 provider 이름만 본다. 여기서는 주소(host)가 이 PC인지도 확인한다 (B 판단 2026-10-21).
"""
import copy
import json
from pathlib import Path
from urllib.parse import urlparse

from llm import LOCAL_PROVIDERS, complete_json, load_config

RECOMMENDATION_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "recommendation.json"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
# recommendation.json 중 LLM이 채우는 칸. 나머지(schema_version, patient_ref, 만든 시각, 모델, index_status)는 recommend()가 붙인다
# supportive_options(골 보호제 보조 약물, 2026-11-04 팀 안건 A)는 선택 칸이라 LLM_REQUIRED에 넣지 않는다
LLM_FIELDS = ("options", "supportive_options", "tests_needed", "out_of_scope", "out_of_scope_reason", "conflicts")
LLM_REQUIRED = ["options", "tests_needed", "out_of_scope", "conflicts"]


class NonLocalLLMError(RuntimeError):
    """환자 정보가 든 질문지를 이 PC 밖의 모델로 보내려 할 때."""


def _lenient(prop):
    """후보 목록 칸에서 후보 하나의 규칙(인용 1개 이상, 급여 분류가 있으면 급여 인용 1개 이상)을 뺀다.
    LLM 답은 이 양식으로 검사해 맞지 않으면 답 전체를 버리는데, 후보 하나의 빈칸 때문에 후보가 모두 사라졌다
    (A 전달 handoff_recommend_options_to_B_2026-11-03.md §5.3, VC-0110·0114·0116). 그 규칙은 후처리가 고치고
    (인용 없는 후보는 지우고, 급여 인용이 비면 약이 맞는 행을 붙이거나 급여 기준 없음), 최종 결과는 validate.py가
    전체 스키마로 다시 검사한다."""
    prop = copy.deepcopy(prop)
    items = prop.get("items") or {}
    items.pop("allOf", None)
    for v in (items.get("properties") or {}).values():
        v.pop("minItems", None)
    return prop


def answer_schema():
    """LLM 답 양식: schemas/recommendation.json에서 LLM이 채우는 칸만 뗀다. 후보 목록은 _lenient로 느슨하게."""
    with open(RECOMMENDATION_SCHEMA, encoding="utf-8") as fh:
        props = json.load(fh)["properties"]
    return {"type": "object", "required": LLM_REQUIRED, "additionalProperties": False,
            "properties": {k: _lenient(props[k]) if k in ("options", "supportive_options") else props[k]
                           for k in LLM_FIELDS}}


def check_local(config):
    """설정이 이 PC의 로컬 모델인지 확인한다. 아니면 NonLocalLLMError."""
    host = urlparse(config.host).hostname
    if not config.patient_data:
        raise NonLocalLLMError("추천 설정은 patient_data = true여야 한다 (환자 정보가 질문지에 들어감)")
    if config.provider not in LOCAL_PROVIDERS:
        raise NonLocalLLMError(f"로컬 provider만 쓴다: provider={config.provider!r}")
    if host not in LOCAL_HOSTS:
        raise NonLocalLLMError(f"이 PC 주소(127.0.0.1, localhost)만 쓴다: host={config.host!r}")


def make_llm(task="recommend", config=None, complete=complete_json):
    """recommend()의 llm 함수. config를 주지 않으면 llm/config.toml의 [task] 칸을 읽는다.
    complete는 시험용으로 바꿀 수 있다 (기본 llm.complete_json)."""
    config = config or load_config(task)
    check_local(config)
    schema = answer_schema()

    def ask(prompt):
        check_local(config)
        return complete([{"role": "user", "content": prompt}], schema, config)
    ask.prompt_budget = config.num_ctx - config.max_tokens   # 질문지 + 답이 num_ctx 안에 들도록 (A 전달 2026-11-02)
    return ask
