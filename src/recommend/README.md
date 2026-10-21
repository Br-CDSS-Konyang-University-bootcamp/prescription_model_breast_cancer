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
| `conditions_eval.py` | 급여 조건 판정기 (아래 "급여 조건 판정기"). `make_conditions_checker(patient_state, biomarker_record)`를 `recommend()`의 `conditions_checker`로 넘긴다 |
| `drug_biomarker.csv` | 약 → 필요한 바이오마커와 상태값. 출처는 D가 쓰는 심평원 공고책자 2026-10-01판(제2026-210호)의 인쇄 쪽·chunk_id(D 확인 2026-10-21)와 ESMO 쪽. 공고 문구는 옮기지 않는다. `disease` 칸이 있으면 그 범주에서만 적용 (pembrolizumab·atezolizumab은 전이성에서만 PD-L1 필요) |

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
| 5 | 급여 조건 판정(`conditions_checker`) 충족 | `covered` |
| 5 | 급여 조건 판정 불충족 | `no_criteria` (이유에 못 맞춘 조건) |
| 5 | 급여 조건을 모두 확인하지 못함, 또는 판정기를 넘기지 않음 | `covered_conditions_unverified` |
| 6 | 지침 청크가 하나도 없음 | 추천을 만들지 않고 `out_of_scope` |

`tests_needed`는 바이오마커 모듈의 검사 공백을 먼저 두고 LLM·후처리가 낸 검사를 이어 붙인다 (같은 검사는 한 번).

## 급여 조건 판정기 (`conditions_eval.py`, 2026-10-21)

PROJECT.md §15.5 "급여 분류 로직", §15.7 "급여 분류 판정 근거를 B의 추천 모듈에 연결", D README "판정 쪽(B)", D 결정 안건 B2 "B의 판정기"에 따라 B가 만든다.
D의 급여 청크 `reimbursement.conditions`를 환자 JSON(`patient_state`)과 바이오마커 판정(`biomarker_record`)에 맞춰 본다.
규칙 코드만 쓴다. LLM·외부 API는 쓰지 않고, D 코드도 불러오지 않는다 (공용 형식 `schemas/chunk.json`과 D의 `schema_proposal.md` "읽는 법"만 따른다).

D 문서·B2 합의대로 (팀 기준):

- 항목 하나는 참·거짓·알 수 없음 셋 중 하나. 행은 거짓이 하나라도 있으면 불충족, 거짓 없이 알 수 없음이 있으면 알 수 없음, 모두 참이면 충족
- `all_of` 모두, `any_of` 묶음마다 하나 이상, `any_of_exceptions` 예외 하나를 모두 만족하면 `any_of` 실패를 덮음, `unless` 만족하면 항목 실패를 덮음
- 바이오마커 status가 `positive`·`negative`·`low`·`ultralow`가 아니면 알 수 없음. `vus`는 `eq positive`가 거짓
- HER2 음성 = `negative`·`low`·`ultralow`, ER 양성 = `positive`·`low`
- 환자 JSON에 칸이 없거나 값이 없는 조건은 알 수 없음 (가상 차트의 gBRCA 줄이 없을 때 포함)
- 칸마다 환자 JSON 위치는 D의 `conditions.py` FIELDS 설명을 따른다

B 임시안 (팀 문서에 없음, 팀 확인 필요. 차수 세기는 A, `prior_failed` 읽는 법은 D 확인 전):

- D의 조건은 아직 사람 검수 전이라(D README), `conditions_reviewed=False`(기본값)면 충족·불충족 모두 확정하지 않고 "급여(조건 확인 필요)"로 둔다. 검수가 끝나면 `True`로 바꾼다
- 시행 중인 급여 청크 여러 개를 인용하면 하나라도 충족이면 충족, 충족이 없고 알 수 없음이 있으면 알 수 없음, 모두 불충족이면 불충족
- 투여단계(`line_rule`): 이번 치료 차수 = 이미 받은 고식적 치료 차수 + 1. 내분비 조건(`palliative_endocrine`)은 `endocrine_line`만, 항암 조건(`palliative_chemo`)은 `chemo_line`만 따로 센다. 공고가 선행·보조요법을 1회로 간주하면(`counts_as_prior_line`) A의 `deemed_lines`에서 같은 범주가 `met`이면 1차를 더해 보고, `unknown`이면 알 수 없음
- `prior_failed`(실패한 이전 약): `stop_reason`이 `progression`이거나 `best_response`가 `PD`인 줄만 실패로 센다. 그런 줄이 없고 중단 이유와 반응이 비어 있는 줄이 있으면 알 수 없음, 다른 이유(부작용·치료 완료 등)로만 끝났으면 실패 아님
- 조건에 쓰인 칸 중 위 목록에 없는 것(예: 아직 저장 칸이 없는 칸)은 알 수 없음

## 환자 정보 주의 (2026-10-20)

질문지에는 환자 정보(아형, 차수, 판정, 받은 약, 폐경 여부, 전이 부위)가 들어간다.

팀 규칙 (근거 문서):

- `recommend()`의 `llm`에는 `llm/` 공용 인터페이스의 **로컬 모델 설정만** 넣는다. Claude API 같은 외부 LLM 함수를 넣지 않는다 (CLAUDE.md "환자 차트는 외부 API로 보내지 않는다", PROJECT.md §7·§9)
- 질문지에는 비식별화한 구조화 값만 넣고 이름·등록번호·차트 원문 인용은 넣지 않는다 (PROJECT.md §7 "구조화된 환자 상태(비식별화)", §4 IN-0)
- 판정 규칙은 직접 만든 입력으로 시험하고, 실제 데이터 검증은 TCGA 정답 세트로 한다 (PROJECT.md §15.5)

B 판단 (팀 문서에 없음, 2026-10-20):

- 질문지에 `patient_ref`도 넣지 않는다. 추천에 필요 없기 때문이다
- 실제 환자의 추천 결과와 LLM 답은 파일로 저장하거나 출력하지 않는다 (`patient_ref`가 들어 있고 저장소가 공개라서)
- 테스트에는 가짜 데이터, TCGA, 가상 차트만 쓴다
- 지금은 코드가 외부 LLM 함수를 막지 않는다. `llm/`이 나오면 로컬 설정인지 확인하는 장치를 넣는다

## 아직 안 한 것

- 실제 LLM 연결: `llm/` 공용 인터페이스(4명 합의)가 먼저 필요
- 급여 조건 판정기를 실제 D 청크로 시험: D 청크 파일은 공개 저장소에 올릴 수 없어 각자 컴퓨터에서만 돌린다. 테스트는 가짜 조건으로 한다
- 검색 호출: C의 `src/rag/query.py`(`search_args`)와 `search_guidelines`를 부르는 쪽에서 청크를 받아 `recommend()`에 넘긴다
