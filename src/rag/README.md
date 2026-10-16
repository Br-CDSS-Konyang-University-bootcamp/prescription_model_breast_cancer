# [3] 지침 RAG + 공용 검색 색인 — 담당 C

ESMO·ASCO 지침을 수집·청킹하고, 지침과 급여 청크가 함께 들어가는 공용 검색 색인을 관리한다.

- 범위: PROJECT.md §6
- 입력: 지침 원문 PDF, D가 만든 급여 청크
- 출력: 검색 API (setting·subtype·line 필터 + biomarker_tags 가중치 + 재정렬)
- 색인 쓰기·검색 코드는 이 폴더에만 둔다. D는 이 폴더의 색인 함수를 호출해 급여 청크를 넣는다.
- 청크 형식은 `schemas/chunk.json`을 따른다.
- 테스트: `tests/rag/`

## 파일

| 파일 | 내용 |
|---|---|
| `client.py` | Qdrant 로컬 DB(`data/qdrant_db/`, git 제외)와 임베딩 모델(bge-m3) |
| `indexer.py` | `init_collection()`, `index_chunks()` |
| `searcher.py` | `search_guidelines()` |
| `run_indexing.py` | `data/chunks/*.json`을 읽어 색인을 새로 만든다. 실행: `team_project` 폴더에서 `python -m src.rag.run_indexing` |

청크 JSON은 `data/chunks/`에 둔다 (`.gitignore`에서 이 폴더의 `.json`만 허용).
