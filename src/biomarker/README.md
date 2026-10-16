# [2] 바이오마커 모듈 — 담당 B

검사 보고서를 지침·급여 기준이 쓰는 상태값으로 바꾼다.

- 하위 단계: BM-1 보고서 정규화(LLM) ~ BM-4 검사 공백 탐지 (PROJECT.md §5). 아형과 치료 상황(현재 범주, 차수)도 이 모듈이 산출한다 (`src/input/handoff_to_B.md` §6)
- 입력: `patient_state`
- 출력: `schemas/biomarker_record.json` (레코드 목록 + 아형 + 치료 상황 + 검사 공백)
- BM-2 판정과 BM-4 공백 규칙은 규칙 코드로 작성한다. LLM이 상태값을 바꿀 수 없다.
- BM-3 근거 주석은 허가사항 변이 목록, CIViC, ClinVar, VEP를 로컬로 조회한다. OncoKB는 쓰지 않는다.
- 테스트: `tests/biomarker/`

## 파일

| 파일 | 내용 |
|---|---|
| `BM.py` | BM-2 ~ BM-4를 한 파일에 둔다. 진입점 `assess(patient_state)` → `biomarker_record` 전체 |

`BM.py`가 만드는 레코드 (환자 1명당 4개):

| 마커 | 입력 (`patient_state.fields`) | 판정 |
|---|---|---|
| ER, PR, HER2 | `receptors.er_percent`, `pr_percent`, `her2_ihc`, `her2_ish` | PROJECT.md §5 세부 규칙 |
| Ki-67 | `proliferation.ki67_percent` | percent → range → result. 20% 이상 positive, 미만 negative, 구간이 20%에 걸치거나 판정이 intermediate면 intermediate, 쓸 값 없으면 unknown (20% 기준은 2026-10-15 확정) |

분자 아형(Luminal A, Luminal B(HER2 negative), Luminal B(HER2 positive), HER2_enriched, Basal_like)은 `molecular_subtype_of(아형, Ki-67 상태값)` 규칙 함수로만 있고 출력에는 넣지 않는다 (PROJECT.md §5).

유전자 변이(ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2)와 그에 걸린 BM-4 검사 공백 규칙(gBRCA, PIK3CA·AKT1·PTEN, ESR1)은 2026-10-15에 코드에서 뺐다. 따로 다시 작성한다.

테스트 실행 (`team_project` 폴더에서): `python -m pytest tests/biomarker` 또는 케이스별 출력은 `python -m tests.biomarker.test_bm`
