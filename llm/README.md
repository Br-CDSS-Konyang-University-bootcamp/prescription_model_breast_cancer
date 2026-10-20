# llm/ — 공용 LLM 인터페이스 (4명 합의)

로컬 모델(Ollama, vLLM)과 Claude API를 같은 함수로 부르고, 설정만 바꿔 모델을 교체한다.

- 환자 데이터를 다루는 모듈([1], [2], [4])은 로컬 설정만 쓴다.
- Claude API 설정은 공개 문서를 다루는 모듈([3] 평가용 질의 생성, [5] 공고 구조화)만 쓴다.
- API 키는 `.env`에 둔다.

## 사용법 (2026-10-20 초안, 담당 A)

```python
from llm import load_config, complete_json

cfg = load_config("extract")          # llm/config.toml의 [extract] 칸
out = complete_json(
    [{"role": "user", "content": "..."}],
    schema,                           # JSON 스키마 (dict)
    cfg,
)
```

- `complete_json`은 JSON 스키마에 맞는 응답 하나를 돌려준다. 온도 0. 맞지 않으면 오류 내용을 붙여 한 번 더 요청하고, 그래도 안 되면 `LLMOutputError`.
- `patient_data = true`인 설정은 로컬 provider(`ollama`)만 허용한다. 외부 provider면 요청을 보내기 전에 `PatientDataError`.
- 모델을 바꿀 때는 `config.toml`만 고친다. 코드에서 잠깐 바꾸려면 `load_config("extract", model="qwen2.5:7b")`.
- `device = "auto"`: Ollama가 GPU를 스스로 찾고 없으면 CPU. `"cpu"`면 GPU를 쓰지 않는다.
- `think = false`(기본): 생각 모드를 끈다. hari-q3-8b(Qwen3 기반)는 켜 두면 답 전에 생각 문장만 길게 만들어 CPU에서 10분 넘게 걸렸다 (2026-10-20). 끄고 JSON 형식을 강제하면 같은 시험이 7초.
- `max_tokens = 4096`(기본): 출력 길이 상한. 생각·반복이 끝없이 이어질 때 멈춘다.

## 설정 (`config.toml`)

| 칸 | 쓰는 곳 | 모델 | 비고 |
|---|---|---|---|
| `[extract]` | [1] IN-2 필드 추출 | `hf.co/mradermacher/hari-q3-8b-GGUF:Q4_K_M` | 2026-10-19 결정 (`notes/llm_components.md`) |
| `[extract_dev]` | 개발·시험 | `hf.co/mradermacher/hari-q3-8b-GGUF:Q4_K_M` | 2026-10-20 hari로 통일. 비교할 때만 `load_config("extract", model="qwen2.5:7b")` |

다른 모듈은 자기 칸을 추가해 쓴다 (예: `[biomarker_parse]`, `[recommend]`).

## 지금 구현된 것

| provider | 상태 |
|---|---|
| `ollama` | 구현. `/api/chat`에 JSON 스키마(`format`)를 넘김 |
| `anthropic` (Claude API) | 아직 없음. [3]·[5]가 필요할 때 추가 |
| vLLM | 아직 없음. 운영 단계에서 추가 |

## 준비

1. Ollama 설치 (각자 PC, conda 밖)
2. 모델 받기: `ollama pull qwen2.5:7b`, `ollama pull hf.co/mradermacher/hari-q3-8b-GGUF:Q4_K_M`
3. 테스트 (team_project 폴더에서): `python -m pytest tests/llm`. 마지막 테스트는 Ollama가 켜져 있을 때만 실제 `[extract]` 모델(hari-q3-8b)로 돈다.

CPU만 있는 PC에서는 7~8B 모델이 초당 약 7~8 토큰이라 차트 문서 하나에 1~3분 걸린다.
