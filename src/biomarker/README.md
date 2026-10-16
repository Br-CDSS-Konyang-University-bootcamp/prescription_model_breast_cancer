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

`BM1_ER,PR,HER2,Ki_67,subtype.py`가 만드는 레코드 (환자 1명당 12개: ER, PR, HER2, Ki-67, PD-L1, 유전자 7개):

| 마커 | 입력 (`patient_state.fields`) | 판정 |
|---|---|---|
| ER, PR, HER2 | `receptors.er_percent`, `pr_percent`, `her2_ihc`, `her2_ish` | PROJECT.md §5 세부 규칙 |
| Ki-67 | `proliferation.ki67_percent` | percent → range → result. 20% 이상 positive, 미만 negative, 구간이 20%에 걸치거나 판정이 intermediate면 intermediate, 쓸 값 없으면 unknown (20% 기준은 2026-10-15 확정) |

PD-L1 판정 (2026-10-16, 전달 문서 6.5절). 입력 `receptors.pdl1` (`assay`, `score_type`, `score`). 검사법·점수 종류에 맞는 약제 기준으로만 판정한다:

| 검사법 + 점수 종류 | 양성 기준 | 약제 | 근거 | 태그 | 규칙 ID |
|---|---|---|---|---|---|
| 22C3 + CPS | 10 이상 | pembrolizumab + 항암 (TNBC 1차) | 심평원 공고 p.58~59 | `PD-L1-CPS10` | `BM2-PDL1-22C3` |
| SP142 + IC | 1% 이상 | atezolizumab + nab-paclitaxel | ESMO MBC | `PD-L1-SP142` | `BM2-PDL1-SP142` |
| 그 밖 (SP263, TPS 등) | 판정하지 않음 → `unknown` | | | | `BM2-PDL1-ASSAY` |

- 검사법과 점수는 `evidence.assay`, `evidence.score`에 남긴다. 기준 숫자는 코드 맨 위 `PDL1_22C3_CPS_MIN`, `PDL1_SP142_IC_MIN`.
- TCGA는 PD-L1이 모두 기록 없음이라 테스트 케이스(P01~P11)로만 확인했다.

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
- `actionable_variants.csv`의 PIK3CA 11개는 therascreen PIK3CA 키트의 QIAGEN 제품 페이지와 AccessGUDID 등록 정보로 확인했다 (사용설명서 원본은 아직 대조하지 않음). AKT1·ESR1 목록은 `verified = no`이고, 판정 이유에 "원문 확인 필요"가 붙는다. FDA 라벨·SSED 원문으로 확인하면 `yes`로 바꾼다.
- TCGA 874명 결과: PIK3CA 양성 211 / VUS 69, AKT1 양성 21, PTEN 양성 34, gBRCA1 양성 9, gBRCA2 양성 6, PALB2 VUS 6, ESR1 양성 2 / 재검 필요 9. 미시행은 유전자마다 28명.

유전자 검사 공백 (BM-4, 2026-10-16). 현재 전이성 환자만, 미시행(`not_done`)일 때만 `tests_needed`에 넣는다:

| 아형 | 권고 | 규칙 ID |
|---|---|---|
| HR+/HER2-, TNBC | gBRCA1·gBRCA2·PALB2 미시행 → 생식세포 검사 | `BM4-GBRCA1`, `BM4-GBRCA2`, `BM4-PALB2` |
| HR+/HER2- | PIK3CA·AKT1·PTEN 미시행 → 검사 | `BM4-PIK3CA`, `BM4-AKT1`, `BM4-PTEN` |
| HR+/HER2- | ESR1 미시행 → 검사 / ESR1 재검 필요 → cfDNA 재검 | `BM4-ESR1` / `BM4-ESR1-RETEST` |

- 생식세포 BRCA가 기록 없음이면 권고하지 않는다 (전달 문서 4.7절의 열린 질문, B 결정 2026-10-16). TCGA가 아닌 차트는 BRCA 레코드가 sBRCA라 생식세포 BRCA 권고가 나오지 않는다.
- TCGA 874명 결과: 현재 전이성 환자는 유전자 검사가 모두 시행돼 미시행 권고는 0명, ESR1 재검 권고 3명.

테스트 실행 (`team_project` 폴더에서): `python -m pytest tests/biomarker` 또는 케이스별 출력은 `python -m tests.biomarker.test_bm`
