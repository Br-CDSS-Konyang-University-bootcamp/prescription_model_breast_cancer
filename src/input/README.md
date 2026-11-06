# [1] 입력 모듈 — 담당 A

차트 원문을 비식별화하고, 로컬 LLM으로 필드를 추출해 `schemas/patient_state.json` 형식으로 출력한다.

- 하위 단계: IN-0 비식별화 ~ IN-7 유전자 보고서 전달 (PROJECT.md §4)
- 입력: 붙여넣은 차트 원문
- 출력: `patient_state` (모든 값에 원문 근거 위치 포함)
- 환자 텍스트는 외부 API로 보내지 않는다. `llm/`의 로컬 모델 설정만 쓴다.
- 테스트: `tests/input/`

문서:

- [llm_performance.md](llm_performance.md): **입력 모듈 최종 성능** (LLM 모델 선택, 세트별 점수, 남은 오류, 다시 재는 방법)
- [py_files.md](py_files.md): 입력 모듈 `.py` 파일마다 이름·기능·실행 명령·테스트, GPU 서버 실행
- [schema_fields.md](schema_fields.md): `patient_state` 필드별 표준값 형태, 정규화 방식과 예시, 바꿔 읽는 값(부분 날짜·KPS 등) 방침
- [patient_state_structure.md](patient_state_structure.md): `patient_state` JSON 구조 그림
- [virtual_patient_cases.md](virtual_patient_cases.md): 가상 환자 사례 목록 (개발·시험·보류·표현 변형 세트, 사례별 기대 결과)
- [line_rules.md](line_rules.md): ESMO 처방 기준 차수와 심평원 급여 투여단계 규칙 명세 (차수 코드 재작성 기준, 열린 결정 4개)
- [proposal_remove_overall_line_2026-11-06.md](proposal_remove_overall_line_2026-11-06.md): 전이 후 전체 차수 `line` 삭제 제안 (내분비·항암 차수만 쓰기, 4명 검토)
- [handoff_locoregional_rule_to_B_2026-11-06.md](handoff_locoregional_rule_to_B_2026-11-06.md): 국소 재발 후 치료 단계 규칙(SET-LOCAL-ADJ) 설계안. 선행·보조·고식 판정을 구간 표 하나로 (B 검토)
- [team_report_run_flow_2026-11-05.md](team_report_run_flow_2026-11-05.md): **46건 재실행 결과와 조원별 할 일** (2026-11-05, 지금 상태)
- B·C·D 전달: [handoff_to_B.md](handoff_to_B.md) (JSON 구조, BM-2 판정 조건, BM-3 출처, 치료 상황 규칙), [handoff_confirmed_state_to_B.md](handoff_confirmed_state_to_B.md) (confirmed_state 연결), [draft7_checklist_BCD_2026-10-28.md](draft7_checklist_BCD_2026-10-28.md) (draft7 후보 칸 확인 체크리스트, §5 4명 결정 남음)
- 해결되어 지운 문서 (2026-11-05): `integration_status_2026-10-29.md`, `handoff_recommend_prompt_to_B_2026-11-02.md`, `handoff_recommend_options_to_B_2026-11-03.md`, `team_agenda_A_2026-11-04.md`. 다른 코드·문서의 주석이 이 이름을 가리키면 `git show 4c27c45:src/input/<파일 이름>`으로 볼 수 있다

코드:

코드는 모두 `script/` 아래에 기능별로 나눠 두었다. `pipeline`·`evaluation`·`rules`는 기능마다 파일 하나이고 (2026-10-26 합침),
파일 안은 옛 파일 이름의 절로 나뉜다. 자세한 설명은 [py_files.md](py_files.md).

| 위치 | 절 (옛 파일) | 역할 |
|---|---|---|
| `script/pipeline.py` | classify, deid, quote, normalize, assemble, pipeline, extract | 차트 원문 → `patient_state` 처리 단계 (IN-0 ~ IN-7). 진입점 `run(chart_text, extract, patient_ref=, created_at=)` → `(patient_state, issues)`. 실행 `python -m src.input.script.pipeline` (LLM 추출 시험) |
| `script/evaluation.py` | candidates, score | 정답 후보(`from_expected`)와 채점 (필드 정확도, 정밀도·재현율, 상태 혼동표, 근거 위치, 인용 준수율). 실행 `python -m src.input.script.evaluation` |
| `script/rules.py` | vocab, lines | 공용 규칙(차수·간주 규칙·판정 기준일 값, `annotate()`)과 표준값 사전(`field_vocab.csv`). 파이프라인과 가상 차트가 같이 쓴다 |
| `script/virtual/` | `virtual_chart.py`, `build_virtual_cases.py`, `build_holdout_cases.py`, `build_variant_cases.py`, `cases/` | 가상 차트와 정답 만들기 (개발 10건 + 짝 19건, 시험 20건, 보류 18건, 표현 변형 15건) |
| `script/tcga/` | `tcga_to_patient_state.py` | B 테스트(`tests/biomarker/test_bm.py`)가 쓰는 변환기만 남김 |
| `script/confirmed.py` | (새 파일) | 화면 1 확정값. `build_draft(patient_state, biomarker_record)` → 초안 (시스템 값이 없거나 `unknown`인 칸은 비우고 `needs`에 표시), `set_item(draft, key, value, reason)` (status 자동, 스키마 밖 값은 거부), `finalize(draft, confirmed_by)` → `data/input/confirmed/<patient_ref>/v<n>.json` (덮어쓰지 않음). `dfi_days`·`high_risk_early`도 여기서 계산 |

화면 1 확정값 규칙 (2026-10-30): gBRCA·sBRCA는 1·2를 하나로 합친다 (하나라도 positive → positive, vus → vus, 둘 다 negative → negative, 한쪽만 negative이고 나머지가 기록 없음 → 의사 확인). 재진(follow_up)은 버전 번호·`supersedes`만 채우고 `previous`·`carried`는 아직 없다. 전이 부위(2026-11-03): 재발·병기 칸의 부위에 영상 판독이 확정한 부위를 더한다 (진행 뒤 새 뇌 전이처럼 영상 소견에만 있는 부위, VC-0111). 치료 단계 `setting.phase`(조기·국소 진행성의 이번 결정, 2026-11-02): 수술을 먼저 할지는 시스템이 고를 근거가 없어 규칙으로 정한다. 원발 수술 기록(pTNM 또는 ypTNM)이 있으면 `adjuvant`, 없으면 선행요법 대상으로 보고 `neoadjuvant`. B의 `setting.line`(마지막 투약의 단계)은 쓰지 않는다.

2026-10-27 TCGA 정답 세트 폐기, 평가는 가상 차트로 (B 테스트용 변환기 `script/tcga/tcga_to_patient_state.py`만 남김).

테스트: `python -m pytest tests/input`.
