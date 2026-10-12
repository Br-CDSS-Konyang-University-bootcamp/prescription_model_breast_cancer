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
