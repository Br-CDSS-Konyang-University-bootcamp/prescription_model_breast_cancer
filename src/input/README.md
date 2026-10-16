# [1] 입력 모듈 — 담당 A

차트 원문을 비식별화하고, 로컬 LLM으로 필드를 추출해 `schemas/patient_state.json` 형식으로 출력한다.

- 하위 단계: IN-0 비식별화 ~ IN-7 유전자 보고서 전달 (PROJECT.md §4)
- 입력: 붙여넣은 차트 원문
- 출력: `patient_state` (모든 값에 원문 근거 위치 포함)
- 환자 텍스트는 외부 API로 보내지 않는다. `llm/`의 로컬 모델 설정만 쓴다.
- 테스트: `tests/input/`

문서:

- [schema_fields.md](schema_fields.md): `patient_state` 필드별 표준값 형태, 정규화 방식과 예시, B와 합의할 제안
- [tcga_mapping.md](tcga_mapping.md): TCGA-BRCA 정리본 → `patient_state` 정답 대응표 (평가용 정답과 가상 차트 생성의 기준)
- [handoff_to_B.md](handoff_to_B.md): B에게 전달하는 문서 (하나로 통합). JSON 구조, B가 받는 값과 정규화, BM-2 판정 조건, BM-3 출처 제안, 치료 상황 규칙(차수, 급여 투여단계), 정답 세트 특성, 예시, 모델 한계, B가 정할 것
- [patient_state_structure.md](patient_state_structure.md): `patient_state` JSON 구조 그림

코드:

| 경로 | 내용 |
|---|---|
| `common/vocab.py` | 표준값 사전(`data/dictionaries/field_vocab.csv`) 조회. 정답 생성과 IN-3 정규화가 같은 사전을 쓴다 |
| `script/tcga_to_patient_state.py` | TCGA 크롭본 → `patient_state` 874명 (2026-10-15). 변환만 하고 기본은 파일을 만들지 않는다. 규칙 명세는 tcga_mapping.md |
| `truth/tcga_truth.py` | 이전 정답 생성기 (같은 변환 + 파일 저장·스키마 검증·보고서). `tests/input/test_tcga_truth.py`가 쓴다 |

patient_state 변환 (team_project 폴더에서, `team_project` conda 환경):

```bash
python -m src.input.script.tcga_to_patient_state                         # 변환만 하고 인원 수 출력
python -m src.input.script.tcga_to_patient_state --ids TCGA-A2-A0EW --show  # 한 명 결과를 화면에 출력
python -m src.input.script.tcga_to_patient_state --out <폴더>            # 파일로 저장
```

- 다른 코드에서는 `convert(load_rows())`로 `{patient_id: patient_state}`를 바로 받는다 (BM 테스트가 이렇게 쓴다)
- `data/truth/`(이전 생성기의 출력 폴더)는 2026-10-15에 지웠다. 이전 생성기(`truth/tcga_truth.py`)는 남아 있고, 실행하면 `data/truth/`에 파일과 보고서를 다시 만든다
- 사전에 없는 값이 나오면 멈춘다. `field_vocab.csv`에 표현을 추가한다
- 모든 정답을 `schemas/patient_state.json`으로 검증하고, 하나라도 실패하면 종료 코드 1

테스트: `python -m pytest tests/input`. 예시 3명(`tests/input/expected/`)과 생성 결과가 같은지, 정답 전체가 스키마를 통과하는지, tcga_mapping.md에 적힌 건수와 맞는지 확인한다. 규칙을 바꾸면 문서·코드·테스트 건수를 함께 고친다.
