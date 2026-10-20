# [3] 지침 RAG + 공용 검색 색인 — 담당 C

ESMO 지침을 수집·청킹하고, 지침과 급여 청크가 함께 들어가는 공용 검색 색인을 관리한다.

- 범위: PROJECT.md §6
- 입력: 지침 원문 PDF, D가 만든 급여 청크
- 출력: 검색 API (setting·subtype·line 필터 + biomarker_tags 가중치 + 재정렬)
- 색인 쓰기·검색 코드는 이 폴더에만 둔다. D는 이 폴더의 색인 함수를 호출해 급여 청크를 넣는다.
- 청크 형식은 `schemas/chunk.json`을 따른다.
- 테스트: `tests/rag/`

## 파일

| 파일 | 내용 |
|---|---|
| `convert_pdf_to_md.py` | `data/guidelines/*.pdf`를 `data/parsed_md/esmo/*.md`로 변환 (pymupdf4llm). PDF가 기호 전용 폰트에 넣어 둔 ≥, =, +, – 를 폰트 표로 되돌린다. 실행: `python -m src.rag.convert_pdf_to_md` |
| `check_md_quality.py` | 변환한 md의 깨짐(기호, 제어문자, 붙은 단어, 그림 글자 등)을 세어 표로 보여 준다. 폴더 두 개를 주면 비교한다. 실행: `python -m src.rag.check_md_quality` |
| `chunker_esmo.py` | ESMO EBC·MBC md → `data/chunks/esmo_chunks.json`. 실행: `python -m src.rag.chunker_esmo` |
| `chunk_common.py` | 두 청커가 같이 쓰는 텍스트 정제, 약제·바이오마커 태깅, 청크 형식, 부모 청크(`attach_parent`) |
| `guideline_terms.py` | 지침 표현 사전 `data/dictionaries/guideline_terms.csv`(환자 JSON 코드 값 → 지침 원문 표현)를 읽어 질의어를 만든다(`query_terms`). `canonical`은 B의 `biomarker_record` 값(아형·치료 상황·`마커:상태값`)과 A의 `patient_state` 값, 약 사전 값으로 고정하고, C는 `expression`만 늘린다 (테스트가 스키마 밖 값을 막는다). 실행하면 표현마다 청크에 몇 번 나오는지 보여 준다: `python -m src.rag.guideline_terms` |
| `query.py` | B의 `biomarker_record`와 환자 정보로 검색 질의와 검색 인자를 만든다. B는 `search_guidelines(**search_args(record, metastatic_sites=..., menopausal_status=..., pcr=..., stage_at_diagnosis=..., prior_subclasses=..., prior_classes=...))`로 부르고, 전이 부위별 권고는 `site_search_args(...)`의 인자로 따로 검색한다. 환자 정보는 A의 `patient_state`에서 고른다. 같은 아형·병기·차수라도 폐경 상태(OFS), pCR(잔존 질환), de novo(원발 종양 수술), 이전 치료에 따라 권고가 갈린다. 이전 치료는 `after …`로 붙인다. 질의는 코드 값을 지침 대표 표현으로 바꿔 이은 문장이다 (예: `ER-positive, HER2-negative MBC second-line ESR1-mutated`). 음성·미시행·VUS 마커는 넣지 않는다 |
| `chunk_store.py` | 청크 JSON을 읽어 `get_chunk(id)`, `get_parent(chunk)`로 찾는다. `select_index_chunks`는 색인할 청크(부모 제외)를 고른다 |
| `client.py` | Qdrant 로컬 DB(`data/qdrant_db/`, git 제외), 임베딩 모델(bge-m3), 재정렬 모델(bge-reranker-v2-m3). 모델을 불러올 때 PyTorch CPU 스레드를 논리 코어의 절반(실제 코어 수)으로 맞춘다. 하이퍼스레딩 PC에서 기본값(논리 코어 전부)보다 빠르다. 환경 변수 `RAG_TORCH_THREADS`로 바꿀 수 있다. GPU가 있으면 sentence-transformers가 자동으로 쓴다(PyTorch CUDA판 필요). 나중에 GPU를 연결할 수 있으므로, 속도만을 이유로 재정렬 모델을 작은 것으로 바꾸지 않는다 (2026-10-20) |
| `indexer.py` | `init_collection()`, `index_chunks()`(chunk_id로 고정 ID), `delete_by_doc_type(doc_type)`(지침 또는 급여 청크만 삭제. D는 `"reimbursement"`로 부름), `delete_guideline_chunks()`, `close_indexer()`. D는 `src.rag`(`__init__.py`)로 공개한 `init_collection`·`index_chunks`·`delete_by_doc_type`·`close_indexer`만 부른다 |
| `searcher.py` | `search_guidelines()`. `with_parent=True`면 결과마다 부모(소단원) 청크를 `parent`로 붙인다. 재정렬이 기본으로 켜져 있다(`rerank=True`, PROJECT.md §6): 뜻 검색 후보 20개(`RERANK_CANDIDATES`)를 재정렬 모델(bge-reranker-v2-m3, 처음 쓸 때 약 2GB 내려받음)로 다시 매긴다. 모델을 불러오지 못하면 경고하고 뜻 검색 점수를 쓴다. 같은 조건의 검색은 결과를 기억해 두고(최대 256개), 색인을 바꾸면 비운다. `metastatic_sites`(예: `["bone", "liver"]`, field_vocab.csv 값)를 주면 부위별 권고(뼈·뇌·연수막 전이 소단원)를 그 부위 전이가 있으면 +0.05, 없으면 -0.3 한다. 연수막 전이는 표준값이 없어 `other: leptomeningeal …`처럼 적힌 값을 찾는다. 주지 않으면 점수를 바꾸지 않는다. 차수는 거르지 않고 점수로 반영한다: 같으면 +0.1, 청크가 `any`면 +0.03, 다른 차수만 가리키면 -1.0 (맞는 차수·any 권고 뒤로). `negative_tags`(환자가 음성으로 확인된 바이오마커 태그, `query.negative_tags(record)`가 만듦)를 주면 그 태그만 조건으로 하는 권고를 -1.0 한다 (예: gBRCA 음성 환자의 gBRCA 변이용 olaparib. 태그가 여러 개인 권고는 모두 음성일 때만). 결과의 `score`는 뜻 검색(또는 재정렬) 점수 + 차수·태그·전이 부위·음성 바이오마커 가점·감점 |
| `run_indexing.py` | `data/chunks/*.json`을 스키마 검증하고, 지침 청크만 지운 뒤 다시 색인한다 (D의 급여 청크는 남김). 실행: `python -m src.rag.run_indexing` |
| `evaluate.py` | 평가 문제집 `data/eval/rag_eval_cases.csv`로 검색을 채점한다. L0 문서(1위가 정답 문서인가), L1 소단원(상위 k개에 정답 소단원), L2 권고(hit@k, recall@k, MRR). 실행: `python -m src.rag.evaluate [--k 5] [--no-rerank] [--candidates 20] [--reranker 모델] [--auto-query] [--out 결과.csv]`. `--auto-query`는 문제집 질의 대신 환자 조건으로 만든 질의(`query.py`)로 채점한다. `--query-style`은 adaptive(기본: 필터로 이미 거른 아형·병기 표현을 빼되 차수·이전 치료만 남으면 넣음), full, focused. 질의당 검색 시간도 보여 준다 (색인을 먼저 만든다) |
| `bench_reranker.py` | 재정렬 모델이 느린 원인을 나눠 잰다 (모델 불러오기, 후보 수, CPU 스레드 수, 최대 입력 길이). 실행: `python -m src.rag.bench_reranker [--model 이름]` |

모든 명령은 `team_project` 폴더에서 실행한다. 순서: PDF 변환 → 품질 검사 → 청커 → `python -m pytest tests/rag` → 색인.

- 지침 PDF와 변환한 md(`data/parsed_md/`)는 저작권 문서라 저장소에 올리지 않는다. 각자 PDF에서 만든다.
- 청크 JSON은 `data/chunks/`에 커밋한다 (`.gitignore`에서 이 폴더의 `.json`만 허용). 커밋 전에 `tests/rag/test_chunks_schema.py`(스키마 검증, chunk_id 중복)가 통과해야 한다.
- chunk_id는 다시 청킹해도 바뀌지 않아야 한다 (평가셋 정답과 추천 결과의 인용이 가리킨다). ESMO 권고는 번호가 없어 첫 근거 등급 표시까지의 문장으로 만든 지문(`esmo-mbc-2026-05-luminal-2l-3f2a9c`, `chunk_common.stable_key`)을 쓴다. 순서 번호(r01, r02)는 앞에 권고 하나만 늘어도 뒤가 모두 밀리므로 쓰지 않는다. `tests/rag/test_chunk_ids.py`가 이 성질을 검사한다.
- 쪽 번호: 변환할 때 쪽마다 `<!-- page pdf=3 printed=1205 -->` 표시를 넣고 (인쇄 쪽은 PDF 정보 칸의 실린 쪽 범위에서 계산), 청커가 청크 본문을 이 md에서 찾아 `page_start`·`page_end`를 채운다. 기본은 학술지 인쇄 쪽(D의 급여 청크도 인쇄 쪽)이고, `chunk_common.PAGE_NUMBERING = "pdf"`로 바꾸면 PDF 쪽이 된다. 2026-10-19 이전에 만든 md에는 쪽 표시가 없으니 `--overwrite`로 다시 변환한다 (안 하면 테스트가 쪽 번호 없음으로 실패).
- 부모-자식 청크: 권고 청크(자식)마다 `parent_id`로 소단원 청크(부모, `chunk_kind: section`)를 가리킨다. 부모 본문은 소단원 제목 + 자식 권고 전체다. ESMO 소단원(`esmo-mbc-2026-05-luminal-2l`)이 부모다. 검색 색인에는 자식만 넣고, 부모는 JSON에 두고 `get_parent`로 찾는다 (D의 급여 청크와 같은 방식).
- ASCO 지침은 재사용 불가로 확인돼 쓰지 않는다 (2026-10-20). PDF·md·청크를 두지 않는다.
- 평가 문제집: 문항마다 질의, 하드 필터 값(setting, subtype, line), 태그, 음성 태그(`negative_tags`), 전이 부위(`metastatic_sites`)와 환자 정보(`menopausal_status`, `pcr`, `stage_at_diagnosis`, `prior_subclasses`, `prior_classes`. 비우면 모름. `--auto-query`가 쓴다), 정답 문서·소단원·권고 ID를 적는다 (목록은 `;`로 구분). 정답은 ESMO 원문에서 고른 초안이라 `status=draft`이고, 원문과 대조해 확인하면 `reviewed`로 바꾼다 (PROJECT.md §12, 의료진 검토 없이 원문 기반). `tests/rag/test_evaluate.py`가 정답 ID가 청크에 있고 그 문항의 필터를 통과하는지 검사한다. 청크 ID가 바뀌면 이 파일도 고친다.
- 청킹하는 문서 목록은 청커의 `DOCS`에 있다. 제외한 문서와 이유는 `rag_non_prescription_docs.md`.
