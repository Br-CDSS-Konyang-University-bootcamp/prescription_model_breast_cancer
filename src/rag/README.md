# [3] 지침 RAG + 공용 검색 색인 — 담당 C

ESMO·ASCO 지침을 수집·청킹하고, 지침과 급여 청크가 함께 들어가는 공용 검색 색인을 관리한다.

- 범위: PROJECT.md §6
- 입력: 지침 원문 PDF, D가 만든 급여 청크
- 출력: 검색 API (setting·subtype·line 필터 + biomarker_tags 가중치 + 재정렬)
- 색인 쓰기·검색 코드는 이 폴더에만 둔다. D는 이 폴더의 색인 함수를 호출해 급여 청크를 넣는다.
- 청크 형식은 `schemas/chunk.json`을 따른다.
- 테스트: `tests/rag/`
