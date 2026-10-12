# [4] LLM 추천 모듈 — 담당 B (2단계)

바이오마커 상태값과 검색된 지침·급여 청크로 처방 후보와 급여 분류를 만든다.

- 범위: PROJECT.md §7
- 입력: `patient_state`, `biomarker_record` 목록, `src/rag/` 검색 결과
- 출력: `schemas/recommendation.json`
- 인용 없는 문장 삭제, 인용 청크의 약제명 재확인 같은 후처리를 이 폴더에 둔다.
- 로컬 모델만 쓴다.
- 테스트: `tests/recommend/`
