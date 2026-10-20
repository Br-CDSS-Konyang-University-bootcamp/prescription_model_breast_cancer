# [4] LLM 추천 모듈 — 담당 B (2단계)

바이오마커 상태값과 검색된 지침·급여 청크로 처방 후보와 급여 분류를 만든다.

- 범위: PROJECT.md §7
- 입력: `patient_state`, `biomarker_record`, 지침 청크(C의 검색 결과)·급여 청크(D), 모두 `schemas/` 형식
- 출력: `schemas/recommendation.json`
- 로컬 모델만 쓴다. 환자 정보는 외부 API로 보내지 않는다.
- 테스트: `python -m pytest tests/recommend` (가짜 LLM 답으로 시험, 모델·검색 색인 없이 돈다)

## 파일 (2026-10-20, LLM 연결 전 단계)

| 파일 | 하는 일 |
|---|---|
| `pipeline.py` | 진입점 `recommend(patient_state, biomarker_record, guideline_chunks, reimbursement_chunks, llm, index_status, model_name)` → (추천, 후처리 로그, 형식 오류). 검색 결과와 LLM 함수(프롬프트 글 → 답 글)는 넘겨받기만 한다. `llm/` 공용 인터페이스가 생기면 그 함수를 넣는다 |
| `prompt.py` | 프롬프트: 환자 요약(구조화 값만, 차트 원문 인용은 넣지 않음), 바이오마커 상태값과 이유, 검사 공백, 지침 청크(ID·출처·쪽·근거 수준·부모 소단원), 급여 청크(공고 번호·시행일). 문장마다 `[청크ID]`를 붙이라고 지시 |
| `postprocess.py` | 환각 방지 후처리 (아래 표) |
| `validate.py` | `schemas/recommendation.json` 형식 검사 |
| `drug_biomarker.csv` | 약 → 필요한 바이오마커와 상태값. 출처는 심평원 공고 제2026-190호 PDF 쪽과 ESMO 쪽. `disease` 칸이 있으면 그 범주에서만 적용 (pembrolizumab·atezolizumab은 전이성에서만 PD-L1 필요) |

## 후처리 규칙 (PROJECT.md §7 환각 방지·급여 분류)

| 순서 | 규칙 | 결과 |
|---|---|---|
| 1 | 받은 청크에 없는 청크 ID 인용 | 그 인용을 지움 |
| 2 | 근거 문장(rationale)에 `[청크ID]`가 없는 문장 | 문장을 지움. 남은 문장이나 지침 인용이 없으면 후보를 지움 |
| 3 | 약 이름이 인용한 지침 청크(`drugs` 목록 또는 본문)에 없음 | 후보를 지움 |
| 4 | 약에 필요한 바이오마커가 `not_done`·`not_recorded`·`unknown`·`retest_needed` (필요한 마커 중 양성이 하나도 없을 때) | 후보 대신 `tests_needed`에 "<마커> 검사 결과 확인" (`blocks_therapy`에 치료 이름) |
| 4 | 필요한 바이오마커가 모두 음성·VUS 등 | 후보를 지우고 `conflicts`에 이유와 출처를 적음 |
| 5 | 급여 분류: 시행 중인 급여 청크(`baseline`·`overlay`, 시행일이 오늘 이전) 인용이 없음. 예고(`preview`)는 근거가 아님 | `no_criteria` |
| 5 | 허가초과 인정인데 허가초과 청크(`HIRA-offlabel`) 인용이 없음 | `no_criteria`. 있으면 청크의 본인부담률을 `copay`에 |
| 5 | `covered`인데 급여 조건을 모두 확인하지 못함 | `covered_conditions_unverified`. 조건 확인은 `conditions_checker` 함수로 넘겨받는다 (D 판정 연결 전이라 지금은 확인 안 됨) |
| 6 | 지침 청크가 하나도 없음 | 추천을 만들지 않고 `out_of_scope` |

`tests_needed`는 바이오마커 모듈의 검사 공백을 먼저 두고 LLM·후처리가 낸 검사를 이어 붙인다 (같은 검사는 한 번).

## 아직 안 한 것

- 실제 LLM 연결: `llm/` 공용 인터페이스(4명 합의)가 먼저 필요
- 급여 조건 세부 확인(차수, 이전 약제 등): D의 판정과 연결 (`conditions_checker`)
- 검색 호출: C의 `src/rag/query.py`(`search_args`)와 `search_guidelines`를 부르는 쪽에서 청크를 받아 `recommend()`에 넘긴다
