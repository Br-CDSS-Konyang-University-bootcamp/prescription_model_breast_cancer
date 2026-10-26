# [1] 입력 모듈 — 담당 A

차트 원문을 비식별화하고, 로컬 LLM으로 필드를 추출해 `schemas/patient_state.json` 형식으로 출력한다.

- 하위 단계: IN-0 비식별화 ~ IN-7 유전자 보고서 전달 (PROJECT.md §4)
- 입력: 붙여넣은 차트 원문
- 출력: `patient_state` (모든 값에 원문 근거 위치 포함)
- 환자 텍스트는 외부 API로 보내지 않는다. `llm/`의 로컬 모델 설정만 쓴다.
- 테스트: `tests/input/`

문서:

- [py_files.md](py_files.md): 입력 모듈 `.py` 파일마다 이름·기능·실행 명령·테스트 (script/의 pipeline·evaluation·rules·virtual·tcga 폴더별)
- [llm_extraction_runs.md](llm_extraction_runs.md): LLM 추출 시험 1~3차 기록. 차수마다 고친 규칙·프롬프트와 점수 비교 (2026-10-23 ~ 10-26, hari-q3-8b, 필드 정확도 91.2% → 98.1%)
- [schema_fields.md](schema_fields.md): `patient_state` 필드별 표준값 형태, 정규화 방식과 예시, B와 합의할 제안
- [tcga_mapping.md](tcga_mapping.md): TCGA-BRCA 정리본 → `patient_state` 정답 대응표 (평가용 정답과 가상 차트 생성의 기준)
- [handoff_to_B.md](handoff_to_B.md): B에게 전달하는 문서 (하나로 통합). JSON 구조, B가 받는 값과 정규화, BM-2 판정 조건, BM-3 출처 제안, 치료 상황 규칙(차수, 급여 투여단계), 정답 세트 특성, 예시, 모델 한계, B가 정할 것
- [patient_state_structure.md](patient_state_structure.md): `patient_state` JSON 구조 그림

코드:

코드는 모두 `script/` 아래에 기능별로 나눠 두었다. `pipeline`·`evaluation`·`rules`는 기능마다 파일 하나이고 (2026-10-26 합침),
파일 안은 옛 파일 이름의 절로 나뉜다. 자세한 설명은 [py_files.md](py_files.md).

| 위치 | 절 (옛 파일) | 역할 |
|---|---|---|
| `script/pipeline.py` | classify, deid, quote, normalize, assemble, pipeline, extract | 차트 원문 → `patient_state` 처리 단계 (IN-0 ~ IN-7). 진입점 `run(chart_text, extract, patient_ref=, created_at=)` → `(patient_state, issues)`. 실행 `python -m src.input.script.pipeline` (LLM 추출 시험) |
| `script/evaluation.py` | candidates, score | 정답 후보(`from_expected`)와 채점 (필드 정확도, 정밀도·재현율, 상태 혼동표, 근거 위치, 인용 준수율). 실행 `python -m src.input.script.evaluation` |
| `script/rules.py` | vocab, lines | 공용 규칙(차수·간주 규칙·판정 기준일 값, `annotate()`)과 표준값 사전(`field_vocab.csv`). 파이프라인·가상 차트·TCGA 도구가 같이 쓴다 |
| `script/virtual/` | `virtual_chart.py`, `build_virtual_cases.py`, `cases/` | 가상 차트와 정답 만들기 (10건 + 짝 사례 19건, 사례 20건) |
| `script/tcga/` | `tcga_to_patient_state.py`, `verify_tcga_conversion.py`, `tcga_truth.py`, `fixed_chart.py` | TCGA 정답 변환·검증, 고정 형식 차트. 지금은 쓰지 않는다 (2026-10-26) |

차트 원문 변환 (고정 형식, 2026-10-21):

```bash
python -m src.input.script.tcga.fixed_chart                              # TCGA 크롭본 전원 왕복 검사
python -m src.input.script.tcga.fixed_chart --ids TCGA-A2-A0EW --show    # 한 명의 차트 원문 출력
python -m src.input.script.tcga.fixed_chart --out <폴더>                 # <폴더>/<환자>/chart.txt, patient_state.json
```

- 형식은 하나로 고정한다: `[병리결과보고서]` → `[분자병리 보고서]` → `<외래 경과기록>` → `[투약 기록]`. 한 줄에 `이름: 값` 하나, 투약 기록은 ` | `로 나눈 표. 미시행은 `미시행`, 기록 없음은 `기록 없음`, 일수는 `D+85`
- ER·PR 구간은 값 그대로 쓴다 (`구간 90-99%`, `구간 0-0%`)
- `parse()`는 차수·간주 규칙·판정 기준일 값(`line`, `deemed_lines`, `at_index`)과 주기 수 추정을 변환기와 같은 규칙으로 다시 계산한다. 그래서 차트에는 원자료만 쓴다
- 왕복 검사: `parse(render(x))`는 `raw`, `source`, `created_at`, `documents`, `genomic_reports[].doc_id`, `anthracycline_drug_dose.drugs[].timeline_index`(TCGA 순번)를 빼고 `x`와 같아야 한다. TCGA 838명 모두 같고, 다시 읽은 값으로 B `assess()`를 돌려도 판정이 같다 (`source_span`만 채워짐)
- 담지 못하는 값(투약 날짜, `observed_date`, `history`, 한 보고서 안에 검체가 다른 값 등)이 오면 `render()`가 `Unsupported`로 멈춘다. 가상 차트(VC)는 이 형식이 아니다

patient_state 변환 (team_project 폴더에서, `team_project` conda 환경):

```bash
python -m src.input.script.tcga.tcga_to_patient_state                         # 변환만 하고 인원 수 출력
python -m src.input.script.tcga.tcga_to_patient_state --ids TCGA-A2-A0EW --show  # 한 명 결과를 화면에 출력
python -m src.input.script.tcga.tcga_to_patient_state --out <폴더>            # 파일로 저장
```

- 다른 코드에서는 `convert(load_rows())`로 `{patient_id: patient_state}`를 바로 받는다 (BM 테스트가 이렇게 쓴다)
- `data/truth/`(이전 생성기의 출력 폴더)는 2026-10-15에 지웠다. 이전 생성기(`script/tcga/tcga_truth.py`)는 남아 있고, 실행하면 `data/truth/`에 파일과 보고서를 다시 만든다
- 사전에 없는 값이 나오면 멈춘다. `field_vocab.csv`에 표현을 추가한다
- 모든 정답을 `schemas/patient_state.json`으로 검증하고, 하나라도 실패하면 종료 코드 1

테스트: `python -m pytest tests/input`. 예시 3명(`tests/input/expected/`)과 생성 결과가 같은지, 정답 전체가 스키마를 통과하는지, tcga_mapping.md에 적힌 건수와 맞는지 확인한다. 규칙을 바꾸면 문서·코드·테스트 건수를 함께 고친다.
