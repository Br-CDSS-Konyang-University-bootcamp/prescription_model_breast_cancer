# confirmed_state → [4] LLM 추천 연결 전달 문서 (A → B)

작성: 2026-10-21. 담당 A. 받는 사람 B ([4] `src/recommend/`). C(`src/rag/retrieve.py`)와 D(급여 조건)도 함께 본다.

## 1. 무엇이 바뀌나

전체 흐름이 2단계로 바뀐다. 1단계에서는 의사가 화면 1에서 환자 상태를 확정하고, 2단계에서는 확정값만으로 처방·급여를 판정한다.

```
[1단계] 차트 txt ─▶ A ─▶ patient_state ─▶ B assess() ─▶ biomarker_record ─▶ 화면 1 (의사 확정) ─▶ confirmed_state
[2단계] confirmed_state ─┬─▶ C retrieve_for_recommend ─┐
                         └─▶ D 급여 조건 ──────────────┴─▶ B recommend() + 로컬 LLM ─▶ recommendation ─▶ 화면 2
```

2단계(`retrieve_for_recommend`, `recommend()`, `postprocess`, 급여 조건 판정기)의 입력이 바뀐다. 지금은 `patient_state` + `biomarker_record`를 받지만, 앞으로는 **`confirmed_state` 하나**를 받는다. 이 파일의 `items.*.confirmed`만 읽는다.

## 2. 이번에 넣은 파일

| 파일 | 내용 |
|---|---|
| `schemas/confirmed_state.json` | JSON Schema 초안 (0.1-draft). 설명은 `schemas/README.md` §9 |
| `tests/fixtures/virtual_charts/VC-0103/expected/confirmed_state.json` | VC-0103 확정 예시 (전이성, 내분비 1차 결정). 스키마 검증 통과. LLM 첫 시험 입력으로 쓴다 |
| 이 문서 | B가 할 일 |

검증:

```python
import json
from jsonschema import Draft202012Validator
schema = json.load(open("schemas/confirmed_state.json", encoding="utf-8"))
data = json.load(open("tests/fixtures/virtual_charts/VC-0103/expected/confirmed_state.json", encoding="utf-8"))
Draft202012Validator(schema).validate(data)
```

## 3. 지금 상태 (2026-10-21 origin/main 기준)

| 부분 | 상태 |
|---|---|
| `recommend()` (`src/recommend/pipeline.py`) | 틀은 있다: 프롬프트 → LLM → 파싱 → 후처리 → `recommendation.json` 스키마 검사. LLM은 "프롬프트 글 → 답 글" 함수로 받는다 |
| 실제 LLM | **연결 안 됨** |
| `llm/` 공용 인터페이스 | `load_config()`, `complete_json()`, Ollama 호출은 있다. `llm/config.toml`에는 A의 `[extract]`·`[extract_dev]`만 있고 추천용 칸이 없다 |
| 입력 | `build_prompt`, `postprocess`, `retrieve_for_recommend` 모두 `biomarker_record`를 읽는다 |

## 4. B가 할 일

1. **LLM 연결.** `llm/config.toml`에 추천용 칸(예: `[recommend]`)을 추가한다. 이 칸은 `provider = "ollama"`, `patient_data = true`로 둔다. `complete_json`을 감싼 함수를 `recommend(..., llm=...)`에 넘긴다. `llm/`은 공용 폴더이므로 4명 검토 규칙을 따른다.
2. **입력 바꾸기.** `recommend(confirmed_state, guideline_chunks, reimbursement_chunks, llm, index_status, model_name, ...)` 형태로 바꾼다. 읽는 값의 대응은 §5에 있다.
3. **C에 요청.** `retrieve_for_recommend(confirmed_state, as_of)`로 바꾼다. 필터는 `subtype`, `setting.disease`, 차수를 쓴다. 차수는 내분비/항암 중 이번에 고를 요법 종류에 맞춘다. 이전 약제는 `prior_regimens[].subclasses`를 쓴다.
4. **첫 시험.** VC-0103 예시 + C·D 청크로 `recommend()`를 돌린다. 나온 `recommendation.json`이 스키마를 통과하는지, scenario.md 기대값과 맞는지 본다. 기대값은 fulvestrant + CDK4/6가 1안이고, 보조 AI 투여 중 재발이라 3가 AI + CDK4/6는 급여 조건 불충족이다.

## 5. 지금 읽는 값 → confirmed_state 값

| 지금 (`build_prompt`·`postprocess`·`retrieve`) | confirmed_state | 차이 |
|---|---|---|
| `biomarker_record.subtype` | `items.subtype.confirmed` | `unknown` 없음 |
| `biomarker_record.setting.disease` | `items["setting.disease"].confirmed` | `unknown` 없음 |
| `biomarker_record.setting.line` | 전이성: `items["setting.line_endocrine"]`, `items["setting.line_chemo"]` / 조기: `items["setting.phase"]` | **나뉨.** "이번에 결정할 차수"다. 간주 규칙은 반영하지 않고 `items.deemed_lines`로 따로 준다 (급여 판정에서 약제별 +1) |
| `biomarker_record.setting.reason` | `items.*.reason`, `memo` | 의사가 바꾼 이유 |
| `biomarker_record.setting.prior_drug_classes` | `items.prior_regimens.confirmed[].subclasses` | `drug_classes.csv`의 `drug_subclass` 수준 (AI_nonsteroidal, CDK4/6_inhibitor …). 급여 3가 "비스테로이드성 AI 이력"에 바로 쓸 수 있다 |
| `biomarker_record.records[]` {marker, status} | `items.markers.<마커>.confirmed` (+ `detail`) | 마커 이름: `gBRCA1`·`gBRCA2` → **`gBRCA` 하나**, `sBRCA1`·`sBRCA2` → `sBRCA`. `drug_biomarker.csv`의 마커 이름과 맞출 것. 판정 불가 값(`unknown`)은 들어오지 않는다 |
| `biomarker_record.tests_needed` | 없음 | 검사 권고는 1단계(B `assess()`) 출력이다. 2단계에 넘길지, 화면 1에서 의사가 고른 것만 넘길지 정해야 한다 (§6 4번) |
| `patient_state` `menopausal_status` | `items.menopausal_status.confirmed` | pre/post 두 값만 (peri → pre) |
| `patient_state` `metastatic_sites` | `items.metastatic_sites.confirmed` | |
| `patient_state` `treatment_history[]` | `items.prior_regimens.confirmed[]` {drugs, subclasses, setting, start_day, end_day, line_endocrine, line_chemo, response, stop_reason} | 항상 전체 목록 |
| `patient_state` `histology` | 없음 | 처방·급여 조건에 없어 확정 항목에서 뺐다. 필요하면 추가 요청 |
| 없음 | `endocrine_relapse_12m`, `dfi_days`, `high_risk_early`, `pcr`, `stage.*`, `grade`, `age_at_index` | 새로 쓸 수 있는 조건 값 (ESMO M02/M03 분기, TNBC DFI, abemaciclib 고위험, 보조 T-DM1·capecitabine 등) |

## 6. 같이 정할 것

| 번호 | 정할 것 | A 제안 |
|---|---|---|
| 1 | `setting.line`의 뜻: 받은 차수인가, 결정할 차수인가 | 결정할 차수. 지금 `assess()`는 전이 후 투약이 없으면 `unknown`이다. 그래서 VC-0103 예시는 의사가 1L로 고친 값(`status: changed`)이다 |
| 2 | 내분비·항암 차수 분리 | `assess()` 출력에도 `line_endocrine`·`line_chemo`를 두어 화면 1 기본값으로 쓴다 |
| 3 | 차트의 BRCA 이름 | gBRCA (A 결정 2026-10-21). 예시의 gBRCA 값은 `assess()`가 낸 `sBRCA1/2`를 옮긴 것이다 |
| 4 | 검사 권고(`tests_needed`)를 2단계에 넘기는 방법 | `confirmed_state`에 `tests_needed` 칸을 추가해 화면 1의 권고 목록을 그대로 넘기는 안. 스키마 변경이 필요해 지금은 넣지 않았다 |
| 5 | 계산 항목 위치 | `endocrine_relapse_12m`은 A의 `deemed_lines`(DEEM-ENDO-ADJ-1Y)로 채운다. `dfi_days`·`high_risk_early`는 A(`lines.py`) 또는 B 중에서 정한다 |

확정 항목을 고른 근거, 초진·재진 구분, 판독이 결정되지 않은 값 17건은 A의 작업 노트(`notes/confirmed_state_items_2026-10-21.md`, 저장소 밖)에 있다. 필요하면 요청하면 된다.
