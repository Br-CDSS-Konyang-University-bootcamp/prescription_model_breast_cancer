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
| `chunk_common.py` | 두 청커가 같이 쓰는 텍스트 정제, 약제·바이오마커 태깅, 청크 형식, 부모 청크(`attach_parent`) |
| `chunk_store.py` | 청크 JSON을 읽어 `get_chunk(id)`, `get_parent(chunk)`로 찾는다. `select_index_chunks`는 색인할 청크(부모 제외)를 고른다 |
| `client.py` | Qdrant 로컬 DB(`data/qdrant_db/`, git 제외)와 임베딩 모델(bge-m3) |
| `indexer.py` | `init_collection()`, `index_chunks()`(chunk_id로 고정 ID), `delete_by_doc_type(doc_type)`(지침 또는 급여 청크만 삭제. D는 `"reimbursement"`로 부름), `delete_guideline_chunks()`, `close_indexer()`. D는 `src.rag`(`__init__.py`)로 공개한 `init_collection`·`index_chunks`·`delete_by_doc_type`·`close_indexer`만 부른다 |
| `searcher.py` | `search_guidelines()`. `with_parent=True`면 결과마다 부모(소단원) 청크를 `parent`로 붙인다 |
| `run_indexing.py` | `data/chunks/*.json`을 스키마 검증하고, 지침 청크만 지운 뒤 다시 색인한다 (D의 급여 청크는 남김). 실행: `python -m src.rag.run_indexing` |

모든 명령은 `team_project` 폴더에서 실행한다. 순서: PDF 변환 → 품질 검사 → 청커 2개 → `python -m pytest tests/rag` → 색인.

- 지침 PDF와 변환한 md(`data/parsed_md/`)는 저작권 문서라 저장소에 올리지 않는다. 각자 PDF에서 만든다.
- 청크 JSON은 `data/chunks/`에 커밋한다 (`.gitignore`에서 이 폴더의 `.json`만 허용). 커밋 전에 `tests/rag/test_chunks_schema.py`(스키마 검증, chunk_id 중복)가 통과해야 한다.
- chunk_id는 다시 청킹해도 바뀌지 않아야 한다 (평가셋 정답과 추천 결과의 인용이 가리킨다). ASCO 권고는 원문 권고 번호(`asco-mbc-2021-07-endo-r3.2`), 번호가 없는 ESMO 권고·ASCO 질문·rapid update는 첫 근거 등급 표시까지의 문장으로 만든 지문(`esmo-mbc-2026-05-luminal-2l-3f2a9c`, `chunk_common.stable_key`)을 쓴다. 순서 번호(r01, r02)는 앞에 권고 하나만 늘어도 뒤가 모두 밀리므로 쓰지 않는다. `tests/rag/test_chunk_ids.py`가 이 성질을 검사한다.
- 쪽 번호: 변환할 때 쪽마다 `<!-- page pdf=3 printed=1205 -->` 표시를 넣고 (인쇄 쪽은 PDF 정보 칸의 실린 쪽 범위에서 계산), 청커가 청크 본문을 이 md에서 찾아 `page_start`·`page_end`를 채운다. 기본은 학술지 인쇄 쪽(D의 급여 청크도 인쇄 쪽)이고, `chunk_common.PAGE_NUMBERING = "pdf"`로 바꾸면 PDF 쪽이 된다. 2026-10-19 이전에 만든 md에는 쪽 표시가 없으니 `--overwrite`로 다시 변환한다 (안 하면 테스트가 쪽 번호 없음으로 실패).
- 부모-자식 청크: 권고 청크(자식)마다 `parent_id`로 소단원 청크(부모, `chunk_kind: section`)를 가리킨다. 부모 본문은 소단원 제목(ASCO는 Clinical Question 질문문) + 자식 권고 전체다. ESMO는 소단원(`esmo-mbc-2026-05-luminal-2l`), ASCO는 Clinical Question(`asco-mbc-2021-07-endo-cq3`)이나 문서(`...-doc`, 번호 없는 권고)가 부모다. 검색 색인에는 자식만 넣고, 부모는 JSON에 두고 `get_parent`로 찾는다 (D의 급여 청크와 같은 방식).
- 청킹하는 문서 목록은 각 청커의 `DOCS`에 있다. 제외한 문서와 이유는 `rag_non_prescription_docs.md`.
