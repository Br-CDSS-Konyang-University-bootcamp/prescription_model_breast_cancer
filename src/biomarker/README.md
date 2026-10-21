# [2] 바이오마커 모듈 — 담당 B

검사 보고서를 지침·급여 기준이 쓰는 상태값으로 바꾼다.

- 하위 단계: BM-1 보고서 정규화(LLM) ~ BM-4 검사 공백 탐지 (PROJECT.md §5). 아형과 치료 상황(현재 범주, 차수)도 이 모듈이 산출한다 (`src/input/handoff_to_B.md` §6)
- 입력: `patient_state`
- 출력: `schemas/biomarker_record.json` (레코드 목록 + 아형 + 치료 상황 + 검사 공백)
- BM-2 판정과 BM-4 공백 규칙은 규칙 코드로 작성한다. LLM이 상태값을 바꿀 수 없다.
- BM-3 근거 주석은 허가사항 변이 목록, CIViC, ClinVar를 로컬로 조회한다. OncoKB와 VEP는 쓰지 않는다 (VEP는 팀 회의 2026-10-20).
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
| 22C3 + CPS | 10 이상 | pembrolizumab + 항암 (TNBC 1차) | 심평원 공고책자 2026-10-01판 p.58 (`hira-booklet-20261001-bc-pal-chemo-1l-r06`·`r07`) | `PD-L1+` | `BM2-PDL1-22C3` |
| SP142 + IC | 1% 이상 | atezolizumab + nab-paclitaxel | ESMO MBC | `PD-L1+` | `BM2-PDL1-SP142` |
| 그 밖 (SP263, TPS 등) | 판정하지 않음 → `unknown` | | | | `BM2-PDL1-ASSAY` |

- 검사법과 점수는 `evidence.assay`, `evidence.score`에 남긴다. 기준 숫자는 코드 맨 위 `PDL1_22C3_CPS_MIN`, `PDL1_SP142_IC_MIN`.
- TCGA는 PD-L1이 모두 기록 없음이라 테스트 케이스(P01~P11)로만 확인했다.

분자 아형(Luminal A, Luminal B(HER2 negative), Luminal B(HER2 positive), HER2_enriched, Basal_like)은 `molecular_subtype_of(아형, Ki-67 상태값)` 규칙 함수로만 있고 출력에는 넣지 않는다 (PROJECT.md §5).

유전자 7개 판정 (2026-10-20 팀 회의 반영. 전달 문서 3.6·4.6·4.7·5.4절). 판정과 근거를 나눈다: 판정은 아래 표로만 하고, 판정에 쓰지 않은 근거까지 모두 이유(`reason`)에 적는다. 위에서부터 처음 맞는 줄로 판정한다:

| 순서 | 조건 | 상태값 | 규칙 ID |
|---|---|---|---|
| 1 | 미시행 / 기록 없음 | `not_done` / `not_recorded` (검사하지 않은 환자는 positive·negative로 내지 않는다) | `BM2-<유전자>-NOTDONE` / `-NOTRECORDED` |
| 2 | 변이 없음 | `negative` | `BM2-<유전자>-NOTDETECTED` |
| 3 | PTEN: 단백질이 바뀌는 변이가 하나라도 있음 (변이 유무, 팀 회의 2026-10-20). `Silent`·`Splice_Region` 등 단백질이 바뀌지 않는 변이만 있으면 `negative` (`BM2-PTEN-NONPROTEIN`) | `positive` | `BM2-PTEN-PRESENT` |
| 3 | PIK3CA·AKT1·ESR1: 변이 중 하나라도 `actionable_variants.csv`에 있음 | `positive` | `BM2-<유전자>-LABEL` |
| 3 | BRCA1·BRCA2(4.7절): 절단 변이. 변이 종류가 `Nonsense_Mutation`, `Frame_Shift_Del`, `Frame_Shift_Ins`, `Splice_Site`일 때. PALB2는 절단 변이 규칙이 없다 (5.4절은 ClinVar 기준만) | `positive` | `BM2-<유전자>-TRUNC` |
| 4 | BRCA1·BRCA2·PALB2: ClinVar 병원성·병원성 가능이고 리뷰 등급 2성 이상 (BM-3, 5.4절) | `positive` | `BM3-<유전자>-CLINVAR` |
| 5 | 그 밖의 검출 변이 | `vus` (음성 처리, 표시 유지) | `BM2-<유전자>-VUS` |
| ESR1 | 원발 조직 결과인데 이후 내분비요법 진행(PD, progression)이 있음 | `retest_needed` | `BM2-ESR1-RETEST` |

- PTEN을 변이 유무로 보는 이유: 팀 회의(2026-10-20)에서 PTEN 결과를 positive/negative로 통일하고 VEP를 쓰지 않기로 했다. 절단형 여부와 ClinVar 판정은 근거로만 적는다.
- CIViC는 판정에 쓰지 않는다 (팀 회의 2026-10-20: 약이 듣는지는 판정하지 않는다). 그래서 `off-label-variant` 태그도 붙이지 않는다.
- 근거 표시 (팀 회의 2026-10-20 5번): 이유 끝에 ` / 근거: ` 뒤로 변이 이름·종류(절단형 표시)·VAF, 허가 동반진단 목록 해당 여부(PIK3CA·AKT1·ESR1), ClinVar 판정(BRCA1·BRCA2·PALB2·PTEN), CIViC 근거(PIK3CA·AKT1·PTEN, "판정에 쓰지 않음"), 급여 근거(심평원 공고책자 2026-10-01판 쪽 번호와 D의 chunk_id, 또는 "B가 연결한 심평원 행 없음 (D 확인 전)"), 지침 근거(ESMO 쪽 번호)를 적는다. 스키마에 칸이 있는 변이 이름·VAF·ClinVar는 `evidence`에도 넣는다. 변이 종류·허가 목록·CIViC·급여·지침 칸은 스키마 변경이라 4명 검토 뒤에 옮긴다. 문서 문장은 옮기지 않고 문서와 쪽만 적는다 (심평원 공고 판권면의 복제 금지 문구).
- 급여·지침 쪽 번호: 코드의 `REIMBURSEMENT_BASIS`(D가 쓰는 심평원 공고책자 2026-10-01판(제2026-210호)의 인쇄 쪽과 D의 chunk_id, D 확인 2026-10-21. 공고 문구는 옮기지 않는다), `GUIDELINE_BASIS`(`data/chunks/esmo_chunks.json`의 ESMO 쪽). 급여 근거는 D가 확인해 준 행(2026-10-21)만 적고, 공고 내용 해석(급여·비급여 여부 등)은 적지 않는다. 급여 판정은 D의 청크로 한다. ESR1·PALB2·체세포 BRCA는 B가 연결한 심평원 행이 없어 "D 확인 전"으로 적는다.
- BRCA1/2 레코드 이름: TCGA·가상·실제 차트 모두 검사 종류와 관계없이 `gBRCA1/2` (전달 문서 4.7절, A 결정 2026-10-21. TCGA는 종양 엑솜을 생식세포 검사로 가정). `sBRCA1/2` 레코드는 만들지 않는다 (체세포 BRCA 근거 권고는 다루지 않음, 모델 한계).
- 태그(`rag_tags`)는 청크 `biomarker_tags`와 같은 어휘를 쓴다 (C의 `src/rag/rag_guideline_chunking_design_update.md` 3.5절 표준 태그): `PIK3CA-mut`, `AKT1-mut`, `PTEN-alt`, `ESR1-mut`, `gBRCA`, `sBRCA`, `gPALB2`, `PD-L1+`.
- BM-3 ClinVar (2026-10-19, 전달 문서 5.4절): `data/clinvar/clinvar_bm3_genes.tsv`를 로컬에서 조회한다. 리뷰 등급 기준은 코드의 `CLINVAR_MIN_STARS`. 단백질 변화(한 글자 표기)로 맞추므로 전사체가 다르면 놓칠 수 있다. ClinVar로 판정하는 유전자는 BRCA1·BRCA2·PALB2이고, PTEN은 근거로만 적는다 (코드의 `CLINVAR_JUDGE_GENES`). 근거는 `evidence.clinvar`에 `Pathogenic (3성, VCV17661)` 형식으로 남긴다. 예: BRCA1 C61G → 양성.
- ClinVar 표 만들기: **각자** `python data/script/clinvar_download.py`를 실행한다 (NCBI `variant_summary.txt.gz` 약 450MB를 내려받으며 BRCA1·BRCA2·PALB2·PTEN만 걸러 약 5.7MB TSV로 저장, 원본 날짜는 `data/clinvar/clinvar_version.log`). 전달 문서 5.6절("스크립트만 올린다")에 따라 표는 git에 올리지 않는다 (`.tsv`·`.log`는 `.gitignore`의 `data/` 규칙으로 제외). 표가 없으면 ClinVar 조회 없이 VUS로 남고 이유에 실행 안내가 붙으며, ClinVar가 필요한 테스트(C01~C08)는 건너뛴다.
- BM-3 CIViC (2026-10-19, 전달 문서 5.4절. 2026-10-20부터 판정에 쓰지 않고 근거로만): `data/civic/civic_bm3_evidence_<받은 날>.csv` 중 가장 최근 파일을 로컬에서 조회한다 (5.6절: 파일명에 받은 날짜, CC0라 git에 올림). "PIK3CA Mutation" 같은 묶음 프로파일과 AND/OR 조합은 쓰지 않고, 변이 하나를 지목한 근거 중 Predictive + Sensitivity/Response 또는 Oncogenic + Oncogenicity, 방향 Supports만 센다 (내성 근거는 양성 근거가 아님). 근거 등급 A~E는 모두 인정하고, 가장 높은 등급(같으면 유방암 근거)을 이유에 `CIViC 근거 등급 A (…, EID12034)` 형식으로 남긴다. `biomarker_record` 스키마에 CIViC 칸이 없어 `evidence`에는 넣지 않는다 (`evidence.oncokb` → `annotation` 변경 제안, 4명 합의 대기).
- CIViC 표 만들기: `python data/script/civic_download.py` (CIViC nightly 근거 파일 약 4MB를 받아 PIK3CA·AKT1·PTEN 근거 47행만 저장, CC0). 표가 없으면 CIViC 조회 없이 VUS로 남고 이유에 실행 안내가 붙는다.
- `actionable_variants.csv`의 PIK3CA 11개는 전달 문서 5.4절 예시와 같고, therascreen PIK3CA 키트의 QIAGEN 제품 페이지와 AccessGUDID 등록 정보로 확인했다 (사용설명서 원본은 아직 대조하지 않음). AKT1(E17K)·ESR1(Y537S/N/C, D538G)은 전달 문서 5.4절의 예시만 넣었고 `verified = no`라 판정 이유에 "원문 확인 필요"가 붙는다. FDA 라벨·SSED 원문으로 확인하면 목록을 채우고 `yes`로 바꾼다.
- TCGA 838명 결과 (2026-10-20 정답 세트 838명, 2026-10-21 다시 셈. ClinVar 2026-10-12 파일·CIViC 2026-10-19 파일 기준): PIK3CA 양성 206 / VUS 67, AKT1 양성 21 / VUS 2, PTEN 양성 46, gBRCA1 양성 10 / VUS 12, gBRCA2 양성 6 / VUS 16, PALB2 VUS 6, ESR1 VUS 8 / 재검 필요 6 / 양성 0. 미시행은 유전자마다 21명 (A의 변환이 변이 검사 대상 아님과 정보 없음을 모두 미시행으로 넘긴다). 2026-10-20 규칙 변경 때(874명 기준) 바뀐 점: PTEN은 변이 유무로 41 → 49 (VUS 8명이 양성), PIK3CA는 CIViC로 양성이던 2명(R88Q, K111N)이 VUS로. 정답 세트가 874명 → 860명 → 838명이 되면서(A, 2026-10-20) 숫자가 다시 바뀌었다.

유전자 검사 공백 (BM-4, 2026-10-16). 현재 전이성 환자만, 미시행(`not_done`)일 때만 `tests_needed`에 넣는다:

| 아형 | 권고 | 규칙 ID |
|---|---|---|
| HR+/HER2-, TNBC | gBRCA1·gBRCA2·PALB2 미시행 → 생식세포 검사 | `BM4-GBRCA1`, `BM4-GBRCA2`, `BM4-PALB2` |
| HR+/HER2- | PIK3CA·AKT1·PTEN 미시행 → 검사 | `BM4-PIK3CA`, `BM4-AKT1`, `BM4-PTEN` |
| HR+/HER2- | ESR1 미시행 → 검사 / ESR1 재검 필요 → cfDNA 재검 | `BM4-ESR1` / `BM4-ESR1-RETEST` |

- 생식세포 BRCA가 기록 없음이면 권고하지 않는다 (전달 문서 4.7절, B 결정 2026-10-16). 미시행이면 TCGA가 아닌 차트도 권고한다 (BRCA는 모두 gBRCA, A 결정 2026-10-21).
- TCGA 838명 결과: 현재 전이성 환자는 유전자 검사가 모두 시행돼 미시행 권고는 0명, ESR1 재검 권고 3명.

검사 결과 대기·예정 (2026-10-19, B 결정, 전달 문서 0절 5번·schema_fields.md 2절): 미시행(`not_done`) 칸의 `raw`가 고정 표기 `"결과 대기"`(검체를 보내 결과를 기다림) 또는 `"예정"`(예약만 됨)이면, 검사 공백(`tests_needed`)을 새 검사 권고 대신 "결과 확인"으로 낸다. `test`는 `"PIK3CA 결과 확인"`처럼 끝에 "결과 확인"을 붙이고, `rule_id`는 원래 규칙 ID에 `-PENDING`(결과 대기) 또는 `-SCHEDULED`(예정)를 붙인다 (예: `BM4-PIK3CA-PENDING`). 그 밖의 `raw`(예: "시행하지 않음")는 그대로 검사 권고. 판정 레코드의 상태는 둘 다 `not_done`이고, 이유에 `(결과 대기)`를 적는다. TCGA에는 해당 환자가 없다.

치료 상황 `setting` (전달 문서 6.1·6.2·6.3a절, draft6, 2026-10-19):

| 현재 범주 | `line` | 규칙 |
|---|---|---|
| metastatic | `1L` / `2L` / `>=3L` | A가 넘긴 `treatment_history[].line` 중 마지막 고식적 요법의 차수. 그 요법이 진행(`best_response = PD`, `stop_reason = progression`)으로 끝났으면 다음 차수 (전달 문서 8.2절 예시: 1차 진행 → `2L`) |
| metastatic | `unknown` | 전이 후 투약 기록 없음 (전달 문서에 규칙 없음) |
| metastatic | `unknown` | 전이 후 투약은 있지만 `line` 값이 없음 |
| early, locally_advanced | `neoadjuvant` / `adjuvant` | 마지막 선행·보조 투약에 A가 적은 `treatment_history[].setting`을 그대로 쓴다. 보조약·골 보호제는 빼고 본다 (6.2절 규칙 3) |
| early, locally_advanced | `unknown` | 선행·보조 투약 없음 |

- 내분비·항암 차수(`endocrine_line`, `chemo_line`)와 충족한 심평원 차수 간주 규칙(`deemed_lines`의 `met`)은 `setting.reason`에 적는다. 급여 판정은 [4] 추천 모듈이 "실제 차수 + 간주 규칙"으로 한다 (6.3a절).
- TCGA 838명 (2026-10-20 정답 세트 838명, 2026-10-21 다시 셈): 전이성 23명 중 1L 11, 2L 6, >=3L 6. 조기·국소 진행성은 adjuvant 607, neoadjuvant 2, unknown 206.
- 판정 기준일(`index_day`) 이후 투약을 빼는 처리는 아직 없다 (TCGA는 기준일이 마지막 추적일이라 영향 없음).

테스트 실행 (`team_project` 폴더에서): `python -m pytest tests/biomarker` 또는 케이스별 출력은 `python -m tests.biomarker.test_bm`
