# 처방 지침 RAG 설계 (B → C 전달용 초안)

> **2026-10-20 변경**: ASCO 지침은 재사용 불가로 확인돼 RAG에서 뺐다 (청커·청크·사전 표현 삭제). 아래의 ASCO 관련 내용은 기록으로만 남긴다. 지금 청킹·검색 대상은 ESMO EBC·MBC 2개다.


작성: 2026-10-16. 대상: `team_project/data/guidelines/`의 처방 지침 13개 (ESMO 2개, ASCO 11개)
근거: PDF 책갈피(목차), 본문 텍스트 추출(PyMuPDF), 키워드 출현 빈도, `schemas/*.json`
처방이 아닌 지침 8개는 이 문서에서 다루지 않는다. 제외 목록과 이유는 `rag_non_prescription_docs.md`에 있다.

## 목차

| 번호 | 제목 | 한 줄 요약 |
|---|---|---|
| **!** | **현재 문제점 요약 (먼저 읽기)** | 지금 C의 청크 데이터·코드와 이 설계 문서의 문제를 한곳에 모음 |
| !.1 | 청크 데이터 | 이미 만든 청크 106개의 문서 구성·메타데이터·텍스트·ID 문제 |
| !.2 | 검색 코드 | `src/rag/` 코드의 필터·ID·색인·테스트 문제 |
| !.3 | 설계와 다른 점 | PROJECT.md 계획 대비 빠진 기능 |
| !.4 | 이 설계 문서의 한계 | 아직 검증하지 않은 추정과 가정 |
| **K** | **핵심 필드 정의: subtype · setting · line** | 검색 필터에 쓰는 세 값이 무엇이고 어떤 값이 오는지 |
| K.1 | 두 쪽의 값 | 환자 쪽(B가 만든 값 1개)과 청크 쪽(C가 붙인 값 배열)을 비교하는 것이 필터라는 점 |
| K.2 | subtype | 아형 5개 값의 뜻, B의 판정 규칙, 청크 쪽 `any` |
| K.3 | setting (disease) | 병기 범주 4개 값의 뜻과 판정 규칙 |
| K.4 | line | 차수 6개 값의 뜻, 계산 규칙, 현재 상태(항상 unknown) |
| K.5 | unknown과 any | 이름은 비슷하지만 반대 쪽에서 쓰이는 두 값의 차이와 처리 규칙 |
| K.6 | 필터 통과표 | 환자 값과 청크 값 조합별로 지금 코드와 고친 코드의 결과 비교 |
| **A** | **RAG 검색 이론과 키워드가 필요한 이유** | 이 설계가 왜 키워드 표를 많이 쓰는지 이해하기 위한 배경 |
| A.1 | RAG란 | 검색한 지침 문장 안에서만 LLM이 답하게 하는 구조. 검색 품질이 곧 추천 품질 |
| A.2 | 벡터(임베딩) 검색 | 뜻이 비슷한 문장을 찾는 방법. 바꿔 쓴 표현에 강하고, 약제명·숫자·부정·JSON 코드에 약함 |
| A.3 | 키워드(BM25) 검색 | 같은 단어가 있는 문장을 찾는 방법. 정확 일치에 강하고, 동의어에 약함 |
| A.4 | 하이브리드 검색과 재정렬 | 두 검색을 합친 뒤 재정렬 모델이 질의와 문장을 함께 읽어 순위를 다시 매김 |
| A.5 | 메타데이터 필터 | 병기·아형처럼 틀리면 위험한 조건은 유사도가 아니라 태그로 먼저 거름 |
| A.6 | 계층적 청킹 | 작은 청크로 정확히 찾고, 큰 부모 청크로 문맥을 넘기는 방법 |
| A.7 | 그래서 키워드가 필요한 이유 | 키워드가 쓰이는 6곳 (문서 고르기, 필터, 질의문, BM25, 가중치, 청크 태깅) |
| **0** | **RAG 설계도** | 색인부터 검색까지 전체 구조 |
| 0.1 | 한눈에 보기 | PDF가 청크가 되고, 환자 JSON이 문서 → 문단 → 문장 순으로 좁혀 가는 전체 흐름도 |
| 0.2 | 청크 계층 | 문서(L0) / 섹션(L1) / 권고 문단(L2) / 문장(L3) 4단계로 자르는 단위와 각 단계의 역할 |
| 0.3 | 검색 단계별 동작 | 하드 필터·소프트 조건·질의문 구성, STEP 1~4에서 각각 무엇을 고르는지 |
| 0.4 | 예시 한 건 | ESR1 변이 HR+/HER2- 전이성 2차 환자가 각 단계에서 얻는 결과 |
| **1** | **대상 문서** | RAG에 넣는 처방 지침 13개 |
| 1.1 | ESMO | 조기·전이성 지침 2개의 범위와 권고가 놓인 위치 |
| 1.2 | ASCO | ASCO 처방 지침 11개의 내용, 대상 setting·subtype, 권고 형식 |
| 1.3 | 문서 사이 갱신 관계 | rapid update가 어떤 정규 지침 권고를 고치거나 보완하는지 (`superseded_by`) |
| 1.4 | 확인된 공백 | 지침 파일에 없어서 검색되지 않는 처방 영역 (ASCO HER2+ 조기, ESR1 처방 등) |
| **2** | **STEP 1: 문서 고르기 키워드** | 환자 JSON 값으로 후보 지침 파일을 정하는 규칙 |
| 2.1 | 1차 분기: setting.disease | 조기·국소진행·전이성에 따라 EBC 문서인지 MBC 문서인지 나누기 |
| 2.2 | 2차 분기: subtype | 아형별로 어떤 ASCO 파일을 고르는지 |
| 2.3 | 마커 트리거 | 바이오마커 양성(gBRCA, PIK3CA, ESR1, HER2-low 등)이 끌어오는 문서와 ESMO 섹션 |
| 2.4 | 보조 트리거 | 폐경, pCR, 림프절, 뇌·뼈 전이, ECOG 등 환자 상태 값이 끌어오는 권고 |
| **3** | **STEP 2·3: 문단·문장 매칭 어휘 사전** | JSON 값과 가이드라인 본문 단어를 짝지어 질의문과 태그를 만드는 사전 |
| 3.1 | subtype | 아형 코드와 ESMO·ASCO가 쓰는 아형 표현의 대응 |
| 3.2 | setting.disease | 병기 범주 코드와 지침의 병기·질환 상태 표현의 대응 |
| 3.3 | setting.line | 치료 차수 코드와 지침의 차수 표현의 대응, 그리고 line을 하드 필터로 쓰면 안 되는 이유 |
| 3.4 | prior_drug_classes | 이전 치료 약제군과 지침의 이전 치료 표현의 대응 |
| 3.5 | 바이오마커 → `biomarker_tags` | 환자 차트의 작성 단어와 가이드라인 본문 단어를 표준화할 태그 목록 |
| 3.6 | 약제명 | 약제 일반명·약어(T-DXd, SG, HP 등) 표준화 |
| **4** | **청킹 상세 규칙** | 실제로 PDF를 자르는 방법 |
| 4.1 | 문서별 분할 | ESMO MBC·EBC, ASCO 정규 지침·rapid update·Q&A별로 L1~L3를 어디서 자르는지 |
| 4.2 | 제외 소단원 | 처방 문서 안에서 청크로 만들지 않는 부분 |
| 4.3 | chunk_id 규칙 | 겹치지 않는 청크 ID를 파일명에서 만드는 형식 |
| 4.4 | 스키마 변경 | 이 설계를 위해 공용 `chunk.json`에서 바꿔야 할 것 |
| **5** | **텍스트 정제** | PDF 추출에서 깨진 하이픈·기호·대시·제어문자·그림 텍스트를 청킹 전에 고치는 방법 |
| **6** | **벡터 DB 구성** | 이 설계를 Qdrant로 구현할 때의 저장 구조 |
| 6.1 | 전체 구성 | 무엇을 Qdrant에 넣고, 무엇을 JSON 파일로 두는지 |
| 6.2 | 컬렉션 설정 | 벡터 2종(dense bge-m3 + sparse BM25)을 한 점(point)에 담는 컬렉션 정의 |
| 6.3 | 점(point) 구조 | 점 ID 규칙, 임베딩할 텍스트(문맥 머리말 붙이기), payload 필드 목록 |
| 6.4 | payload 인덱스 | 필터에 쓰는 필드와 인덱스 종류 |
| 6.5 | 검색 쿼리 구성 | STEP 1~4를 Qdrant 쿼리(필터, prefetch, RRF 융합)로 옮긴 모습 |
| 6.6 | 색인 절차 | 청크 JSON → 임베딩 → upsert 순서와 재색인·버전 관리 |
| 6.7 | 규모와 운영 | 예상 점 개수, 로컬 모드의 동시 접근 제약, D의 급여 청크와 같이 쓰는 방법 |
| **7** | **C가 고칠 것** | 현재 C 코드·청크의 문제를 P0(연동 필수) / P1(검색 품질) / P2(미구현)로 정리 |
| **8** | **팀 결정이 필요한 것** | 혼자 정할 수 없어 4명이 합의해야 하는 항목 |
| 부록 | 키워드 출현 빈도 | 문서 고르기 표의 근거가 된 파일별 키워드 빈도 |

---

## !. 현재 문제점 요약 (먼저 읽기)

`feature-rag-chunking`에서 들어온 C의 결과물(`data/chunks/*.json`, `src/rag/`, `tests/rag/`)을 2026-10-16 기준으로 확인한 결과다. 고치는 방법과 우선순위는 §7에 있다.

**한 줄 결론**: 지금 상태로 B가 검색을 부르면 ① 대부분의 ASCO 청크가 필터에 걸려 안 나오고, ② 나오는 청크의 43%는 처방과 무관한 검사·예방 지침이며, ③ 전이성 ESMO 권고와 HER2+ 전이성 권고는 거의 없다.

### !.1 청크 데이터 (`data/chunks/`, ASCO 68개 + ESMO 38개)

| # | 문제 | 확인한 사실 | 영향 |
|---|---|---|---|
| 1 | **처방이 아닌 문서가 섞임** | ASCO 68개 중 29개(43%)가 검사·예방·대체된 지침에서 나옴: ER/PR 검사 8, 생식세포 검사 8, MBC 바이오마커 검사 6, TAILORx(대체됨) 4, 예방 3 | 처방 질의에 검사법 문장이 상위로 올라옴 |
| 2 | **처방 문서가 빠지거나 너무 적음** | 0개: parp_olaparib, abemaciclib_qa, pembrolizumab_tnbc. 1개: trastuzumab_deruxtecan, sacituzumab, capivasertib. HER2+ 전이성 지침 3개, endocrine_targeted 4개 | 조기 TNBC의 pembrolizumab, 보조 olaparib·abemaciclib 권고가 검색될 수 없음 |
| 3 | **ESMO 전이성(MBC) 청크 없음** | ESMO 38개가 모두 EBC(`setting: early`). `esmo_mbc_2026-05.pdf`는 폴더에 있음 | 전이성 환자는 ESMO 권고를 하나도 못 받음 |
| 4 | **any 투성이 메타데이터** | ASCO 66/68개가 `subtype: ["any"]`, `line: ["any"]` | 아형·차수로 구분이 안 됨 (코드 문제 !.2-1과 겹쳐 아예 검색 안 됨) |
| 5 | **스키마 위반** | ESMO 11개가 `subtype: ["HER2+"]` (허용값은 `HR+/HER2+`, `HR-/HER2+`) | 스키마 검증 실패, HER2+ 환자 필터에 안 걸림 |
| 6 | **태그·약제 비어 있음** | `drugs` 채워진 청크 1개, `biomarker_tags` 3개 | 태그 가중치와 약제명 재확인(PROJECT.md §7 환각 방지)이 작동 안 함 |
| 7 | **ID·버전·출처 오류** | `chunk_id` 12종 중복, `version` 전부 `2023-01`, URL이 `doi.org/asco/<파일명>` 형태의 가짜 DOI | 인용이 엉뚱한 청크를 가리키고, 출처 표시를 그대로 쓸 수 없음 |
| 8 | **계층 없음** | 106개 모두 `chunk_kind: recommendation`, `parent_id` 0개 | 부모 소단원을 LLM에 넘길 수 없음, 문장 단위로 짚을 수 없음 |
| 9 | **길이 편차·텍스트 깨짐** | 2만 5천 자짜리 청크 1개, ESMO 제어문자 3개 (원인: PDF 불릿이 `\x03`으로 추출, §5) | 긴 청크는 벡터가 흐려지고 LLM 문맥을 낭비함 |

### !.2 검색 코드 (`src/rag/`)

| # | 파일 | 문제 | 영향 |
|---|---|---|---|
| 1 | `searcher.py` | `subtype`·`line`·`setting`을 `MatchValue`(정확 일치)로 거름 | `HR+/HER2-`로 부르면 `any` 청크 66개가 빠짐 |
| 2 | `searcher.py` | `unknown` 처리 없음 | B가 판정 불가(`unknown`)를 넘기면 결과 0건 |
| 3 | `searcher.py` | `line`이 하드 필터 | 지침은 차수를 조건문으로 써서 맞는 권고를 놓침 (§3.3) |
| 4 | `searcher.py` | `doc_type`, `superseded_by` 필터 없음 | D의 급여 청크가 들어오면 지침 검색에 섞이고, 대체된 권고도 나옴 |
| 5 | `searcher.py` | ESMO·ASCO를 한 순위로 섞어 상위 k개 | 한쪽 출처가 다른 쪽을 밀어냄 (출처별 분리 규칙 위반) |
| 6 | `indexer.py` | 점 ID가 `uuid4`(무작위) | `force_recreate=False`로 다시 색인하면 같은 청크가 중복으로 쌓임 |
| 7 | `indexer.py` | 청크 `text`만 임베딩 | 소단원·아형 문맥이 벡터에 안 들어감 (§6.3 문맥 머리말) |
| 8 | `run_indexing.py` | 컬렉션을 통째로 지우고 다시 만듦 | D의 급여 청크까지 같이 사라짐 |
| 9 | `run_indexing.py` | 스키마 검증 없이 색인 | !.1-5 같은 위반이 그대로 들어감 |
| 10 | `client.py` | 로컬 모드 (`path=`) | 한 프로세스만 DB를 열 수 있어 D의 색인과 B의 검색이 동시에 못 돎 |
| 11 | `tests/rag/test_search.py` | 실제 색인과 bge-m3(약 2GB)가 있어야 통과, 없으면 건너뛰지 않고 실패 | 다른 팀원 환경에서 테스트가 깨짐. 필터 로직 단위 테스트 없음 |

### !.3 설계(PROJECT.md §6, §15.6)와 다른 점

| 계획 | 현재 |
|---|---|
| bge-m3 + BM25 하이브리드 검색 | dense 벡터 검색만 |
| bge-reranker-v2-m3 재정렬 | 없음 |
| 부모 소단원을 함께 LLM에 넘김 | `parent_id` 없음 |
| `superseded_by`로 구버전 관리 | 필드만 있고 쓰지 않음 |
| ESMO EBC + MBC + ASCO 전체 | ESMO EBC 일부 + ASCO 일부 |

### !.4 이 설계 문서의 한계

| 항목 | 상태 |
|---|---|
| 청크 예상 개수(§6.7), 권고 개수(§1) | PDF 텍스트에서 정규식으로 센 추정치. 실제 청킹 후 달라질 수 있음 |
| 키워드 빈도(부록) | 하이픈·기호 깨짐을 고치기 전 텍스트로 셈. 약어(SG 등)는 빠짐 |
| 문서 고르기 표(§2), 어휘 사전(§3) | 목차와 권고문 일부를 읽고 만든 초안. 권고 전체를 하나씩 대조하지는 않음 |
| 검색 예시(§0.4, A.7) | 실제로 돌린 결과가 아니라 예상 결과 |
| Qdrant 코드(§6) | 실행해 보지 않음. qdrant-client 버전과 로컬 모드 지원 여부 확인 필요 |
| ASCO 기호 복원(§5) | `IHC 11` → `IHC 1+` 같은 규칙은 몇 군데만 확인함. 정규식이 다른 숫자를 잘못 바꿀 위험이 있어 전수 확인 필요 |
| 성능 기준 | 맞는 권고를 몇 % 찾아야 통과인지 정하지 않음. 가상 환자로 정답 권고 목록을 만들어 평가해야 함 |

---

## K. 핵심 필드 정의: subtype · setting · line

§7의 1~3번(필터 수정)을 이해하려면 이 세 값이 무엇인지부터 알아야 한다.
근거: `schemas/biomarker_record.json`, `schemas/chunk.json`, `src/biomarker/BM1_ER,PR,HER2,Ki_67,subtype.py`, `src/input/handoff_to_B.md` §6

### K.1 두 쪽의 값: 환자 쪽과 청크 쪽

같은 이름의 필드가 두 곳에 있고, **검색 필터는 둘을 비교하는 일**이다.

| | 환자 쪽 (질의) | 청크 쪽 (색인) |
|---|---|---|
| 어디에 | `biomarker_record.subtype`, `biomarker_record.setting.disease`, `biomarker_record.setting.line` | `chunk.subtype`, `chunk.setting`, `chunk.line` |
| 누가 만드나 | B (규칙 코드) | C (청킹할 때 태깅) |
| 형식 | **값 1개** (문자열) | **값 배열** (그 권고가 적용되는 범위 전부) |
| 뜻 | "이 환자는 지금 어떤 상태인가" | "이 권고는 어떤 환자에게 해당하나" |
| 모를 때 | `unknown` | (해당 없음) |
| 전부 해당할 때 | (해당 없음) | `any` |

필터 규칙: **환자 값 1개가 청크 배열 안에 있으면 통과.** 예: 환자 `subtype = "TNBC"`, 청크 `subtype = ["HR+/HER2-", "TNBC"]` → 통과.

### K.2 subtype (아형)

호르몬 수용체(HR)와 HER2 상태로 나눈 유방암 아형이다. 처방 지침은 거의 모든 권고를 아형별로 나눠 쓴다.

**환자 쪽 값** (`biomarker_record.subtype`)

| 값 | 뜻 | B의 판정 조건 (`subtype_of`) | 지침 표현 (§3.1) |
|---|---|---|---|
| `HR+/HER2-` | 호르몬 수용체 양성, HER2 음성 | (ER 또는 PR 양성) + HER2가 negative·low·ultralow | ER-positive HER2-negative, luminal, HR-positive |
| `HR+/HER2+` | 호르몬 수용체 양성, HER2 양성 | (ER 또는 PR 양성) + HER2 positive | HER2-positive (HR-positive) |
| `HR-/HER2+` | 호르몬 수용체 음성, HER2 양성 | ER·PR 모두 음성 + HER2 positive | HER2-positive, HR-negative |
| `TNBC` | 삼중음성 (ER·PR·HER2 모두 음성) | ER·PR 모두 음성 + HER2가 negative·low·ultralow | triple-negative, TNBC |
| `unknown` | 아형을 정할 수 없음 | ER·PR·HER2 중 판정이 없는 값이 있어 위 넷에 안 들어감 | — |

판정에서 주의할 점:
- **ER 저발현(1~9%)은 지금 HR+로 본다** (`ER_LOW_IS_HR_POSITIVE = True`). 팀 결정 전 임시값이다.
- **HER2 low·ultralow는 아형에서 HER2-음성**이다. 그래서 HER2-low 환자는 `HR+/HER2-`나 `TNBC`가 되고, HER2-low 여부는 아형이 아니라 바이오마커 레코드(`HER2` status `low`)와 태그(`HER2-low`)로 따로 전달된다. trastuzumab deruxtecan 권고는 아형 필터가 아니라 태그로 찾는다.
- 분자 아형(Luminal A/B 등)은 출력에 넣지 않는다. 지침의 "luminal A-like" 같은 표현은 질의문에서만 쓴다.

**청크 쪽 값** (`chunk.subtype`, 배열): 위 4개 + `any`. `unknown`은 없다.

| 권고 예 | 청크 subtype |
|---|---|
| "AI–CDK4/6 inhibitor ... ER-positive, HER2-negative MBC" | `["HR+/HER2-"]` |
| "HER2-directed therapy ... 12 months" (HR 상태 무관) | `["HR+/HER2+", "HR-/HER2+"]` (지금 ESMO 청크는 `["HER2+"]`로 잘못 씀) |
| "olaparib ... gBRCA1/2m and HER2-negative" | `["HR+/HER2-", "TNBC"]` |
| "Brain imaging is recommended for symptomatic patients" | `["any"]` |

### K.3 setting (병기 범주)

치료 목적이 완치(조기·국소진행)인지 연장·완화(전이성)인지를 가른다. **조기 지침(EBC)과 전이성 지침(MBC)이 완전히 다른 문서**라서 가장 먼저 거르는 값이다.

**환자 쪽 값** (`biomarker_record.setting.disease`)

| 값 | 뜻 | B의 판정 조건 (`setting_of`, 전달 문서 §6.1) |
|---|---|---|
| `early` | 조기 (진단 시 I~II기) | 진단 시 범주가 early이고 원격 전이 재발이 없음 |
| `locally_advanced` | 국소 진행성 (진단 시 III기, 심평원 급여 조건 기준) | 진단 시 범주가 locally_advanced이고 원격 전이 재발이 없음 |
| `metastatic` | 전이성 | 진단 시 IV기(M1) **또는** 이후 원격 전이 재발 |
| `unknown` | 모름 | 진단 시 병기 범주 기록이 없음 |

- 국소 재발(`recurrence.status = locoregional`)은 전이가 아니므로 진단 시 범주를 그대로 쓴다.
- `locally_advanced`는 수술 가능하면 EBC 지침(선행요법), 수술 불가능하면 MBC 지침에 가깝다. `patient_state.stage.operable`로 가른다 (§2.1).

**청크 쪽 값** (`chunk.setting`, 배열): `early`, `locally_advanced`, `metastatic`. **`any`가 없다.** 여러 범주에 해당하는 권고는 해당하는 값을 모두 넣는다 (예: ESMO EBC의 선행요법 권고 → `["early", "locally_advanced"]`).

### K.4 line (치료 차수)

이 환자가 지금 몇 번째 치료를 받을 차례인지다. 조기·국소진행과 전이성에서 쓰는 값이 다르다.

**환자 쪽 값** (`biomarker_record.setting.line`)

| 값 | 뜻 | 쓰는 범주 |
|---|---|---|
| `neoadjuvant` | 수술 전 선행요법 차례 | early, locally_advanced |
| `adjuvant` | 수술 후 보조요법 차례 (선행 후 잔존 질환에 대한 추가 요법 포함) | early, locally_advanced |
| `1L` | 전이 후 첫 번째 요법 차례 | metastatic |
| `2L` | 전이 후 첫 요법에서 진행, 두 번째 차례 | metastatic |
| `>=3L` | 전이 후 세 번째 이상 | metastatic |
| `unknown` | 계산할 수 없음 | 모두 |

계산 규칙 (전달 문서 §6.2): 전이 기준일(`recurrence.metastasis_day`) 이후 시작한 요법을 시작일 순으로 세고, **진행(PD)으로 바뀐 요법만** 다음 차수로 센다. 계획된 순차 요법(AC→T)과 유지요법은 같은 차수다. 보조약·골 보호제는 세지 않는다.

**현재 상태**:
- **B 코드(`setting_of`)는 지금 `line`을 항상 `unknown`으로 낸다.** 아직 계산하지 않는다.
- 2026-10-16에 차수 계산 담당이 A의 변환 단계로 바뀌었다 (전달 문서 §6 담당). 스키마 설명은 아직 "B가 산출"로 되어 있어 정리가 필요하다.
- 지침 차수와 심평원 급여 투여단계는 세는 법이 다르다. 급여는 고식적 내분비요법과 고식적 항암화학요법을 **따로** 센다 (전달 문서 §6.3). `line`은 지침 차수 하나만 담는다.

**청크 쪽 값** (`chunk.line`, 배열): 위 5개 + `any`. `unknown`은 없다.

line을 하드 필터로 쓰면 안 되는 이유는 §3.3에 있다. 요약하면 지침은 "보조 ET 종료 12개월 이내 재발", "ET 2차례 이후"처럼 차수를 조건으로 쓰고, 환자 쪽 값은 지금 항상 `unknown`이다.

### K.5 unknown과 any

| | `unknown` | `any` |
|---|---|---|
| 쓰는 쪽 | 환자 쪽 (B 출력) | 청크 쪽 (C 태깅) |
| 뜻 | "이 환자의 값을 모른다" | "이 권고는 모든 값에 해당한다" |
| 필터에서 처리 | **필터를 건다** → 그 필드 조건을 빼고 검색 | **항상 통과** → 환자 값이 무엇이든 포함 |
| 지금 코드 | `MatchValue("unknown")`로 찾아 결과 0건 | `MatchValue("HR+/HER2-")`와 안 맞아 빠짐 |

### K.6 필터 통과표 (subtype 예)

환자 `subtype`과 청크 `subtype` 조합별 결과. `line`도 같은 원리다.

| 환자 값 | 청크 값 | 지금 코드 (`MatchValue`) | 고친 코드 (`MatchAny([값, "any"])`, unknown이면 필터 없음) |
|---|---|---|---|
| `HR+/HER2-` | `["HR+/HER2-"]` | 통과 | 통과 |
| `HR+/HER2-` | `["HR+/HER2-", "TNBC"]` | 통과 | 통과 |
| `HR+/HER2-` | `["any"]` | **빠짐** | 통과 |
| `HR+/HER2-` | `["TNBC"]` | 빠짐 | 빠짐 (맞음) |
| `HR+/HER2+` | `["HER2+"]` (현재 ESMO 오류) | **빠짐** | **빠짐** → 청크를 `["HR+/HER2+", "HR-/HER2+"]`로 고쳐야 함 |
| `unknown` | 아무 값 | **모두 빠짐 (0건)** | 모두 통과 (아형 필터 없음) |

지금 ASCO 청크 68개 중 66개가 `["any"]`라서, 환자 아형을 넣고 검색하면 ASCO는 사실상 2개만 후보가 된다.

---

## A. RAG 검색 이론과 키워드가 필요한 이유

### A.1 RAG란

RAG(Retrieval-Augmented Generation)는 **먼저 관련 문서 조각(청크)을 검색하고, LLM은 검색된 조각 안에서만 답하게 하는** 구조다.

```
환자 정보 → [검색기] → 지침 청크 k개 → [LLM] → 처방 후보 + 인용 청크 ID
```

- LLM이 기억에 의존해 지어내지(환각) 않게 하고, 모든 문장에 출처를 붙일 수 있다 (PROJECT.md §7).
- 반대로 **검색기가 맞는 권고를 못 가져오면 LLM은 그 처방을 절대 말할 수 없다.** 처방 추천의 품질은 검색 단계에서 대부분 정해진다.
- 그래서 이 문서는 LLM 프롬프트보다 "어떤 청크를 어떻게 찾을지"에 집중한다.

### A.2 벡터(임베딩) 검색: 뜻으로 찾기

- 임베딩 모델(bge-m3)이 문장을 1024개 숫자(벡터)로 바꾼다. 뜻이 비슷한 문장은 벡터 방향이 비슷하다.
- 질의문 벡터와 청크 벡터의 코사인 유사도가 높은 순으로 가져온다. 지금 C의 `searcher.py`가 이 방식만 쓴다.

| 잘하는 것 | 못하는 것 (처방 RAG에서 문제가 되는 것) |
|---|---|
| 바꿔 쓴 표현: "progression after AI" ≈ "endocrine-pretreated" | **약제명·유전자명 정확 일치**: elacestrant와 imlunestrant, olaparib와 talazoparib를 비슷하게 봄 |
| 다른 문장 구조라도 같은 뜻이면 찾음 | **부정·반대 조건**: "PIK3CA-mutated"와 "PIK3CA-wild type"의 벡터가 매우 가까움 |
| 오타·어순 차이에 강함 | **숫자·기준값**: "≤12 months"와 ">12 months", "IHC 1+"와 "IHC 3+"를 구분 못 함 |
| | **JSON 코드**: `HR+/HER2-`, `2L`, `gBRCA1 positive` 같은 코드는 지침 본문에 그대로 나오지 않아 유사도가 낮음 |
| | **긴 청크**: 한 청크에 여러 권고가 섞이면 벡터가 평균이 돼서 어느 질의에도 애매하게 걸림 |

### A.3 키워드(BM25) 검색: 단어로 찾기

- 질의 단어가 청크에 몇 번 나오는지(TF)와 그 단어가 전체 문서에서 얼마나 드문지(IDF)로 점수를 매긴다. "capivasertib"처럼 드문 단어가 일치하면 점수가 크게 오른다.

| 잘하는 것 | 못하는 것 |
|---|---|
| 약제명, 유전자명, 약어(T-DXd, ESR1)의 정확 일치 | **동의어**: 질의가 "HR-positive"인데 ESMO는 "ER-positive", "luminal"이라고 씀 |
| 드문 전문 용어에 강함 | **뜻 이해 없음**: "after at least one line of ET"가 2차라는 것을 모름 |
| | 텍스트가 깨지면 바로 실패: `der-uxtecan`, `IHC 11` (§5) |

### A.4 하이브리드 검색과 재정렬

- **하이브리드**: 벡터 순위와 BM25 순위를 합친다 (예: RRF, 두 순위의 역수를 더함). 뜻과 정확한 단어를 둘 다 본다. PROJECT.md §6의 계획이다.
- **재정렬(reranker)**: bge-reranker-v2-m3는 질의와 청크를 **한 번에 같이 읽고** 관련도를 매긴다. 벡터 검색보다 조건·부정을 잘 구분하지만 느려서 상위 20개 정도에만 쓴다.

```
전체 청크 → (필터) → 하이브리드로 상위 20개 → (재정렬) → 상위 k개
```

### A.5 메타데이터 필터: 틀리면 위험한 조건은 태그로

- 청크마다 `setting`, `subtype`, `line`, `biomarker_tags`, `drugs` 같은 구조화된 값을 붙여 두고, 유사도 계산 **전에** 조건이 맞는 청크만 남긴다.
- 조기 유방암 환자에게 전이성 권고가, TNBC 환자에게 HER2+ 권고가 섞이면 의학적으로 위험하다. 유사도는 확률이라 이 구분을 보장하지 못한다. 그래서 병기와 아형은 **하드 필터**(안 맞으면 제외)로 쓴다.
- 차수(line)나 바이오마커처럼 지침이 조건문으로 쓰는 값은 **소프트 조건**(맞으면 점수 가산)으로 쓴다. 하드 필터로 쓰면 맞는 권고를 놓친다 (§3.3).

### A.6 계층적 청킹: 작게 찾고 크게 넘기기

| 청크 크기 | 장점 | 단점 |
|---|---|---|
| 작음 (문장 1개) | 질의와 정확히 맞는 처방 문장을 짚음 | 앞뒤 조건(아형, 이전 치료)이 잘려 LLM이 오해할 수 있음 |
| 큼 (소단원 전체) | 문맥이 다 들어 있음 | 여러 권고가 섞여 벡터가 흐려지고 검색 정확도가 떨어짐 |

- 해결책은 **small-to-big**(부모 문서 검색)이다. 작은 단위(권고 L2, 문장 L3)로 검색하고, 맞은 청크의 부모(섹션 L1)를 LLM에 함께 넘긴다.
- 문서(L0) 단위로 먼저 후보를 줄이면 엉뚱한 지침의 비슷한 문장이 끼어드는 것도 막는다.

### A.7 그래서 키워드가 필요한 이유

B의 JSON은 `HR+/HER2-`, `metastatic`, `2L`, `ESR1 positive` 같은 **코드**이고, 지침은 "ER-positive, HER2-negative MBC ... after at least one line of ET ... ESR1-mutated" 같은 **문장**이다. 키워드 사전은 이 둘을 잇는 다리다. 이 문서의 키워드 표는 아래 6곳에 쓰인다.

| # | 쓰이는 곳 | 하는 일 | 없으면 생기는 문제 | 해당 절 |
|---|---|---|---|---|
| 1 | 문서 고르기 (STEP 1) | JSON 값으로 후보 지침 파일을 정함 | 전이성 환자에게 조기 지침 문장이 섞임 | §2 |
| 2 | 메타데이터 필터 | 청크의 `setting`/`subtype` 태그와 JSON 값을 비교 | 아형·병기가 다른 권고가 결과에 들어옴 | §2, §3.1~3.2 |
| 3 | 질의문 만들기 | JSON 코드를 지침 표현으로 바꿔 질의문을 만듦 (질의 확장) | `HR+/HER2- 2L`로 검색하면 유사도가 낮아 엉뚱한 결과 | §3 |
| 4 | BM25 정확 일치 | 약제명·마커명·약어를 정확히 맞춤 | 비슷한 이름의 다른 약제가 섞임 | §3.5, §3.6 |
| 5 | 태그 가중치 | `biomarker_tags`, `line`이 맞으면 점수 가산 | 같은 차수 안에서 환자 변이에 맞는 선택지가 위로 오지 않음 | §3.3, §3.5 |
| 6 | 청크 태깅 (색인 때) | 같은 사전으로 청크에 태그를 붙임 | 질의 쪽과 청크 쪽 단어가 달라 2·4·5번이 작동 안 함 | §3, §4 |

예: 같은 환자를 두 가지 질의문으로 검색할 때

| 질의문 | 예상 결과 |
|---|---|
| `HR+/HER2- metastatic 2L ESR1 positive` (JSON 그대로) | 코드가 본문에 없어 유사도가 낮다. ESR1 검사법 문장이나 일반 2차 문장이 섞인다 |
| `ER-positive HER2-negative metastatic breast cancer, progression after aromatase inhibitor and CDK4/6 inhibitor, ESR1-mutated, second-line` (사전으로 변환) | ESMO luminal 2L의 elacestrant/imlunestrant 권고가 상위에 온다 |

---

## 0. RAG 설계도

### 0.1 한눈에 보기

```
[색인: 미리 한 번]
 처방 지침 PDF 13개
   │ ① 텍스트 정제 (하이픈, 깨진 기호, 머리말·꼬리말)
   │ ② 책갈피로 소단원 구조 파싱, 처방 무관 소단원 제외
   │ ③ 4단계 계층 청크 생성 (L0 문서 / L1 섹션 / L2 권고 / L3 문장)
   │ ④ 메타데이터 태깅 (setting, subtype, line, biomarker_tags, drugs, evidence)
   ▼
 Qdrant: L2·L3·근거 문단은 벡터(bge-m3) + BM25, L0·L1은 메타데이터만

[검색: 환자마다]
 patient_state.json + biomarker_record.json
   │ ⓐ 질의 프로필 만들기: 하드 필터 / 소프트 조건 / 질의문
   ▼
 STEP 1 문서 고르기 (L0)   setting.disease, subtype, 마커로 후보 문서를 좁힘
   ▼
 STEP 2 문단 고르기 (L2)   후보 문서 안에서 권고 문단을 하이브리드 검색
   ▼
 STEP 3 문장 고르기 (L3)   상위 권고 안에서 약제·조건 문장을 짚음
   ▼
 STEP 4 정리               재정렬, 부모 섹션(L1) 붙이기, ESMO/ASCO 분리
   ▼
 B의 추천 LLM → recommendation.json (citations = 청크 ID)
```

### 0.2 청크 계층: 무엇을 어떤 크기로 자르나

| 단계 | 단위 | 예 (ESMO MBC) | 예 (ASCO) | 하는 일 |
|---|---|---|---|---|
| **L0 문서** | PDF 1개 | `esmo-mbc-2026-05` | `asco-mbc-2021-07-endo` | 문서 고르기. 임베딩 안 함 |
| **L1 섹션** | 책갈피 최하위 소단원 | Management of luminal MBC > Second-line treatment | Clinical Question 3 + 질문문 | LLM에 넘기는 부모 문맥 |
| **L2 권고** | 권고 1개 | `•` 불릿 1개와 그 아래 `○` 선택지 전부 | `Recommendation 3.2.` 문장과 Qualifying statement | 문단 검색의 기본 단위 |
| **L3 문장** | 약제 선택지 1개 또는 문장 1개 | `○ Fulvestrant—palbociclib (ESMO-MCBS v2.0 score: 4)` | 권고 안의 문장 1개 | 정확한 처방 문장 짚기 |
| L2' 근거 | 근거 문단 300~800토큰 | (ESMO EBC 본문) | Literature review, Clinical interpretation | 보조 근거. 가중치를 낮춤 |

부모-자식은 `parent_id`로 연결한다: L3 → L2 → L1 → L0.

### 0.3 검색 단계별 동작

**ⓐ 질의 프로필**: B의 JSON 값을 세 가지로 나눈다.
- 하드 필터 (틀리면 안 되는 조건): `setting.disease`, `subtype`. `subtype`은 `[값, "any"]`로 찾는다. 값이 `unknown`이면 필터를 뺀다.
- 소프트 조건 (점수만 더함): `setting.line`, 바이오마커 태그, 폐경 여부, 이전 약제, 전이 부위
- 질의문: §2 어휘 사전으로 JSON 값을 지침 표현으로 바꿔 영어 문장 하나로 만든다.

**STEP 1 문서 고르기 (L0)**: 벡터를 쓰지 않고 표(§2.1~2.3)로 정한다. 예: `metastatic` + `HR+/HER2-` → ESMO MBC, ASCO endocrine_targeted, capivasertib, chemo_targeted, sacituzumab. HER2가 low면 trastuzumab_deruxtecan을 더한다. `superseded_by`가 있는 청크는 뺀다.

**STEP 2 문단 고르기 (L2)**: 후보 문서 안의 L2 권고만 대상으로 한다.
- 질의문 벡터 유사도(bge-m3)와 BM25 점수를 합친다. 약제명이나 마커명처럼 정확히 일치해야 하는 단어는 BM25가 잡는다.
- `line`이 맞으면 점수를 더하고, `biomarker_tags`가 겹치면 하나당 점수를 더한다.
- 상위 20개를 재정렬 모델(bge-reranker-v2-m3)로 다시 매기고 상위 k개를 남긴다.

**STEP 3 문장 고르기 (L3)**: STEP 2에서 남은 권고의 자식 L3만 다시 검색한다.
- 같은 질의로 유사도를 계산해 가장 맞는 선택지·문장을 고른다. 예: 같은 1L 권고라도 PIK3CA 변이 환자는 "Fulvestrant—palbociclib—inavolisib" 줄이 위로 온다.
- L3가 아주 높게 맞았는데 그 부모 L2가 STEP 2에서 빠졌으면 부모를 결과에 다시 넣는다 (small-to-big).

**STEP 4 정리**: 결과마다 L2 전문, 하이라이트할 L3, L1 섹션 전문, 출처(문서·쪽·버전·DOI), 근거 수준을 묶는다. ESMO와 ASCO는 합치지 않고 따로 돌려준다.

### 0.4 예시 한 건

입력: `metastatic`, `HR+/HER2-`, `line=2L`, `prior_drug_classes=[aromatase inhibitor, CDK4/6 inhibitor]`, ESR1 positive, PIK3CA negative, 폐경 후

| 단계 | 결과 |
|---|---|
| ⓐ | 하드 필터 `setting ∋ metastatic`, `subtype ∈ {HR+/HER2-, any}`. 소프트 조건 `line=2L`, `ESR1-mut`, `PIK3CA-wt`. 질의문 "ER-positive HER2-negative metastatic breast cancer, progression after aromatase inhibitor and CDK4/6 inhibitor, ESR1-mutated, postmenopausal, second-line" |
| STEP 1 | ESMO MBC, ASCO endocrine_targeted, capivasertib, chemo_targeted, sacituzumab |
| STEP 2 | ESMO luminal 2L "Elacestrant or imlunestrant ... ESR1-mutated MBC after at least one line of ET" 권고, ASCO endocrine_targeted Rec 3.2 (fulvestrant + CDK4/6) 등 |
| STEP 3 | "Elacestrant [I, A; ESMO-MCBS v2.0 score: 3] or imlunestrant ..." 문장 |
| STEP 4 | 부모 L1 = "Management of luminal MBC > Second-line treatment" 전문, 출처 ESMO MBC 2026-05 p4 |

---

## 1. 대상 문서: 처방 지침 13개

### 1.1 ESMO (2개)

| 파일 | 범위 | 권고 형식 | 구조 (책갈피) |
|---|---|---|---|
| `esmo_ebc_2024-02` (24쪽) | 조기·국소진행(수술 가능), 전 아형, 선행/보조/선행 후 | `• 문장 [I, A; ESMO-MCBS; ESCAT]` 불릿 약 110개. **권고가 p13~15에 아형별로 모여 있음** | (Neo)adjuvant systemic treatment > HR+/HER2- · HER2+ · TNBC · 잔존 질환. 그 뒤 Recommendations > 같은 아형 소제목 |
| `esmo_mbc_2026-05` (17쪽) | 전이성, 전 아형 | 불릿 약 320개. 하위 선택지는 `○`, `■`. **권고가 소단원마다 본문 안에 있음** | luminal > 1L/2L/≥3L, HER2+ > 1L/2L/3L/≥4L, TNBC > 1L/≥2L, Site-specific > de novo IV · OMD · 뼈 · 뇌 전이 · LMD |

### 1.2 ASCO (11개)

| 파일 | 내용 | setting / subtype | 권고 형식 |
|---|---|---|---|
| `asco_ebc_2021-08_parp_olaparib` | gBRCA, 고위험, HER2-음성 보조 olaparib | early / HR+/HER2-, TNBC | Rapid update, 번호 없는 권고 1개 |
| `asco_ebc_2022-01_bisphosphonates_bone` | 보조 bisphosphonate·denosumab | early / any (폐경 후) | Rec 2.1, 3.1 등 |
| `asco_ebc_2022-04_abemaciclib_qa` | 보조 abemaciclib Q&A (Ki-67, olaparib 병용, 방사선) | early / HR+/HER2- | **Question 6개** (정식 권고 아님) |
| `asco_ebc_2022-04_biomarkers_adjuvant` | 유전자 검사·Ki-67로 보조 항암·연장 ET 여부 결정 | early / 주로 HR+/HER2- | Rec 1.1~1.26 등 31개 |
| `asco_ebc_2022-04_pembrolizumab_tnbc` | 고위험 조기 TNBC 선행 pembrolizumab | early(neoadjuvant) / TNBC | Rapid update 1개 + Qualifying statements |
| `asco_mbc_2021-07_chemo_targeted_guideline` | HER2-음성 MBC 항암·표적 (ET 이후 또는 HR-) | metastatic / HR+/HER2- (내분비 불응), TNBC | Rec 1.1~4.1 |
| `asco_mbc_2021-07_endocrine_targeted` | HR+/HER2- MBC 내분비·표적 (alpelisib, CDK4/6, PARPi) | metastatic / HR+/HER2- | Rec 1.1, 2.3, 3.1~3.2 (2.1·2.2는 검사 권고라 제외) |
| `asco_mbc_2022-05_her2_positive_systemic` | HER2+ 진행성 1L·2L·3L+, 뇌 전이 | metastatic / HR+/HER2+, HR-/HER2+ | Rec 1.x~3.x. 약제별 소제목(3.1.1 T-DM1 등) |
| `asco_mbc_2022-08_..._trastuzumab_deruxtecan` | HER2-low에 T-DXd (DESTINY-Breast04) | metastatic / HR+/HER2-, TNBC (HER2-low) | Rapid update 1개 |
| `asco_mbc_2023-01_..._sacituzumab_govitecan` | HR+/HER2-, 내분비 불응, 항암 2~4차 이후 SG | metastatic / HR+/HER2- | Rapid update 1개 |
| `asco_mbc_2024-03_capivasertib_fulvestrant` | PIK3CA/AKT1/PTEN 변이에 capivasertib | metastatic / HR+/HER2- | Rec 1.1, 1.2 + Qualifying |

### 1.3 문서 사이 갱신 관계 (`superseded_by`)

| 이전 | 이후 | 관계 |
|---|---|---|
| `asco_mbc_2021-07_chemo_targeted_guideline` 관련 권고 | `..._2022-08_trastuzumab_deruxtecan`, `..._2023-01_sacituzumab_govitecan` | 권고 추가·수정 |
| `asco_mbc_2021-07_endocrine_targeted` Rec 1.1 (alpelisib) | `asco_mbc_2024-03_capivasertib_fulvestrant` | 선택지 추가 (대체 아님) |

어떤 권고가 정확히 바뀌었는지는 rapid update의 BACKGROUND를 보고 C가 권고 단위로 연결한다.

### 1.4 확인된 공백
- ASCO에는 **HER2+ 조기 유방암 처방 지침이 없다.** 조기 HER2+는 ESMO EBC만 검색된다.
- **ESR1 변이 처방(elacestrant)은 ESMO MBC에만 있다.**
- ASCO 전이성 HR+ 1L 최신 개정 등은 폴더에 없다. 추가할지는 팀 결정이다.

---

## 2. STEP 1: 문서 고르기 키워드

### 2.1 1차 분기: `biomarker_record.setting.disease`

| 값 | ESMO | ASCO |
|---|---|---|
| `early` | ESMO EBC | `asco_ebc_*` 5개 |
| `locally_advanced` | ESMO EBC (수술 가능). `patient_state.stage.operable.value = no`면 ESMO MBC 추가 | `asco_ebc_*`. 수술 불가면 `asco_mbc_*` 추가 |
| `metastatic` | ESMO MBC | `asco_mbc_*` 6개 |
| `unknown` | 둘 다 | 둘 다 |

### 2.2 2차 분기: `biomarker_record.subtype` (ASCO 문서 고르기)

| subtype | early (ASCO) | metastatic (ASCO) |
|---|---|---|
| `HR+/HER2-` | biomarkers_adjuvant, abemaciclib_qa, parp_olaparib\*, bisphosphonates\*\* | endocrine_targeted, capivasertib, chemo_targeted, sacituzumab, trastuzumab_deruxtecan\*\*\* |
| `HR+/HER2+` | (없음, ESMO만) | her2_positive_systemic |
| `HR-/HER2+` | (없음, ESMO만) | her2_positive_systemic |
| `TNBC` | pembrolizumab_tnbc, parp_olaparib\* | chemo_targeted, trastuzumab_deruxtecan\*\*\* |
| `unknown` | 위 전부 | 위 전부 |

\* gBRCA 양성일 때, \*\* 폐경 후 또는 OFS일 때, \*\*\* HER2 `low`/`ultralow`일 때 가중치를 준다.
ESMO는 setting마다 문서가 하나라서 subtype은 STEP 2의 청크 필터로 쓴다.

### 2.3 마커 트리거: `biomarker_record.records[]` (positive일 때)

| marker | 끌어오는 ASCO 문서 | 끌어오는 ESMO 섹션 |
|---|---|---|
| `gBRCA1`/`gBRCA2` | parp_olaparib(early), endocrine_targeted Rec 2.3, chemo_targeted | EBC HR+/HER2- · TNBC (olaparib), MBC luminal 2L · TNBC |
| `PALB2` | 없음 | MBC luminal 2L (olaparib/talazoparib [II, B]) |
| `sBRCA1`/`sBRCA2` | endocrine_targeted Qualifying statement | MBC luminal 2L |
| `PIK3CA` | capivasertib, endocrine_targeted Rec 1.1 (alpelisib) | MBC luminal 1L(inavolisib), 2L |
| `AKT1`, `PTEN` | capivasertib | MBC luminal 2L |
| `ESR1` | 없음 | MBC luminal 2L (elacestrant, imlunestrant) |
| `HER2` low / ultralow | trastuzumab_deruxtecan | MBC luminal ≥3L, TNBC 2L+, 뇌 전이 |
| `PD-L1` | chemo_targeted | MBC TNBC 1L. EBC TNBC는 PD-L1과 무관하게 pembrolizumab |
| `Ki-67` | abemaciclib_qa, biomarkers_adjuvant | EBC HR+/HER2- |

상태가 `not_done`·`retest_needed`인 마커는 문서를 끌어오지 않는다. 그 마커가 필요한 치료는 B의 후처리에서 검사 권고(`tests_needed`)로 바뀐다.

### 2.4 보조 트리거: `patient_state.fields`

| 필드 | 값 | 끌어오는 것 |
|---|---|---|
| `patient.menopausal_status` | premenopausal / perimenopausal | OFS 권고 (ESMO EBC·MBC). bisphosphonates 제외 |
| `patient.gender` | MALE | ASCO endocrine_targeted의 male 문구 |
| `neoadjuvant_response.pcr` | no | EBC 잔존 질환 (T-DM1, capecitabine, olaparib) |
| `stage.positive_ln_count` | 양성 ≥1, ≥4 | EBC abemaciclib(고위험), pertuzumab(림프절 양성), olaparib |
| `stage.metastatic_sites`, `recurrence.metastatic_sites` | brain | MBC Site-specific > BMs, her2_positive_systemic (tucatinib) |
| 같은 필드 | bone | MBC 뼈 전이, bone-modifying agents |
| `patient.ecog` | ≥2 | MBC "ET alone" 등 PS 관련 권고 |
| `recurrence.*`, `treatment_history[]` | 보조 ET 종료 후 재발까지 기간 | ESMO MBC 1L 분기 (§3.3) |

---

## 3. STEP 2·3: 문단·문장 매칭 어휘 사전

JSON 값은 약어나 코드라서 지침 문장과 표현이 다르다. 아래 사전으로 **(1) 질의문을 만들고 (2) 청크 메타데이터를 태깅한다.** ESMO와 ASCO가 같은 개념을 다르게 쓰는 경우가 많다.

### 3.1 subtype

| JSON 값 | ESMO 표현 | ASCO 표현 |
|---|---|---|
| `HR+/HER2-` | ER-positive, HER2-negative / luminal / luminal A-like, luminal B-like | hormone receptor–positive, HER2-negative / HR-positive |
| `HR+/HER2+` | HER2-positive (HR-positive) | HR-positive, HER2-positive |
| `HR-/HER2+` | HER2-positive | HER2-positive, HR-negative |
| `TNBC` | TNBC / mTNBC / triple-negative | triple-negative / hormone receptor–negative (HER2-negative) |

### 3.2 setting.disease

| JSON 값 | 표현 |
|---|---|
| `early` | early breast cancer, EBC, early-stage, stage I–II, operable |
| `locally_advanced` | stage III, locally advanced, inoperable, high-risk stage II–III |
| `metastatic` | metastatic, MBC, advanced breast cancer (ABC), stage IV, de novo stage IV, recurrent |

### 3.3 setting.line: 하드 필터로 쓰면 안 되는 이유

| JSON 값 | 지침 표현 |
|---|---|
| `neoadjuvant` | neoadjuvant, preoperative, primary systemic therapy (PST) |
| `adjuvant` | adjuvant, post-neoadjuvant, residual (invasive) disease, after completion of locoregional therapy, extended ET |
| `1L` | first-line, previously untreated, treatment-naive, **de novo or recurring >12 months after end of adjuvant ET** |
| `2L` | second-line, progression on/after AI, after prior CDK4/6 inhibitor, **after at least one line of ET** |
| `>=3L` | third-line and beyond, after at least two lines (of ET / ChT), 2–4 prior chemotherapy regimens, fourth-line |

- ESMO MBC는 "보조 ET 중 또는 종료 12개월 이내 재발"을 **1L 섹션**에서 다른 약제(fulvestrant 병용)로 다룬다. 같은 1L이라도 내분비 감수성에 따라 권고가 갈린다.
- "ET 2차례 후", "ChT 1차례 후"처럼 **내분비 차수와 항암 차수를 따로 센다** (심평원도 따로 셈, handoff_to_B.md §6).
- 그래서 `line`은 점수 가중치로만 쓴다. **B가 추가로 산출하면 좋은 값**: `endocrine_sensitivity`(보조 ET 종료 후 재발까지 12개월 기준), 전이 후 ET 차수, 전이 후 ChT 차수, 이전 CDK4/6 사용 여부. 스키마에 넣을지는 팀 결정이다.

### 3.4 prior_drug_classes (이전 치료)

**주의**: 지금 B 코드(`setting_of`)는 `drug_classes.csv`의 `drug_class` 열(Chemotherapy, Hormone Therapy, HER2-targeted Therapy 등)을 넣는다. 이 정도로는 AI와 CDK4/6 억제제, tamoxifen과 fulvestrant를 구분할 수 없어 2차 권고를 고를 수 없다. 아래 표 수준으로 쓰려면 `drug_subclass` 열(AI_nonsteroidal, SERD 등)을 쓰고 CDK4/6 억제제 같은 하위 분류를 사전에 더해야 한다.

| 값 예시 | 표현 |
|---|---|
| aromatase inhibitor | AI, aromatase inhibitor, nonsteroidal AI, letrozole/anastrozole/exemestane |
| CDK4/6 inhibitor | CDK4/6 inhibitor, palbociclib/ribociclib/abemaciclib |
| tamoxifen / SERM | tamoxifen, SERM |
| SERD | fulvestrant, SERD |
| trastuzumab | trastuzumab, HER2-directed therapy, anti-HER2 |
| T-DM1 | trastuzumab emtansine, T-DM1 |
| taxane / anthracycline | taxane, anthracycline, prior chemotherapy |

### 3.5 바이오마커 → `biomarker_tags` 표준값과 표현

`biomarker_record.records[].rag_tags`와 청크 `biomarker_tags`가 **같은 어휘**를 써야 가중치가 작동한다.

| marker + status | 표준 태그(제안) | 지침 표현 |
|---|---|---|
| HER2 low | `HER2-low` | HER2-low, HER2 IHC 1+ or 2+ and ISH-negative |
| HER2 ultralow | `HER2-ultralow` | HER2-ultralow, IHC 0 with faint staining |
| gBRCA1/2 positive | `gBRCA` | germline BRCA1/2 mutation, gBRCA1/2m, gBRCA carriers |
| sBRCA positive | `sBRCA` | somatic BRCA1/2 mutation |
| PALB2 positive | `gPALB2` | germline PALB2 mutation |
| PIK3CA positive | `PIK3CA-mut` | PIK3CA-mutated, PIK3CA mutation (exons 7, 9, 20) |
| PIK3CA negative | `PIK3CA-wt` | PIK3CA-wild type, absence of targetable alterations |
| AKT1 / PTEN positive | `AKT1-mut`, `PTEN-alt` | AKT1 or PTEN alterations |
| ESR1 positive | `ESR1-mut` | ESR1-mutated, ESR1 mutation (ctDNA) |
| PD-L1 positive | `PD-L1+` | PD-L1 CPS ≥10 (22C3), PD-L1-positive, IC ≥1% (SP142) |
| Ki-67 high | `Ki67-high` | Ki-67 ≥20%, high Ki-67 |
| ER low | `ER-low` | ER-low, ER 1–10% |

### 3.6 약제명
청크 `drugs`는 일반명 소문자로 넣고 `data/dictionaries/drug_names.csv`·`drug_classes.csv`와 같은 사전을 쓴다. 지침 약어도 사전에 넣는다: T-DXd, T-DM1, SG(sacituzumab govitecan), HP(trastuzumab+pertuzumab), AI, ET, ChT, OFS, PARPi, ICI.

---

## 4. 청킹 상세 규칙

### 4.1 문서별 분할

**ESMO MBC**
- L1 = 책갈피 3단계 소제목 (예: luminal > Second-line). `line`은 소제목에서 바로 정한다 (First-line → 1L, Second-line → 2L, Third-line and beyond · Fourth-line and beyond → >=3L).
- L2 = `•`로 시작해 다음 `•` 앞까지. `[I, A; ESMO-MCBS v2.0 score: 3]` 패턴에서 `evidence.loe`, `gor`, `esmo_mcbs`, `escat`를 뽑는다.
- L3 = `○`, `■` 줄 하나. 약제 조합은 `—`로 나뉜다 (`Fulvestrant—palbociclib—inavolisib`).
- Figure 2~4(알고리즘)는 본문 사이에 끼어 추출되므로 걸러 낸다. 필요하면 손으로 옮겨 `chunk_kind: algorithm`으로 넣는다.
- Site-specific(뇌·뼈 전이, de novo IV)은 `subtype: any`로 두고, "HER2-positive BC with BMs"처럼 아형이 적힌 소단원만 좁힌다.

**ESMO EBC**
- 권고가 p13~15 "Recommendations"에 아형별로 모여 있다. 이 부분에서 L2를 만들고, 같은 아형의 본문(p7~13)은 L2' 근거로 연결한다.
- `line`은 문장에서 neoadjuvant / adjuvant / post-neoadjuvant(잔존 질환)로 정한다. 둘 다 해당하면 둘 다 넣는다.
- 불릿 문자가 `\x03`, 하위 불릿이 `o`로 추출된다 (§5).

**ASCO 정규 지침** (endocrine_targeted, chemo_targeted, her2_positive_systemic, biomarkers_adjuvant, bisphosphonates)
- 1~2쪽 요약 상자(THE BOTTOM LINE / UPDATED RECOMMENDATIONS)에 권고 전문이 깨끗하게 모여 있고, 본문에서 같은 권고가 반복된다. **요약 상자에서 L2를 만들고, 본문에서는 Literature review, Clinical interpretation만 L2'로** 쓴다. 이렇게 해야 중복으로 색인되지 않는다.
- L1 = Clinical Question N + 질문문. 질문문에 대상 집단(아형, 폐경, 이전 치료)이 들어 있어 부모 문맥으로 좋다.
- `(type: ...; evidence quality: high; strength of recommendation: strong)`에서 근거 수준을 뽑는다. ESMO와 체계가 달라 원문 문자열 그대로 둔다.
- 권고 번호가 모든 파일에서 잡히지는 않는다 (her2_positive_systemic은 정규식으로 3개만 잡힘). 책갈피와 요약 상자를 함께 쓴다.
- 검사만 권하는 권고(endocrine_targeted Rec 2.1, 2.2)는 청크로 만들지 않는다.

**ASCO rapid update** (olaparib, pembrolizumab, trastuzumab_deruxtecan, sacituzumab, capivasertib)
- 권고가 1~2개이고 번호가 없다. "UPDATED RECOMMENDATION(S)" 아래를 L2로, EVIDENCE REVIEW를 L2'로 쓴다. chunk_id는 순서 번호로 만든다.
- 갱신하는 정규 지침 권고를 `superseded_by` 또는 연결 필드로 잇는다 (§1.3).

**ASCO abemaciclib Q&A**
- Question 6개를 각각 L2로 만든다 (`chunk_kind: section`). 정식 권고가 아니므로 `evidence`는 null로 둔다.

### 4.2 제외 소단원
처방 문서 안의 수술·방사선·진단·추적관찰 소단원과 METHODS, Disclaimer, References 같은 공통 소단원은 청크로 만들지 않는다. 목록은 `rag_non_prescription_docs.md` §2에 있다.

### 4.3 chunk_id 규칙 (제안)

```
{source}-{setting}-{yyyy-mm}-{doc_slug}-{L1번호}-{L2번호}[-o{L3번호}]
esmo-mbc-2026-05-luminal-2l-r03-o02
asco-mbc-2021-07-endo-cq3-r3.2
asco-mbc-2024-03-capi-r1.1
```
L0는 `{source}-{setting}-{yyyy-mm}-{doc_slug}`, L1은 그 뒤에 `{L1번호}`를 붙인다. 파일명에서 바로 만들 수 있어 ID가 겹치지 않는다.

### 4.4 스키마에 필요한 변경 (공용 → 4명 검토 필요)
- `chunk_kind` enum에 `option`(L3), `evidence`(L2')를 추가할지, 기존 값을 재사용할지
- L0 문서 메타데이터를 별도 `guideline_docs.json`에 둘지, 청크 필드(`doc_id`)로 넣을지
- `biomarker_tags` 표준 어휘(§3.5)를 `biomarker_record.rag_tags`와 공유하는 사전 파일로 둘지

---

## 5. 텍스트 정제 (청킹 전)

| 문제 | 위치 | 예 | 처리 |
|---|---|---|---|
| 줄 끝 하이픈 | 전 파일 | `trastuzumab der-\nuxtecan`, `pacli-\ntaxel` | 하이픈과 줄바꿈을 지우고 붙인다. 약제명 검색 누락의 원인 |
| ASCO 기호 폰트 깨짐 | ASCO 전 파일 | `IHC 11 or 21` = IHC 1+ or 2+, `n 5 272` = n = 272, `grade $ 3` = ≥ 3 | 정규식으로 복원. HER2 점수가 바뀌므로 중요 |
| 합자 | ASCO | `ﬁ`, `ﬂ` | NFKC 정규화 |
| ESMO EBC 대시 깨짐 | ESMO EBC | `OFSetamoxifen` = OFS–tamoxifen, `taxaneecarboplatin`, `combineddif indicateddwith` | en dash가 `e`로, em dash가 `d`로 추출됨. 약제 조합 사전으로 복원 |
| ESMO EBC 제어문자 | ESMO EBC | 불릿이 `\x03`(98개), `\x04`, `\x05`, `\x01` | 기존 청크에 제어문자가 섞인 원인. 불릿 문자로 바꾼다 |
| 그림 텍스트 섞임 | ESMO MBC p4~ | Figure 2 알고리즘 글자가 권고 사이에 끼어 듦 | 그림 영역(bbox)을 빼고 추출하거나 Figure 캡션 기준으로 잘라 낸다 |
| 2단 편집 | ESMO 둘 다 | 단 경계에서 문장이 끊김 | PyMuPDF `sort=True` 또는 블록 단위 추출 |
| 머리말·꼬리말 | 전 파일 | `Annals of Oncology`, `Volume 37 ■ Issue 9`, `Downloaded from ascopubs.org by <IP>` | 패턴으로 지운다 |
| 약어 | 전 파일 | sacituzumab 파일은 본문에서 `SG`로만 써서 약제명 빈도가 0 | 약어 사전(§3.6)으로 `drugs` 태깅 |

---

## 6. 벡터 DB 구성

PROJECT.md §6·§15.6의 계획(Qdrant, bge-m3, BM25 하이브리드, bge-reranker-v2-m3)을 따른다. 현재 C의 코드(`src/rag/client.py`, `indexer.py`, `searcher.py`)는 dense 벡터 하나, 무작위 ID, 정확 일치 필터만 있다. 아래는 이 설계(§0)를 구현하기 위한 목표 구성이다.

### 6.1 전체 구성

| 데이터 | 저장 위치 | 이유 |
|---|---|---|
| L0 문서 (13개) | `data/chunks/guideline_docs.json` | 개수가 적고 STEP 1은 표로 고른다. 벡터가 필요 없다. git으로 검토할 수 있다 |
| L1 섹션 (약 100~150개) | `data/chunks/guideline_sections.json` | 검색 대상이 아니라 부모 문맥으로 ID 조회만 한다. 메모리에 올려 dict로 찾는다 |
| L2 권고, L3 문장, L2' 근거 | Qdrant 컬렉션 `bc_index` | 실제 검색 대상. dense + sparse 벡터와 payload를 함께 저장 |
| D의 급여 청크 | 같은 컬렉션 `bc_index` | PROJECT.md의 "공용 색인". `doc_type`으로 구분하고 검색할 때 항상 거른다 |
| 청크 원본 | `data/chunks/esmo_*.json`, `asco_*.json` | 색인은 이 파일에서 언제든 다시 만들 수 있어야 한다 |
| Qdrant 데이터 | `data/qdrant_db/` (git 제외) | 로컬 모드 저장 폴더 |
| 색인 정보 | `data/qdrant_db/index_meta.json` (git 제외) | 임베딩 모델 이름, 청크 파일 해시, 색인 날짜. 다르면 다시 색인 |

`guideline_docs.json` 항목 예:

```json
{
  "doc_id": "asco-mbc-2024-03-capi",
  "file": "asco/asco_mbc_2024-03_capivasertib_fulvestrant.pdf",
  "source": "ASCO", "version": "2024-03", "url": "https://doi.org/10.1200/JCO.24.00248",
  "setting": ["metastatic"], "subtype": ["HR+/HER2-"],
  "trigger_tags": ["PIK3CA-mut", "AKT1-mut", "PTEN-alt"],
  "updates": ["asco-mbc-2021-07-endo-cq1-r1.1"], "role": "prescription"
}
```

### 6.2 컬렉션 설정

한 점(point)에 **이름 붙은 벡터 두 개**를 담는다.

| 벡터 이름 | 종류 | 만드는 방법 | 설정 |
|---|---|---|---|
| `dense` | dense 1024차원 | bge-m3 | `VectorParams(size=1024, distance=COSINE)` |
| `bm25` | sparse | fastembed `Qdrant/bm25` (토큰 빈도) | `SparseVectorParams(modifier=Modifier.IDF)`: IDF는 Qdrant가 컬렉션 전체로 계산 |

```python
client.create_collection(
    collection_name="bc_index",
    vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
    sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
)
```

- sparse 대안: bge-m3 자체의 sparse 출력(FlagEmbedding `BGEM3FlagModel`, `return_sparse=True`). 모델 하나로 두 벡터를 만들 수 있지만, 학습된 가중치라 드문 약제명 정확 일치가 BM25만큼 확실한지는 시험해 봐야 한다. 지금 쓰는 `sentence_transformers`로는 sparse가 나오지 않는다.
- BM25 토큰화 전에 §5 정제가 끝나 있어야 한다. `der-uxtecan`, `IHC 11`이 그대로 들어가면 BM25가 실패한다.
- 약어는 색인 텍스트에 일반명을 함께 넣는다 (예: "T-DXd (trastuzumab deruxtecan)"). BM25는 동의어를 모른다.

### 6.3 점(point) 구조

**점 ID**: `uuid5(NAMESPACE, chunk_id)`. 같은 청크는 항상 같은 ID가 되어 다시 색인해도 덮어쓰기만 된다 (지금은 uuid4라 중복이 쌓임).

**임베딩할 텍스트**: 청크 본문 앞에 **문맥 머리말**을 붙여 임베딩한다. 화면 표시·인용에는 원문(`text`)을 쓴다.

```
embed_text = "[ESMO MBC 2026-05 > Luminal MBC > Second-line | ER-positive HER2-negative metastatic] "
             + "Fulvestrant—palbociclib (ESMO-MCBS v2.0 score: 4)"
```

L3 문장은 혼자서는 "Options include ..."처럼 대상 환자가 빠져 있다. 머리말이 없으면 1L의 fulvestrant 선택지와 2L의 fulvestrant 선택지가 같은 벡터가 된다.

**payload 필드** (`schemas/chunk.json` 기준 + 이 설계에서 추가하는 것)

| 필드 | 형식 | 예 | 출처 |
|---|---|---|---|
| `chunk_id` | string | `esmo-mbc-2026-05-luminal-2l-r03-o02` | chunk.json |
| `doc_id` | string | `esmo-mbc-2026-05` | **추가** (L0 연결) |
| `level` | enum | `L2` / `L3` / `L2e`(근거) | **추가** |
| `parent_id` | string | L3 → L2 ID, L2 → L1 ID | chunk.json |
| `doc_type` | enum | `guideline` / `reimbursement` | chunk.json |
| `source`, `version`, `url`, `section`, `page_start`, `page_end` | | 인용 표시용 | chunk.json |
| `chunk_kind` | enum | `recommendation`, `option`, `evidence` 등 | chunk.json (enum 추가 필요, §4.4) |
| `text` | string | 원문 (정제 후) | chunk.json |
| `embed_text` | string | 머리말 + 원문 | **추가** (디버깅용, 선택) |
| `setting` | string[] | `["metastatic"]` | chunk.json |
| `subtype` | string[] | `["HR+/HER2-"]` 또는 `["any"]` | chunk.json |
| `line` | string[] | `["2L"]` | chunk.json (소프트 조건) |
| `biomarker_tags` | string[] | `["ESR1-mut"]` | chunk.json (§3.5 어휘) |
| `drugs` | string[] | `["elacestrant", "imlunestrant"]` | chunk.json |
| `evidence` | object | `{"loe": "I", "gor": "A", "esmo_mcbs": "3"}` | chunk.json |
| `superseded_by` | string/null | | chunk.json |
| `copyright_notice` | string/null | ESMO 청크 | chunk.json |

### 6.4 payload 인덱스

| 필드 | 인덱스 종류 | 쓰는 곳 |
|---|---|---|
| `doc_type`, `doc_id`, `level`, `source` | keyword | STEP 1 후보 문서, 단계 구분 |
| `setting`, `subtype` | keyword (배열) | 하드 필터 (`MatchAny`) |
| `line`, `biomarker_tags`, `drugs` | keyword (배열) | 소프트 가중치, 약제 재확인 |
| `parent_id` | keyword | STEP 3 (상위 L2의 자식만), small-to-big |
| `superseded_by` | keyword | `IsNullCondition`으로 최신 청크만 |

로컬 모드(`QdrantClient(path=...)`)는 payload 인덱스를 만들어도 무시하고 전체를 훑는다. 수천 개 규모에서는 문제가 없고, 서버 모드로 옮기면 그대로 적용된다.

### 6.5 검색 쿼리 구성

**STEP 2: 권고 문단 (L2) 하이브리드 검색**

```python
flt = Filter(must=[
    FieldCondition(key="doc_type", match=MatchValue(value="guideline")),
    FieldCondition(key="level",    match=MatchValue(value="L2")),
    FieldCondition(key="doc_id",   match=MatchAny(any=candidate_doc_ids)),      # STEP 1 결과
    FieldCondition(key="setting",  match=MatchAny(any=[disease])),              # unknown이면 생략
    FieldCondition(key="subtype",  match=MatchAny(any=[subtype, "any"])),       # unknown이면 생략
    IsNullCondition(is_null=PayloadField(key="superseded_by")),
])
res = client.query_points(
    "bc_index",
    prefetch=[
        Prefetch(query=dense_vec,  using="dense", filter=flt, limit=40),
        Prefetch(query=bm25_vec,   using="bm25",  filter=flt, limit=40),
    ],
    query=FusionQuery(fusion=Fusion.RRF),   # 두 순위를 RRF로 합침
    limit=20,
)
```

이어서 Python에서 처리한다:
1. 소프트 가중치: `line` 일치 +α, `biomarker_tags` 겹침 하나당 +β (α, β는 평가로 정함)
2. 재정렬: bge-reranker-v2-m3에 (질의문, L2 `text`) 20쌍을 넣어 점수를 다시 매기고 상위 k개를 남김

**STEP 3: 문장 (L3)**

```python
flt3 = Filter(must=[
    FieldCondition(key="level",     match=MatchValue(value="L3")),
    FieldCondition(key="parent_id", match=MatchAny(any=top_l2_ids)),
])
```
같은 질의 벡터로 dense 검색만 해도 충분하다 (후보가 수십 개). 권고마다 가장 높은 L3를 하이라이트로 고른다.

**STEP 4: 부모 붙이기**: L2의 `parent_id`로 `guideline_sections.json`에서 L1 전문을, `doc_id`로 `guideline_docs.json`에서 출처를 찾아 묶는다. Qdrant를 다시 조회하지 않는다.

**출처 분리**: `source`가 ESMO인 결과와 ASCO인 결과를 따로 k개씩 돌려준다. 한쪽이 점수가 높아 다른 쪽을 밀어내지 않도록 STEP 2 쿼리를 출처별로 두 번 보내는 방법도 있다.

### 6.6 색인 절차

```
청크 JSON (L2·L3·L2e)
  → 스키마 검증 (schemas/chunk.json)          실패하면 중단
  → embed_text 만들기 (문맥 머리말 + text)
  → dense: bge-m3 배치 인코딩 (normalize)
  → sparse: Qdrant/bm25 인코딩
  → PointStruct(id=uuid5(chunk_id), vector={"dense":..., "bm25":...}, payload=청크)
  → upsert (배치 64)
  → index_meta.json 기록 (모델 이름, 청크 파일 해시, 점 개수, 날짜)
```

- 전체 재색인: 지침 청크를 바꿨을 때. `doc_type=guideline`인 점만 지우고 다시 넣는다. 컬렉션 전체를 지우면 D의 급여 청크까지 사라진다 (지금 `run_indexing`은 컬렉션을 통째로 지움).
- 부분 추가: D의 새 공고처럼 청크가 늘 때. 고정 ID라 upsert만 하면 된다.
- 임베딩 모델을 바꾸면 dense 벡터가 호환되지 않으므로 컬렉션을 새로 만든다. `index_meta.json`의 모델 이름이 다르면 검색 함수가 경고를 낸다.

### 6.7 규모와 운영

| 항목 | 예상 |
|---|---|
| 점 개수 | ESMO MBC L2 약 150 + L3 약 250, ESMO EBC L2 약 110 + L3 약 100, ASCO L2 약 70 + L3 약 200, 근거 문단 약 300 → **지침 약 1,200개** + D의 급여 청크 |
| 저장 용량 | dense 1,200 × 1024 × 4바이트 ≈ 5MB. 로컬 모드로 충분 |
| 임베딩 시간 | bge-m3 CPU 기준 수 분. GPU면 1분 이내 |

- **로컬 모드는 한 프로세스만 폴더를 열 수 있다.** D가 색인하는 동안 B가 검색하면 잠금 오류가 난다. 개발 중에는 순서대로 실행하고, 통합 단계에서는 Qdrant 서버(도커)로 바꾼다. `client.py`의 `QdrantClient(path=...)` 한 줄만 `QdrantClient(url=...)`로 바꾸면 된다.
- Query API(prefetch, RRF 융합)와 sparse IDF modifier는 qdrant-client 1.10 이후 기능이다. 도입할 때 설치 버전과 로컬 모드 지원 여부를 확인한다.
- 지침 검색과 급여 검색은 같은 컬렉션을 쓰지만 함수를 나눈다 (`search_guidelines`, `search_reimbursement`). 둘 다 `doc_type` 필터를 반드시 건다.

---

## 7. C가 고칠 것 (우선순위순)

### P0: B 연동 전에 꼭 필요

1~4번에 나오는 `subtype`, `setting`, `line`, `any`, `unknown`의 뜻과 허용값은 §K에 있다.

| # | 문제 | 수정 방향 |
|---|---|---|
| 1 | `subtype`/`line` 필터가 정확히 같은 값만 찾음. ASCO 청크 68개 중 66개는 `any`라 검색에서 빠짐 | `MatchAny([요청값, "any"])` |
| 2 | B가 `unknown`을 넘기면 결과가 0건 | `None`/`unknown`이면 해당 필터를 뺀다. 호출 규칙은 B와 합의 |
| 3 | `line`을 하드 필터로 씀 (§3.3) | 하드 필터는 `setting` + `subtype`만, `line`은 가중치로 |
| 4 | ESMO 청크 11건이 `subtype: ["HER2+"]`로 스키마 위반 | `["HR+/HER2+", "HR-/HER2+"]`로 펼친다 |
| 5 | ESMO MBC 청크가 없음 | §4.1 규칙으로 청킹해 추가 |
| 6 | ASCO `chunk_id` 12종 중복, `version`이 모두 `2023-01`, URL이 가짜 DOI | §4.3 ID 규칙, 파일명 날짜, PDF 첫 쪽의 실제 DOI |
| 7 | 현재 ASCO 청크에 처방이 아닌 문서(검사법 지침 등)가 섞여 있음 | `rag_non_prescription_docs.md`의 8개 문서 청크를 뺀다 |

### P1: 검색 품질

| # | 문제 | 수정 방향 |
|---|---|---|
| 8 | 색인 ID가 uuid4라 다시 색인하면 중복이 쌓임 | `uuid5(NAMESPACE, chunk_id)` 고정 ID (§6.3) |
| 9 | `superseded_by`, `doc_type` 필터가 없음 | 기본 검색에서 대체된 청크 제외, `doc_type` 인자 추가 (§6.5) |
| 9-1 | `run_indexing`이 컬렉션을 통째로 지움. D의 급여 청크가 들어오면 같이 사라짐 | `doc_type=guideline` 점만 지우고 다시 넣음 (§6.6) |
| 9-2 | L3 문장을 머리말 없이 임베딩하면 차수·아형이 다른 같은 약제 문장이 구분되지 않음 | 문맥 머리말을 붙여 임베딩 (§6.3) |
| 10 | 메타데이터가 비어 있음 (`drugs` 1건, `biomarker_tags` 3건) | §3 사전으로 자동 태깅하고 사람이 검수 |
| 11 | 텍스트가 깨짐 | §5 정제 |
| 12 | 청크 길이 편차가 큼 (2만 5천 자짜리 1개) | §0.2 계층으로 다시 자름. L2는 800토큰 이하 |
| 13 | 부모 소단원을 함께 넘기지 않음 | `parent_id`를 채우고 결과에 L1 텍스트를 붙여 돌려줌 |

### P2: 설계 대비 미구현

| # | 문제 | 수정 방향 |
|---|---|---|
| 14 | 벡터 검색만 있음 (PROJECT.md §6은 bge-m3 + BM25 + bge-reranker-v2-m3) | dense + sparse(BM25) 이름 붙은 벡터 컬렉션, RRF 융합, 재정렬, L3 문장 검색 추가 (§6.2, §6.5) |
| 15 | 테스트가 실제 색인과 모델(약 2GB)에 의존함 | 색인이나 모델이 없으면 `pytest.skip`. 필터 로직은 가짜 임베더로 단위 테스트 |

---

## 8. 팀 결정이 필요한 것

1. `line`을 하드 필터에서 뺄지 (제안: 뺀다)
2. B가 `endocrine_sensitivity`, ET·ChT 차수 같은 값을 추가로 낼지 (§3.3)
3. 빠진 문서(§1.4)를 추가할지
4. §4.4 스키마 변경
5. 처방이 아닌 문서를 검사 근거용으로 따로 색인할지 (`rag_non_prescription_docs.md` §4)

## 부록: 키워드 출현 빈도 (참고문헌 제외 본문)

라우팅 표의 근거로 쓴 숫자 일부다. 숫자가 클수록 그 주제를 주로 다룬다.

| 파일 | 주요 키워드 (빈도) |
|---|---|
| esmo_mbc_2026-05 | metastatic 89, HER2+ 21, HER2-low 12, ultralow 5, TNBC 26, 1L 19 / 2L 17 / ≥3L 17, PIK3CA 13, ESR1 4, gBRCA 19, brain 61, trastuzumab 51, fulvestrant 29 |
| esmo_ebc_2024-02 | early 54, neoadjuvant 68, adjuvant 74, residual/pCR 32, node+ 28, gBRCA 22, olaparib 12, pembrolizumab 8 |
| asco_mbc_2021-07_endocrine_targeted | HR+ 63, PIK3CA 43, ESR1 16, AI 72, CDK4/6 71, fulvestrant 108, alpelisib 56 |
| asco_mbc_2022-05_her2_positive_systemic | HER2+ 21, 2L 25, ≥3L 22, brain 42, trastuzumab 134, T-DM1 65, tucatinib 20 |
| asco_mbc_2021-07_chemo_targeted | TNBC 47, gBRCA 49, PD-L1 33, capecitabine 39, paclitaxel 38 |
| asco_mbc_2024-03_capivasertib | PIK3CA 12, AKT1 11, PTEN 14, capivasertib 26 |
| asco_ebc_2022-04_biomarkers_adjuvant | genomic assay 151, Ki-67 68, node+ 98, premeno 32 |
| asco_ebc_2022-04_abemaciclib_qa | Ki-67 25, abemaciclib 30 |
| asco_ebc_2021-08_parp_olaparib | gBRCA 9, olaparib 15 |
| asco_ebc_2022-04_pembrolizumab_tnbc | TNBC 8, neoadjuvant 8, pembrolizumab 22 |
