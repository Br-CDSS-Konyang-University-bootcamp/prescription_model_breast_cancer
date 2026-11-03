# [5] 급여 기준 자동 업데이트 — 담당 D

심평원 공고책자, 개정 공고, 공고예고를 수집해 조건 단위 급여 청크를 만든다.
청킹 방식은 B의 설계 문서 `reimbursement_chunking_design.md`(2026-10-16)를 따른다.

- 범위: PROJECT.md §8. 책자의 일반원칙([별표] 앞), 9. 유방암, 40. 기타 항암제 병용요법의 유방암 행,
  Ⅳ 기타 약제(G-CSF·zoledronic acid·denosumab·dexrazoxane의 유방암 줄 + 모든 암종 공통인 sodium thiosulfate, 설계 §10.2).
  개정 공고 덧씌우기(설계 §6)는 아직 없다. 새 공고가 올라오면 실행해 보고 수정한다 (그때까지 책자 우선 방식).
  허가초과 항암요법 목록은 v0.1에서 쓰지 않는다 (2026-11-02 결정, PROJECT.md §8). 받지도 청크로 만들지도 않는다.
  읽는 코드는 꺼 둔 채로 남겨 두었다 (`--with-offlabel`로 켬)
- 청크 계층 (설계 §0.2): L1 원칙(`section`) / L2 단계·소단원(`section`) / L3 요법 행·조건 묶음(`reimbursement_condition`).
  chunk_id 예: `hira-booklet-20261101-bc-pal-endo-1l-r01`, `…-combo-r22`, `…-supp-zoledronic-b`
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
python -m src.reimbursement.pipeline --with-offlabel  # 허가초과 목록 청크도 만든다 (v0.1에서 쓰지 않음)
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
| 6. 투여 조건 | `reimbursement.conditions`를 설계 §3.5 형식으로 채우기. 저장본(`conditions_cache.jsonl`)에 있으면 그대로 쓰고, 없는 청크만 로컬 LLM(`REIMB_OLLAMA_MODEL`이 있을 때) → Claude API(claude-sonnet-5-5) → Claude Code(`claude -p`, 구독 사용량) 순서로 쓸 수 있는 것에 같은 프롬프트를 보냄. 저장본은 손으로 쓴 조건을 `--import`로 넣어 채울 수도 있음. 사람 검수표(.tsv) 만들기 | 항목마다 원문 구절, field·op·값 어휘, 약 이름 사전. 하나라도 틀리면 그 청크 조건을 버림. 둘 다 안 되면 경고만 내고 조건 없이 진행 (`--no-llm`은 부르지 않음) |
| 7. 반영 | 레지스트리 신설·변경·삭제, 청크 파일·`index_status.json` 저장 | 허가초과 변경대비표와 diff 대조 |

로컬 LLM (PROJECT.md §9, 2026-10-23 Claude API에서 바꿈): qwen3:32b로 바뀐 행·새 행의 **초안**을 만들고 사람이 검수한다 (2026-11-02 D 결정). 환경 변수 `REIMB_OLLAMA_MODEL`이 있으면 조건 구조화를 Ollama로 먼저 한다 (공용 `llm/`의 `complete_json`).
예시 없이는 우리 조건 형식의 관례(칸 고르기·단위·묶음 위치·원문 그대로 붙이기)를 몰라 131행 항목 정확도가 25%였다 (2026-10-29). 그래서 `OllamaStructurer`는 행마다 이렇게 한다 (두 번째 답까지 만들어 행당 16~22초):

0. 원문 내용이 같은 행은 모델에 보내지 않는다 (`carry_over`, 2026-11-03). 지난번 청크 파일에 같은 소단원·같은 약 목록의 검수된 행이 있고, 본문과 소단원 안내가 공백·문장부호(와 행 자신의 연번 숫자)만 다르면 그 조건을 그대로 옮기고 원문 구절만 새 책자 표기로 맞춘다. 저장본 만든 이는 "<검수한 사람> (이전 판에서 옮김)"이라 검수된 조건으로 친다. 이전 판 안내는 반영 때 함께 쓰는 `chunks/reimbursement_contexts_current.json`에서 읽고, 이 파일이 없거나 구절을 맞춘 뒤 검사에 걸리면 옮기지 않고 모델로 넘긴다. 원문이 같은데 모델에 다시 물으면 맞는 조건을 고쳐 써서다 (아래 바뀐 행 평가에서 이전 판이 맞는데 17행을 바꿈).
1. 예시: 이번 책자에서 저장본의 검수된 조건(`--import`로 넣은 것. 모델 초안은 빼고)을 쓰는 행 중 원문 낱말이 가장 많이 겹치는 3개를 앞선 문답으로 넣는다.
2. 바뀐 행: 지난번 청크 파일(`reimbursement_chunks_current.jsonl`)에 같은 소단원·같은 약 목록의 검수된 행이 있는데 글자가 실제로 바뀌었으면 이전 판 원문·조건을 주고 바뀐 부분만 고치게 한다. 없으면 새 행.
3. 규칙 고치기 (`fix_conditions`): 치료 시기로 정해지는 병기·크기 칸, 구절의 비교 낱말(초과·이상·미만·이하)이 한 종류일 때 op, cm → mm, in·eq 목록 형식, 약 이름 표기, 원문 구절 앞뒤 따옴표·마침표. 사람이 쓴 저장본 131행에 쓰면 바뀌는 것이 없다 (테스트).
4. 다시 묻기: 형식·어휘·원문 구절 검사에 걸리면 문제 목록을 주고 한 번 더 묻는다. 그래도 걸리면 버린다.
5. 확인 (`verify.py`): 팀 사전 대조(칸·값), 숫자 대조, 투여대상 중 빠진 조건, 다른 질문으로 한 번 더 만든 답과 비교. 걸린 구절은 `human_review`에 넣어 그 행은 판정에서 '알 수 없음'이 된다. 1~3번 확인은 사람이 쓴 131행에 하나도 걸리지 않는다 (테스트). 1~3번만으로는 틀린 초안을 39개 중 5개만 잡았다 (빠뜨림·더 넣음·묶음 위치 오류가 많음). 4번 두 답 비교까지 넣은 결과는 아래 확인 표.
6. 검수표: 끝에 '검수 우선'·'만든 이'·'코드가 고친 것' 칸. 비슷한 검수 행이 없는 새 행부터 늘어놓는다. 검수해서 고친 조건(맞으면 초안 그대로)을 `--import`로 넣어야 검수된 조건이 되고 다음 예시 후보가 된다.

131행 평가 (2026-11-02, `reports/llm_eval_qwen3_32b_*.json`, 각 행을 빼고 나머지 검수 행만 보여 줌):

| 방식 | 검사 통과 | 완전 일치 | 항목 정확도 | 항목 재현율 | 행당 |
|---|---|---|---|---|---|
| 예시 없이 | 81 | 2 | 25% | 34% | 14초 |
| 비슷한 검수 행 3개 | 117 | 85 | 80% | 86% | 9초 |
| + 규칙 고치기·다시 묻기 (새 행) | 122 | 85 | 81% | 86% | 10초 |
| + 이전 판 (바뀐 행, 이전 판 = 2026-10-01 책자) | 130 | 112 | 95% | 99% | 9초 |

새 행은 가장 비슷한 검수 행과의 겹침에 따라 갈린다: 0.7 이상 80행은 정확도 95%, 0.5~0.7 27행은 74%, 0.5 미만 24행은 47%. 병용요법·Ⅳ 기타 약제는 행마다 구조가 달라 새 행이면 약하다 (정확도 47%·32%). 바뀐 행 평가는 2026-11-01 책자 변경이 문장부호뿐이라 실제 내용 변경보다 쉬운 경우다.

확인(`verify.py`, 두 답 비교 포함)이 사람 검토로 돌린 초안 (2026-11-03, `--similar 3 --fix`, 검사를 통과한 초안 기준):

| 방식 | 틀린 초안 중 잡음 | 틀렸는데 못 잡음 | 맞았는데 검토로 돌림 | 두 답이 같을 때 맞은 비율 | 행당 |
|---|---|---|---|---|---|
| 새 행 | 33 / 37 | 4 | 26 / 85 | 59 / 64 | 22초 |
| 바뀐 행 (이전 판 = 2026-10-01 책자) | 21 / 23 | 2 | 29 / 105 | 76 / 78 | 16초 |

못 잡은 행은 전이 항암화학요법(bc-pal-chemo-*)과 선행 HER2 음성 1행으로, 두 답이 같은 방향으로 빠뜨리거나 더 넣은 경우다. 맞은 초안의 약 1/4~1/3도 검토로 가므로 검토량은 줄지만 검수를 대신하지는 못한다. 바뀐 행 평가의 완전 일치(105)가 11-02(112)보다 낮은 것은 11-03 검수로 수술후보조 14행의 정답(각주·LVEF → `notes`)이 바뀌었는데 이전 판에는 옛 조건이 들어 있어서다 (그중 7행이 이전 판을 따라 틀림).

0번(원문이 같은 행은 옮기기)을 같은 두 책자에 써 본 결과 (2026-11-03, 모델 없이):
- 10-01 → 11-01 책자 131행 중 108행을 옮겼다. 옮긴 조건은 모두 10-01 검수 조건과 같다.
  - 지금 저장본과 다른 7행(수술후보조 r01~r03·r07~r09, thiosulfate 1)은 10-01 뒤 검수에서 조건을 고친 행이다.
- 모델로 넘긴 23행:
  - 16행: 10-01 청크의 조건이 10-29에 바뀐 어휘(`t_stage`·`ln_status`) 그대로라 검사에 걸렸다. 실제 운영에서는 지난번 청크가 지금 어휘라 생기지 않는다.
  - 7행: 글자가 실제로 바뀌었다. 개정 이력 날짜·위치(선행 HER2 양성 r05·r06, 전이 1차 항암 r05), 약 이름 오타 수정(병용 r21), 문장 순서(병용 r22·r26·r27).
- 다음 책자가 이번과 내용이 같으면 131행 모두 옮겨지고 조건도 지금과 같다 (빈 저장본으로 확인).
- 평가: `eval_llm ... --previous 옛청크.jsonl --previous-contexts 옛안내.json` (결과 이름 끝 `_carry`)은 옮긴 행을 모델 없이 채점한다.
- 0번을 넣은 바뀐 행 평가 (2026-11-03, `llm_eval_qwen3_32b_sim3_fix_update_carry.json`):
  - 131행 완전 일치 121, 항목 정확도 100%, 재현율 99.8%, 행당 3초.
  - 모델이 쓴 23행 중 20행이 완전 일치했다. 다른 3행(수술후보조 r20~r22)은 이전 판의 LVEF `human_review`를 따른 것으로, 모두 확인에 걸려 사람 검토로 갔다.
  - 틀렸는데 못 잡은 7행은 모두 옮긴 행으로, 10-01 뒤 검수에서 조건을 고친 행이다.
  - 이번 바뀐 행은 변경이 작은 경우(문장부호·이력·오타·문장 순서)라, 내용이 실제로 바뀐 공고에서는 다시 확인해야 한다.
모델 서버는 `REIMB_OLLAMA_HOST` (기본 `http://127.0.0.1:11500`). GPU 서버에서 Ollama를 `127.0.0.1:11500`에 띄우고 이 PC에서 `ssh -N -L 11500:127.0.0.1:11500 <서버>`로 터널을 연다.
공고 글만 오가고 환자 데이터는 없다. 서버나 모델이 없으면 건너뛰고 아래 Claude 방식으로 넘어간다. `llm/config.toml`에 칸을 두는 것은 4명 검토 뒤에 한다.
평가: `python -m src.reimbursement.eval_llm --model qwen3:32b [--limit 20] [--similar 3] [--fix] [--previous 옛청크.jsonl]` (저장본 조건과 항목 일치·검사 통과·시간, 결과는 `reports/llm_eval_<모델>[_sim3][_fix][_update].json`, 행 이름과 숫자만).

Claude API를 쓰려면 `conda install -n team_project -c conda-forge anthropic` 후 저장소 루트 `.env`에 `ANTHROPIC_API_KEY=...`를 넣는다 (git 제외).
Claude Code로 돌리려면 터미널에서 `claude`를 한 번 실행해 `/login`으로 구독 계정에 로그인해 둔다. PATH에 없으면 Claude 데스크톱 앱에 든 것을 찾고, 다른 곳이면 `CLAUDE_CODE_EXE`에 경로를 넣는다.
조건 field 어휘와 환자 JSON 경로는 `conditions.py`의 `FIELDS` (설계 문서·`reimbursement_field_values.csv` 기준, B 검토). 환자 JSON 경로는 `patient_state` 0.1-draft6에 draft7 후보 칸을 더한 것이다 (A의 `draft7_checklist_BCD_2026-10-28` §3, 2026-10-29 반영).
병기·크기는 치료 시기에 맞는 칸을 따로 둔다 (체크리스트 §4): 선행요법 행은 `ct_stage`·`cn_status`·`clinical_size_mm`, 수술후보조요법 행은 `pt_stage`·`pn_status`·`pathologic_size_mm` (수술 병리 병기: 수술을 먼저 했으면 `ptnm`, 선행요법 뒤 수술이면 `yptnm`). 그 칸이 비면 다른 병기로 대신하지 않고 '알 수 없음'이다. 크기(cm) 조건은 T 범주로 바꾸지 않고 mm 값으로 둔다 ('직경 > 2㎝' → `clinical_size_mm gt 20`). 옛 `t_stage`·`ln_status`는 없앴다.
`cardiac_history`, `mediastinal_radiation`은 `patient.cardiac_history`·`mediastinal_radiation` (yes → true, no → false, 기록 없음은 알 수 없음)을 본다. 4나-19 '심장위험요소'의 공고 원문 정의에 LVEF 기준은 없다.
`bone_metastasis`는 '영상으로 입증'이라 `imaging_findings[]`의 bone + `confirmed`를 본다. 누적 용량은 `treatment_history[].doses[]` (mg면 키·몸무게로 mg/m²로 바꿈, 체표면적은 Mosteller: B 제안, D 동의 2026-10-29). cisplatin 1회 용량은 `per_admin_dose_mg_m2`.
`recurrence_operable`은 환자 JSON에 칸을 두지 않고, 재발 후 수술 여부(`recurrence.surgery`, `surgery_intent`)로 대신 읽는다. `surgery = yes`이고 `surgery_intent = curative`면 절제 가능, 그 밖은 '알 수 없음'이다 (A 결정 2026-10-21, PROJECT.md).
차수 간주 규칙 `counts_as_prior_line`은 draft6의 `fields.deemed_lines[]`와 대응한다. 항목에 `rule_id`가 있으면 그 규칙을 그대로 본다 (`schema_proposal.md`).
조건 131행 모두 D가 원문과 대조한 검수 기록이 있다 (`reports/review_decisions_20261001.tsv`, 일부는 B 확인). 2026-10-22까지 84행을 검수했고, 10-20 비교에서 두 작성본이 같아 기록이 없던 47행은 2026-11-03에 원문과 대조했다.
이때 형제 행까지 14행을 고쳤다. 주2 abemaciclib 고위험 각주(수술후보조 연번 1~9)와 trastuzumab LVEF 중단 기준(연번 20~24)은 `unmapped`·`human_review`에서 `notes`로 옮겼다. 각주는 abemaciclib 병용 때의 허가 기준이고 LVEF는 투여 시작 뒤의 중단 기준이라 투여 대상 조건이 아닌데, 그대로 두면 그 행이 늘 '알 수 없음'이 되기 때문이다. zoledronic acid 가에는 빠진 구절을 더했다.
의료진 검토는 아직이라, 판정 쪽(B)은 이 조건만으로 `covered`라고 하지 않고 `covered_conditions_unverified`로 둔다.

API 없이 손으로 쓴 조건도 같은 검사(형식·어휘·원문 구절)를 거쳐 저장본에 넣을 수 있다. 통과한 행만 들어가고, 이후 파이프라인은 그 결과를 그대로 쓴다.
2026-10-01 책자의 L3 131행은 이렇게 넣었다 (`data/reimbursement/conditions_manual/batch_*.json`, 작성자 "claude (대화에서 직접 작성, 2026-10-19)"). 책자 본문이 바뀐 행은 다시 써야 한다.
2026-11-01 책자(제2026-232호)는 유방암 내용이 바뀌지 않았다. 다시 편집하면서 마침표·따옴표·줄바꿈이 바뀌었고, 병용요법은 비소세포폐암 연번 11이 새로 생겨 유방암 행이 21~31로 하나씩 밀렸다. 그래서 공백·문장부호를 빼고 옛 행과 내용이 같은지 확인한 뒤 조건을 새 행으로 옮겼다 (작성자 뒤에 "(2026-11-01 책자로 옮김)"). 원문 구절 검사에 걸린 14행은 구절을 새 책자 문장부호로 맞췄다. 배치 파일의 키도 새 행 이름이다.
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
- `data/reimbursement/conditions_cache.jsonl` — 조건 결과 저장본 (로컬 LLM, Claude API, Claude Code 또는 `--import`)
- `data/reimbursement/reports/llm_eval_<모델>.json` — 로컬 LLM 비교 결과 (행 이름과 숫자만)
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
| `conditions.py` | 투여 조건 어휘(FIELDS), 로컬 모델(Ollama)·Claude 구조화, 예시 고르기·이전 판 찾기·규칙 고치기·다시 묻기, 원문 구절 검사, 결과 저장, 검수표 |
| `verify.py` | 로컬 모델 초안 확인 (팀 사전·숫자·빠진 조건·두 답 비교), 걸린 구절을 사람 검토로 |
| `eval_llm.py` | 조건 구조화 로컬 모델을 저장본 조건과 비교 |
| `schema_proposal.md` | `schemas/chunk.json` 개정안 (설계 문서의 새 칸) |
| `index.py` | 급여 청크를 C의 공용 색인에 넣기 (src/rag 함수 호출만) |
| `qc.py` | 단계별 품질 검사 함수 |
| `vocab.py` | 약제명 목록(공용 사전 + 유방암 추가분), 오타 찾기 |
| `registry.py` | SQLite 레지스트리 |
| `dates.py`, `status.py` | 날짜 표기 통일, §8 날짜 규칙 |
| `check_booklet.py` | 공고책자 하나만 검증하는 보조 실행 파일 |

새 약제가 나와 "약제명 목록에 없는 영문 낱말" 경고가 뜨면 `vocab.py`의 `BREAST_EXTRA`에 추가한다.

## 남은 일 (2026-11-02)

판정기가 새 칸 이름(`ct_stage` 등)과 Mosteller를 읽는 것은 B가 반영했다 (B 답변 2026-10-29).

| 할 일 | 누가 |
|---|---|
| 보류 세트 D 확인 (VC-0130~0144, 2026-10-29): 24개 중 15개 일치. 규칙은 보류 세트로 맞추지 않으므로 고치지 않고 판정 쪽 안건으로 넘김: `human_review`·`unmapped`가 있는 행을 충족으로 내지 않기 (zoledronic acid 가), 투약 중(`ongoing`) 요법의 `treatment_years`, 빈 이력의 `not_contains`(알 수 없음, A §6-5), `prior_failed` 요법 단위(A §4), `recent_therapy_28d`(기준일 전 투약만, PROJECT.md)는 이미 정한 규칙대로 나온 것이라 규칙은 그대로 두고, 시나리오 기대값과 다르다는 것만 A에게 알림 (VC-0137·0142·0138·0143) | B, A |
| 로컬 LLM 초안이 실제로 내용이 바뀐 공고에서 얼마나 맞는지 다음 공고 때 확인 (이번 평가의 바뀐 행은 문장부호 변경뿐) | D |
| 팀 사전 `reimbursement_terms.csv`의 '림프절 양성'(`stage.ptnm.n`)에 선행요법 행은 `stage.ctnm.n`이라는 설명 추가 (공용 폴더) | D 제안, 4명 검토 |
| 판정기: 선행요법을 받은 환자의 보조 행 `pt_stage`·`pn_status`·`pathologic_size_mm`는 `yptnm`(t, n, residual_size_mm)으로 읽기 (체크리스트 §4대로 D가 2026-11-02 정함) | B |
| 투여 조건 의료진 검토 (D 검수는 131행 모두 끝남, 2026-11-03) | D, B 확인 |
| `schemas/chunk.json` 개정 (`schema_proposal.md`) | D 제안, 4명 검토 |
| 판정 규칙 문서화 (`all_of`, `any_of`, `any_of_exceptions`, `unless`, `contains`, `not_contains`, 유전자 `vus`·`not_done` 처리) | B, D |
| 3가 밖의 "보조요법 종료 후 ~ 재발" 기간: 지금은 공고 문구대로 첫 재발일까지 셈 (2026-10-22, A가 지금 데이터로는 판단 불가라고 답함). 가상차트에 국소 재발 후 전이 환자가 생기면 다시 봄 | A, D |
| 결과물(청크, 조건 JSON, registry.db) 비공개 백업·공유 위치 | 팀 |
| 개정 공고 덧씌우기 (설계 §6). 새 공고가 올라오면 실행해 보고 만든다 | D |

회의 안건 결정 (2026-10-21):

| 안건 | 결정 |
|---|---|
| 1. `text_normalized` 위치 | 청크 최상위. 필수 칸이 아님 (ESMO 지침은 영어라 필요 없고, 필수로 하면 지침 청크를 모두 고쳐야 함). 검색은 지금처럼 원문 `text`로 하고 급여 검색은 약 이름·날짜로 거르므로 C 검색 코드는 바뀌지 않음. `schemas/chunk.json`은 공용 파일이라 4명 검토 |
| 2. `line_rule` 값 | 공고 표기 그대로 한국어 + `setting.line` 대응표 (`schema_proposal.md`). 다른 팀원 문서에 반대 내용 없음, B 동의 |
| 3. `copay` | 요법 전체에 하나일 때만 값, 약제마다 다르면 `null`과 `copay_by_drug`. 반영함. `recommendation.json` 설명은 PR로 4명 검토 |
| 4. 허가초과 | v0.1에서 쓰지 않음 (2026-11-02 결정, PROJECT.md §8 고침). 읽는 코드는 꺼 둔 채로 남김 |
| 5. 색인 주기 | 바뀌었을 때만, 앱 시작 직후·검색 전에. 같은 연결을 같이 써서 `close_searcher()`는 부르지 않음. 반영함 (위 "색인 주기") |
