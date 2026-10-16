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
| `BM1_ER,PR,HER2,Ki_67,subtype.py` | BM-2 ~ BM-4를 한 파일에 둔다. 진입점 `assess(patient_state)` → `biomarker_record` 전체 |
| `actionable_variants.csv` | 허가 동반진단 변이 목록 (PIK3CA, AKT1, ESR1). 약, 출처, 원문 확인 여부(`verified`) |

`BM1_ER,PR,HER2,Ki_67,subtype.py`가 만드는 레코드 (환자 1명당 11개):

| 마커 | 입력 (`patient_state.fields`) | 판정 |
|---|---|---|
| ER, PR, HER2 | `receptors.er_percent`, `pr_percent`, `her2_ihc`, `her2_ish` | PROJECT.md §5 세부 규칙 |
| Ki-67 | `proliferation.ki67_percent` | percent → range → result. 20% 이상 positive, 미만 negative, 구간이 20%에 걸치거나 판정이 intermediate면 intermediate, 쓸 값 없으면 unknown (20% 기준은 2026-10-15 확정) |

분자 아형(Luminal A, Luminal B(HER2 negative), Luminal B(HER2 positive), HER2_enriched, Basal_like)은 `molecular_subtype_of(아형, Ki-67 상태값)` 규칙 함수로만 있고 출력에는 넣지 않는다 (PROJECT.md §5).

유전자 7개 판정 (2026-10-16, 1차 규칙. 전달 문서 3.6·4.6·4.7·5.4절). 위에서부터 처음 맞는 줄로 판정한다:

| 순서 | 조건 | 상태값 | 규칙 ID |
|---|---|---|---|
| 1 | 미시행 / 기록 없음 | `not_done` / `not_recorded` | `BM2-<유전자>-NOTDONE` / `-NOTRECORDED` |
| 2 | 변이 없음 | `negative` | `BM2-<유전자>-NOTDETECTED` |
| 3 | PIK3CA·AKT1·ESR1: 변이 중 하나라도 `actionable_variants.csv`에 있음 | `positive` | `BM2-<유전자>-LABEL` |
| 3 | PTEN·BRCA1·BRCA2·PALB2: 절단 변이(nonsense, frameshift, 스플라이스 부위) | `positive` | `BM2-<유전자>-TRUNC` |
| 4 | 그 밖의 검출 변이 | `vus` (음성 처리, 표시 유지) | `BM2-<유전자>-VUS` |
| ESR1 | 원발 조직 결과인데 이후 내분비요법 진행(PD, progression)이 있음 | `retest_needed` | `BM2-ESR1-RETEST` |

- BRCA1/2 레코드 이름: patient_ref가 `TCGA-`로 시작하면 `gBRCA1/2`(종양 엑솜을 생식세포 검사로 가정), 아니면 `sBRCA1/2`.
- VUS는 BM-3(ClinVar·CIViC 로컬 조회)이 생기면 다시 가른다. 미스센스 병원성 변이(예: BRCA1 C61G)는 지금 VUS로 나온다.
- `actionable_variants.csv`의 PIK3CA 11개는 therascreen PIK3CA 키트 문서로 확인했다. AKT1·ESR1 목록은 `verified = no`이고, 판정 이유에 "원문 확인 필요"가 붙는다. FDA 라벨·SSED 원문으로 확인하면 `yes`로 바꾼다.
- TCGA 874명 결과: PIK3CA 양성 211 / VUS 69, AKT1 양성 21, PTEN 양성 34, gBRCA1 양성 9, gBRCA2 양성 6, PALB2 VUS 6, ESR1 양성 2 / 재검 필요 9. 미시행은 유전자마다 28명.
- 유전자 검사 공백(BM-4: gBRCA, PIK3CA·AKT1·PTEN, ESR1)은 아직 넣지 않았다. 다음 작업이다.

테스트 실행 (`team_project` 폴더에서): `python -m pytest tests/biomarker` 또는 케이스별 출력은 `python -m tests.biomarker.test_bm`
