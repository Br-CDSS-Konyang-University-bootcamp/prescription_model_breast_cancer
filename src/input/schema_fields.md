# patient_state 필드 정리와 정규화 예시

> 담당 A · 2026-10-12 (2026-10-13 `stage.disease_extent` 추가, 2026-10-15 draft5 필드 추가, 2026-10-16 draft6 필드 추가) · 기준 스키마: `schemas/patient_state.json` (0.1-draft6)

입력 모듈(A)이 만드는 `patient_state`의 필드, 표준값 형태, 정규화 방식, 예시, TCGA 정답 생성 규칙을 정리한다. TCGA 열 변환의 세부 규칙은 [tcga_mapping.md](tcga_mapping.md)에 있다.

표기:

- 정규화 방식: **사전** = `data/dictionaries/field_vocab.csv` 조회 · **해석** = 정규식·파싱 함수 · **그대로** = 원문 보존
- **[제안]**: 현재 스키마 초안에 없거나 형태가 다른 항목. B와 합의 후 스키마에 반영한다
- **[A 결정]**: 담당 A가 정한 TCGA 정답 생성 규칙 (2026-10-12)
- **[합의 예정]**: A가 받아들인 제안. 스키마 반영 전에 B와 확인한다

A는 원칙적으로 표기만 정리한다. 예외: HER2 IHC의 `result`는 ISH 결과로 보정한다 (§5, A 결정). TCGA 정답의 ER `low_positive`는 크롭 단계에서 원본 구간 `<10%`와 판정 Positive를 나눠 만든 값이다 (§5). 양성·음성·저발현 같은 최종 판정은 B가 한다. B에게 전달하는 내용은 [handoff_to_B.md](handoff_to_B.md)에 있다.

## 1. 최상위 구조

| 항목 | 의미 | 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `schema_version` | 스키마 버전 | 문자열 | 고정 | → `"0.1-draft6"` |
| `patient_ref` | 가명 ID | 문자열 | 비식별화(IN-0). 실제 값은 내부 대응표에만 | `홍길동 (등록번호 12345678)` → `"VC-0001"` |
| `created_at` | 생성 시각 | ISO 8601 | 자동 | → `"2026-10-12T09:00:00+09:00"` |
| `index_day` [draft6] | 판정 기준일 (진단일 = 0). 추천·급여 판정을 하는 '지금' 시점 | 정수 또는 `null` | 해석 (차트 작성일 → 진단일 기준 일수) | 진단 2024-03-05, 진료일 2026-10-16 → `955` |
| `fields.at_index` [2026-10-20, 검토 전] | 기준일 시점 값. `age`(기준일 나이), `recent_therapy_28d`(최근 4주 이내 항암제·호르몬제 투여 `{status, basis, regimen_refs, gap_days}`) | 객체 | 규칙 (`index_day`, 진단 시 나이, `treatment_history[]`로 계산) | `index_day` 1000, letrozole `end_day` 980 → `{"status":"yes","gap_days":20,…}` |
| `documents[]` | 문서 목록 (IN-1). `doc_type`은 `progress_note` / `pathology` / `molecular` / `medication` / `radiology` [2026-10-22, 검토 전] | `{doc_id, doc_type, doc_date}` | 해석 + 사전 | `[병리결과보고서] 2024.03.05` → `{"doc_id":"D1","doc_type":"pathology","doc_date":"2024-03-05"}`, `[영상 판독] 뼈 스캔` → `"radiology"` |
| `conflicts[]` | 같은 시점에 값이 다른 경우 (IN-5) | `{field, candidates[], note}` | 규칙 | `암 3기` vs `cT2N1M0` → `{"field":"stage.group","candidates":[…III…, …IIB…],"note":"적힌 병기와 TNM 계산 병기가 다름"}` |

## 2. 추출값 공통 틀

아래 3~9의 칸은 대부분 이 틀에 담긴다. 예외: `treatment_history[]`, `anthracycline_drug_dose`, `molecular.mutations.*`, `genomic_reports[]`는 각자의 키를 그대로 쓴다.

| 항목 | 의미 | 예시 (원문 "ER(+) 95%") |
|---|---|---|
| `status` | `present`(값 있음) / `not_done`(미시행) / `not_recorded`(기록 없음) | `"present"` |
| `value` | 표준값 | `{"percent": 95}` |
| `raw` | 원문 표기 그대로 | `"ER(+) 95%"` |
| `observed_date` | 검사일·기록일 | `"2024-03-05"` |
| `specimen` [합의 예정] | `primary` / `metastasis` / `cfDNA` / `unknown` | `"primary"` |
| `confidence` | LLM 추출 확신도 0–1 | `0.97` |
| `source` | 원문 근거 (문서 ID, 인용, 문자 위치) | `{"doc_id":"D1","quote":"ER(+) 95%","char_start":120,"char_end":129}` |
| `history[]` [합의 예정, A 결정] | 새 결과에 밀려난 이전 값 (참고용). 항목마다 밀려난 이유 `superseded_reason`을 적는다: `recurrence`(재발 병소 재생검 결과로 대체), `newer_result`(같은 검체의 더 최근 결과로 대체) | `[{"specimen":"primary", "value":{"result":"positive"}, "superseded_reason":"recurrence", …}]` |

### 특수 표기값 [A 결정]

TCGA 정답에서 아래 표기는 `value` 안에 그대로 쓴다. 칸 전체가 비어 있으면 `status`로 표시한다.

| 표기 | 의미 | 쓰는 곳 |
|---|---|---|
| `not_assessed` (평가 안됨) | 평가하지 않았거나 평가할 수 없음 | TNM의 TX·NX·MX, 병기군 `Stage X` |
| `[Not Available]` | 그 항목만 기록 없음 | 림프절 수의 한쪽 값 |
| `[Not Applicable]` (해당 없음) | 해당 사항 없음 | 진단 시 전이 없음(전이 여부 NO 또는 M0)일 때 전이 부위 |
| `No value` | 값 없음 | `anthracycline_drug_dose`의 투여 여부·용량·주기 |

평가 안됨·평가 불가는 `not_assessed` 하나로 통합한다 [A 결정].

### 미시행의 세부 표기: "결과 대기"·"예정" [A 결정, 2026-10-19, draft6]

검사를 의뢰했거나 예약했지만 결과가 아직 없으면 `status`는 `not_done`이다 (값이 없으므로). 이때 `raw`에 아래 고정 표기를 넣어 단순 미시행과 구분한다. 원문 문장은 `source.quote`에 남긴다.

| 차트 원문 예 | `status` | `raw` | 뜻 |
|---|---|---|---|
| `gBRCA 검사 의뢰함 (결과 대기)`, `PD-L1 검사 중`, `NGS sent, pending` | `not_done` | `"결과 대기"` | 검사는 했고(검체를 보냄) 결과를 기다림 |
| `PD-L1 22C3 시행 예정`, `다음 외래에 gBRCA 검사 예약` | `not_done` | `"예정"` | 예약됐지만 아직 시행 전 |
| `gBRCA 검사 시행하지 않음`, 언급은 있으나 계획 없음 | `not_done` | 원문 그대로 또는 `null` | 단순 미시행 |
| 언급 없음 | `not_recorded` | — | 기록 없음 |

- 유전자 칸(`molecular.mutations.{유전자}`)도 같은 규칙이다. draft6에서 `raw` 키를 추가했다.
- B는 `raw`가 `"결과 대기"`·`"예정"`이면 검사 권고 대신 "결과 확인 필요"로 낼 수 있다 (B와 확인할 것).

## 3. 진단 (`fields.diagnosis`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 정답 규칙 |
|---|---|---|---|---|---|
| `diagnosis_date` | 진단일 | `YYYY-MM-DD` | 해석 | `2024.3.5 조직검사로 진단` → `"2024-03-05"` | `not_recorded` (tcga_mapping.md §2.3) |
| `histology` | 조직형 | `IDC` / `ILC` / `mucinous` / `metaplastic` / `invasive_NOS` / `other` | 사전 | `침윤성 유관암` → `"IDC"` | [A 결정] 아래 표 |
| `grade` | 조직학적 등급 | `1` / `2` / `3` | 사전 + 해석 | `Nottingham grade III (3+3+2=8)` → `3` | 없음 (합성) |

`histology` TCGA 규칙 [A 결정]:

1. `gdc_histological_type`이 `Other, specify`, `Mixed Histology (please specify)`, `Medullary Carcinoma`이면 `cbio_sample_ONCOTREE_CODE` 값을 쓴다.
2. 그 밖의 값은 `gdc_histological_type`을 사전으로 변환한다.

| 출처 값 | 표준값 | 건수 |
|---|---|---|
| `gdc_histological_type` = Infiltrating Ductal Carcinoma | `IDC` | 634 |
| `gdc_histological_type` = Infiltrating Lobular Carcinoma | `ILC` | 167 |
| `gdc_histological_type` = Mucinous Carcinoma | `mucinous` | 13 |
| `gdc_histological_type` = Metaplastic Carcinoma | `metaplastic` | 9 |
| `gdc_histological_type` = Infiltrating Carcinoma NOS | `invasive_NOS` | 0 (크롭 단계에서 삭제) |
| ONCOTREE = `IMMC` | `mucinous` | 1번 대상 행 중 0 |
| ONCOTREE = `BRCNOS` | `invasive_NOS` | Other 29 + Mixed 20 = 49 |
| ONCOTREE = `IDC` | `IDC` | Medullary 5 (WHO 2019에서 수질암은 IDC/NST의 한 형태) |

Mixed·Other의 자유 기재(`gdc_histologic_diagnosis_other`, 예: "infiltrating ductal and mucinous")는 `raw`에 남긴다.

## 4. 병기 (`fields.stage`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 정답 규칙 |
|---|---|---|---|---|---|
| `ctnm` | 임상 TNM | `{t, n, m}` | 해석 | `cT2N1M0` → `{"t":"T2","n":"N1","m":"M0"}` | 없음 (TCGA는 병리 병기만 있음) |
| `ptnm` | 병리 TNM (수술을 먼저 한 환자) | `{t, n, m, edition}` | 해석 | `pT2 pNX M0, AJCC 7th` → `{"t":"T2","n":"not_assessed","m":"M0","edition":"7th"}` | [A 결정] 아래 |
| `yptnm` [2026-10-22, 검토 전] | 선행요법 뒤 수술 병리 병기. status `present` = 결과 있음, `not_done` = 선행요법 뒤 아직 수술 전 (`raw` "예정"), `not_recorded` = 수술했지만 병기 기록 없음. 선행요법을 안 받았으면 칸 없음 | `{t, n, m, edition, residual_size_mm, positive_ln, examined_ln}` (y는 빼고 범주만, M은 선행 전 값) | 해석 | `ypT1c ypN1a (2/12), 잔존 침윤암 1.4cm` → `{"t":"T1c","n":"N1a","m":"M0","residual_size_mm":14,"positive_ln":2,"examined_ln":12}` | 없음 |
| `group` [합의 예정] | 병기군 | `I`, `IA`, `IIA` … `IV` / `not_assessed` | 해석 | `Stage IIA` → `"IIA"` / `Stage X` → `"not_assessed"` | [A 결정] 아래 |
| `positive_ln_count` [합의 예정] | 양성 림프절 수 / 검사한 수 | `{positive, examined}` | 해석 | `LN 2/15 (+)` → `{"positive":2,"examined":15}` | [A 결정] 아래 |
| `disease_extent` | 진단 시 병기 범주 | `early` / `locally_advanced` / `metastatic` | 규칙 | `Stage IIB` → `"early"`, `Stage IIIA` → `"locally_advanced"`, `pT2N1M1` → `"metastatic"` | 아래 |
| `metastatic_sites` | 진단 시 원격 전이 부위 | `bone` / `liver` / `lung` / `brain` / `distant_ln` / `skin` / `other` 목록, 또는 `[Not Applicable]` / `[Not Available]` | 사전 | `간과 뼈에 다발성 전이` → `["liver","bone"]` | [A 결정] 아래 |
| `operable` [draft5] | 수술 가능 여부 | `yes` / `no` / `unknown` | 사전 | `inoperable, locally advanced` → `"no"` | 없음 (`not_recorded`) |
| `clinical_size_mm` [2026-10-22, 검토 전] | 치료 전 임상 종양 크기 (영상·촉진 최대 직경) | 숫자 (mm) | 해석 (cm → mm) | `유방 초음파상 3.2cm 종괴` → `32` | 없음 |
| `pathologic_size_mm` [2026-10-22, 검토 전] | 수술 검체 침윤암 최대 직경 (관내암 제외). 선행요법 뒤 잔존 크기는 ypTNM 결정 후 | 숫자 (mm) | 해석 (cm → mm) | `invasive tumor size 5.5 x 4.0 cm` → `55` | 없음 |

`ptnm` TCGA 규칙 [A 결정]:

- T = `gdc_ajcc_tumor_pathologic_pt`, N = `gdc_ajcc_nodes_pathologic_pn`, M = `gdc_ajcc_metastasis_pathologic_pm`, 판 = `gdc_ajcc_staging_edition`
- 값이 X(TX, NX, MX)이면 `not_assessed` (평가 안됨). 건수: TX 0, NX 10, MX 133
- TCGA 값은 병리 병기이므로 `ctnm`이 아니라 `ptnm`에 넣는다. 가상 차트에는 `pT2N1M0`처럼 p를 붙여 쓴다
- 세부 표기는 공백만 지우고 그대로 둔다 [합의 예정]: `N0 (i-)` → `N0(i-)`, `N0 (i+)` → `N0(i+)`, `N1mi`, `N0 (mol+)` → `N0(mol+)`, `cM0 (i+)` → `cM0(i+)`

`group` TCGA 규칙 [A 결정]:

- 출처: `gdc_ajcc_pathologic_tumor_stage`
- `Stage X` → `not_assessed` (평가 안됨). 크롭본 2명 (원래 13명 중 범주를 정할 수 없는 11명은 크롭 단계에서 삭제, 2026-10-13)
- `Stage` 뒤의 로마숫자와 A~C를 그대로 쓴다: `Stage IIA` → `IIA`, `Stage IIIC` → `IIIC`
- 알파벳이 없으면 로마숫자만 쓴다: `Stage I` → `I`, `Stage IV` → `IV`
- `[Discrepancy]`(6명)와 `[Not Available]`(5명)인 환자는 **정답 세트에서 행 전체를 제외한다** [A 결정]. 모든 값이 빈칸인 1명도 제외한다. 이 규칙은 2026-10-13부터 크롭 스크립트(`data/script/tcga_brca_crop.py`)가 먼저 적용한다. 크롭 단계에서 빠진 다른 환자는 tcga_mapping.md §2.2에 있다. 크롭본 985명이 곧 정답 세트다

`disease_extent` 규칙 (사용자 결정, 2026-10-13):

- 병기군 I~II → `early`(조기), III → `locally_advanced`(국소 진행성, 심평원 급여 조건의 3기), IV → `metastatic`(전이성)
- 병기군이 없거나 `not_assessed`이면 TNM으로 정한다: M1 → `metastatic`, M0·MX이면서 T4 또는 N2~N3 → `locally_advanced` (AJCC 규칙). 그 밖은 정할 수 없으므로 `not_recorded`
- TCGA 값은 크롭본의 `stage_disease_extent` 열을 그대로 쓴다 (`data/script/tcga_brca_crop.py`가 위 규칙으로 만든다)
- 진단 시 범주다. 재발 후 현재 상태는 B의 `biomarker_record.setting.disease`가 정한다

`positive_ln_count` TCGA 규칙 [A 결정]:

- positive = `gdc_lymph_nodes_examined_he_count` (이름과 달리 양성 개수), examined = `gdc_lymph_nodes_examined_count`

| 경우 | 건수 | 정답 value |
|---|---|---|
| 둘 다 있음 | 744 | `LN 2/15 (+)` → `{"positive":2,"examined":15}` |
| examined만 `[Not Available]` | 1 | `LN 4/[Not Available] (+)` → `{"positive":4,"examined":"[Not Available]"}` |
| positive만 `[Not Available]` | 29 | `{"positive":"[Not Available]","examined":15}` |
| 둘 다 `[Not Available]` [합의 예정] | 100 | 칸 전체 `status: not_recorded` |

`metastatic_sites` TCGA 규칙 [A 결정]:

1. `gdc_metastatic_tumor_indicator`를 먼저 본다.
2. `NO`이면 `[Not Applicable]` (해당 없음). 313명
3. [사용자 결정, 2026-10-15] `[Not Available]`이어도 병리 M이 `M0`·`cM0(i+)`이면 `[Not Applicable]`. 468명
4. `YES`(4명) 또는 남은 `[Not Available]`(MX·M1 98명)이면 `gdc_metastasis_site`를 쓴다 (`|`로 나눠 목록).
5. `gdc_metastasis_site`가 `[Not Available]`이면 `gdc_metastasis_site_other`를 쓴다. 이것도 `[Not Available]`이면 `[Not Available]`.
6. [합의 예정] `gdc_metastasis_site` 안의 `Other, specify` 항목은 `gdc_metastasis_site_other`의 내용으로 바꾼다 (예: `Lung|Other, specify` + `left adrenal gland` → `["lung","other: left adrenal gland"]`). 해당 4명

## 5. 수용체 (`fields.receptors`)

| 필드 | 의미 | 표준값 형태 [A 결정] | 정규화 방식 | 원문 → 정규화 예시 | TCGA 열 |
|---|---|---|---|---|---|
| `er_percent` | ER 결과 | `percent`, `range`, `allred`, `result` 중 **있는 것을 모두** 한 객체에 | 해석 + 사전 | `ER 강양성 (90-99%)` → `{"range":[90,99],"result":"positive"}` / `ER Allred 6/8 (PS 4, IS 2)` → `{"allred":{"total":6,"ps":4,"is":2}}` | `gdc_er_status_ihc_Percent_Positive`, `gdc_er_status_by_ihc` (점수 열은 쓰지 않음) |
| `pr_percent` | PR 결과 | ER과 같음. 단 `result`에 `low_positive` 없음 | 해석 + 사전 | `PR 0%` → `{"percent":0}` / `PR 5%, positive` → `{"percent":5,"result":"positive"}` | `gdc_pr_status_ihc_percent_positive`, `gdc_pr_status_by_ihc` (점수 열은 쓰지 않음) |
| `her2_ihc` | HER2 면역염색 | `score`(+`faint`: IHC 0이면서 10% 이하 세포에 희미한 불완전 막 염색 → `true`, 초저발현)와 `result`를 **있는 것 모두** | 해석 + 사전 | `c-erbB2 2+, SISH 음성` → `{"score":"2+","result":"negative"}` | `gdc_her2_ihc_score`, `gdc_her2_status_by_ihc`, `gdc_her2_fish_status` |
| `her2_ish` | HER2 ISH (FISH/SISH/DISH) | `{result, method}` | 해석 + 사전 | `SISH: not amplified` → `{"result":"not_amplified","method":"SISH"}` | `gdc_her2_fish_status` |
| `pdl1` [draft5] | PD-L1 발현 (면역염색) | `{assay, score_type, score}` | 해석 + 사전 | `PD-L1 (22C3) CPS 12` → `{"assay":"22C3","score_type":"CPS","score":12}` | 없음 (`not_recorded`). 판정은 B가 약제별로 |

`result` 표준값: `positive` / `low_positive` (저발현, **ER만**, 1–10%) / `negative` / `indeterminate` / `unknown` (HER2만)

`allred` 형태: `{total, ps, is}` 중 적힌 것만. total = ps + is (0, 2~8), ps = 비율 점수 0~5, is = 강도 점수 0~3. 차트에 총점만 있으면 `{"total": 6}`.

### ER·PR 규칙 [A 결정]

- ER·PR에는 `score` 키를 두지 않는다 (2026-10-15 결정). 점수는 Allred(`allred.total`, `ps`, `is`)로만 받는다.
- 비율·구간·Allred·판정 중 **있는 것을 모두** 한 객체에 담아 B(BM-2)에 넘긴다. 어느 하나를 고르지 않는다.
- ER과 PR 모두 같은 규칙을 쓴다. 단 `low_positive`는 ER에만 쓴다 (ASCO/CAP 2020의 Low Positive는 ER에만 정의됨) [A 결정].
- 점수는 Allred(`Allred 6/8`, `TS 6`, `PS 4`, `IS 2`)만 `allred`에 담는다. 강도만 적힌 표기(`ER 3+`, `strong`)는 `raw`에만 남긴다. 척도가 적혀 있지 않은 숫자(예: `ER score 6`)는 `raw`에만 남기고 `value`에 넣지 않는다.
- 양성·음성 판정 조건(비율, 구간, Allred)은 B의 BM-2 규칙이다. A의 제안은 [handoff_to_B.md](handoff_to_B.md) §4.

### TCGA 정답 규칙 [A 결정]

- TCGA의 ER·PR 점수 열(`gdc_er_ihc_score`, `gdc_pr_positivity_ihc_intensity_score`)은 입력이 적고(약 19%), 비율 점수와 강도 점수(예: Allred의 5점 + 3점) 중 하나만 적혀 있어 잘못 해석될 수 있다.
- 구간과 판정이 있으면 둘 다 넣는다.
- ER 판정 `Low Positive`는 `low_positive`로 바꾼다. PR에는 `Low Positive`가 없다.
- 원본 구간 `<10%`는 크롭 스크립트(`data/script/tcga_brca_crop.py`)가 판정에 따라 둘로 나눴다 (2026-10-12). 그래서 정답에는 `<10%`가 없다.
  - ER: `<10%` + Positive → 판정 `Low Positive`, 구간 `1-9%` → `{"range":[1,9],"result":"low_positive"}` (14명)
  - PR: `<10%` + Positive → 판정 `Positive` 유지, 구간 `1-9%` → `{"range":[1,9],"result":"positive"}` (49명)
  - `<10%` + Negative → 구간 `<1%` → `{"range":[0,0],"result":"negative"}` (ER 48명, PR 75명)
  - 가정: Negative를 1% 기준 음성으로 본다. 1% 기준은 2010년 ASCO/CAP 지침부터라, 2010년 이전 진단(ER 40명, PR 55명)의 음성 판정은 10% 기준이었을 수 있다. 변경 기록 `tcga_brca_merging_cropped_changes.txt`에 환자 목록이 있다.

정답 세트(874명, 2026-10-15 재집계) 건수:

| 경우 | ER | PR | 정답 value |
|---|---|---|---|
| 구간 + 판정 | 422 | 391 | `{"range":[90,99],"result":"positive"}` |
| 판정만 | 452 | 483 | `{"result":"positive"}` |
| 판정 `[Not Evaluated]` | 0 | 0 | `status: not_done` (ER·PR 미시행 환자는 정답 세트에서 모두 뺐다, 2026-10-15) |

판정값 분포: ER positive 668 / negative 191 / low_positive 14 / indeterminate 1, PR positive 595 (이 중 1-9% 49) / negative 279. PR indeterminate 4명, ER·PR·HER2 모두 미시행 43명, ER 또는 PR이 미시행인 2명(TCGA-C8-A9FZ, E9-A1N8, HR 평가 불가), HER2 판정 불가 62명(IHC 2+인데 ISH가 equivocal·미시행·기록 없음 21명, IHC 점수 없이 판정이 Indeterminate·미시행·기록 없음이고 ISH도 없는 41명)은 정답 세트에서 뺐다 (2026-10-15).

### HER2 IHC 규칙 [A 결정]

1. `score`(0, 1+, 2+, 3+)와 `result`(판정)가 둘 다 있으면 둘 다 넣는다.
2. 판정이 `Equivocal`인데 점수가 없으면 `score: "2+"`를 채운다 (Equivocal의 정의가 IHC 2+). 5명 (2026-10-15 삭제 후)
3. `score`가 `2+`이거나 `result`가 `Equivocal`이면 `gdc_her2_fish_status`를 확인한다.
   - FISH `Negative` → `result`를 `negative`로
   - FISH `Positive` → `result`를 `positive`로
   - FISH가 Positive·Negative가 아니고 `result`가 `Equivocal`이면 → `result`를 `unknown`으로
4. `gdc_her2_copy_number`, `gdc_cent17_copy_number`, `gdc_her2_cent17_ratio`는 넣지 않는다.

TCGA 건수 (score 2+ 또는 Equivocal):

| score | 원래 판정 | FISH | 정답 value | 건수 |
|---|---|---|---|---|
| 2+ | Equivocal | Negative | `{"score":"2+","result":"negative"}` | 118 |
| 2+ | Equivocal | Positive | `{"score":"2+","result":"positive"}` | 17 |
| 2+ | Positive | Negative | `{"score":"2+","result":"negative"}` (판정이 바뀜) | 6 |
| 2+ | Positive | Positive | `{"score":"2+","result":"positive"}` | 14 |
| 2+ | Positive | [Not Evaluated] / [Not Available] | `{"score":"2+","result":"positive"}` (ISH 없어 판정 유지, B는 positive + ISH 검사 권고) | 4 / 1 |
| 2+ | Indeterminate | Negative / Positive | `result`를 `negative` / `positive`로 | 2 / 2 |
| 2+ | Negative | Negative | `{"score":"2+","result":"negative"}` | 1 |
| 1+ | Equivocal | Negative | `{"score":"1+","result":"negative"}` | 2 |
| 3+ | Equivocal | Negative | `{"score":"3+","result":"negative"}` (점수와 판정이 어긋남) | 1 |
| 없음 → 2+ | Equivocal | Negative | `{"score":"2+","result":"negative"}` | 5 |

건수는 정답 세트(874명) 기준이다 (2026-10-15 재집계). IHC 2+(점수 없는 Equivocal 포함)인데 FISH가 Positive·Negative가 아니고 판정도 Positive·Negative가 아닌 환자 21명은 정답 세트에서 뺐다 (사용자 결정, 2026-10-15). 판정 Positive인 5명은 뺐다가 다시 넣었다. 그래서 정답에 `result: unknown`인 2+는 없다.

참고:

- `score 2+`와 `result negative`가 함께 있으면 B는 HER2 저발현으로 판정할 수 있다. 그래서 B는 `result`보다 `score`를 먼저 읽어야 한다.
- `3+`인데 판정이 negative가 되는 1명은 원자료끼리 어긋난 경우다. 가상 차트 생성 시 확인한다.

### 재발 병소 재생검 수용체 → `value`, 원발 값 → `history[]` [A 결정]

재생검(재발 병소) 결과로 평가하고 처방하므로, 재생검 결과를 `value`로 쓴다. PROJECT.md IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.

**TCGA 정답 예외:** TCGA 정답은 진단 시(원발 종양) 병기·수용체만 쓴다. 재발 병소 수용체(`gdc_nte_*`)는 정답에 쓰지 않는다 (크롭본 4명 중 재발 기록과 맞는 환자가 1명뿐, 검사 부위·날짜도 없음). 재발 병소 결과 우선 규칙(IN-4)은 가상 차트와 실제 차트 등 다른 입력에만 적용한다 (사용자 결정, 2026-10-14). 아래 규칙은 가상 차트와 실제 차트에 적용한다.

- 재발 병소 수용체(`gdc_nte_er_status`, `gdc_nte_pr_status_by_ihc`, `gdc_nte_her2_status` 등)가 있는 환자는 크롭본에서 4명이다 (ER 4, PR 3, HER2 2). 그중 재발 기록과 맞는 환자는 1명이라 TCGA 정답에는 쓰지 않는다.
- 재발 병소 값을 `value`로 쓴다. `specimen`은 `metastasis`. 변환 규칙은 원발 값과 같다 (score 제외, `<10%` 구분, HER2 FISH 보정).
- 원발 조직 값은 `history[]`로 옮기고 `"superseded_reason": "recurrence"`로 재발 때문에 대체되었음을 적는다. `specimen`은 `primary`.
- 재발 병소 값이 없는 마커는 원발 값을 그대로 `value`로 둔다. 예: 재발 병소에서 ER만 검사했으면 PR·HER2는 원발 값.

예 (ER):

```json
"er_percent": {
  "status": "present",
  "value": {"result": "negative"},
  "specimen": "metastasis",
  "raw": "재발 병소 ER Negative",
  "history": [
    {"status": "present", "value": {"range": [90, 99], "result": "positive"}, "specimen": "primary",
     "raw": "ER Positive (90-99%)", "superseded_reason": "recurrence"}
  ]
}
```

## 6. 증식 (`fields.proliferation`)

| 필드 | 의미 | 표준값 형태 [제안] | 정규화 방식 | 원문 → 정규화 예시 | TCGA 열 |
|---|---|---|---|---|---|
| `ki67_percent` | Ki-67 지수 | `{percent}` / `{range}` / `{result}` | 해석 + 사전 | `Ki-67 labeling index: 30%` → `{"percent":30}` | 없음 (합성) |

## 7. 환자 (`fields.patient`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 열 |
|---|---|---|---|---|---|
| `gender` [제안, A 결정] | 성별 | `FEMALE` / `MALE` | 사전 | `F/62` → `"FEMALE"` | `gdc_gender` (정리본은 FEMALE 874명) |
| `age` | 진단 시 나이 | 정수 | 해석 | `F/62` → `62` | `gdc_age_at_diagnosis` |
| `menopausal_status` | 폐경 여부 | `premenopausal` / `perimenopausal` / `postmenopausal` / `indeterminate` | 사전 | `폐경 후 상태` → `"postmenopausal"` | `gdc_menopause_status` |
| `ecog` | 전신 수행 상태 | `0`~`4` | 해석 | `ECOG PS 1` → `1` | 없음 (합성) |
| `menopausal_basis` [draft5] | 폐경 판정 근거 | `age_amenorrhea` / `fsh` / `oophorectomy` / `ovarian_radiation` / `hysterectomy` / `unknown` (`ovarian_radiation`·`hysterectomy`는 2026-10-22 추가, 공고 p.48 원문 대조 전) | 사전 | `양측 난소절제술 후` → `"oophorectomy"`, `자궁적출술 후, FSH 68` → `"hysterectomy"` (FSH 값은 `raw`) | 없음 (`not_recorded`) |
| `cardiac_history` [2026-10-22, 검토 전] | 심장 위험요소·병력 (병명은 `raw`) | `yes` / `no` | 사전 | `HTN, 협심증으로 스텐트 시술` → `"yes"` | 없음 |
| `lvef_percent` [2026-10-22, 검토 전] | 좌심실 박출률 | 숫자 (%) | 해석 | `Echo: LVEF 62%` → `62` | 없음 |
| `mediastinal_radiation` [2026-10-22, 검토 전] | 종격동 방사선 치료 이력 | `yes` / `no` | 사전 | `호지킨 림프종으로 종격동 RT (2001)` → `"yes"` | 없음 |
| `visceral_crisis` [2026-10-22, 검토 전] | 장기 위기. 의사가 적은 판단만 옮김 | `yes` / `no` | 사전 | `visceral crisis 소견` → `"yes"` | 없음 |
| `comorbidities` [2026-10-22, 검토 전] | 치료 선택에 영향을 주는 동반질환 | 원문 표기 목록 | 그대로 | `간경화 Child B, CKD 4기` → `["간경화 Child B","CKD 4기"]` | 없음 |
| `height_cm`, `weight_kg` [2026-10-22, 검토 전] | 키, 몸무게 (체표면적 → anthracycline 누적 용량 mg/m²) | 숫자 | 해석 | `Ht 158cm / Wt 55.5kg` → `158`, `55.5` | 없음 |

- 성별은 범위 외 판정(남성 유방암)에 쓰인다
- 폐경 여부는 적힌 것만 옮긴다. 마지막 생리일(LMP)만 있으면 계산하지 않고 `raw`에 남긴다
- `KPS 90`처럼 다른 척도는 ECOG로 바꾸지 않는다

## 8. 치료 이력 (`fields.treatment_history[]`)

항목 하나가 투약 기록 하나다. 원본 한 기록에 약이 여러 개면(AC 등) 한 항목에 여러 약이 들어간다. 여러 기록을 한 요법으로 묶고 차수를 매기는 일은 A가 변환할 때 한다 (`src/input/script/rules.py`, handoff_to_B.md §6.2) [2026-10-16 변경, draft6].

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 정답 규칙 |
|---|---|---|---|---|---|
| `drugs` | 약제 목록 | 일반명 소문자 목록 | 사전 (`drug_names.csv` + 요법 약어 사전) | `AC #4` → `["doxorubicin","cyclophosphamide"]` | `drug_timeline` 성분명 |
| `setting` | 치료 단계 | `neoadjuvant` / `adjuvant` / `metastatic` / `unknown` | 사전 | `수술 전 항암` → `"neoadjuvant"` | 유도 규칙 (tcga_mapping.md §3.6) |
| `start_date` | 시작일 | `YYYY-MM-DD` | 해석 | `'25.1.10부터` → `"2025-01-10"` | [A 결정] TCGA에는 날짜가 없으므로 `null` |
| `end_date` | 종료일 | `YYYY-MM-DD` 또는 `null` | 해석 | `2026.6.20 중단` → `"2026-06-20"` | [A 결정] TCGA에는 날짜가 없으므로 `null` |
| `start_day`, `end_day` [draft5] | 시작일·종료일 (진단일 = 0) | 정수 또는 `null` | 해석 (날짜 → 진단일 기준 일수) | 진단 2024-03-05, 시작 2024-04-04 → `30` | 크롭본 `drug_start_days`, `drug_end_days` |
| `duration_days` [제안, A 결정] | 투여일 (일) | 정수 또는 `null` | 해석 | `2025.1.10 ~ 2025.3.10` → `59` | `end_day − start_day` |
| `cycles` [draft5] | 주기 수와 주기 길이 | `{value, basis, interval_days, interval_basis}` 또는 `null` | 해석 | `AC q3w #4` → `{"value":4,"basis":"recorded","interval_days":21,"interval_basis":"recorded"}` | tcga_mapping.md §3.6 |
| `progression_day` [draft5] | 진행일 (진단일 = 0) | 정수 또는 `null` | 해석 | `2026.3 CT상 PD` → 진단일 기준 일수 | 없음 (`null`) |
| `doses[]` [2026-10-23, 검토 전] | 약별 용량. `drugs`의 약마다 하나. 급여 조건이 약을 골라 1회·누적 용량을 볼 때 (cisplatin, anthracycline 등) | `{drug, per_admin, total, basis, source}`. 용량은 `{value, unit}` 또는 `"No value"`, `basis`는 `recorded` / `estimated`(1회 × 주기) | 해석 | `DP: docetaxel 75mg/m2 + cisplatin 75mg/m2 q3w #4` → `[{"drug":"cisplatin","per_admin":{"value":75,"unit":"mg/m2"},"total":{"value":300,"unit":"mg/m2"},"basis":"estimated"}, …]` | 넣지 않음 (anthracycline은 `anthracycline_drug_dose`) |
| `ongoing` [2026-10-22, 검토 전] | 기준일에 투약 중인지. `end_day` null만으로는 "투약 중"과 "종료 기록 없음"을 가를 수 없어 둔다 | `true` / `false` / `null`(모름) | 사전 | `현재 키스칼리·페마라 복용 중` → `true` (`end_day`는 `null`) | 없음 (`null`) |
| `stop_reason` | 중단 사유 | `progression` / `toxicity` / `completed` / `planned_switch` / `maintenance` / `other` | 사전 | `PD로 중단` → `"progression"` | 없음 |
| `best_response` | 최선 반응 | `CR` / `PR` / `SD` / `PD` / `unknown` | 사전 | `완전관해` → `"CR"` | 괄호 안 반응 |
| `line`, `endocrine_line`, `chemo_line` [draft6] | 전이 후 전체 차수, 고식적 내분비 차수, 고식적 항암 차수 (간주 규칙 없음) | 정수 또는 `null` | 계산 (`lines.py`) | 전이 후 letrozole → paclitaxel → `1/1/null`, `2/null/1` | `lines.py` 계산 (tcga_mapping.md §3.6) |
| `source` | 원문 근거 | 공통 틀과 같음 | — | `{"doc_id":"D3","quote":"AI + palbociclib, PD"}` | 가상 차트 생성 시 채움 |

`duration_days` TCGA 규칙 [A 결정]:

| 시작일·종료일 (`drug_start_days`, `drug_end_days`) | 건수 | 정답 |
|---|---|---|
| 둘 다 있음 (예: 63, 126) | 1,507 | `126 − 63 = 63` |
| 종료 모름 | 441 | `null` |
| 시작 모름 (그중 종료만 있는 31건) | 84 | `null` |

- 투약 기록 2,033건 기준 (성분명 `unknown` 제외).
- [변경, 2026-10-15, draft5] 상대 일수는 `start_day`·`end_day`로 정답에 넣는다. 이전 결정("출력에 넣지 않음")은 폐기.

## 9. 선행요법 반응, 재발, 유전자 보고서

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 출처 |
|---|---|---|---|---|---|
| `neoadjuvant_response.pcr` | 병리적 완전관해 | `yes` / `no` | 사전 | `pCR 달성` → `"yes"` | 없음 (합성) |
| `neoadjuvant_response.rcb` | 잔존암 부담 등급 | `RCB-0` / `RCB-I` / `RCB-II` / `RCB-III` | 사전 + 해석 | `RCB class II (index 2.1)` → `"RCB-II"` | 없음 (합성) |
| `recurrence.recurrence_date` | 재발일 | 날짜 | 해석 | `2026년 6월 간 전이로 재발` → `"2026-06"` [제안: 부분 날짜] | `not_recorded` (전이 기준일은 `metastasis_day`) |
| `recurrence.adjuvant_endocrine_end_date` | 보조 내분비요법 종료일 | 날짜 | 해석 | `타목시펜 5년 복용 후 2023.3 종료` → `"2023-03"` | `not_recorded` (B가 `end_day`로 계산) |
| `recurrence.status`, `metastatic_sites`, `metastasis_day`, `surgery`, `surgery_intent`, `later_distant` [draft5] | 재발 상태, 재발 전이 부위, 전이 기준일, 재발 후 수술 | handoff_to_B.md §3.1 | 사전 + 해석 | `2026.6 간 전이 재발` → `status: distant`, `metastatic_sites: ["liver"]` | tcga_mapping.md §3.7 |
| `recurrence.recurrence_day` [draft6] | 첫 재발일 (국소·원격, 진단일 = 0). 진단 시 IV기는 넣지 않음 | 정수 | 해석 | `2026.6 흉벽 재발` → 진단일 기준 일수 | tcga_mapping.md §3.7 |
| `deemed_lines[]` [draft6] | 심평원 차수 간주 규칙 4개의 충족 여부 | `{rule_id, category, status, basis, regimen_refs, gap_days, notice_page}` | 계산 (`lines.py`) | 보조 AC → paclitaxel 후 전이 → `DEEM-ANTHRA-TAXANE: met` | tcga_mapping.md §3.6b |
| `anthracycline_drug_dose` [draft5] | anthracycline 투여 여부와 약별 용량 | `{administered, drugs[]}` | 해석 | `doxorubicin 60 mg/m2 #4` → `{"drug":"doxorubicin","dose_per_admin":{"value":60,"unit":"mg/m2"}, …}` | tcga_mapping.md §3.7a |
| `molecular.mutations.{유전자}` [draft5] | 유전자별 변이 (ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2) | `{status, result, variants[], specimen}` | 해석 | `PIK3CA H1047R, VAF 31%` → `{"status":"present","result":"detected","variants":[…]}` | `mut_*` (tcga_mapping.md §3.8) |
| `imaging_findings[]` [2026-10-22, 검토 전] | 영상 소견 (골전이 영상 입증, M 병기 근거) | `{modality, day, date, sites[], certainty, source}` | 해석 + 사전 | `Bone scan: 척추·골반 다발성 골전이` → `{"modality":"bone_scan","sites":["bone"],"certainty":"confirmed"}` | 없음 |
| `molecular.germline.{BRCA1, BRCA2, PALB2}` [2026-10-22, 검토 전] | 생식세포 검사 (혈액·타액) 결과. `mutations`는 종양 조직·cfDNA. 한 유전자에 두 결과가 있을 수 있어 칸을 나눈다 | `mutations`와 같은 `{status, result, variants[]}` | 해석 | `혈액 BRCA1/2 유전자 검사: 병원성 변이 없음` → `BRCA1`·`BRCA2` `{"status":"present","result":"not_detected","variants":[]}` | 없음 (칸을 두지 않음. B는 `mutations`의 BRCA를 gBRCA로 가정) |
| `genomic_reports[].specimen` | 검체 | `primary` / `metastasis` / `cfDNA` / `unknown` | 사전 | `혈장 cfDNA NGS` → `"cfDNA"` | 원발(01) 고정 |
| `genomic_reports[].report_date` | 보고일 | `YYYY-MM-DD` | 해석 | `보고일 2026-07-01` → `"2026-07-01"` | `null` |
| `genomic_reports[].raw_text` | 보고서 원문 | 문자열 | **그대로** | `ESR1 p.Y537S detected, VAF 4.2%` → 그대로 | `mut_*`, `cna_*`로 가상 보고서 |

- 유전자 보고서(`genomic_reports`)는 검체와 날짜만 정리하고 원문은 손대지 않는다. TCGA 정답은 유전자별 값을 `molecular.mutations`에도 넣는다. 변이의 의미 판정은 B의 BM-2·BM-3
- pCR은 명시된 경우만 옮긴다. `ypT0 ypN0`처럼 병기만 있으면 병기만 저장한다

## 10. B와 합의할 항목

A가 받아들인 제안과 A 결정이다. 2026-10-12에 `schemas/patient_state.json` 0.1-draft3로 모두 반영했다. B 검토 후 `0.1`로 확정한다.

| 항목 | 상태 |
|---|---|
| 수용체 `value`: `percent`/`range`/`allred`/`result` 중 있는 것을 모두 한 객체에 (ER·PR `score`는 2026-10-15 삭제). `result`에 `low_positive` 추가 (ER만) | A 결정, 스키마 반영 (0.1-draft3) |
| `allred`를 `{total, ps, is}` 객체로 | A 결정, 스키마 반영 (0.1-draft3) |
| ER·PR·HER2 판정 조건 (BM-2) | A 제안 → B 결정. handoff_to_B.md §4 |
| ER·PR `score` 키 삭제 (Allred 총점·강도와 중복) | 2026-10-15 결정, 스키마 반영 |
| HER2 IHC `{score, faint}` + `{result}` 동시 표기, ISH로 `result` 보정 | A 결정. B는 score를 먼저 읽는다 |
| `her2_ish`는 `{result, method}`만 (복제수·비율 제외) | A 결정 |
| `specimen`, `history[]`(`superseded_reason`: `recurrence` / `newer_result`) 추가 | 스키마 반영 (0.1-draft3) |
| 재발 병소 재생검 결과를 `value`로, 원발 값을 `history[]`로 (IN-4와 같음) | A 결정. 가상 차트·실제 차트에만 적용, TCGA 정답은 원발 값만 (사용자 결정, 2026-10-14) |
| ER·PR 원본 구간 `<10%`를 `1-9%` / `<1%`로 나눔 (ER만 Low Positive). Negative는 1% 기준 음성으로 가정 | A 결정 |
| `stage.group`, `stage.positive_ln_count` 추가 | 스키마 반영 (0.1-draft3) |
| `patient.gender` 추가 | 스키마 반영 (0.1-draft3) |
| `treatment_history[].duration_days` 추가 | 스키마 반영 (0.1-draft3) |
| 특수 표기값 `not_assessed`, `[Not Available]`, `[Not Applicable]`을 `value`에 허용 | A 결정 (평가 안됨·불가 통합) |
| `stop_reason` 표준값 목록 | 스키마 반영 (0.1-draft3) |
| 부분 날짜(`YYYY-MM`, `YYYY`) 허용 | 스키마 반영 (0.1-draft3) |
| `stage.disease_extent` 추가 (I~II 조기, III 국소 진행성, IV 전이성) | 사용자 결정 (2026-10-13), 스키마 반영 (0.1-draft4) |
| TCGA 정답의 모든 날짜를 비움 (가상 날짜를 만들지 않음) | A 결정 (2026-10-12) |
| 상대 일수(진단일 = 0) `start_day`·`end_day`·`metastasis_day`를 정답에 넣음. 날짜 칸은 계속 비움 | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `treatment_history[].cycles` (`value`, `basis`, `interval_days`, `interval_basis`), `progression_day`, `stop_reason`에 `planned_switch`·`maintenance` | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `anthracycline_drug_dose` (투여 여부, 약별 1회 용량·주기·총 투여량. 범위 용량은 최대값, 값이 없으면 `No value`) | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `recurrence.status`, `metastatic_sites`, `metastasis_day`, `surgery`, `surgery_intent`, `later_distant` | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `receptors.pdl1` (발현: 검사법, 점수 종류, 점수. 판정은 B) | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `molecular.mutations` 유전자별 (ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2): 변이 있음 / 변이 없음 / 미시행 | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| `stage.operable`, `patient.menopausal_basis` (TCGA에 없음, 가상 차트용) | 사용자 결정 (2026-10-15), 스키마 반영 (0.1-draft5) |
| TCGA 정답에서 BRCA1/2 체세포 결과를 gBRCA 측정으로 가정. B가 positive / negative / vus 판정 | 협의 완료 (2026-10-15). handoff_to_B.md §4.7 |
| 차수(line)는 정답에 넣지 않고 B가 `start_day`·`metastasis_day`로 판단 | 협의 완료 (2026-10-15). handoff_to_B.md §6.2 |
| 진단 시 M0(`cM0(i+)` 포함)이면 `stage.metastatic_sites`를 `[Not Applicable]`로 (원본 전이 여부가 `[Not Available]`이어도) | 사용자 결정 (2026-10-15). tcga_mapping.md §3.2 |
| 점수 없는 HER2 Equivocal에 `score: "2+"` 채우기 (2026-10-15 삭제 후 5명) | A 결정 |
| `treatment_history`는 투약 기록 하나 = 항목 하나. 같은 날 시작한 별도 기록·중복 기록을 묶지 않음 (요법 묶음은 B) | 사용자 결정 (2026-10-15) |
| ER 판정: Allred 총점 우선 (0~2 음성, 3~4 저발현, 5는 비율로 가름, 6~8 양성). HER2 `faint` = IHC 0 + 10% 이하 세포의 희미한 불완전 막 염색 | 사용자 결정 (2026-10-15). handoff_to_B.md §4.1·§4.4 |

draft5 필드의 TCGA 변환 규칙은 [tcga_mapping.md](tcga_mapping.md) §3.6·§3.7·§3.7a·§3.8에 있다.
