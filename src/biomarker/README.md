# [2] 바이오마커 모듈 — 담당 B

검사 보고서를 지침·급여 기준이 쓰는 상태값으로 바꾼다.

- 하위 단계: BM-1 보고서 정규화(LLM) ~ BM-4 검사 공백 탐지 (PROJECT.md §5)
- 입력: `patient_state`
- 출력: `schemas/biomarker_record.json` 레코드 목록
- BM-2 판정과 BM-4 공백 규칙은 규칙 코드로 작성한다. LLM이 상태값을 바꿀 수 없다.
- 테스트: `tests/biomarker/`
