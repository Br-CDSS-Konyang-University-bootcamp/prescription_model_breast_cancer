# [5] 급여 기준 자동 업데이트 — 담당 D

심평원 공고책자, 개정 공고, 공고예고, 허가초과 항암요법 목록을 수집해 조건 단위 급여 청크를 만든다.

- 범위: PROJECT.md §8
- 입력: 심평원 게시판
- 출력: `schemas/chunk.json` 형식의 급여 청크 (doc_type = reimbursement), SQLite 레지스트리
- 색인 반영은 `src/rag/`의 색인 함수를 호출한다. 색인 코드를 이 폴더에 따로 만들지 않는다.
- 공고 원문과 가공물은 외부에 공개하지 않는다.
- 테스트: `tests/reimbursement/`
