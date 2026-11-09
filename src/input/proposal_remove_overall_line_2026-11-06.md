# 제안: 전이 후 전체 차수 `line` 삭제

> 작성: 담당 A · 2026-11-06 · 상태: **제안 (4명 검토 필요: 공용 스키마, B·C 코드)**
> 관련: [line_rules.md](line_rules.md) §1·§3·결정 4, [handoff_to_B.md](handoff_to_B.md) §6.2, [handoff_confirmed_state_to_B.md](handoff_confirmed_state_to_B.md) §6 1·2번

## 1. 제안

`treatment_history[].line`(전이 후 전체 차수)을 계산하지도 저장하지도 않는다. 차수는 심평원 방식의 고식적 내분비 차수(`endocrine_line`)와 고식적 항암 차수(`chemo_line`) 둘만 쓴다. 이 둘로 ESMO 지침 검색, 추천, 급여 판정을 모두 한다.

## 2. 이유

### 2.1 ESMO는 전체 차수를 정의하지 않고, 종류별 횟수로 권고를 가른다

ESMO MBC 2026-05 청크(`data/chunks/esmo_chunks.json`)에서 확인한 내용:

| 장 | 차수 절 | 권고를 가르는 조건 |
|---|---|---|
| 호르몬 양성 (`luminal-1l`·`-2l`·`-3l`) | 1차 / 2차 / 3차 이후 | 보조 ET 종료 후 기간(1차), 이전 ET의 무진행 기간·AI 노출(2차), "ET 2회 이상 후 비내분비로", "이전 ChT 없음", "ChT 1회 이상 후", "ET 1회 이상 후"(3차 이후) |
| HER2 양성 (`her2-1l` ~ `-4l`) | 1차 ~ 4차 이후 | 이전 항HER2 요법 (taxane–trastuzumab 후 진행 등). 모든 차수가 항암·항HER2 기반이라 항암 차수 = 전체 차수 |
| TNBC (`tnbc-1l`·`-2l`) | 1차 / 2차 이후 | 이전 항암, 1차에서 쓴 약. 내분비요법 없음 → 항암 차수 = 전체 차수 |

- 호르몬 양성 장의 차수 절은 내분비 기반 치료 순서이고, 그 안의 조건은 종류별 횟수다. 내분비 차수 + 항암 차수로 같은 판단을 할 수 있다.
- HER2 양성·TNBC는 항암 차수가 전체 차수와 같다.
- 전체 차수를 공식으로 정의한 지침은 없다. 심평원 공고는 내분비·항암 투여단계를 따로 센다 (p.55).

### 2.2 지금 전체 차수는 검색·판정에 쓰이지 않는다

| 사용처 | 쓰는 차수 | `line` 사용 |
|---|---|---|
| 화면 1 확정 칸 (`confirmed_state`) | `setting.line_endocrine`, `setting.line_chemo` | 칸 없음 |
| C 지침 검색 `decision_lines` (`src/rag/retrieve.py`) | HR+/HER2-는 내분비 차수 (+ 다르면 항암 차수), 그 밖은 항암 차수 | 안 씀 |
| C 급여 검색 | 위 차수 + 간주 규칙 met이면 한 차수 위 | 안 씀 |
| B 급여 조건 `_line_rule` (`src/recommend/conditions_eval.py`) | `endocrine_line`·`chemo_line` + `deemed_lines` | 안 씀 |
| B `line_of` → `biomarker_record.setting.line` (전이성) | **`line`** | 씀 |
| B `line_kind_of` | 전이 후 투약에 `line`이 없으면 `unknown` | 검사에만 씀 |
| B 추천 프롬프트 `patient_summary` (`src/recommend/prompt.py`) | `setting.line`, `treatment_history[].line` | LLM 참고값 |
| C 옛 입력 경로 (`patient_state` + `biomarker_record`) | `setting.line` | 경고를 내는 옛 경로 |

의사가 확인하지 않는 값이 프롬프트에만 들어가고, 화면 1에서 의사가 고친 차수와 어긋날 수 있다.

## 3. 바꿀 곳

| 담당 | 파일 | 변경 |
|---|---|---|
| 공용 (4명) | `schemas/patient_state.json` | `treatment_history[].line` 삭제 |
| A | `src/input/script/rules.py` `palliative_lines`·`annotate` | `line` 계산·기록 삭제. 내분비·항암 차수와 같은 차수 묶음 판단(진행 → 다음, 유지·순차·독성 → 같음)은 그대로 |
| A | `src/input/script/virtual/` 사례 코드, `tests/fixtures/virtual_charts/**/expected/patient_state.json` | 생성기로 다시 씀 (`--check`로 `line`만 빠지는지 확인) |
| A | `src/input/schema_fields.md`, `handoff_to_B.md` §6.2, `line_rules.md` | `line` 설명 삭제 |
| B | `src/biomarker/BM1_ER,PR,HER2,Ki_67,subtype.py` `line_of` | 전이성의 `setting.line` = C `decision_lines`와 같은 규칙의 주 차수 (HR+/HER2-이고 내분비 차수가 있으면 내분비 차수, 그 밖은 항암 차수). `biomarker_record.setting.line` 칸과 값 목록은 그대로 둔다 (조기암의 neoadjuvant / adjuvant도 이 칸) |
| B | 같은 파일 `line_kind_of` | `unknown` 검사를 "전이 후 투약에 `endocrine_line`·`chemo_line`이 하나도 없으면"으로 |
| B | `src/recommend/prompt.py` `patient_summary` | `line` 대신 `line_endocrine`·`line_chemo` (confirmed_state가 있으면 확정값), 투약 목록도 `endocrine_line`·`chemo_line` |
| C | `src/rag/retrieve.py` 옛 입력 경로, `query.py` | `setting.line`을 계속 받으므로 B가 위처럼 채우면 바꿀 것 없음. 확인만 |

## 4. 바뀌지 않는 것

- 차수를 세는 규칙 (진행이면 다음 차수, 선행·보조는 세지 않음, 내분비·항암 따로).
- 간주 규칙 `deemed_lines` 4개와 급여 판정.
- 화면 1 확정 칸과 C 검색 결과 (지금도 `line`을 쓰지 않음).

## 5. 확인 방법

- `python -m src.input.script.virtual.build_virtual_cases --check` 등 생성기 `--check`: `line` 말고 바뀌는 값 없음.
- `python -m pytest tests/input tests/app tests/biomarker tests/recommend tests/rag`.
- `python -m src.app.script.run_flow --summary`: 46건 인용 비교가 지금과 같음 (프롬프트만 바뀌므로 LLM 출력 차이는 따로 본다).

## 6. 검토 요청

| 질문 | 대상 |
|---|---|
| 전체 차수를 프롬프트에서 빼도 추천 품질에 문제가 없나 (내분비·항암 차수로 대신) | B |
| 옛 입력 경로를 계속 둘지 | C |
| 진행 순서: A 계산 삭제와 B 변경을 한 PR로 낼지, B 먼저 낼지 | 4명 |

B가 `line_of`·`line_kind_of`를 바꾸기 전에 A가 `line`을 먼저 지우면 B가 전이성 환자에 `unknown`을 낸다. 그래서 이 문서가 합의되면 B 변경을 먼저 또는 같이 낸다.
