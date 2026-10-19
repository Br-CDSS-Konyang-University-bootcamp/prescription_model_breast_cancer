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
| `convert_pdf_to_md.py` | `data/guidelines/*.pdf`를 `data/parsed_md/{asco,esmo}/*.md`로 변환 (pymupdf4llm). PDF가 기호 전용 폰트에 넣어 둔 ≥, =, +, – 를 폰트 표로 되돌린다. 실행: `python -m src.rag.convert_pdf_to_md` |
| `check_md_quality.py` | 변환한 md의 깨짐(기호, 제어문자, 붙은 단어, 그림 글자 등)을 세어 표로 보여 준다. 폴더 두 개를 주면 비교한다. 실행: `python -m src.rag.check_md_quality` |
| `chunker_asco_all.py` | ASCO 처방 지침 11개 md → `data/chunks/asco_chunks_all.json`. 실행: `python -m src.rag.chunker_asco_all` |
| `chunker_esmo.py` | ESMO EBC·MBC md → `data/chunks/esmo_chunks.json`. 실행: `python -m src.rag.chunker_esmo` |
| `chunk_common.py` | 두 청커가 같이 쓰는 텍스트 정제, 약제·바이오마커 태깅, 청크 형식 |
| `client.py` | Qdrant 로컬 DB(`data/qdrant_db/`, git 제외)와 임베딩 모델(bge-m3) |
| `indexer.py` | `init_collection()`, `index_chunks()`(chunk_id로 고정 ID), `delete_guideline_chunks()`(지침 청크만 삭제) |
| `searcher.py` | `search_guidelines()` |
| `run_indexing.py` | `data/chunks/*.json`을 스키마 검증하고, 지침 청크만 지운 뒤 다시 색인한다 (D의 급여 청크는 남김). 실행: `python -m src.rag.run_indexing` |

모든 명령은 `team_project` 폴더에서 실행한다. 순서: PDF 변환 → 품질 검사 → 청커 2개 → `python -m pytest tests/rag` → 색인.

- 지침 PDF와 변환한 md(`data/parsed_md/`)는 저작권 문서라 저장소에 올리지 않는다. 각자 PDF에서 만든다.
- 청크 JSON은 `data/chunks/`에 커밋한다 (`.gitignore`에서 이 폴더의 `.json`만 허용). 커밋 전에 `tests/rag/test_chunks_schema.py`(스키마 검증, chunk_id 중복)가 통과해야 한다.
- 청킹하는 문서 목록은 각 청커의 `DOCS`에 있다. 제외한 문서와 이유는 `rag_non_prescription_docs.md`.
