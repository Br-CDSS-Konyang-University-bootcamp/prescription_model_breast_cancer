# patient_state 필드 정리와 정규화 예시

> 담당 A · 2026-10-12 (2026-10-13 `stage.disease_extent` 추가) · 기준 스키마: `schemas/patient_state.json` (0.1-draft4)

입력 모듈(A)이 만드는 `patient_state`의 필드, 표준값 형태, 정규화 방식, 예시, TCGA 정답 생성 규칙을 정리한다. TCGA 열 변환의 세부 규칙은 [tcga_mapping.md](tcga_mapping.md)에 있다.

표기:

- 정규화 방식: **사전** = `data/dictionaries/field_vocab.csv` 조회 · **해석** = 정규식·파싱 함수 · **그대로** = 원문 보존
- **[제안]**: 현재 스키마 초안에 없거나 형태가 다른 항목. B와 합의 후 스키마에 반영한다
- **[A 결정]**: 담당 A가 정한 TCGA 정답 생성 규칙 (2026-10-12)
- **[합의 예정]**: A가 받아들인 제안. 스키마 반영 전에 B와 확인한다

A는 원칙적으로 표기만 정리한다. 예외: HER2 IHC의 `result`는 ISH 결과로 보정한다 (§5, A 결정). 양성·음성·저발현 같은 최종 판정은 B가 한다.

## 1. 최상위 구조

| 항목 | 의미 | 형태 | 정규화 방식 | 원문 → 정규화 예시 |
|---|---|---|---|---|
| `schema_version` | 스키마 버전 | 문자열 | 고정 | → `"0.1-draft"` |
| `patient_ref` | 가명 ID | 문자열 | 비식별화(IN-0). 실제 값은 내부 대응표에만 | `홍길동 (등록번호 12345678)` → `"VC-0001"` |
| `created_at` | 생성 시각 | ISO 8601 | 자동 | → `"2026-10-12T09:00:00+09:00"` |
| `documents[]` | 문서 목록 (IN-1) | `{doc_id, doc_type, doc_date}` | 해석 + 사전 | `[병리결과보고서] 2024.03.05` → `{"doc_id":"D1","doc_type":"pathology","doc_date":"2024-03-05"}` |
| `conflicts[]` | 같은 시점에 값이 다른 경우 (IN-5) | `{field, candidates[], note}` | 규칙 | `암 3기` vs `cT2N1M0` → `{"field":"stage.group","candidates":[…III…, …IIB…],"note":"적힌 병기와 TNM 계산 병기가 다름"}` |

## 2. 추출값 공통 틀

아래 3~9의 모든 칸은 이 틀에 담긴다.

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
| `[Not Applicable]` (해당 없음) | 해당 사항 없음 | 진단 시 전이 없음(NO)일 때 전이 부위 |

평가 안됨·평가 불가는 `not_assessed` 하나로 통합한다 [A 결정].

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
| `gdc_histological_type` = Infiltrating Ductal Carcinoma | `IDC` | 758 |
| `gdc_histological_type` = Infiltrating Lobular Carcinoma | `ILC` | 200 |
| `gdc_histological_type` = Mucinous Carcinoma | `mucinous` | 17 |
| `gdc_histological_type` = Metaplastic Carcinoma | `metaplastic` | 9 |
| `gdc_histological_type` = Infiltrating Carcinoma NOS | `invasive_NOS` | 0 (크롭 단계에서 삭제) |
| ONCOTREE = `IMMC` | `mucinous` | 1번 대상 행 중 0 |
| ONCOTREE = `BRCNOS` | `invasive_NOS` | Other 43 + Mixed 28 = 71 |
| ONCOTREE = `IDC` | `IDC` | Medullary 6 (WHO 2019에서 수질암은 IDC/NST의 한 형태) |

Mixed·Other의 자유 기재(`gdc_histologic_diagnosis_other`, 예: "infiltrating ductal and mucinous")는 `raw`에 남긴다.

## 4. 병기 (`fields.stage`)

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 정답 규칙 |
|---|---|---|---|---|---|
| `ctnm` | 임상 TNM | `{t, n, m}` | 해석 | `cT2N1M0` → `{"t":"T2","n":"N1","m":"M0"}` | 없음 (TCGA는 병리 병기만 있음) |
| `ptnm` | 병리 TNM | `{t, n, m, edition}` | 해석 | `pT2 pNX M0, AJCC 7th` → `{"t":"T2","n":"not_assessed","m":"M0","edition":"7th"}` | [A 결정] 아래 |
| `group` [합의 예정] | 병기군 | `I`, `IA`, `IIA` … `IV` / `not_assessed` | 해석 | `Stage IIA` → `"IIA"` / `Stage X` → `"not_assessed"` | [A 결정] 아래 |
| `positive_ln_count` [합의 예정] | 양성 림프절 수 / 검사한 수 | `{positive, examined}` | 해석 | `LN 2/15 (+)` → `{"positive":2,"examined":15}` | [A 결정] 아래 |
| `disease_extent` | 진단 시 병기 범주 | `early` / `locally_advanced` / `metastatic` | 규칙 | `Stage IIB` → `"early"`, `Stage IIIA` → `"locally_advanced"`, `pT2N1M1` → `"metastatic"` | 아래 |
| `metastatic_sites` | 진단 시 원격 전이 부위 | `bone` / `liver` / `lung` / `brain` / `distant_ln` / `skin` / `other` 목록, 또는 `[Not Applicable]` | 사전 | `간과 뼈에 다발성 전이` → `["liver","bone"]` | [A 결정] 아래 |

`ptnm` TCGA 규칙 [A 결정]:

- T = `gdc_ajcc_tumor_pathologic_pt`, N = `gdc_ajcc_nodes_pathologic_pn`, M = `gdc_ajcc_metastasis_pathologic_pm`, 판 = `gdc_ajcc_staging_edition`
- 값이 X(TX, NX, MX)이면 `not_assessed` (평가 안됨). 건수: TX 0, NX 11, MX 151
- TCGA 값은 병리 병기이므로 `ctnm`이 아니라 `ptnm`에 넣는다. 가상 차트에는 `pT2N1M0`처럼 p를 붙여 쓴다
- 세부 표기는 공백만 지우고 그대로 둔다 [합의 예정]: `N0 (i-)` → `N0(i-)`, `N0 (i+)` → `N0(i+)`, `N1mi`, `N0 (mol+)` → `N0(mol+)`, `cM0 (i+)` → `cM0(i+)`

`group` TCGA 규칙 [A 결정]:

- 출처: `gdc_ajcc_pathologic_tumor_stage`
- `Stage X` → `not_assessed` (평가 안됨). 크롭본 2명 (원래 13명 중 범주를 정할 수 없는 11명은 크롭 단계에서 삭제, 2026-10-13)
- `Stage` 뒤의 로마숫자와 A~C를 그대로 쓴다: `Stage IIA` → `IIA`, `Stage IIIC` → `IIIC`
- 알파벳이 없으면 로마숫자만 쓴다: `Stage I` → `I`, `Stage IV` → `IV`
- `[Discrepancy]`(6명)와 `[Not Available]`(5명)인 환자는 **정답 세트에서 행 전체를 제외한다** [A 결정]. 모든 값이 빈칸인 1명도 제외한다. 이 규칙은 2026-10-13부터 크롭 스크립트(`data/script/tcga_brca_crop.py`)가 먼저 적용한다. 크롭본 1,061명이 곧 정답 세트다

`disease_extent` 규칙 (사용자 결정, 2026-10-13):

- 병기군 I~II → `early`(조기), III → `locally_advanced`(국소 진행성, 심평원 급여 조건의 3기), IV → `metastatic`(전이성)
- 병기군이 없거나 `not_assessed`이면 TNM으로 정한다: M1 → `metastatic`, M0·MX이면서 T4 또는 N2~N3 → `locally_advanced` (AJCC 규칙). 그 밖은 정할 수 없으므로 `not_recorded`
- TCGA 값은 크롭본의 `stage_disease_extent` 열을 그대로 쓴다 (`data/script/tcga_brca_crop.py`가 위 규칙으로 만든다)
- 진단 시 범주다. 재발 후 현재 상태는 B의 `biomarker_record.setting.disease`가 정한다

`positive_ln_count` TCGA 규칙 [A 결정]:

- positive = `gdc_lymph_nodes_examined_he_count` (이름과 달리 양성 개수), examined = `gdc_lymph_nodes_examined_count`

| 경우 | 건수 | 정답 value |
|---|---|---|
| 둘 다 있음 | 905 | `LN 2/15 (+)` → `{"positive":2,"examined":15}` |
| examined만 `[Not Available]` | 1 | `LN 4/[Not Available] (+)` → `{"positive":4,"examined":"[Not Available]"}` |
| positive만 `[Not Available]` | 39 | `{"positive":"[Not Available]","examined":15}` |
| 둘 다 `[Not Available]` [합의 예정] | 116 | 칸 전체 `status: not_recorded` |

`metastatic_sites` TCGA 규칙 [A 결정]:

1. `gdc_metastatic_tumor_indicator`를 먼저 본다.
2. `NO`이면 `[Not Applicable]` (해당 없음). 375명
3. `YES`(12명) 또는 `[Not Available]`(674명)이면 `gdc_metastasis_site`를 쓴다 (`|`로 나눠 목록).
4. `gdc_metastasis_site`가 `[Not Available]`이면 `gdc_metastasis_site_other`를 쓴다. 이것도 `[Not Available]`이면 `[Not Available]`.
5. [합의 예정] `gdc_metastasis_site` 안의 `Other, specify` 항목은 `gdc_metastasis_site_other`의 내용으로 바꾼다 (예: `Lung|Other, specify` + `left adrenal gland` → `["lung","other: left adrenal gland"]`). 해당 6명

## 5. 수용체 (`fields.receptors`)

| 필드 | 의미 | 표준값 형태 [A 결정] | 정규화 방식 | 원문 → 정규화 예시 | TCGA 열 |
|---|---|---|---|---|---|
| `er_percent` | ER 결과 | `percent`, `range`, `score`, `allred`, `result` 중 **있는 것을 모두** 한 객체에 | 해석 + 사전 | `ER 강양성 (90-99%), 3+` → `{"range":[90,99],"score":"3+","result":"positive"}` / `ER Allred 6/8 (PS 4, IS 2)` → `{"allred":{"total":6,"ps":4,"is":2}}` | `gdc_er_status_ihc_Percent_Positive`, `gdc_er_status_by_ihc` (점수 열은 쓰지 않음) |
| `pr_percent` | PR 결과 | ER과 같음. 단 `result`에 `low_positive` 없음 | 해석 + 사전 | `PR 0%` → `{"percent":0}` / `PR 5%, positive` → `{"percent":5,"result":"positive"}` | `gdc_pr_status_ihc_percent_positive`, `gdc_pr_status_by_ihc` (점수 열은 쓰지 않음) |
| `her2_ihc` | HER2 면역염색 | `score`(+`faint`)와 `result`를 **있는 것 모두** | 해석 + 사전 | `c-erbB2 2+, SISH 음성` → `{"score":"2+","result":"negative"}` | `gdc_her2_ihc_score`, `gdc_her2_status_by_ihc`, `gdc_her2_fish_status` |
| `her2_ish` | HER2 ISH (FISH/SISH/DISH) | `{result, method}` | 해석 + 사전 | `SISH: not amplified` → `{"result":"not_amplified","method":"SISH"}` | `gdc_her2_fish_status` |

`result` 표준값: `positive` / `low_positive` (저발현, **ER만**, 1–10%) / `negative` / `indeterminate` / `unknown` (HER2만)

`allred` 형태: `{total, ps, is}` 중 적힌 것만. total = ps + is (0, 2~8), ps = 비율 점수 0~5, is = 강도 점수 0~3. 차트에 총점만 있으면 `{"total": 6}`.

### ER·PR 규칙 [A 결정]

- 차트에서는 비율(%) 대신 점수(score)로 적힐 수 있어서 `score` 키를 둔다.
- 비율·구간·점수·Allred·판정 중 **있는 것을 모두** 한 객체에 담아 B(BM-2)에 넘긴다. 어느 하나를 고르지 않는다.
- ER과 PR 모두 같은 규칙을 쓴다. 단 `low_positive`는 ER에만 쓴다 (ASCO/CAP 2020의 Low Positive는 ER에만 정의됨) [A 결정].
- 점수는 척도를 구분해서 저장한다: 강도 점수(`ER 3+`, `strong`) → `score`, Allred(`Allred 6/8`, `TS 6`, `PS 4`, `IS 2`) → `allred`. 척도가 적혀 있지 않은 숫자(예: `ER score 6`)는 `raw`에만 남기고 `value`에 넣지 않는다.
- 양성·음성 판정 조건(비율, 구간, Allred)은 B의 BM-2 규칙이다. A의 제안은 [handoff_to_B.md](handoff_to_B.md) §4.

### TCGA 정답 규칙 [A 결정]

- **TCGA 정답에는 `score`를 넣지 않는다.** TCGA의 ER·PR 점수 열(`gdc_er_ihc_score`, `gdc_pr_positivity_ihc_intensity_score`)은 입력이 적고(약 19%), 비율 점수와 강도 점수(예: Allred의 5점 + 3점) 중 하나만 적혀 있어 잘못 해석될 수 있다.
- 구간과 판정이 있으면 둘 다 넣는다.
- ER 판정 `Low Positive`는 `low_positive`로 바꾼다. PR에는 `Low Positive`가 없다.
- 원본 구간 `<10%`는 크롭 스크립트(`data/script/tcga_brca_crop.py`)가 판정에 따라 둘로 나눴다 (2026-10-12). 그래서 정답에는 `<10%`가 없다.
  - ER: `<10%` + Positive → 판정 `Low Positive`, 구간 `1-9%` → `{"range":[1,9],"result":"low_positive"}` (17명)
  - PR: `<10%` + Positive → 판정 `Positive` 유지, 구간 `1-9%` → `{"range":[1,9],"result":"positive"}` (53명)
  - `<10%` + Negative → 구간 `<1%` → `{"range":[0,0],"result":"negative"}` (ER 53명, PR 84명)
  - 가정: Negative를 1% 기준 음성으로 본다. 1% 기준은 2010년 ASCO/CAP 지침부터라, 2010년 이전 진단(ER 44명, PR 60명)의 음성 판정은 10% 기준이었을 수 있다. 변경 기록 `tcga_brca_merging_cropped_changes.txt`에 환자 목록이 있다.

정답 세트(1,061명, 2026-10-13 재집계) 건수:

| 경우 | ER | PR | 정답 value |
|---|---|---|---|
| 구간 + 판정 | 459 | 422 | `{"range":[90,99],"result":"positive"}` |
| 판정만 | 554 | 590 | `{"result":"positive"}` |
| 판정 `[Not Evaluated]` | 48 | 49 | `status: not_done` |

판정값 분포: ER positive 764 / negative 230 / low_positive 17 / indeterminate 2, PR positive 675 (이 중 1-9% 53) / negative 333 / indeterminate 4.

### HER2 IHC 규칙 [A 결정]

1. `score`(0, 1+, 2+, 3+)와 `result`(판정)가 둘 다 있으면 둘 다 넣는다.
2. 판정이 `Equivocal`인데 점수가 없으면 `score: "2+"`를 채운다 (Equivocal의 정의가 IHC 2+). 7명
3. `score`가 `2+`이거나 `result`가 `Equivocal`이면 `gdc_her2_fish_status`를 확인한다.
   - FISH `Negative` → `result`를 `negative`로
   - FISH `Positive` → `result`를 `positive`로
   - FISH가 Positive·Negative가 아니고 `result`가 `Equivocal`이면 → `result`를 `unknown`으로
4. `gdc_her2_copy_number`, `gdc_cent17_copy_number`, `gdc_her2_cent17_ratio`는 넣지 않는다.

TCGA 건수 (score 2+ 또는 Equivocal):

| score | 원래 판정 | FISH | 정답 value | 건수 |
|---|---|---|---|---|
| 2+ | Equivocal | Negative | `{"score":"2+","result":"negative"}` | 127 |
| 2+ | Equivocal | Positive | `{"score":"2+","result":"positive"}` | 17 |
| 2+ | Equivocal | Equivocal / [Not Available] / [Not Evaluated] | `{"score":"2+","result":"unknown"}` | 2 / 2 / 15 |
| 2+ | Positive | Negative | `{"score":"2+","result":"negative"}` (판정이 바뀜) | 6 |
| 2+ | Positive | Positive | `{"score":"2+","result":"positive"}` | 15 |
| 2+ | Positive | Equivocal / 없음 | `{"score":"2+","result":"positive"}` (Equivocal이 아니라 유지) | 6 |
| 2+ | Indeterminate | Negative / Positive | `result`를 `negative` / `positive`로 | 2 / 2 |
| 2+ | Negative | Negative | `{"score":"2+","result":"negative"}` | 1 |
| 1+ | Equivocal | Negative | `{"score":"1+","result":"negative"}` | 4 |
| 3+ | Equivocal | Negative | `{"score":"3+","result":"negative"}` (점수와 판정이 어긋남) | 1 |
| 없음 → 2+ | Equivocal | Negative | `{"score":"2+","result":"negative"}` | 5 |
| 없음 → 2+ | Equivocal | Equivocal / [Not Evaluated] | `{"score":"2+","result":"unknown"}` | 1 / 1 |

건수는 정답 세트(1,061명) 기준이다 (2026-10-13 재집계).

참고:

- `score 2+`와 `result negative`가 함께 있으면 B는 HER2 저발현으로 판정할 수 있다. 그래서 B는 `result`보다 `score`를 먼저 읽어야 한다.
- `3+`인데 판정이 negative가 되는 1명은 원자료끼리 어긋난 경우다. 가상 차트 생성 시 확인한다.

### 재발 병소 재생검 수용체 → `value`, 원발 값 → `history[]` [A 결정]

재생검(재발 병소) 결과로 평가하고 처방하므로, 재생검 결과를 `value`로 쓴다. PROJECT.md IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.

- 재발 병소 수용체(`gdc_nte_er_status`, `gdc_nte_pr_status_by_ihc`, `gdc_nte_her2_status` 등)가 있는 환자는 정답 세트에서 11명이다 (ER 11, PR 10, HER2 8).
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
| `gender` [제안, A 결정] | 성별 | `FEMALE` / `MALE` | 사전 | `F/62` → `"FEMALE"` | `gdc_gender` (정리본은 FEMALE 1,061명) |
| `age` | 진단 시 나이 | 정수 | 해석 | `F/62` → `62` | `gdc_age_at_diagnosis` |
| `menopausal_status` | 폐경 여부 | `premenopausal` / `perimenopausal` / `postmenopausal` / `indeterminate` | 사전 | `폐경 후 상태` → `"postmenopausal"` | `gdc_menopause_status` |
| `ecog` | 전신 수행 상태 | `0`~`4` | 해석 | `ECOG PS 1` → `1` | 없음 (합성) |

- 성별은 범위 외 판정(남성 유방암)에 쓰인다
- 폐경 여부는 적힌 것만 옮긴다. 마지막 생리일(LMP)만 있으면 계산하지 않고 `raw`에 남긴다
- `KPS 90`처럼 다른 척도는 ECOG로 바꾸지 않는다

## 8. 치료 이력 (`fields.treatment_history[]`)

항목 하나가 요법 하나다.

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 정답 규칙 |
|---|---|---|---|---|---|
| `drugs` | 약제 목록 | 일반명 소문자 목록 | 사전 (`drug_names.csv` + 요법 약어 사전) | `AC #4` → `["doxorubicin","cyclophosphamide"]` | `drug_timeline` 성분명 |
| `setting` | 치료 단계 | `neoadjuvant` / `adjuvant` / `metastatic` / `unknown` | 사전 | `수술 전 항암` → `"neoadjuvant"` | 유도 규칙 (tcga_mapping.md §3.6) |
| `start_date` | 시작일 | `YYYY-MM-DD` | 해석 | `'25.1.10부터` → `"2025-01-10"` | [A 결정] TCGA에는 날짜가 없으므로 `null` |
| `end_date` | 종료일 | `YYYY-MM-DD` 또는 `null` | 해석 | `2026.6.20 중단` → `"2026-06-20"` | [A 결정] TCGA에는 날짜가 없으므로 `null` |
| `duration_days` [제안, A 결정] | 투여일 (일) | 정수 또는 `null` | 해석 | `2025.1.10 ~ 2025.3.10` → `59` | [A 결정] TCGA에서만 `d종료 − d시작` |
| `stop_reason` | 중단 사유 | `progression` / `toxicity` / `completed` / `other` [제안] | 사전 | `PD로 중단` → `"progression"` | 없음 |
| `best_response` | 최선 반응 | `CR` / `PR` / `SD` / `PD` / `unknown` | 사전 | `완전관해` → `"CR"` | 괄호 안 반응 |
| `source` | 원문 근거 | 공통 틀과 같음 | — | `{"doc_id":"D3","quote":"AI + palbociclib, PD"}` | 가상 차트 생성 시 채움 |

`duration_days` TCGA 규칙 [A 결정]:

| `drug_timeline` 항목 형태 | 건수 | 정답 |
|---|---|---|
| `d63~d126` (시작·종료 있음) | 1,722 | `126 − 63 = 63` |
| `d1828~?` (종료 모름) | 514 | `null` |
| `날짜 없음` | 109 | `null` |

- 종료일이 시작일보다 앞선 항목은 없다 (0건).
- 상대 일수(d시작)는 출력에는 넣지 않고, 정답 생성 코드 안에서 요법 순서 정렬과 `setting` 유도에만 쓴다.

## 9. 선행요법 반응, 재발, 유전자 보고서

| 필드 | 의미 | 표준값 형태 | 정규화 방식 | 원문 → 정규화 예시 | TCGA 출처 |
|---|---|---|---|---|---|
| `neoadjuvant_response.pcr` | 병리적 완전관해 | `yes` / `no` | 사전 | `pCR 달성` → `"yes"` | 없음 (합성) |
| `neoadjuvant_response.rcb` | 잔존암 부담 등급 | `RCB-0` / `RCB-I` / `RCB-II` / `RCB-III` | 사전 + 해석 | `RCB class II (index 2.1)` → `"RCB-II"` | 없음 (합성) |
| `recurrence.recurrence_date` | 재발일 | 날짜 | 해석 | `2026년 6월 간 전이로 재발` → `"2026-06"` [제안: 부분 날짜] | `nte_first_dx_days` |
| `recurrence.adjuvant_endocrine_end_date` | 보조 내분비요법 종료일 | 날짜 | 해석 | `타목시펜 5년 복용 후 2023.3 종료` → `"2023-03"` | `drug_timeline`에서 유도 |
| `genomic_reports[].specimen` | 검체 | `primary` / `metastasis` / `cfDNA` / `unknown` | 사전 | `혈장 cfDNA NGS` → `"cfDNA"` | 원발(01) 고정 |
| `genomic_reports[].report_date` | 보고일 | `YYYY-MM-DD` | 해석 | `보고일 2026-07-01` → `"2026-07-01"` | `null` |
| `genomic_reports[].raw_text` | 보고서 원문 | 문자열 | **그대로** | `ESR1 p.Y537S detected, VAF 4.2%` → 그대로 | `mut_*`, `cna_*`로 가상 보고서 |

- 유전자 보고서는 검체와 날짜만 정리하고 변이 내용은 손대지 않는다 (B의 BM-1~3)
- pCR은 명시된 경우만 옮긴다. `ypT0 ypN0`처럼 병기만 있으면 병기만 저장한다

## 10. B와 합의할 항목

A가 받아들인 제안과 A 결정이다. 2026-10-12에 `schemas/patient_state.json` 0.1-draft3로 모두 반영했다. B 검토 후 `0.1`로 확정한다.

| 항목 | 상태 |
|---|---|
| 수용체 `value`: `percent`/`range`/`score`/`allred`/`result` 중 있는 것을 모두 한 객체에. `result`에 `low_positive` 추가 (ER만) | A 결정, 스키마 반영 (0.1-draft3) |
| `allred`를 `{total, ps, is}` 객체로 | A 결정, 스키마 반영 (0.1-draft3) |
| ER·PR·HER2 판정 조건 (BM-2) | A 제안 → B 결정. handoff_to_B.md §4 |
| TCGA 정답에는 ER·PR `score`를 넣지 않음 | A 결정 |
| HER2 IHC `{score, faint}` + `{result}` 동시 표기, ISH로 `result` 보정 | A 결정. B는 score를 먼저 읽는다 |
| `her2_ish`는 `{result, method}`만 (복제수·비율 제외) | A 결정 |
| `specimen`, `history[]`(`superseded_reason`: `recurrence` / `newer_result`) 추가 | 스키마 반영 (0.1-draft3) |
| 재발 병소 재생검 결과를 `value`로, 원발 값을 `history[]`로 (IN-4와 같음) | A 결정 |
| ER·PR 원본 구간 `<10%`를 `1-9%` / `<1%`로 나눔 (ER만 Low Positive). Negative는 1% 기준 음성으로 가정 | A 결정 |
| `stage.group`, `stage.positive_ln_count` 추가 | 스키마 반영 (0.1-draft3) |
| `patient.gender` 추가 | 스키마 반영 (0.1-draft3) |
| `treatment_history[].duration_days` 추가 | 스키마 반영 (0.1-draft3) |
| 특수 표기값 `not_assessed`, `[Not Available]`, `[Not Applicable]`을 `value`에 허용 | A 결정 (평가 안됨·불가 통합) |
| `stop_reason` 표준값 목록 | 스키마 반영 (0.1-draft3) |
| 부분 날짜(`YYYY-MM`, `YYYY`) 허용 | 스키마 반영 (0.1-draft3) |
| `stage.disease_extent` 추가 (I~II 조기, III 국소 진행성, IV 전이성) | 사용자 결정 (2026-10-13), 스키마 반영 (0.1-draft4) |
| TCGA 정답의 모든 날짜를 비움 (가상 날짜를 만들지 않음) | A 결정 (2026-10-12) |
| 점수 없는 HER2 Equivocal 7명에 `score: "2+"` 채우기 | A 결정 |
