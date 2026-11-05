# confirmed_state → [4] LLM 추천 연결 전달 문서 (A → B)

작성: 2026-10-21. 갱신: 2026-11-05 (§2~§6을 지금 코드와 결정에 맞춤). 담당 A. 받는 사람 B ([4] `src/recommend/`). C(`src/rag/retrieve.py`)와 D(급여 조건)도 함께 본다.

## 1. 무엇이 바뀌나

전체 흐름은 2단계다. 1단계에서는 의사가 화면 1에서 환자 상태를 확정하고, 2단계에서는 확정값으로 처방·급여를 판정한다.

```
[1단계] 차트 txt ─▶ A ─▶ patient_state ─▶ B assess() ─▶ biomarker_record ─▶ 화면 1 (의사 확정) ─▶ confirmed_state
[2단계] confirmed_state ─┬─▶ C retrieve_for_recommend ─┐
                         └─▶ D 급여 조건 ──────────────┴─▶ B recommend() + 로컬 LLM ─▶ recommendation ─▶ 화면 2
```

목표는 2단계(`retrieve_for_recommend`, `recommend()`, `postprocess`, 급여 조건 판정기)가 **`confirmed_state` 하나**만 받고, 이 파일의 `items.*.confirmed`만 읽는 것이다. **2026-11-05 현재는 C만 이렇게 읽는다.** B와 D는 아직 `patient_state` + `biomarker_record`를 읽는다 (§3). 바꿀지는 4명이 정한다 (`draft7_checklist_BCD_2026-10-28.md` §5 1번).

## 2. 관련 파일

| 파일 | 내용 |
|---|---|
| `schemas/confirmed_state.json` | JSON Schema 초안 (0.1-draft). 설명은 `schemas/README.md` §9 |
| `src/input/script/confirmed.py` | 화면 1 초안(`build_draft`), 칸 수정(`set_item`), 확정 저장(`finalize`). 계산 항목(`dfi_days`, `high_risk_early`, `setting.phase` 등)도 여기서 만든다. 테스트 `tests/input/test_confirmed.py` |
| `tests/fixtures/virtual_charts/<case>/expected/confirmed_state.json` | 가상 차트별 정답 확정값. VC-0103은 손으로 만들었고, 나머지는 `python -m src.app.script.confirmed_fixtures`가 만든다 (VC-0106b, VC-0129 제외). 검토표 `confirmed_review.csv` |
| `src/app/script/screen1.py`, `screen2.py` | 화면 1(확정), 화면 2(추천과 선택) |
| `src/app/script/run_flow.py` | 화면 없이 2단계만 전체 사례에 돌린다. 결과 `data/app/runs/<이름>/summary.csv` |
| 이 문서 | B가 할 일 |

검증:

```python
import json
from jsonschema import Draft202012Validator
schema = json.load(open("schemas/confirmed_state.json", encoding="utf-8"))
data = json.load(open("tests/fixtures/virtual_charts/VC-0103/expected/confirmed_state.json", encoding="utf-8"))
Draft202012Validator(schema).validate(data)
```

## 3. 지금 상태 (2026-11-05 main 기준)

| 부분 | 상태 |
|---|---|
| 실제 LLM | **연결됨.** `llm/config.toml`의 `[recommend]` qwen3:14b (B, 2026-11-02 `b2357e4`). GPU 서버에 SSH 터널(127.0.0.1:11435)로 붙는다 |
| C 검색 | `retrieve_for_recommend(confirmed_state, as_of)`. `items.*.confirmed`만 읽는다 |
| B `recommend()` | `recommend(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, llm, index_status, model_name, today=None, conditions_checker=None, confirmed_state=None)`. 프롬프트의 아형·차수·마커는 `biomarker_record`에서 읽는다. `confirmed_state`는 세 곳에만 쓴다: 치료 단계(`setting.phase`), 골 보조약 판단(`metastatic_sites`), 참고란(`visceral_crisis`, `contraindicated_classes`) |
| 급여 판정기 | `make_conditions_checker(patient_state, biomarker_record)`. D의 조건 정의(`src/reimbursement/conditions.py` FIELDS)가 `patient_state` 경로로 적혀 있다 |
| 첫 시험 | VC-0103: 2026-11-04 시나리오 기대값과 일치. 46건 실행 결과는 `team_report_run_flow_2026-11-05.md` |

**지금 구조의 결과:** 의사가 화면 1에서 고친 값(아형, 마커, 차수, 폐경 상태, 이전 요법 등)은 C 검색에만 반영되고, B의 프롬프트와 급여 판정에는 반영되지 않는다.

## 4. B가 할 일

| 번호 | 할 일 | 상태 |
|---|---|---|
| 1 | **LLM 연결.** `llm/config.toml`에 `[recommend]`(`provider = "ollama"`, `patient_data = true`), `complete_json`을 감싼 함수를 `recommend(..., llm=...)`에 넘김 | 완료 (2026-11-02) |
| 2 | **입력 바꾸기.** `recommend()`와 급여 판정기가 `confirmed_state`의 확정값을 읽게 한다. 읽는 값의 대응은 §5에 있다. D의 조건 경로도 함께 바뀐다 | **남음.** 4명 결정 뒤 (draft7 체크리스트 §5 1번) |
| 3 | **C에 요청.** `retrieve_for_recommend(confirmed_state, as_of)`. 필터는 `subtype`, `setting.disease`, 차수(이번에 고를 요법 종류의 차수), 이전 약은 `prior_regimens[].subclasses` | 완료 |
| 4 | **첫 시험.** VC-0103 확정값 + C·D 청크로 `recommend()`. 기대값은 fulvestrant + CDK4/6가 1안이고, 보조 AI 투여 중 재발이라 AI + CDK4/6는 급여 조건 불충족 | 완료 (2026-11-04 일치) |

## 5. 지금 읽는 값 → confirmed_state 값

`items` 키 전체: `age_at_index`, `anthracycline_cumulative`, `bone_metastasis_imaging`, `cardiac_risk`, `contraindicated_classes`, `deemed_lines`, `dfi_days`, `endocrine_relapse_12m`, `grade`, `high_risk_early`, `markers`, `mediastinal_radiation`, `menopausal_status`, `metastasis_day`, `metastatic_sites`, `operable`, `pcr`, `prior_regimens`, `recent_therapy_28d`, `recurrence_day`, `recurrence_type`, `setting.disease`, `setting.line_chemo`, `setting.line_endocrine`, `setting.phase`, `stage.group`, `stage.n`, `stage.positive_ln_count`, `stage.size_mm`, `stage.t`, `subtype`, `visceral_crisis`.

필수는 `setting.disease`, `subtype`, `markers`(ER·PR·HER2)이다. 결정 범주에 따라 더 필요하다 (`confirmed.py`의 `required_items`):

- 전이성: `setting.line_endocrine`, `setting.line_chemo`, `prior_regimens`, `metastatic_sites`.
- 조기: `setting.phase`, `stage.t`, `stage.positive_ln_count`, `stage.group`.
- HR+: `menopausal_status`. 전이성이면 `endocrine_relapse_12m`도 필요하다.
- 전이성 TNBC: `dfi_days`, `markers.PD-L1`.

| 지금 (`build_prompt`·`postprocess`·급여 판정기) | confirmed_state | 차이 |
|---|---|---|
| `biomarker_record.subtype` | `items.subtype.confirmed` | `unknown` 없음 |
| `biomarker_record.setting.disease` | `items["setting.disease"].confirmed` | `unknown` 없음 |
| `biomarker_record.setting.line` (전이성) | `items["setting.line_endocrine"]`, `items["setting.line_chemo"]` | "이번에 결정할 차수" (2026-10-21 합의, B `assess()`도 같은 뜻으로 냄). 간주 규칙은 반영하지 않고 `items.deemed_lines`로 따로 준다 (급여 판정에서 약제별 +1) |
| `biomarker_record.setting.line` (조기) | `items["setting.phase"]` | A 규칙 (2026-11-02): 원발 수술 기록(pTNM 또는 ypTNM)이 있으면 `adjuvant`, 없으면 `neoadjuvant`. B의 `setting.line`(마지막 투약의 단계)은 쓰지 않는다 |
| `biomarker_record.setting.reason` | `items.*.reason`, `memo` | 의사가 바꾼 이유 |
| `biomarker_record.setting.prior_drug_classes` | `items.prior_regimens.confirmed[].subclasses` | `drug_classes.csv`의 `drug_subclass` 수준 (AI_nonsteroidal, CDK4/6_inhibitor …) |
| `biomarker_record.records[]` {marker, status} | `items.markers.<마커>.confirmed` (+ `detail`) | `gBRCA1`·`gBRCA2` → **`gBRCA` 하나** (하나라도 positive면 positive, vus면 vus, 둘 다 negative면 negative, 하나만 negative이고 나머지가 기록 없음이면 의사 확인). `sBRCA`도 같다. 판정 불가 값(`unknown`)은 들어오지 않는다 |
| `biomarker_record.tests_needed` | 없음 | **열림** (§6 4번). 지금 `recommend()`는 `assess()`의 `tests_needed`를 그대로 쓴다 |
| `patient_state` `menopausal_status` | `items.menopausal_status.confirmed` | pre/post 두 값만 (peri → pre) |
| `patient_state` `recurrence.metastatic_sites` (없으면 `stage.metastatic_sites`) | `items.metastatic_sites.confirmed` | 전이성이면 영상 판독(`imaging_findings`)에서 확정(`confirmed`)된 부위를 더한다 (2026-11-03, VC-0111 뇌 전이). 더한 부위는 `note`에 남긴다 |
| `patient_state` `imaging_findings[]` (골전이 영상) | `items.bone_metastasis_imaging.confirmed` | 확정된 뼈 영상 소견이 있으면 `yes`. 뼈 전이 부위는 있는데 영상 확인 기록이 없으면 비워서 의사가 확인 |
| `patient_state` `treatment_history[]` | `items.prior_regimens.confirmed[]` {drugs, subclasses, setting, start_day, end_day, line_endocrine, line_chemo, response, stop_reason} | 항상 전체 목록. 판정 기준일 뒤에 시작한 투약은 뺀다 |
| `patient_state` `anthracycline_drug_dose`, `treatment_history[].doses[]` | `items.anthracycline_cumulative.confirmed` | 약별 누적 mg/m². mg 기록은 키·몸무게로 구한 체표면적(Mosteller)으로 나눈다 |
| `patient_state` `patient.cardiac_history` | `items.cardiac_risk.confirmed` | yes / no |
| `patient_state` `patient.mediastinal_radiation` | `items.mediastinal_radiation.confirmed` | yes / no |
| `patient_state` `patient.visceral_crisis` | `items.visceral_crisis.confirmed` | 의사 판단. B는 지금도 참고란에서 이 확정값을 먼저 읽는다 |
| 없음 | `items.contraindicated_classes.confirmed` | 의사가 고르는 금기 약 계열 (초안은 빈 목록). B는 참고란에 쓴다 |
| `patient_state` `at_index.recent_therapy_28d` | `items.recent_therapy_28d.confirmed` | |
| `patient_state` `fields.deemed_lines` | `items.deemed_lines.confirmed` | |
| `patient_state` `recurrence.*` | `items.recurrence_type`, `recurrence_day`, `metastasis_day` | |
| `patient_state` `histology` | 없음 | 처방·급여 조건에 없어 확정 항목에서 뺐다. 필요하면 추가 요청 |
| 없음 | `endocrine_relapse_12m`, `dfi_days`, `high_risk_early`, `pcr`, `operable`, `stage.*`, `grade`, `age_at_index` | A가 계산하거나 옮기는 조건 값 (ESMO M02/M03 분기, TNBC DFI, abemaciclib 고위험, 보조 T-DM1·capecitabine 등) |

## 6. 같이 정할 것

| 번호 | 정할 것 | 상태 |
|---|---|---|
| 1 | `setting.line`의 뜻: 받은 차수인가, 결정할 차수인가 | **결정 (2026-10-21):** 결정할 차수. B `assess()`도 전이 후 투약이 없으면 1L을 낸다 (2026-10-22 `ca29f70`) |
| 2 | 내분비·항암 차수 분리 | **결정:** `assess()`가 `line_endocrine`·`line_chemo`를 내고 화면 1 기본값으로 쓴다 (B 2026-10-21 `af75391`) |
| 3 | 차트의 BRCA 이름 | **결정:** gBRCA. 생식세포 칸(`molecular.germline`)을 먼저, 없으면 `mutations`를 읽는다 (A 2026-10-28, B 2026-10-29 `gene_field_of`). 확정값에서는 gBRCA1·2를 하나로 합친다 (§5) |
| 4 | 검사 권고(`tests_needed`)를 2단계에 넘기는 방법 | **열림.** A 제안: `confirmed_state`에 `tests_needed` 칸을 추가해 화면 1에서 의사가 고른 권고만 넘긴다. 스키마 변경이라 4명 검토가 필요하다. 그 전까지는 `assess()`의 목록을 그대로 쓴다 |
| 5 | 계산 항목 위치 | **결정 (2026-10-30):** `dfi_days`, `high_risk_early`, `endocrine_relapse_12m`, `setting.phase`는 A가 `confirmed.py`에서 계산한다 |
| 6 | 2단계 모듈의 입력을 `confirmed_state`만으로 할지 (§4 2번) | **열림.** draft7 체크리스트 §5 1번 (4명) |
| 7 | 의사 판단 칸 추가: 항암 불가, 내분비 적합, 활동성 뇌 전이·국소 치료 적응, 소수 전이, 임신 | **열림.** draft7 체크리스트 §5 3번 (4명). 2026-11-04 46건 실행에서 이 칸이 없어 틀린 추천이 나왔다 (VC-0137, 0141, 0111, 0143, 0144) |

확정 항목을 고른 근거, 초진·재진 구분, 판독이 결정되지 않은 값 17건은 A의 작업 노트(`notes/confirmed_state_items_2026-10-21.md`, 저장소 밖)에 있다. 필요하면 요청하면 된다.
