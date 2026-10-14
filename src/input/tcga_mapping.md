# TCGA-BRCA → patient_state 대응표 (초안)

> 담당 A · 2026-10-12 초안, 같은 날 A 결정 규칙 반영 (§3.1 조직형, §3.2 병기·림프절·전이, §3.5 성별, §3.6 투여일) · 입력: `data/tcga_brca/merged/tcga_brca_merging_cropped.csv` (환자 997명 × 117열, 2026-10-14 기준) · 출력: `schemas/patient_state.json` 형식의 **정답 값**

## 1. 목적

이 대응표는 실제 처리 경로가 아니라 **평가용 정답(ground truth)을 만드는 규칙**이다.

```
TCGA 한 행 ──(1) 이 대응표로 변환──▶ 정답 값
                                     ├──(2) 가상 차트 생성기──▶ 가상 차트 원문 (양식 여러 종) + 정답의 원문 인용·위치
                                     ▼
가상 차트 원문 ──입력 모듈──▶ 추출 결과 ──(3) 비교──▶ 필드별 정확도
```

- (1)은 규칙 코드다. LLM을 쓰지 않는다.
- (1)의 결과에는 원문 인용(`source`)이 아직 없다. (2)가 차트 문장을 만들면서 인용과 위치를 채운다.
- 문서 묶음(`documents`)도 (2)가 만든다 (병리 보고서, 경과기록, 투약 기록, 분자병리 보고서).

## 2. 공통 변환 규칙

### 2.1 결측 코드 → 상태값

| CSV 값 | `status` | 비고 |
|---|---|---|
| 정상 값 | `present` | |
| `[Not Available]`, `[Unknown]` | `not_recorded` | 기록 없음 |
| `[Not Evaluated]` | `not_done` | 미시행 |
| `[Not Applicable]` | 필드를 만들지 않음 | 해당 없음 |
| `[Discrepancy]` | `conflicts`에 넣을 후보 | 가상 차트에서 서로 다른 두 값으로 표현해 IN-5 테스트에 쓴다. 단, 병기군(`gdc_ajcc_pathologic_tumor_stage`)의 `[Discrepancy]`는 환자를 제외한다 (§2.2) |
| 빈칸 | `not_recorded` | 그 출처에 기록 자체가 없음 |

### 2.2 정답 세트에서 제외하는 환자 [A 결정]

| 조건 | 건수 |
|---|---|
| `gdc_ajcc_pathologic_tumor_stage`가 `[Discrepancy]` | 6 |
| `gdc_ajcc_pathologic_tumor_stage`가 `[Not Available]` | 5 |
| 모든 값이 빈칸인 행 | 1 |

2026-10-13부터 이 제외 규칙은 크롭 스크립트가 먼저 적용한다 (사용자 결정). 크롭 단계에서 Stage X 중 범주를 정할 수 없는 11명, 조직형 NOS·기록 없음 2명, 진단 시 전이성이 아니면서 새 원발암만 있는 18명, 현재 전이성인데 전이 후 항암 투약 기록이 없는 46명도 함께 빠져 크롭본 997명이 곧 정답 세트다.

### 2.3 날짜 [A 결정, 2026-10-12]

TCGA에는 실제 날짜가 없고 "진단 후 일수(d77)"만 있다. **가상 날짜를 만들지 않고 모든 날짜를 비운다.**

- 추출값 날짜 칸(`diagnosis_date`, `recurrence_date`, `adjuvant_endocrine_end_date`): `{"status": "not_recorded"}`
- 날짜 속성(`observed_date`, 치료 이력의 `start_date`·`end_date`, 보고서의 `report_date`, 문서의 `doc_date`): `null`
- 상대 일수는 정답에 넣지 않고, 코드 안에서 순서 정렬과 유도(치료 단계, 보조 내분비요법 종료, 재발 이전·이후 판단)에만 쓴다. 투여 기간만 `duration_days`로 남긴다 (§3.6).
- 가상 차트에도 실제 날짜를 쓰지 않는다. 정답과 맞지 않게 되기 때문이다. 순서는 "수술 후", "재발 후" 같은 표현으로 나타낸다.

### 2.4 구간 값

ER/PR/HER2 양성 비율은 `90-99%` 같은 구간이다. 정답 `value`에 구간 문자열을 그대로 두고, 가상 차트에는 구간 안의 대표값(예: 95%)을 쓴다. 대표값과 구간을 함께 저장해야 추출 결과를 비교할 수 있다.

## 3. 필드별 대응표

### 3.1 진단 (`fields.diagnosis`)

| 필드 | TCGA 열 | 변환 | 실제 값 비율 · 주의 |
|---|---|---|---|
| `diagnosis_date` | 없음 | `{"status": "not_recorded"}` (§2.3) | TCGA에는 진단 연도만 있음 |
| `histology` | `gdc_histological_type`, `cbio_sample_ONCOTREE_CODE`, `gdc_histologic_diagnosis_other` | 아래 규칙 [A 결정] | 99.8% |
| `grade` | 없음 | `not_recorded`. 경계 사례가 필요하면 합성값 (§4) | TCGA에 조직학적 등급 열 없음 |

조직형 규칙 [A 결정, 2026-10-12]:

1. `gdc_histological_type`이 `Other, specify`, `Mixed Histology (please specify)`, `Medullary Carcinoma`이면 `cbio_sample_ONCOTREE_CODE` 값을 쓴다. ONCOTREE `IMMC` → `mucinous`, `BRCNOS` → `invasive_NOS`, `IDC` → `IDC`.
2. 그 밖의 값은 `gdc_histological_type`을 아래 표로 변환한다.

| 출처 값 | 정답 value | 건수 |
|---|---|---|
| Infiltrating Ductal Carcinoma | `IDC` (침윤성 관암, NST) | 720 |
| Infiltrating Lobular Carcinoma | `ILC` | 186 |
| Mucinous Carcinoma | `mucinous` (침윤성 특수 아형) | 14 |
| Metaplastic Carcinoma | `metaplastic` | 9 |
| Infiltrating Carcinoma NOS | `invasive_NOS` | 0 (크롭 단계에서 삭제) |
| Other, specify → ONCOTREE `BRCNOS` | `invasive_NOS` | 37 |
| Mixed Histology → ONCOTREE `BRCNOS` | `invasive_NOS` | 26 |
| Medullary Carcinoma → ONCOTREE `IDC` | `IDC` (WHO 2019에서 수질암은 IDC/NST의 한 형태) | 5 |

Other·Mixed의 자유 기재(`gdc_histologic_diagnosis_other`, 예: "infiltrating ductal and mucinous")는 `raw`에 남긴다.

### 3.2 병기 (`fields.stage`)

| 필드 | TCGA 열 | 변환 | 주의 |
|---|---|---|---|
| `ptnm` | T = `gdc_ajcc_tumor_pathologic_pt`, N = `gdc_ajcc_nodes_pathologic_pn`, M = `gdc_ajcc_metastasis_pathologic_pm`, 판 = `gdc_ajcc_staging_edition` | `{"t": "T2", "n": "N1a", "m": "M0", "edition": "7th"}`. X값(TX·NX·MX)은 `not_assessed` (평가 안됨) [A 결정] | TX 0, NX 10, MX 143. AJCC 판(3rd~7th)마다 기준이 다르므로 판을 함께 저장 |
| `group` [합의 예정] | `gdc_ajcc_pathologic_tumor_stage` | `Stage IIA` → `IIA`, `Stage I` → `I`. `Stage X` → `not_assessed` (평가 안됨·불가 통합) [A 결정] | Stage X 2명 (2026-10-13 크롭 후) |
| `positive_ln_count` [제안] | positive = `gdc_lymph_nodes_examined_he_count` (이름과 달리 양성 개수), examined = `gdc_lymph_nodes_examined_count` | 아래 표 [A 결정] | 심평원 abemaciclib 기준(4개)에 사용 |
| `ctnm` | 없음 | `not_recorded` | TCGA는 병리 병기만 있음. TCGA 값은 `ctnm`이 아니라 `ptnm`에 넣고, 가상 차트에는 `pT2N1M0`처럼 p를 붙인다 |
| `metastatic_sites` | `gdc_metastatic_tumor_indicator`, `gdc_metastasis_site`, `gdc_metastasis_site_other` | 아래 규칙 [A 결정]. 진단 시 전이만 | 재발 후 전이 부위는 `recurrence` 쪽 (§3.7) |

TNM 세부 표기 [합의 예정]: 공백만 지우고 그대로 둔다. `N0 (i-)` → `N0(i-)` 153, `N0 (i+)` → `N0(i+)` 27, `N1mi` 37, `N0 (mol+)` → `N0(mol+)` 1, `cM0 (i+)` → `cM0(i+)` 6.

병기군 [A 결정]: `[Discrepancy]`(6명)와 `[Not Available]`(5명)인 환자는 정답 세트에서 제외한다 (§2.2).

양성 림프절 수 [A 결정]:

| 경우 | 건수 | 정답 value |
|---|---|---|
| 둘 다 있음 | 848 | `{"positive": 2, "examined": 15}` |
| examined만 `[Not Available]` | 1 | `{"positive": 4, "examined": "[Not Available]"}` |
| positive만 `[Not Available]` | 38 | `{"positive": "[Not Available]", "examined": 15}` |
| 둘 다 `[Not Available]` [합의 예정] | 110 | 칸 전체 `status: not_recorded` |

`gdc_lymph_nodes_examined_ihc_count`(면역염색 양성 수, 31.4%)는 가상 차트 문장에만 쓴다.

전이 부위 [A 결정]:

1. `gdc_metastatic_tumor_indicator`를 먼저 본다.
2. `NO`이면 `[Not Applicable]` (해당 없음). 359명
3. `YES`(4명) 또는 `[Not Available]`(634명)이면 `gdc_metastasis_site`를 `|`로 나눠 쓴다.
4. `gdc_metastasis_site`가 `[Not Available]`이면 `gdc_metastasis_site_other`를 쓴다. 이것도 `[Not Available]`이면 `[Not Available]`.
5. [합의 예정] `gdc_metastasis_site` 안의 `Other, specify` 항목은 `gdc_metastasis_site_other` 내용으로 바꾼다. 해당 4명.

참고: 진단 시 M1은 10명인데 전이 여부 `YES`는 4명이다. 두 출처가 다를 수 있으므로 가상 차트를 만들 때 함께 확인한다.

### 3.3 수용체 (`fields.receptors`) — 진단 시 원발 종양

세부 규칙과 건수 표는 [schema_fields.md §5](schema_fields.md)에 있다. 요약:

| 필드 | TCGA 열 | 변환 [A 결정] |
|---|---|---|
| `er_percent` | `gdc_er_status_ihc_Percent_Positive`(구간), `gdc_er_status_by_ihc`(판정) | 구간과 판정을 모두 넣는다. 판정 `Low Positive` → `low_positive`. **점수 열(`gdc_er_ihc_score`)은 쓰지 않는다** |
| `pr_percent` | `gdc_pr_status_ihc_percent_positive`, `gdc_pr_status_by_ihc` | ER과 같음. 단 저발현 범주가 없다 (`1-9%`도 `positive`). 점수 열(`gdc_pr_positivity_ihc_intensity_score`)은 쓰지 않는다 |
| `her2_ihc` | `gdc_her2_ihc_score`, `gdc_her2_status_by_ihc`, `gdc_her2_fish_status` | 점수와 판정을 함께 표기. 점수 없는 Equivocal은 `2+`로 채움. 2+ 또는 Equivocal이면 FISH로 `result` 보정 (Negative → negative, Positive → positive, 그 밖에 Equivocal이면 unknown) |
| `her2_ish` | `gdc_her2_fish_status` | `{result, method: "FISH"}`. Positive → amplified, Negative → not_amplified, Equivocal → equivocal. `[Not Evaluated]` 547건 → `not_done`. 복제수·비율 열은 넣지 않는다 |

원본 구간 `<10%`는 크롭 스크립트가 판정에 따라 둘로 나눴다: `<10%` + Positive → 구간 `1-9%`, ER만 판정 `Low Positive` (ER 16명, PR 53명은 `Positive` 유지) / `<10%` + Negative → 구간 `<1%` (ER 48명, PR 76명, 1% 기준 음성으로 가정. 2010년 이전 진단은 10% 기준이었을 수 있음). 재발 병소 칸도 같은 규칙. ER 저발현 경계 사례 테스트에는 `1-9%` 환자를 쓴다.

### 3.4 증식 (`fields.proliferation`)

| 필드 | TCGA 열 | 변환 |
|---|---|---|
| `ki67_percent` | 없음 | `not_recorded`. 합성값으로 경계 사례 추가 (§4) |

### 3.5 환자 (`fields.patient`)

| 필드 | TCGA 열 | 변환 | 실제 값 비율 · 주의 |
|---|---|---|---|
| `gender` [제안, A 결정] | `gdc_gender` | `FEMALE` / `MALE` | 정리본은 FEMALE 997명 (남성은 정리 단계에서 제외됨) |
| `age` | `gdc_age_at_diagnosis` | 정수. `observed_date`는 `null` | 99.9% |
| `menopausal_status` | `gdc_menopause_status` | Post → `postmenopausal`, Pre → `premenopausal`, Peri → `perimenopausal`, Indeterminate → `indeterminate` (기록된 판단이므로 `present`) | 92.7%. 괄호 안 정의 문장은 `raw`에 보관 |
| `ecog` | 없음 | `not_recorded`. 합성값 가능 (§4) | |

### 3.6 치료 이력 (`fields.treatment_history`)

`drug_timeline`을 ` | `로 나눠 약 하나를 한 항목으로 만든다. 형식: `성분명 [치료 종류] d시작~d종료 (최선 반응)`.

| 필드 | 출처 | 변환 |
|---|---|---|
| `drugs` | 성분명 | `[이름]`. 같은 기간·같은 반응의 약은 한 요법으로 묶는다 (예: doxorubicin + cyclophosphamide) |
| `start_date`, `end_date` | — | [A 결정] TCGA에는 실제 날짜가 없으므로 `null` |
| `duration_days` [제안, A 결정] | `d시작`, `d종료` | `d종료 − d시작` (일). TCGA 정답에서만 계산. `d1828~?`(종료 모름, 494건)와 `날짜 없음`(88건)은 `null`. 시작·종료가 모두 있는 1,652건만 값이 있고, 종료가 시작보다 앞선 항목은 0건 |
| `best_response` | 괄호 안 반응 | Complete Response → `CR`, Partial Response → `PR`, Stable Disease → `SD`, Clinical Progressive Disease → `PD`, 없으면 `unknown` |
| `stop_reason` | 없음 | `null` |
| `setting` | 유도 | 아래 규칙 (유도값이라는 표시를 남긴다) |

상대 일수(`d시작`)는 정답에 넣지 않고, 코드 안에서 요법 순서 정렬과 `setting` 유도에만 쓴다.

`setting` 유도 규칙:

1. 진단 시 M1이면 → `metastatic`
2. 원격 전이 재발(`nte_types`에 Distant Metastasis)이 있고 시작일 ≥ `nte_first_dx_days`이면 → `metastatic`
3. `gdc_history_neoadjuvant_treatment` = Yes이고 첫 요법이면 → `neoadjuvant` (수술일이 없어서 정확하지 않음, 13명뿐이므로 수작업 확인)
4. 나머지 → `adjuvant`

제외: 성분명이 `unknown`인 항목(`unknown [[Not Available]]`)은 정답에 넣지 않는다. 같은 약이 기간이 겹쳐 두 번 기록된 경우(예: trastuzumab d151~d511, d154~d490)는 하나로 합치고 기록을 남긴다.

투약 기록이 없는 환자(29.1%)는 빈 배열이다. "치료를 안 했다"가 아니라 "기록이 없다"이다.

### 3.7 선행요법 반응, 재발

| 필드 | TCGA 열 | 변환 |
|---|---|---|
| `neoadjuvant_response.pcr`, `.rcb` | 없음 | `not_recorded` |
| `recurrence.recurrence_date` | `nte_first_dx_days`, `nte_types`, `nte_sites`, `nte_sites_other` | 날짜는 `not_recorded` (§2.3). 재발 여부와 사건 종류·부위는 가상 차트 문장에 쓴다. New Primary Tumor는 재발이 아니므로 제외 |
| `recurrence.adjuvant_endocrine_end_date` | `drug_timeline` | 재발일 이전에 끝난 마지막 Hormone Therapy의 종료일 (유도값) |

재발 병소 재생검 수용체 [A 결정, 2026-10-14 변경]:

- **TCGA 정답에는 쓰지 않는다.** TCGA 정답은 진단 시(원발 종양) 병기·수용체만 쓴다. 재발 병소 수용체(`gdc_nte_*`)는 정답에 쓰지 않는다 (크롭본 4명 중 재발 기록과 맞는 환자가 1명뿐, 검사 부위·날짜도 없음). 재발 병소 결과 우선 규칙(IN-4)은 가상 차트와 실제 차트 등 다른 입력에만 적용한다 (사용자 결정, 2026-10-14). 아래 규칙은 가상 차트와 실제 차트에 적용한다.

- 재생검 결과로 평가하고 처방하므로, 재발 병소 수용체를 `value`로 쓰고 `specimen`은 `metastasis`. IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.
- 원발 조직 값은 `history[]`로 옮기고 `"superseded_reason": "recurrence"`를 적는다.
- 재발 병소 값이 없는 마커는 원발 값을 그대로 둔다.
- 크롭본에서 4명 (ER 4, PR 3, HER2 2). 재발 기록(원격 전이)과 맞는 환자는 TCGA-GM-A2D9 1명이다.

### 3.8 유전자 보고서 (`fields.genomic_reports`)

입력 모듈은 보고서를 해석하지 않고 원문만 넘긴다(IN-7). 그래서 정답은 "어떤 보고서 원문이 넘어가야 하는가"이다.

| 출처 | 변환 |
|---|---|
| `mut_ERBB2`, `mut_ESR1`, `mut_PIK3CA`, `mut_AKT1`, `mut_PTEN`, `mut_BRCA1`, `mut_BRCA2`, `mut_PALB2` | 가상 NGS 보고서 문장으로 만든다. 예: `PIK3CA p.H1047R (missense), VAF 40.0%`. "변이 없음"은 "검출되지 않음"으로 쓴다 |
| `cna_*` | 2(증폭), -2(깊은 결실)만 보고서에 쓴다. 예: `ERBB2 amplification` |
| `mut_sequenced`, `cna_profiled` | False 또는 빈칸이면 보고서를 만들지 않는다 |

- 검체(`specimen`)는 "원발 조직"으로 쓴다. TCGA는 원발 종양 샘플(01)이다.
- **주의: TCGA 변이는 체세포(somatic) 변이다.** `mut_BRCA1/2`, `mut_PALB2`를 생식세포(gBRCA) 결과로 쓰면 안 된다. 가상 보고서에 "종양 조직 체세포 검사"라고 명시한다. gBRCA 사례는 합성값으로 만든다 (§4).
- 바이오마커 상태 판정의 정답은 B가 BM-2 기준으로 만든다. A는 보고서 원문만 책임진다.

## 4. TCGA에 없어서 합성값이 필요한 필드

경계 사례 테스트에 필요하지만 TCGA에 없는 값이다. 합성값을 쓰면 정답 파일에 `"synthetic": true`를 표시한다.

| 필드 | 필요한 경계 사례 | 사용 모듈 |
|---|---|---|
| `grade` | grade 3 (심평원 abemaciclib 조건) | A, D |
| `ki67_percent` | 20% 내외, 30% | A, B |
| `ecog` | 0, 1, 2 | A, [4] |
| `pcr`, `rcb` | ypT0N0, RCB-I, 잔존 병변 | A, [4] |
| `ctnm` | 선행요법 환자의 임상 병기 | A |
| gBRCA1/2, PALB2 보고서 | 병원성, VUS | B |
| ESR1 cfDNA 보고서 | 진행 이후 재검 결과 | B |
| PD-L1 보고서 | 22C3 CPS, SP142 IC | B |
| HER2 IHC 0 중 미약한 막 염색 | 초저발현 | B |
| ER 1–10% | ER 저발현 | B |

## 5. 정답에 넣지 않는 열

| 열 | 이유 |
|---|---|
| `cbio_*_MONTHS`, `cbio_*_STATUS`, `fu_*` | 생존·추적 정보. 입력 스키마에 해당 필드 없음. 가상 차트의 경과기록 문장 재료로만 사용 |
| `cbio_SUBTYPE` (PAM50) | 유전자 발현 아형이라 IHC 아형과 다를 수 있음. 차트 값이 아님 |
| `cbio_sample_TMB_NONSYNONYMOUS`, `cbio_sample_MSI_*` | v0.1 바이오마커 범위 밖 |
| `gdc_race`, `gdc_ethnicity`, `gdc_gender` | 스키마에 없음 |
| `gdc_tissue_source_site` | 정답에는 넣지 않지만 메타데이터로 보관 (v0.2 기관 단위 분할) |
| `omf_*`, `gdc_history_other_malignancy` | 다른 암 병력. 스키마에 없음 (필요하면 0단계에서 추가 논의) |
| `gdc_radiation_treatment_adjuvant`, `cbio_RADIATION_THERAPY` | 방사선은 v0.1 범위 밖 |
| `has_*`, `cbio_sample_sampleId`, `drug_*_raw`, `drug_n_records` 등 | 연결·대조용 |

## 6. 0단계에서 정할 것

스키마 변경 항목은 [schema_fields.md §10](schema_fields.md)에 모았다. 이 대응표에만 해당하는 것:

- [ ] 치료 이력의 유도값(setting, 보조 내분비요법 종료일)을 정답에서 구분하는 방법 (`derived: true` 필드 추가 등)
- [ ] 다른 암 병력을 스키마에 넣을지
- [ ] 정답 파일 위치: `tests/fixtures/truth/` (공용 폴더라 4명 합의)
