# [5] 급여 기준 자동 업데이트 — 담당 D

심평원 공고책자, 개정 공고, 공고예고를 수집해 조건 단위 급여 청크를 만든다.
청킹 방식은 B의 설계 문서 `reimbursement_chunking_design.md`(2026-10-16)를 따른다.

- 범위: PROJECT.md §8. 책자의 일반원칙([별표] 앞), 9. 유방암, 40. 기타 항암제 병용요법의 유방암 행,
  Ⅳ 기타 약제(G-CSF·zoledronic acid·denosumab·dexrazoxane의 유방암 줄 + 모든 암종 공통인 sodium thiosulfate, 설계 §10.2).
  개정 공고 덧씌우기(설계 §6)는 아직 없다. 새 공고가 올라오면 실행해 보고 수정한다 (그때까지 책자 우선 방식).
  허가초과 항암요법 목록은 범위 밖, 팀 결정 대기 (설계 §7 결정 4). 기본 실행에서는 받지도 청크로 만들지도 않는다.
  읽는 코드는 꺼 둔 채로 남겨 두었다 (`--with-offlabel`로 켬)
- 청크 계층 (설계 §0.2): L1 원칙(`section`) / L2 단계·소단원(`section`) / L3 요법 행·조건 묶음(`reimbursement_condition`).
  chunk_id 예: `hira-booklet-20261001-bc-pal-endo-1l-r01`, `…-combo-r22`, `…-supp-zoledronic-b`
- 설계가 제안한 새 칸(stage, line_rule, history, combination 등)은 공용 스키마에 아직 없다. 개정안: `schema_proposal.md`
- 입력: 심평원 게시판 (항암화학요법, 공고, 공고예고)
- 출력: `schemas/chunk.json` 형식의 급여 청크 (doc_type = reimbursement), SQLite 레지스트리
- 색인 반영은 `src/rag/`의 색인 함수를 호출한다. 색인 코드를 이 폴더에 따로 만들지 않는다.
- 공고 원문과 가공물은 외부에 공개하지 않는다.
- 테스트: `tests/reimbursement/`

## 필요 패키지

`team_project` 환경에 `conda install -n team_project -c conda-forge pymupdf jsonschema pytest`를 설치한다.
`pdfplumber`는 `--cross-check`에만 쓰고, `anthropic`은 Claude API로 투여 조건을 채울 때만 쓴다.

## 실행

```bash
python -m src.reimbursement.pipeline              # 게시판 확인 -> 새 파일만 받기 -> 검증 -> 청크
python -m src.reimbursement.pipeline --offline    # 이미 받은 파일(data/reimbursement/raw/)로만
python -m src.reimbursement.pipeline --cross-check  # pdfplumber로 한 번 더 읽어 비교 (첫 실행 1분 남짓)
python -m src.reimbursement.pipeline --no-llm     # Claude API 없이 (저장해 둔 투여 조건만)
python -m src.reimbursement.pipeline --with-offlabel  # 허가초과 목록 청크도 만든다
```

공용 색인(C의 Qdrant)에 넣기는 따로 실행한다. 예전 급여 점을 지운 뒤 L3 청크만 넣는다 (설계 §0.1: L1·L2는 벡터 없이
청크 파일에서 `parent_id`로 찾는다). 검토중 요법은 뺀다.
C의 공개 함수(`src/rag/__init__.py`)의 `replace_doc_type("reimbursement", chunks)`로 새 청크를 먼저 넣고(점 ID는 chunk_id의
uuid5라 같은 청크는 덮어씀) 새 목록에 없는 옛 급여 점만 지운 뒤 `close_indexer`로 닫는다 (팀 결정 C1, 2026-10-20).
넣다가 실패하면 지우기까지 가지 않아 옛 급여 점이 남는다. 지침 점은 건드리지 않는다.
`replace_doc_type`이 없는 예전 `src/rag`에서는 `delete_by_doc_type` → `index_chunks`(지운 뒤 넣기)로 대신한다.
`init_collection(force_recreate=True)`는 지침 점까지 지우므로 쓰지 않는다.
성공하면 기록 장부의 그 책자를 indexed로, 예전 indexed 책자를 superseded로 바꾼다.
Qdrant 로컬 모드는 한 프로세스만 열 수 있으니 검색·`run_indexing`과 동시에 돌리지 않는다.

옛 책자 기준 보존 (2026-10-20 결정, D):

| 상황 | 방식 |
|---|---|
| 새 공고책자 (전체 교체) | 색인에는 새 책자만 둔다. 옛 책자는 날짜별 보관 파일 `chunks/reimbursement_chunks_<책자날짜>.jsonl`과 `registry.db`(항목별 유효 기간)로 재현한다 |
| 개정 공고 (일부 행 교체, 설계 §6, 아직 없음) | 새 행을 overlay로 넣고 옛 행에 `superseded_by`를 단다. 검색(`src.rag.search_reimbursement`)이 `superseded_by`가 있는 행을 뺀다 |

- 이유: 추천 결과에 남는 인용 `chunk_id`에 책자 날짜가 들어 있어(`hira-booklet-<책자날짜>-…`) 그 날짜의 보관 파일로 당시 원문·조건을 그대로 찾을 수 있다.
  판정은 늘 지금 기준이라 옛 책자 점을 색인에 쌓을 이유가 약하고, `superseded_by`는 책자 중간에 일부 행만 바뀌는 개정 공고용이다.
- 보관 파일은 공고 가공물이라 git에 올리지 않고 이 PC에만 있으므로, 새 책자를 반영할 때마다 결과물 백업(zip)을 팀 공유 위치에 올린다.

```bash
python -m src.reimbursement.index --dry-run     # 넣을 청크 수만 확인
python -m src.reimbursement.index               # 늘 색인
python -m src.reimbursement.index --if-changed  # 마지막 색인 때와 같으면 건너뜀
python -m src.reimbursement.pipeline --index    # 파이프라인이 정상이면 이어서 --if-changed 색인
```

색인 주기 (회의 5 결정, 2026-10-21): 바뀌었을 때만 색인한다. 앱 시작 때 파이프라인(게시판 확인)을 돌리고, 색인할 청크가
마지막 색인 때(`reports/last_indexed.json`의 해시)와 다르면 이어서 색인한다. 새 공고의 신설·변경·삭제뿐 아니라 조건 수정도
청크가 바뀌므로 다시 색인된다. DB도 함께 비교해서(폴더 경로 + `data/qdrant_db/meta.json` 수정 시각), DB를 새로 만들었거나
다른 폴더로 옮겼으면 청크가 같아도 다시 색인한다 (청크 파일만 복사한 새 작업 폴더에서 빈 DB를 건너뛰지 않게).
색인하는 1~2분 동안 검색이 막히므로 앱 시작 직후, 검색 전에 끝낸다.
검색과 색인은 `src/rag`의 Qdrant 연결 하나를 같이 쓰므로 같은 프로그램 안에서는 `close_searcher()`를 부르지 않는다
(부르면 진행 중인 검색이 끊길 수 있다). 앱이 켜져 있을 때 다른 프로그램(터미널 등)에서 색인을 따로 돌리지 않는다.
색인이 실패하면 해시를 남기지 않아 다음 실행 때 다시 색인한다. 시행일이 미래인 공고는 검색이 `effective_from ≤ 기준일`로
거르므로 날짜가 됐다고 다시 색인하지 않는다.

단계마다 검사하고, 오류가 하나라도 있으면 아무것도 바꾸지 않는다 (마지막 정상 청크 파일 유지).

| 단계 | 하는 일 | 검사 |
|---|---|---|
| 1. 수집 | 항암화학요법 게시판 HEAD로 파일명 날짜 비교, 새 파일·같은 날짜 재업로드만 받기. 공고 1쪽, 공고예고 1쪽 | 파일 크기, PDF·xlsx 서명, 오류 페이지(HTML), 파일명 날짜 |
| 2. 책자 검증 | 공고책자 읽기. 목차(Ⅰ~Ⅳ, 별첨) 순서대로 책자 전체를 섹션으로 나눠 `sections/`에 저장 | 목차 항목을 본문에서 모두 찾았는지, 목차 쪽 번호와 본문 위치, 섹션 밖 글자, 개정 이력, 변경 표시, 같은 번호 공고전문과 대조, 깨진 글자 |
| 3. 유방암 추출 | 일반원칙, 유방암(주N 각주·연번 범위 규칙을 해당 행에, 병합 셀 물려받기 표시), 병용요법 유방암 행(추가 약제·기존 급여 요법 나누기), Ⅳ 기타 약제 유방암 줄 | 표 연번 연속성, 다른 섹션에 남은 '유방' 언급 (Ⅳ 기타 약제는 유방암 줄을 모두 넣었는지) |
| 4. 허가초과 | (`--with-offlabel`일 때만) 유방암 인정 요법·검토중 요법 | 시트·건수·요법코드 |
| 5. 청크 검사 | 청크 만들기, 요법 구조화(순차·선택 약제·제형·약제별 본인부담·복합제) | 스키마(+설계 제안 칸), 빠진 낱말(행 청크·소단원 청크·일반원칙 각각), 원문에 없는 낱말, 깨진 글자, 약제명 목록·오타, 이전 실행 대비 행 수 |
| 6. 투여 조건 | `reimbursement.conditions`를 설계 §3.5 형식으로 채우기. 저장본(`conditions_cache.jsonl`)에 있으면 그대로 쓰고, 없는 청크만 Claude API(claude-sonnet-5-5)에 요청. API 키·크레딧이 없으면 Claude Code(`claude -p`, 구독 사용량)로 같은 프롬프트를 보냄. 저장본은 손으로 쓴 조건을 `--import`로 넣어 채울 수도 있음. 사람 검수표(.tsv) 만들기 | 항목마다 원문 구절, field·op·값 어휘, 약 이름 사전. 하나라도 틀리면 그 청크 조건을 버림. 둘 다 안 되면 경고만 내고 조건 없이 진행 (`--no-llm`은 부르지 않음) |
| 7. 반영 | 레지스트리 신설·변경·삭제, 청크 파일·`index_status.json` 저장 | 허가초과 변경대비표와 diff 대조 |

Claude API를 쓰려면 `conda install -n team_project -c conda-forge anthropic` 후 저장소 루트 `.env`에 `ANTHROPIC_API_KEY=...`를 넣는다 (git 제외).
Claude Code로 돌리려면 터미널에서 `claude`를 한 번 실행해 `/login`으로 구독 계정에 로그인해 둔다. PATH에 없으면 Claude 데스크톱 앱에 든 것을 찾고, 다른 곳이면 `CLAUDE_CODE_EXE`에 경로를 넣는다.
조건 field 어휘와 환자 JSON 경로는 `conditions.py`의 `FIELDS` (설계 문서·`reimbursement_field_values.csv` 기준, B 검토). 환자 JSON 경로는 `patient_state` 0.1-draft6 기준이다.
`cardiac_history`, `mediastinal_radiation`은 이번 모델에서 뺐다 (PROJECT.md §12). 판정하면 늘 '알 수 없음'이 된다.
`recurrence_operable`은 환자 JSON에 칸을 두지 않고, 재발 후 수술 여부(`recurrence.surgery`, `surgery_intent`)로 대신 읽는다. `surgery = yes`이고 `surgery_intent = curative`면 절제 가능, 그 밖은 '알 수 없음'이다 (A 결정 2026-10-21, PROJECT.md).
차수 간주 규칙 `counts_as_prior_line`은 draft6의 `fields.deemed_lines[]`와 대응한다. 항목에 `rule_id`가 있으면 그 규칙을 그대로 본다 (`schema_proposal.md`).
조건 131행 중 109행은 D가 검수 기록을 남겼다 (`reports/review_decisions_20261001.tsv`, 일부는 B 확인). 나머지 행 검수와 의료진 검토는 아직이라, 판정 쪽(B)은 이 조건만으로 `covered`라고 하지 않고 `covered_conditions_unverified`로 둔다.

API 없이 손으로 쓴 조건도 같은 검사(형식·어휘·원문 구절)를 거쳐 저장본에 넣을 수 있다. 통과한 행만 들어가고, 이후 파이프라인은 그 결과를 그대로 쓴다.
2026-10-01 책자의 L3 131행은 이렇게 넣었다 (`data/reimbursement/conditions_manual/batch_*.json`, 작성자 "claude (대화에서 직접 작성, 2026-10-19)"). 책자 본문이 바뀐 행은 다시 써야 한다.
조건 JSON에는 공고 원문 구절이 들어 있어 git에 올리지 않는다 (D의 PC에만 있음). 다른 팀원이 조건이 채워진 청크를 쓰려면 D에게 청크 파일을 받는다.

```bash
python -m src.reimbursement.conditions --import data/reimbursement/conditions_manual/batch_01_neo.json --author "이름"
```

결과물 (git에 올리지 않음):

- `data/reimbursement/chunks/reimbursement_chunks_current.jsonl` — 마지막 정상 청크 (C의 색인에 넣을 파일)
- `data/reimbursement/sections/booklet_sections_<책자날짜>.jsonl` — 목차 단위로 나눈 책자 전체 (섹션 하나 = 한 줄: 키, 제목, 목차 쪽, 본문 쪽, 글자 수, '유방' 언급 수, 본문)
- `data/reimbursement/reports/run_<시각>.json` — 단계별 검사 결과, `last_good.json` — 마지막 정상 실행
- `data/reimbursement/registry.db` — 문서·항목 버전 기록
- `data/reimbursement/index_status.json` — 화면 하단 요약과 예정·진행중 공고 목록 (B의 `recommendation.index_status`, `pending_notices`)
- `data/reimbursement/conditions_cache.jsonl` — 조건 결과 저장본 (Claude API 또는 `--import`)
- `data/reimbursement/conditions_manual/` — 손으로 쓴 조건 JSON (`--import` 입력)
- `data/reimbursement/reports/conditions_review_<책자날짜>.tsv` — 투여 조건 사람 검수표 (엑셀로 연다. 원문이 들어 있어 git에 올라가는 .csv 대신 .tsv)

## 파일

| 파일 | 내용 |
|---|---|
| `pipeline.py` | 전체 흐름과 단계별 검사 묶음 |
| `fetch.py` | 게시판 파싱, 수집 계획, 내려받기 (요청 수 제한) |
| `booklet.py`, `notice.py`, `extract.py` | 공고책자·공고전문 PDF 읽기 |
| `validate.py` | 공고책자 검증 |
| `offlabel.py` | 허가초과 xlsx 읽기와 검증 |
| `chunks.py` | 유방암·병용요법 표 읽기, Ⅳ 기타 약제, 요법 구조화, 청크 만들기, 스키마 검사(+설계 제안 칸) |
| `conditions.py` | 투여 조건 어휘(FIELDS), Claude API 구조화, 원문 구절 검사, 결과 저장, 검수표 |
| `schema_proposal.md` | `schemas/chunk.json` 개정안 (설계 문서의 새 칸) |
| `index.py` | 급여 청크를 C의 공용 색인에 넣기 (src/rag 함수 호출만) |
| `qc.py` | 단계별 품질 검사 함수 |
| `vocab.py` | 약제명 목록(공용 사전 + 유방암 추가분), 오타 찾기 |
| `registry.py` | SQLite 레지스트리 |
| `dates.py`, `status.py` | 날짜 표기 통일, §8 날짜 규칙 |
| `check_booklet.py` | 공고책자 하나만 검증하는 보조 실행 파일 |

새 약제가 나와 "약제명 목록에 없는 영문 낱말" 경고가 뜨면 `vocab.py`의 `BREAST_EXTRA`에 추가한다.

## 남은 일 (2026-10-22)

| 할 일 | 누가 |
|---|---|
| 투여 조건 검수 마무리 (131행 중 남은 22행)와 의료진 검토 | D, B 확인 |
| `schemas/chunk.json` 개정 (`schema_proposal.md`) | D 제안, 4명 검토 |
| 판정 규칙 문서화 (`all_of`, `any_of`, `any_of_exceptions`, `unless`, `contains`, `not_contains`, 유전자 `vus`·`not_done` 처리) | B, D |
| 3가 밖의 "보조요법 종료 후 ~ 재발" 기간(`days_end_to_recurrence`)도 전이 기준일까지 셀지 | A 답변 대기 |
| 결과물(청크, 조건 JSON, registry.db) 비공개 백업·공유 위치 | 팀 |
| 개정 공고 덧씌우기 (설계 §6). 새 공고가 올라오면 실행해 보고 만든다 | D |
| 허가초과 포함 여부: v0.1에서는 빼고 PROJECT.md §8을 설계 문서에 맞추자는 D 의견. 지금은 범위 밖, 팀 결정 대기 (기본 끔) | 팀 |

회의 안건 결정 (2026-10-21):

| 안건 | 결정 |
|---|---|
| 1. `text_normalized` 위치 | 청크 최상위. 필수 칸이 아님 (ESMO 지침은 영어라 필요 없고, 필수로 하면 지침 청크를 모두 고쳐야 함). 검색은 지금처럼 원문 `text`로 하고 급여 검색은 약 이름·날짜로 거르므로 C 검색 코드는 바뀌지 않음. `schemas/chunk.json`은 공용 파일이라 4명 검토 |
| 2. `line_rule` 값 | 공고 표기 그대로 한국어 + `setting.line` 대응표 (`schema_proposal.md`). 다른 팀원 문서에 반대 내용 없음, B 동의 |
| 3. `copay` | 요법 전체에 하나일 때만 값, 약제마다 다르면 `null`과 `copay_by_drug`. 반영함. `recommendation.json` 설명은 PR로 4명 검토 |
| 4. 허가초과 | 위 표 (범위 밖, 팀 결정 대기) |
| 5. 색인 주기 | 바뀌었을 때만, 앱 시작 직후·검색 전에. 같은 연결을 같이 써서 `close_searcher()`는 부르지 않음. 반영함 (위 "색인 주기") |
