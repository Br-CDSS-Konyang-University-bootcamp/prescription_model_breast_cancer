# TCGA-BRCA → patient_state 대응표 (초안)

> 담당 A · 2026-10-12 초안, 같은 날 A 결정 규칙 반영 (§3.1 조직형, §3.2 병기·림프절·전이, §3.5 성별, §3.6 투여일) · 입력: `data/tcga_brca/merged/tcga_brca_merging_cropped.csv` (환자 874명 × 129열, 2026-10-15 기준) · 출력: `schemas/patient_state.json` 형식의 **정답 값**

## 1. 목적

이 대응표는 실제 처리 경로가 아니라 **평가용 정답(ground truth)을 만드는 규칙**이다.

```
TCGA 한 행 ──(1) 이 대응표로 변환──▶ 정답 값
                                     ├──(2) 가상 차트 생성기──▶ 가상 차트 원문 (양식 여러 종) + 정답의 원문 인용·위치
                                     ▼
가상 차트 원문 ──입력 모듈──▶ 추출 결과 ──(3) 비교──▶ 필드별 정확도
```

- (1)은 규칙 코드다. LLM을 쓰지 않는다. 구현: `src/input/truth/tcga_truth.py` (2026-10-15). 값 대응은 `data/dictionaries/field_vocab.csv`. 결과는 `data/truth/`, 규칙별 건수는 `data/truth/truth_report.txt`.
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

2026-10-13부터 이 제외 규칙은 크롭 스크립트가 먼저 적용한다 (사용자 결정). 크롭 단계에서 Stage X 중 범주를 정할 수 없는 11명, 조직형 NOS·기록 없음 2명, 진단 시 전이성이 아니면서 새 원발암만 있는 19명, 재발 없음인데 재발 후 수술 YES인 1명, 현재 전이성인데 전이 진단일·투약·전이 후 항암 투약 기록이 없는 48명도 함께 빠진다. 2026-10-15에는 anthracycline 병용 기록의 용량을 약별로 나눌 수 없는 4명(TCGA-D8-A27N, D8-A1XL, D8-A140, D8-A1JM)과 재발했지만 부위를 알 수 없는 7명(`recurrence_status = site_unknown`)도 뺐다 (사용자 결정). 같은 날 HER2 IHC 2+인데 ISH 결과 없이 판정만 Positive인 5명(TCGA-A8-A07R, AN-A041, AN-A0AK, AN-A0FZ, AN-A0XP)을 뺐다가, 2+이고 ISH가 없으면 적힌 판정(positive·negative)을 따르기로 해 다시 넣었다 (사용자 결정, 869명 → 874명). 같은 날 PR 판정이 Indeterminate로만 적힌 4명(TCGA-AN-A0FW, B6-A0IO, BH-A1F0, D8-A1X8)과 ER·PR·HER2(IHC·FISH)가 모두 미시행인 43명, ER 또는 PR이 미시행인 2명(TCGA-C8-A9FZ, E9-A1N8, HR 평가 불가), HER2 판정 불가 62명(IHC 2+인데 ISH가 equivocal·미시행·기록 없음 21명, IHC 점수 없이 판정이 Indeterminate·미시행·기록 없음이고 ISH도 없는 41명)도 뺐다 (사용자 결정, 수용체 판정 불가). 크롭본 874명이 곧 정답 세트다.

### 2.3 날짜 [A 결정, 2026-10-12]

TCGA에는 실제 날짜가 없고 "진단 후 일수(d77)"만 있다. **가상 날짜를 만들지 않고 모든 날짜를 비운다.**

- 추출값 날짜 칸(`diagnosis_date`, `recurrence_date`, `adjuvant_endocrine_end_date`): `{"status": "not_recorded"}`
- 날짜 속성(`observed_date`, 치료 이력의 `start_date`·`end_date`, 보고서의 `report_date`, 문서의 `doc_date`): `null`
- [변경, 2026-10-15, 스키마 0.1-draft5] 상대 일수(진단일 = 0인 정수)는 실제 날짜가 아니므로 정답에 넣는다: `treatment_history[].start_day`·`end_day`, `recurrence.metastasis_day`. B가 처방 시작일과 전이 기준일을 비교해 차수를 정하는 데 쓴다. 날짜 칸은 위 규칙대로 비운다.
- [변경, 2026-10-16, 스키마 0.1-draft6] 판정 기준일 `index_day`(최상위)는 마지막 추적일 `fu_last_days`로 채운다. 802명은 값이 있고 72명은 `null`. 6명은 마지막 추적일보다 늦게 시작한 투약 기록이 있다 (원자료끼리 어긋남, 고치지 않고 둔다). 첫 재발일 `recurrence.recurrence_day`는 §3.7.
- 가상 차트에도 실제 날짜를 쓰지 않는다. 정답과 맞지 않게 되기 때문이다. 순서는 "수술 후", "재발 후" 같은 표현으로 나타낸다.

### 2.4 구간 값

ER/PR 양성 비율은 `90-99%` 같은 구간이다. 정답 `value`에는 구간을 `[최소, 최대]` 배열로 넣고 (`90-99%` → `[90, 99]`, `<1%` → `[0, 0]`), 가상 차트에는 구간 안의 대표값(예: 95%)을 쓴다. 대표값과 구간을 함께 저장해야 추출 결과를 비교할 수 있다.

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
| Infiltrating Ductal Carcinoma | `IDC` (침윤성 관암, NST) | 634 |
| Infiltrating Lobular Carcinoma | `ILC` | 167 |
| Mucinous Carcinoma | `mucinous` (침윤성 특수 아형) | 13 |
| Metaplastic Carcinoma | `metaplastic` | 9 |
| Infiltrating Carcinoma NOS | `invasive_NOS` | 0 (크롭 단계에서 삭제) |
| Other, specify → ONCOTREE `BRCNOS` | `invasive_NOS` | 29 |
| Mixed Histology → ONCOTREE `BRCNOS` | `invasive_NOS` | 20 |
| Medullary Carcinoma → ONCOTREE `IDC` | `IDC` (WHO 2019에서 수질암은 IDC/NST의 한 형태) | 2 |

Other·Mixed의 자유 기재(`gdc_histologic_diagnosis_other`, 예: "infiltrating ductal and mucinous")는 `raw`에 남긴다.

### 3.2 병기 (`fields.stage`)

| 필드 | TCGA 열 | 변환 | 주의 |
|---|---|---|---|
| `ptnm` | T = `gdc_ajcc_tumor_pathologic_pt`, N = `gdc_ajcc_nodes_pathologic_pn`, M = `gdc_ajcc_metastasis_pathologic_pm`, 판 = `gdc_ajcc_staging_edition` | `{"t": "T2", "n": "N1a", "m": "M0", "edition": "7th"}`. X값(TX·NX·MX)은 `not_assessed` (평가 안됨) [A 결정] | TX 0, NX 10, MX 133. AJCC 판(3rd~7th)마다 기준이 다르므로 판을 함께 저장 |
| `group` [합의 예정] | `gdc_ajcc_pathologic_tumor_stage` | `Stage IIA` → `IIA`, `Stage I` → `I`. `Stage X` → `not_assessed` (평가 안됨·불가 통합) [A 결정] | Stage X 2명 (2026-10-13 크롭 후) |
| `positive_ln_count` [제안] | positive = `gdc_lymph_nodes_examined_he_count` (이름과 달리 양성 개수), examined = `gdc_lymph_nodes_examined_count` | 아래 표 [A 결정] | 심평원 abemaciclib 기준(4개)에 사용 |
| `ctnm` | 없음 | `not_recorded` | TCGA는 병리 병기만 있음. TCGA 값은 `ctnm`이 아니라 `ptnm`에 넣고, 가상 차트에는 `pT2N1M0`처럼 p를 붙인다 |
| `metastatic_sites` | `gdc_metastatic_tumor_indicator`, `gdc_metastasis_site`, `gdc_metastasis_site_other` | 아래 규칙 [A 결정]. 진단 시 전이만 | 재발 후 전이 부위는 `recurrence` 쪽 (§3.7) |
| `operable` [draft5] | 없음 | `not_recorded` | 수술 가능 여부. 가상 차트로 테스트 |

TNM 세부 표기 [합의 예정]: 공백만 지우고 그대로 둔다. `N0 (i-)` → `N0(i-)` 144, `N0 (i+)` → `N0(i+)` 27, `N1mi` 34, `N0 (mol+)` → `N0(mol+)` 1, `cM0 (i+)` → `cM0(i+)` 6.

병기군 [A 결정]: `[Discrepancy]`(6명)와 `[Not Available]`(5명)인 환자는 정답 세트에서 제외한다 (§2.2).

양성 림프절 수 [A 결정]:

| 경우 | 건수 | 정답 value |
|---|---|---|
| 둘 다 있음 | 744 | `{"positive": 2, "examined": 15}` |
| examined만 `[Not Available]` | 1 | `{"positive": 4, "examined": "[Not Available]"}` |
| positive만 `[Not Available]` | 29 | `{"positive": "[Not Available]", "examined": 15}` |
| 둘 다 `[Not Available]` [합의 예정] | 100 | 칸 전체 `status: not_recorded` |

`raw`는 원본 값을 `양성/검사`로 잇고, 없는 쪽은 원본 코드 `[Not Available]`를 그대로 쓴다 (예: `26/[Not Available]`, `[Not Available]/15`). 2026-10-19 수정: 그전에는 없는 쪽이 `None`으로 찍혔다 (30명).

`gdc_lymph_nodes_examined_ihc_count`(면역염색 양성 수, 31.4%)는 가상 차트 문장에만 쓴다.

전이 부위 [A 결정]:

1. `gdc_metastatic_tumor_indicator`를 먼저 본다.
2. `NO`이면 `[Not Applicable]` (해당 없음). 313명
3. [사용자 결정, 2026-10-15] `[Not Available]`이어도 병리 M이 `M0`·`cM0(i+)`이면 진단 시 전이가 없으므로 `[Not Applicable]`. 468명 (874명 기준). B가 기록 없음을 전이 가능성으로 읽지 않게 하려는 것이다
4. `YES`(4명) 또는 남은 `[Not Available]`(MX·M1 98명)이면 `gdc_metastasis_site`를 `|`로 나눠 쓴다.
5. `gdc_metastasis_site`가 `[Not Available]`이면 `gdc_metastasis_site_other`를 쓴다. 이것도 `[Not Available]`이면 `[Not Available]`.
6. [합의 예정] `gdc_metastasis_site` 안의 `Other, specify` 항목은 `gdc_metastasis_site_other` 내용으로 바꾼다. 해당 4명.

참고: 진단 시 M1은 8명인데 전이 여부 `YES`는 4명이다. 두 출처가 다를 수 있으므로 가상 차트를 만들 때 함께 확인한다.

### 3.3 수용체 (`fields.receptors`) — 진단 시 원발 종양

세부 규칙과 건수 표는 [schema_fields.md §5](schema_fields.md)에 있다. 요약:

| 필드 | TCGA 열 | 변환 [A 결정] |
|---|---|---|
| `er_percent` | `gdc_er_status_ihc_Percent_Positive`(구간), `gdc_er_status_by_ihc`(판정) | 구간과 판정을 모두 넣는다. 판정 `Low Positive` → `low_positive`. **점수 열(`gdc_er_ihc_score`)은 쓰지 않는다** |
| `pr_percent` | `gdc_pr_status_ihc_percent_positive`, `gdc_pr_status_by_ihc` | ER과 같음. 단 저발현 범주가 없다 (`1-9%`도 `positive`). 점수 열(`gdc_pr_positivity_ihc_intensity_score`)은 쓰지 않는다 |
| `her2_ihc` | `gdc_her2_ihc_score`, `gdc_her2_status_by_ihc`, `gdc_her2_fish_status` | 점수와 판정을 함께 표기. 점수 없는 Equivocal은 `2+`로 채움. 2+ 또는 Equivocal이면 FISH로 `result` 보정 (Negative → negative, Positive → positive, 그 밖에 Equivocal이면 unknown) |
| `her2_ish` | `gdc_her2_fish_status` | `{result, method: "FISH"}`. Positive → amplified, Negative → not_amplified, Equivocal → equivocal. `[Not Evaluated]` 542건 → `not_done`. 복제수·비율 열은 넣지 않는다 |
| `pdl1` [draft5] | 없음 | `not_recorded`. 발현 점수(검사법, 점수 종류, 점수)만 담고 판정은 B가 약제별 기준으로 한다 |

원본 구간 `<10%`는 크롭 스크립트가 판정에 따라 둘로 나눴다: `<10%` + Positive → 구간 `1-9%`, ER만 판정 `Low Positive` (ER 14명, PR 49명은 `Positive` 유지) / `<10%` + Negative → 구간 `<1%` (ER 48명, PR 75명, 1% 기준 음성으로 가정. 2010년 이전 진단은 10% 기준이었을 수 있음). 재발 병소 칸도 같은 규칙. ER 저발현 경계 사례 테스트에는 `1-9%` 환자를 쓴다.

### 3.4 증식 (`fields.proliferation`)

| 필드 | TCGA 열 | 변환 |
|---|---|---|
| `ki67_percent` | 없음 | `not_recorded`. 합성값으로 경계 사례 추가 (§4) |

### 3.5 환자 (`fields.patient`)

| 필드 | TCGA 열 | 변환 | 실제 값 비율 · 주의 |
|---|---|---|---|
| `gender` [제안, A 결정] | `gdc_gender` | `FEMALE` / `MALE` | 정리본은 FEMALE 874명 (남성은 정리 단계에서 제외됨) |
| `age` | `gdc_age_at_diagnosis` | 정수. `observed_date`는 `null` | 100% |
| `menopausal_status` | `gdc_menopause_status` | Post → `postmenopausal`, Pre → `premenopausal`, Peri → `perimenopausal`, Indeterminate → `indeterminate` (기록된 판단이므로 `present`) | 92.5%. 괄호 안 정의 문장은 `raw`에 보관 |
| `ecog` | 없음 | `not_recorded`. 합성값 가능 (§4) | |
| `menopausal_basis` [draft5] | 없음 | `not_recorded` | 폐경 판정 근거 |

### 3.6 치료 이력 (`fields.treatment_history`)

`drug_timeline`을 ` | `로 나눠 약 하나를 한 항목으로 만든다. 형식: `성분명 [치료 종류] d시작~d종료 (최선 반응)`.

| 필드 | 출처 | 변환 |
|---|---|---|
| `drugs` | 성분명 | `drug_timeline` 항목 하나 = `treatment_history` 원소 하나. 원본 한 기록에 약이 여러 개면(`doxorubicin+cyclophosphamide`) 한 원소에 여러 약. 같은 날 시작한 별도 기록은 묶지 않는다. 요법 묶음과 차수는 아래 `line` 칸에서 계산한다 [2026-10-16 변경] |
| `start_date`, `end_date` | — | [A 결정] TCGA에는 실제 날짜가 없으므로 `null` |
| `duration_days` [제안, A 결정] | `drug_start_days`, `drug_end_days` | `end_day − start_day` (일). 투약 기록 2,033건 중 시작·종료가 모두 있는 1,507건만 값이 있다. 종료 모름 442건, 시작 모름 84건(그중 종료만 있는 31건)은 `null` |
| `best_response` | 괄호 안 반응 | Complete Response → `CR`, Partial Response → `PR`, Stable Disease → `SD`, Clinical Progressive Disease → `PD`, 없으면 `unknown` |
| `stop_reason` | 없음 | `null` |
| `setting` | 유도 | 아래 규칙 (유도값이라는 표시를 남긴다) |
| `start_day`, `end_day` [draft5] | `drug_start_days`, `drug_end_days` (2026-10-15 추가. 원본 `pharmaceutical_tx_started_days_to`, `pharmaceutical_tx_ended_days_to`를 `drug_timeline`과 같은 순서로 ` \| `로 이은 열) | 정수. 괄호 코드·`-`이면 `null`. `drug_timeline`은 시작일이 없으면 종료일도 버리지만, 이 열은 종료일을 남긴다 (31건) |
| `progression_day` [draft5] | 없음 | `null` |
| `cycles` [draft5] | `drug_cycles`, `d시작`·`d종료`, `data/dictionaries/drug_classes.csv`의 `cycle_days` | 아래 규칙 |
| `line`, `endocrine_line`, `chemo_line` [draft6] | `start_day`, `setting`, `best_response`, `recurrence.metastasis_day`, `drug_classes.csv`의 `drug_class` | `src/input/common/lines.py`의 `palliative_lines` (규칙은 handoff_to_B.md §6.2). 전이 전 투약·보조약·골 보호제·시작일 없는 투약은 `null`. 정답 세트에서 값이 있는 투약 90건, 환자 28명 |

주기 수 `cycles` 규칙 [사용자 결정, 2026-10-15]:

| 경우 | `value` | `basis` | `interval_days` | `interval_basis` |
|---|---|---|---|---|
| `drug_cycles` 기록 있음, 투여 일수 있음, 2주기 이상 | 기록값 | `recorded` | 투여 일수 ÷ (주기 수 − 1), 반올림 | `derived` |
| `drug_cycles` 기록 있음, 나머지 | 기록값 | `recorded` | 사전 기본값 (없으면 `null`) | `standard` |
| 기록 없음, 투여 일수 있음, 사전에 있는 약 | 투여 일수 ÷ 기본값 + 1, 반올림 | `estimated` | 사전 기본값 | `standard` |
| 그 밖 (매일 먹는 내분비요법 등) | 칸 전체 `null` | | | |

- 병용 기록(`doxorubicin+cyclophosphamide`)은 사전 기본값 중 큰 값을 쓴다.
- 기록 주기 수는 투여 횟수일 수 있다. 예: trastuzumab 47주기 = 매주 투여 (`interval_days` 8). 공고의 "18주기"(3주 기준)와 비교할 때는 `interval_days`를 함께 본다.

`setting` 유도 규칙:

1. 시작일 ≥ `metastasis_dx_days`(전이 기준일)이면 → `metastatic`. 진단 시 M1은 전이 기준일이 0이므로 진단 후 시작한 약이 모두 여기에 해당한다 [2026-10-15 변경: 첫 재발일에는 국소 재발이 섞일 수 있어 전이 기준일로 바꿈]
2. 시작일이 없으면 판정하지 않고 아래 규칙으로 간다 (84건)
3. `gdc_history_neoadjuvant_treatment` = Yes이고 첫 요법이면 → `neoadjuvant` (선행요법 이력 Yes 13명 중 실제로 붙는 환자는 8명. 수술일이 없어 정확하지 않으므로 수작업 확인)
4. 나머지 → `adjuvant`

제외: 성분명이 `unknown`인 항목(`unknown [[Not Available]]`)은 정답에 넣지 않는다. 같은 약이 기간이 겹쳐 두 번 기록된 경우(예: trastuzumab d151~d511, d154~d490)도 원본대로 두 원소로 둔다 [2026-10-15 변경].

투약 기록이 없는 환자(213명, 24.4%)는 빈 배열이다. "치료를 안 했다"가 아니라 "기록이 없다"이다.

### 3.6b 차수 간주 규칙 (`fields.deemed_lines`) [draft6, 2026-10-16]

`src/input/common/lines.py`의 `deemed_lines`. 규칙 4개를 환자마다 모두 적는다. 기간은 근거 투약 종료일부터 전이 기준일까지 세고, 종료일이 없으면 시작일을 하한으로 쓴다.

| 규칙 | 공고 | 조건 | met | not_met | unknown | not_applicable |
|---|---|---|---|---|---|---|
| `DEEM-ANTHRA-TAXANE` | p.61~62 | 선행·보조요법에 anthracycline과 taxane이 모두 있음 (기간 제한 없음) | 8 | 20 | 0 | 846 |
| `DEEM-SG-1Y` | p.63 | 선행·보조요법 종료 후 365일 이내 전이 | 13 | 14 | 1 | 846 |
| `DEEM-HER2ADC-6M` | p.62~63 | trastuzumab 포함 보조요법 종료 후 183일 이내 전이 | 1 | 27 | 0 | 846 |
| `DEEM-ENDO-ADJ-1Y` | p.57 | 보조 내분비요법 종료 후 365일 이내 전이 | 8 | 19 | 1 | 846 |

- `not_applicable` 846명 = 전이 기준일이 없는 환자 (전이성 아님). 전이성 28명만 판정한다.
- 재발 시점은 첫 재발일이 아니라 전이 기준일을 쓴다. 간주 규칙은 고식적 요법의 차수에 관한 것이라 원격 전이가 기준이다.

### 3.7 선행요법 반응, 재발

| 필드 | TCGA 열 | 변환 |
|---|---|---|
| `neoadjuvant_response.pcr`, `.rcb` | 없음 | `not_recorded` |
| `recurrence.recurrence_date` | `nte_first_dx_days`, `nte_types`, `nte_sites`, `nte_sites_other` | 날짜는 `not_recorded` (§2.3). 재발 여부와 사건 종류·부위는 가상 차트 문장에 쓴다. New Primary Tumor는 재발이 아니므로 제외 |
| `recurrence.adjuvant_endocrine_end_date` | 없음 | 날짜 칸이므로 `not_recorded` (§2.3). 보조 내분비요법 종료 시점은 B가 `treatment_history[].end_day`로 계산한다 |
| `recurrence.status` [draft5] | `recurrence_status` | 그대로: `none` / `distant` / `locoregional` / `unknown`. `site_unknown`은 크롭 단계에서 뺐다 (2026-10-15) |
| `recurrence.metastatic_sites` [draft5] | `nte_sites`, `nte_sites_other` | `status = distant`일 때만. Bone → `bone`, Liver → `liver`, Lung → `lung`, Brain → `brain`, `Other, specify` → `other: <nte_sites_other 항목>`. 여러 개 나열. 국소 부위(Axilla, Chest wall 등)가 섞일 수 있으나 처방·급여 판정에는 영향이 없다고 봄 (사용자 결정) |
| `recurrence.metastasis_day` [draft5] | `metastasis_dx_days` | 정수 (진단 시 IV기 = 0). 값이 없으면 칸을 만들지 않음 |
| `recurrence.recurrence_day` [draft6] | `locoregional_dx_days`, `metastasis_dx_days` | `status`가 `distant`·`locoregional`일 때만. 국소 재발일과 원격 전이 재발일(`distant`일 때) 중 이른 값. 진단 시 IV기는 재발이 아니므로 넣지 않음. 34명 (distant 22, locoregional 12) |
| `recurrence.surgery` [draft5] | `nte_surgery` | `status`가 `none`·`unknown`이 아닐 때만. YES가 하나라도 있으면 `yes`, NO만 있으면 `no`, 빈칸이면 `unknown` |
| `recurrence.surgery_intent` [draft5] | 없음 | `surgery`를 만들 때 항상 `unknown` |
| `recurrence.later_distant` [draft5] | `locoregional_dx_days`, `metastasis_dx_days` | `status = locoregional` → `no`. `status = distant`이고 국소 재발일이 있으면 국소 재발일 < 전이 기준일 → `yes`, 아니면 `no`. 그 밖은 칸을 만들지 않음 |

국소 재발 후 보조요법 [사용자 결정, 2026-10-15]: `status = locoregional`, `surgery = yes`, `later_distant = no`이면 B가 이후 요법을 수술후보조요법으로 본다 (공고 p.48). 수술 의도는 TCGA에 없어 `unknown`이어도 적용한다.

### 3.7a anthracycline 투약 용량 (`fields.anthracycline_drug_dose`) [draft5, 사용자 결정 2026-10-15]

대상 약: doxorubicin, epirubicin, liposomal doxorubicin (mitoxantrone 제외). `drug_names`가 아니라 `drug_timeline` 항목 순서로 용량 열(`drug_prescribed_dose`, `drug_dose_units`, `drug_cycles`, `drug_total_dose`, `drug_total_dose_units`)을 맞춘다. `drug_names`는 중복을 없앤 목록이라 57명에서 항목 수가 다르다.

| 필드 | 변환 |
|---|---|
| `administered` | `drug_timeline`에 대상 약이 있으면 `positive`, 투약 기록은 있는데 없으면 `negative`, 투약 기록이 없으면 `No value` |
| `drugs[]` | 대상 약이 든 항목 하나 = 원소 하나. `drug`, `timeline_index`(0부터), `combined_with`, `raw` |
| `dose_per_admin`, `total_dose` | `{value, unit}`. 병용 기록은 `+`로 나눈 값 중 약 위치의 값 (예: `doxorubicin+cyclophosphamide`, `60+600` → 60). 단위가 하나면 병용 약 모두에 같은 단위. 범위(`100-102`)는 최대값. 괄호 코드·빈칸이면 `No value` |
| `cycles` | `drug_cycles` 기록값만 (§3.6 `cycles` 형식, `basis: recorded`). 없으면 `No value` |

재발 병소 재생검 수용체 [A 결정, 2026-10-14 변경]:

- **TCGA 정답에는 쓰지 않는다.** TCGA 정답은 진단 시(원발 종양) 병기·수용체만 쓴다. 재발 병소 수용체(`gdc_nte_*`)는 정답에 쓰지 않는다 (크롭본 4명 중 재발 기록과 맞는 환자가 1명뿐, 검사 부위·날짜도 없음). 재발 병소 결과 우선 규칙(IN-4)은 가상 차트와 실제 차트 등 다른 입력에만 적용한다 (사용자 결정, 2026-10-14). 아래 규칙은 가상 차트와 실제 차트에 적용한다.

- 재생검 결과로 평가하고 처방하므로, 재발 병소 수용체를 `value`로 쓰고 `specimen`은 `metastasis`. IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.
- 원발 조직 값은 `history[]`로 옮기고 `"superseded_reason": "recurrence"`를 적는다.
- 재발 병소 값이 없는 마커는 원발 값을 그대로 둔다.
- 크롭본에서 4명 (ER 4, PR 3, HER2 2). 재발 기록(원격 전이)과 맞는 환자는 TCGA-GM-A2D9 1명이다.

### 3.8 유전자 보고서 (`fields.genomic_reports`)

입력 모듈은 보고서를 해석하지 않고 원문만 넘긴다(IN-7). 그래서 정답은 "어떤 보고서 원문이 넘어가야 하는가"이다.

구조화된 변이 값은 `fields.molecular.mutations`에 유전자별로 넣는다 [draft5, 사용자 결정 2026-10-15]:

| `mut_*` 값 (ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2. ERBB2 제외) | 정답 |
|---|---|
| 변이 표기 (`H1047R (Missense_Mutation, VAF 0.31)`, 여러 개면 `; `) | `{"status": "present", "result": "detected", "variants": [{"protein_change", "variant_type", "vaf", "raw"}], "specimen": "primary"}` |
| `변이 없음` | `{"status": "present", "result": "not_detected", "variants": [], "specimen": "primary"}` |
| 빈칸 | `{"status": "not_done"}` (미시행) |

가상 보고서 원문(`genomic_reports`)은 아래처럼 만든다.

| 출처 | 변환 |
|---|---|
| `mut_ERBB2`, `mut_ESR1`, `mut_PIK3CA`, `mut_AKT1`, `mut_PTEN`, `mut_BRCA1`, `mut_BRCA2`, `mut_PALB2` | 가상 NGS 보고서 문장으로 만든다. 예: `PIK3CA p.H1047R (missense), VAF 40.0%`. "변이 없음"은 "검출되지 않음"으로 쓴다 |
| `cna_*` | 2(증폭), -2(깊은 결실)만 보고서에 쓴다. 예: `ERBB2 amplification` |
| `mut_sequenced`, `cna_profiled` | False 또는 빈칸이면 보고서를 만들지 않는다 |

- 검체(`specimen`)는 "원발 조직"으로 쓴다. TCGA는 원발 종양 샘플(01)이다.
- [변경, 사용자 결정 2026-10-15] TCGA 변이는 종양 조직 엑솜 결과지만, 정답 세트에서는 `mut_BRCA1/2`를 gBRCA 측정 결과로 가정한다. A는 BRCA1·BRCA2 값을 그대로 넘기고 B가 positive / negative / vus를 판정한다. 모델 한계로 기록한다 (협의 완료, `handoff_to_B.md` §4.7).
- 바이오마커 상태 판정의 정답은 B가 BM-2 기준으로 만든다. A는 보고서 원문과 `molecular.mutations`의 유전자별 값만 책임진다.

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

- [x] 치료 이력의 유도값 구분 (2026-10-15): 스키마에 필드를 추가하지 않고, `truth_report.txt`에 '(유도)' 규칙별 적용 건수를 남긴다
- [x] 다른 암 병력: v0.1에서는 넣지 않는다 (2026-10-15)
- [x] 정답 파일 위치 (2026-10-15): `data/truth/<patient_id>.json` (git 제외, 스크립트로 재생성). 팀 공유용 fixture는 `tests/fixtures/`에 따로 (4명 합의)
