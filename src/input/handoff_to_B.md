# A → B 전달 문서: patient_state 사용 안내, BM-2 판정 조건, BM-3 출처, 치료 상황 규칙

> 작성: 담당 A · 기준 스키마: `schemas/patient_state.json` **0.1-draft5**
> 받는 사람: 담당 B ([2] 바이오마커 모듈, [4] LLM 추천 모듈)
> 관련 문서: [schema_fields.md](schema_fields.md) (필드별 상세), [tcga_mapping.md](tcga_mapping.md) (TCGA 정답 규칙), [schemas/README.md](../../schemas/README.md), PROJECT.md §5·§10
> 이 문서는 아래 세 문서를 합친 것이다 (2026-10-15). 이전 문서는 git 이력에 있다.

| 날짜 | 내용 | 상태 |
|---|---|---|
| 2026-10-12 | patient_state 사용 안내와 BM-2 판정 조건 (기존 `handoff_to_B.md`, draft4) | ER·PR 결정, 나머지 A 제안 |
| 2026-10-13 | BM-3 근거 주석에서 OncoKB를 빼고 대체 출처를 쓰는 제안 (기존 `handoff_to_B_bm3.md`) | **제안** (4명 합의 필요) |
| 2026-10-15 | draft5: 차수 재료, 재발·전이, PD-L1, 유전자 변이, anthracycline 용량, gBRCA 규칙 (기존 `handoff_to_B_draft5.md`) | **협의 완료** |

## 목차

0. 요약
1. 전달 방식
2. A와 B의 경계
3. B가 받는 값 (JSON 구조, 공통 틀, 수용체, 재발, 유전자, 전체 필드표)
4. BM-2 판정 조건
5. BM-3 근거 주석 출처 (제안)
6. 치료 상황 규칙 (현재 범주, 차수, 급여 투여단계, 국소 재발, PD-L1, 주기, anthracycline)
7. TCGA-BRCA 정답 세트의 특성
8. 예시
9. 넘기지 않는 정보 (모델 한계)
10. B가 정할 것과 할 일

## 0. 요약

1. A는 환자마다 `patient_state` JSON 하나를 넘긴다. 형식은 `schemas/patient_state.json`(0.1-draft5)이고, 스키마 검증을 통과한 것만 보낸다.
2. A는 **적힌 값을 표준 표기로 정리**만 한다. 양성·음성·저발현 판정은 B가 한다. 예외는 하나: HER2 IHC의 `result`는 A가 ISH 결과로 보정해서 넘긴다 (§3.4). 그래서 **HER2는 `result`보다 `score`를 먼저 읽어야** 저발현을 놓치지 않는다.
3. 저발현 판정값(`low_positive`)은 **ER에만** 있다 (ASCO/CAP 2020). PR은 양성/음성 두 범주만 쓴다 (§4.2).
4. 재발 환자는 **재생검(재발 병소) 결과가 `value`**이고, 원발 결과는 `history[]`에 있다 (§3.5). 가상 차트·실제 차트에만 해당하고, **TCGA 정답은 원발 결과만** 쓴다.
5. `not_done`(미시행)과 `not_recorded`(기록 없음)는 다르다. 미시행만 검사 권고 대상이다.
6. **차수(line)는 정답에 넣지 않는다. B가 직접 판단한다** (협의 완료, 2026-10-15). 재료는 투약 시작·종료일(`treatment_history[].start_day`, `end_day`)과 전이 기준일(`recurrence.metastasis_day`)이다. 모두 진단일 = 0인 정수다 (§6.2).
7. **현재 범주**: 진단 시 IV기이거나 원격 전이 재발이면 전이성. 국소 재발은 전이가 아니다 (§6.1). **국소 재발 후 수술**(이후 원격 전이 없음)이면 이후 요법은 수술후보조요법이다 (§6.4).
8. **gBRCA**: TCGA 정답 세트에서는 BRCA1·BRCA2 결과를 gBRCA 측정으로 가정한다. B가 positive / negative / vus를 판정한다 (§4.7).
9. **PD-L1은 발현 점수**다 (변이 아님). 검사법·점수만 넘기고 약제별 판정은 B가 한다 (§6.5).
10. **유전자 변이**는 `molecular.mutations`에 유전자별로 넘긴다: 변이 있음 / 변이 없음 / 미시행 (§3.6).
11. **anthracycline 투약 용량**과 **주기 길이가 붙은 투여 주기**를 넘긴다 (§6.6·§6.7).
12. BM-3(변이 근거 주석)은 OncoKB 대신 허가사항·CIViC·ClinVar·VEP를 쓰자는 **제안**이 있다 (§5).
13. §4.1 ER, §4.2 PR 판정 규칙은 2026-10-12 결정이다. §4의 나머지 조건은 A의 제안이고, 수치 기준은 종양내과·병리과 검토로 확정한다. §10에 B가 정할 것을 모았다.

## 1. 전달 방식

| 항목 | 내용 |
|---|---|
| 형식 | `schemas/patient_state.json` (JSON Schema 2020-12). 환자 1명 = JSON 1개 |
| 개발 중 | 파일로 전달: `tests/fixtures/patient_state/<patient_ref>.json` (예정. 공용 폴더라 4명 합의 후 생성). 지금은 범주별 예시 3명이 `src/input/examples/`에 있다 (§8.1) |
| 연결 후 | 함수 반환값: A의 `run(chart_text) → patient_state` 결과를 B의 `assess(patient_state) → biomarker_record`가 받는다 |
| 검증 | A가 보내기 전에 검증한다. B도 받을 때 검증하면 버전 불일치를 바로 알 수 있다 (`schema_version` = `"0.1-draft5"`) |
| 첫 전달 예정 | TCGA-BRCA 정답 세트 992명 (§7) 중 경계 사례 5건부터 |

```python
import json
from jsonschema import Draft202012Validator

schema = json.load(open("schemas/patient_state.json", encoding="utf-8"))
Draft202012Validator(schema).validate(patient_state)  # 실패하면 ValidationError
```

## 2. A와 B의 경계

| 질문 | 답이 "예"면 |
|---|---|
| **차트 쓰는 방식**이 바뀌면 고쳐야 하는 규칙인가? (병원, 작성자, 약어, 국문·영문) | A |
| **판정 기준**이 바뀌면 고쳐야 하는 규칙인가? (ASCO/CAP 기준, 1% 경계, 급여 기준) | B |

| 원문 | A가 넘기는 값 | B가 판정할 것 |
|---|---|---|
| ER 90% | `{"percent": 90}` | ER 양성 |
| ER Allred 6/8 | `{"allred": {"total": 6}}` | ER 양성 |
| HER2 2+, SISH 음성 | `her2_ihc {"score":"2+","result":"negative"}`, `her2_ish {"result":"not_amplified"}` | HER2 저발현 |
| PIK3CA p.H1047R, VAF 31% | `molecular.mutations.PIK3CA` (유전자별 값), `genomic_reports[].raw_text` (원문) | 양성(BM-2) → 근거 주석(BM-3) |
| PD-L1 22C3 CPS 12 | `receptors.pdl1 {"assay":"22C3","score_type":"CPS","score":12}` | 약제별 기준으로 양성·음성 |
| AC 후 paclitaxel, 이후 원격 전이 | `treatment_history[]`의 `start_day`, `recurrence.metastasis_day` | 보조요법인지 몇 차인지 |

## 3. B가 받는 값

### 3.1 JSON 구조

```
patient_state.json
├── schema_version            "0.1-draft5"
├── patient_ref               가명 ID (TCGA는 바코드)
├── created_at                생성 시각
├── documents[]               {doc_id, doc_type, doc_date}
├── fields
│   ├── diagnosis
│   │   ├── diagnosis_date
│   │   ├── histology         IDC / ILC / mucinous / metaplastic / invasive_NOS / other
│   │   └── grade             1 / 2 / 3
│   ├── stage
│   │   ├── ctnm, ptnm        {t, n, m, edition}
│   │   ├── group             IIA, IIIC, IV …
│   │   ├── positive_ln_count {positive, examined}
│   │   ├── disease_extent    early / locally_advanced / metastatic (진단 시)
│   │   ├── metastatic_sites  진단 시 전이 부위
│   │   └── operable          yes / no / unknown
│   ├── receptors
│   │   ├── er_percent        {percent, range, score, allred, result}
│   │   ├── pr_percent        {percent, range, score, allred, result}
│   │   ├── her2_ihc          {score, faint, result}
│   │   ├── her2_ish          {result, method}
│   │   └── pdl1              {assay, score_type, score}
│   ├── proliferation
│   │   └── ki67_percent      {percent, range, result}
│   ├── patient
│   │   ├── gender, age
│   │   ├── menopausal_status, menopausal_basis
│   │   └── ecog
│   ├── treatment_history[]   투약 기록 하나 = 원소 하나
│   │   ├── drugs[], setting
│   │   ├── start_date, end_date          (날짜, TCGA는 null)
│   │   ├── start_day, end_day            (진단일 = 0)
│   │   ├── duration_days
│   │   ├── cycles            {value, basis, interval_days, interval_basis}
│   │   ├── progression_day
│   │   ├── stop_reason, best_response
│   │   └── source
│   ├── anthracycline_drug_dose
│   │   ├── administered      positive / negative / No value
│   │   └── drugs[]
│   │       ├── drug, timeline_index, combined_with[]
│   │       ├── dose_per_admin   {value, unit} 또는 "No value"
│   │       ├── cycles           cycles 형식 또는 "No value"
│   │       ├── total_dose       {value, unit} 또는 "No value"
│   │       └── raw
│   ├── neoadjuvant_response
│   │   ├── pcr               yes / no
│   │   └── rcb               RCB-0 ~ RCB-III
│   ├── recurrence
│   │   ├── recurrence_date, adjuvant_endocrine_end_date
│   │   ├── status            none / distant / locoregional / site_unknown / unknown
│   │   ├── metastatic_sites  재발 전이 부위
│   │   ├── metastasis_day    전이 기준일 (진단일 = 0)
│   │   ├── surgery           재발 후 수술 yes / no / unknown
│   │   ├── surgery_intent    curative / palliative / unknown
│   │   └── later_distant     국소 재발 후 원격 전이 yes / no / unknown
│   ├── molecular
│   │   └── mutations
│   │       └── ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2
│   │           ├── status    present / not_done
│   │           ├── result    detected / not_detected
│   │           ├── variants[]  {protein_change, variant_type, vaf, raw}
│   │           └── specimen
│   └── genomic_reports[]     {doc_id, report_date, specimen, raw_text}
└── conflicts[]               {field, candidates[], note}
```

`fields` 아래의 칸(예: `histology`, `er_percent`, `recurrence.status`)은 대부분 아래 공통 틀로 감싸져 있다. 예외는 `treatment_history[]`, `anthracycline_drug_dose`, `molecular.mutations.*`, `genomic_reports[]`로 위 그림의 키를 그대로 쓴다.

### 3.2 모든 칸의 공통 틀

| 키 | 의미 | B가 쓰는 방법 |
|---|---|---|
| `status` | `present` 값 있음 / `not_done` 미시행 / `not_recorded` 기록 없음 | `not_done` → 검사 공백 규칙(BM-4)의 검사 권고 대상. `not_recorded` → "기록 없음"으로만 남김 |
| `value` | 표준값 (형태는 칸마다 다름). `present`일 때만 있음 | 판정 입력 |
| `raw` | 원문 표기 | 판정이 이상할 때 확인용 |
| `specimen` | `primary` 원발 / `metastasis` 전이·재발 병소 / `cfDNA` / `unknown` | 재생검 여부, ESR1 재검 판단 |
| `observed_date` | 검사일. `YYYY-MM-DD`, `YYYY-MM`, `YYYY` 또는 `null` | 재검 필요 판단. **TCGA 정답은 항상 `null`** |
| `source` | 원문 근거 `{doc_id, quote, char_start, char_end}` | B 출력의 `source_span`에 그대로 사용 |
| `history[]` | 새 결과에 밀려난 이전 값. `superseded_reason`: `recurrence` / `newer_result` | 판정에는 쓰지 않고 "바뀜" 설명에 사용 |

특수 표기: `not_assessed` 평가 안됨, `[Not Available]` 그 항목만 기록 없음, `[Not Applicable]` 해당 없음, `No value` anthracycline 용량 값 없음. 해당 없는 칸은 만들지 않는다.

### 3.3 ER·PR (`receptors.er_percent`, `receptors.pr_percent`)

`value`는 아래 키 중 **차트에 적힌 것을 모두** 담은 객체다. A는 하나를 고르지 않는다.

| 키 | 의미 | 예 |
|---|---|---|
| `percent` | 양성 세포 비율 (%) | `ER 95%` → `{"percent": 95}` |
| `range` | 비율 구간 `[최소, 최대]` | `90-99%` → `[90, 99]` / `1-9%` → `[1, 9]` / `<1%` → `[0, 0]` |
| `score` | **염색 강도** 점수 `0`, `1+`~`4+` | `ER intensity 3+`, `strong` → `{"score": "3+"}` |
| `allred` | Allred 점수 `{total, ps, is}` 중 적힌 것 | `Allred 6/8 (PS 4, IS 2)` → `{"allred": {"total": 6, "ps": 4, "is": 2}}` |
| `result` | 차트에 적힌 판정 | ER: `positive` / `low_positive` / `negative` / `indeterminate`, PR: `positive` / `negative` / `indeterminate` |

- `low_positive`는 **ER에만** 있다.
- Allred: total = ps + is (0, 2~8). ps = 비율 점수 (0 없음, 1 <1%, 2 1~10%, 3 11~33%, 4 34~66%, 5 ≥67%), is = 강도 점수 (0~3).
- 척도가 적혀 있지 않은 점수(예: `ER score 6`)는 `raw`에만 남기고 `value`에 넣지 않는다.
- **TCGA 정답에는 `score`와 `allred`가 없다** (§7).

### 3.4 HER2 (`receptors.her2_ihc`, `receptors.her2_ish`)

| 칸 | `value` | 비고 |
|---|---|---|
| `her2_ihc` | `{score, faint, result}` 중 있는 것 모두 | `score`: `0`, `1+`, `2+`, `3+` / `faint`: IHC 0 중 미약한 막 염색 / `result`: `positive`, `negative`, `equivocal`, `indeterminate`, `unknown` |
| `her2_ish` | `{result, method}` | `result`: `amplified`, `not_amplified`, `equivocal` / `method`: `FISH`, `SISH`, `DISH`, `unknown`. 복제수·비율은 넣지 않는다 |

**A의 `result` 보정 규칙 (A 결정, TCGA 정답에 적용):**

1. `score`와 `result`가 둘 다 있으면 둘 다 넣는다.
2. 판정이 Equivocal인데 점수가 없으면 `score: "2+"`를 채운다 (Equivocal의 정의가 IHC 2+).
3. `score`가 `2+`이거나 판정이 Equivocal이면 ISH 결과로 `result`를 바꾼다: ISH 음성 → `negative`, ISH 양성 → `positive`, ISH 결과가 없는데 판정이 Equivocal → `unknown`.

그래서 `{"score":"2+","result":"negative"}`는 "IHC 2+, ISH 비증폭"이라는 뜻이다. **`result`만 보고 HER2 음성으로 판정하면 저발현 환자를 놓친다.** 트라스투주맙 데룩스테칸 같은 저발현 대상 치료가 후보에서 빠진다.

### 3.5 재발 환자의 수용체

- 재발 병소 재생검 결과를 `value`로 쓰고 `specimen: "metastasis"`. PROJECT.md IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.
- 원발 결과는 `history[]`에 `"superseded_reason": "recurrence"`, `"specimen": "primary"`로 들어 있다.
- 재생검에서 검사하지 않은 마커는 원발 결과가 그대로 `value`다.
- **TCGA 정답 예외:** TCGA 정답은 진단 시(원발 종양) 병기·수용체만 쓴다. 재발 병소 수용체(`gdc_nte_*`)는 정답에 쓰지 않는다 (재발 기록과 맞는 환자가 1명뿐, 검사 부위·날짜도 없음). 재생검 우선 규칙은 가상 차트와 실제 차트에만 적용한다 (2026-10-14).

```json
"er_percent": {
  "status": "present", "value": {"range": [70, 79], "result": "positive"}, "specimen": "metastasis",
  "history": [{"status": "present", "value": {"range": [90, 99], "result": "positive"},
               "specimen": "primary", "superseded_reason": "recurrence"}]
}
```

### 3.6 유전자 (`molecular.mutations`, `genomic_reports[]`)

유전자별 값 (draft5, 협의 완료):

| 유전자별 원본 값 (TCGA `mut_*`) | 정답 |
|---|---|
| 변이 표기 (`H1047R (Missense_Mutation, VAF 0.31)`, 여러 개면 `; `) | `{"status": "present", "result": "detected", "variants": [{"protein_change", "variant_type", "vaf", "raw"}], "specimen": "primary"}` |
| `변이 없음` | `{"status": "present", "result": "not_detected", "variants": [], "specimen": "primary"}` |
| 빈 값 | `{"status": "not_done"}` (미시행) |

- 대상: ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2. **ERBB2 변이는 넣지 않는다** (협의).
- `genomic_reports[]`는 `{doc_id, report_date, specimen, raw_text}`이고 A는 `raw_text`를 해석하지 않는다. 가상·실제 차트에서 변이 파싱은 B의 BM-1이다. 같은 정보가 두 곳에 있으면 `molecular`를 우선한다.
- TCGA 보고서는 종양 조직 엑솜 검사다. `specimen`은 항상 `primary`, `report_date`는 `null`이다.
- BRCA1/2의 gBRCA 처리는 §4.7.

### 3.7 필드별 전체 출력과 B의 정규화 (TCGA 정답 992명 기준)

**문서 단위**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `schema_version` | `"0.1-draft5"` | 고정 | 버전이 다르면 거부 |
| `patient_ref` | 문자열 | TCGA 바코드 | 그대로 |
| `documents[]` | `{doc_id, doc_type, doc_date}` | `doc_date`는 모두 `null` | |
| `conflicts[]` | `{field, candidates[], note}` | 대부분 빈 배열 | 자동 선택하지 말고 확인 요청 |

**diagnosis / stage**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `diagnosis.diagnosis_date` | 날짜 | 모두 `not_recorded` | 순서는 `*_day`로 판단 |
| `diagnosis.histology` | `IDC` / `ILC` / `mucinous` / `metaplastic` / `invasive_NOS` / `other` | 원본 조직형 변환 | |
| `diagnosis.grade` | 1 / 2 / 3 | 모두 `not_recorded` | abemaciclib 보조요법 조건(등급 3) 판정 불가 |
| `stage.ptnm` | `{t, n, m, edition}` | TX·NX·MX는 `not_assessed` | AJCC 판(3~7판)이 섞여 있음 |
| `stage.ctnm` | 같음 | 모두 `not_recorded` | |
| `stage.group` | `IIA`, `IIIC`, `IV`, `not_assessed` | | |
| `stage.positive_ln_count` | `{positive, examined}`. 각각 정수 또는 `[Not Available]` | | 공고 보조요법 조건 (4개 이상, 1~3개 등) |
| `stage.disease_extent` | `early` / `locally_advanced` / `metastatic` | 진단 시 범주 | 현재 범주는 §6.1 |
| `stage.metastatic_sites` | 부위 목록 / `[Not Applicable]` / `[Not Available]` | M0(`cM0(i+)` 포함)이면 `[Not Applicable]` (2026-10-15) | `[Not Available]`은 MX·M1이면서 부위 기록이 없는 경우뿐 |
| `stage.operable` | `yes` / `no` / `unknown` | 없음 | 국소진행성의 선행·고식 구분 불가 |

**receptors / proliferation / patient**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `receptors.er_percent`, `pr_percent` | §3.3 | `range` + `result` (`score` 없음) | §4.1·§4.2 |
| `receptors.her2_ihc`, `her2_ish` | §3.4 | | `score`를 먼저 읽기 (§4.4) |
| `receptors.pdl1` | `{assay, score_type, score}` | 모두 `not_recorded` | §6.5 |
| `proliferation.ki67_percent` | `{percent, range, result}` | 모두 `not_recorded` | |
| `patient.gender`, `age` | `FEMALE` / 정수 | 모두 FEMALE | |
| `patient.menopausal_status` | 폐경 4종 | 진단 시점 값 | 공고는 "약제 전환 시점"의 폐경 상태를 요구함 |
| `patient.menopausal_basis` | `age_amenorrhea` / `fsh` / `oophorectomy` / `unknown` | 없음 | |
| `patient.ecog` | 0~4 | 모두 `not_recorded` | |

**treatment_history[]** (투약 기록 2,215개)

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `drugs` | 일반명 소문자 배열 | 병용 기록은 여러 개 (`["doxorubicin", "cyclophosphamide"]`) | 약제 계열로 바꿔 `prior_drug_classes`에 사용 |
| `setting` | `neoadjuvant` / `adjuvant` / `metastatic` / `unknown` | adjuvant 2,107, metastatic 108 | A의 유도값 (시작일 ≥ 전이 기준일 → metastatic). neoadjuvant 13명은 수작업 확인 예정 |
| `start_date`, `end_date` | 날짜 | 모두 `null` | |
| `start_day`, `end_day` | 정수 / `null` | `start_day` null 84, `end_day` null 574 | **차수 계산의 핵심** (§6.2). `end_day` null = 종료 모름 |
| `duration_days` | 정수 / `null` | `end_day − start_day` | |
| `cycles` | `{value, basis, interval_days, interval_basis}` / `null` | 기록값 787, 추정값 716, null 712 | §6.6 |
| `progression_day` | 정수 / `null` | 모두 `null` | 공고 "종료 후 1달 이내 진행" 판정 불가 |
| `stop_reason` | `progression` / `toxicity` / `completed` / `planned_switch` / `maintenance` / `other` / `null` | 모두 `null` | `planned_switch`·`maintenance`는 같은 차수 |
| `best_response` | `CR` / `PR` / `SD` / `PD` / `unknown` | | `PD`는 진행으로 차수가 넘어갔다는 근거 |

골 보호제(zoledronic acid, denosumab 등)와 보조약도 기록에 들어 있다. 차수를 셀 때는 뺀다.

**anthracycline_drug_dose**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `administered` | `positive` / `negative` / `No value` | positive 374, negative 344, No value 274 | `No value` = 투약 기록 없음 (투여 안 함이 아님) |
| `drugs[].drug` | `doxorubicin` / `epirubicin` / `liposomal doxorubicin` | 338 / 40 / 2 | mitoxantrone은 제외 |
| `drugs[].timeline_index`, `combined_with`, `raw` | 정수, 배열, 문자열 | | 대조용 |
| `drugs[].dose_per_admin` | `{value, unit}` / `"No value"` | No value 201, mg 95, mg/m² 68, mg/day 13, mg/m²/day 3 | 원문이 범위(100-102)면 최대값. 단위가 섞여 있음 (§6.7) |
| `drugs[].cycles` | `cycles` 형식 (`basis: recorded`만) / `"No value"` | 기록 205, No value 175 | |
| `drugs[].total_dose` | `{value, unit}` / `"No value"` | No value 217, mg 158, mg/m² 3, 기타 2 | 대부분 mg |

**recurrence**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `recurrence_date`, `adjuvant_endocrine_end_date` | 날짜 | 모두 `not_recorded` | 대신 `*_day`와 `treatment_history` 사용 |
| `status` | `none` / `distant` / `locoregional` / `site_unknown` / `unknown` | none 776, unknown 170, distant 24, locoregional 15, site_unknown 7 | §6.1 |
| `metastatic_sites` | 부위 목록 | distant 24명만 | 국소 부위(`other: Axilla` 등)가 섞일 수 있음. 처방·급여 판정에는 쓰지 않음 |
| `metastasis_day` | 정수 (진단 시 IV기 = 0) | 전이성 32명만 | **차수 기준점** (§6.2) |
| `surgery` | `yes` / `no` / `unknown` | 재발 46명: yes 18, no 19, unknown 9 | §6.4 |
| `surgery_intent` | `curative` / `palliative` / `unknown` | 모두 `unknown` | |
| `later_distant` | `yes` / `no` / `unknown` | 20명 (모두 `no`) | §6.4 |

**molecular / genomic_reports**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `molecular.mutations.{유전자}` | §3.6 | 유전자마다 미시행 30명 | |
| 변이 있음 건수 | | PIK3CA 318, PTEN 53, AKT1 25, BRCA2 25, BRCA1 24, ESR1 9, PALB2 7 | `variants[]`로 BM-3 (§5) |
| `specimen` | `primary` | 모두 원발 조직 | ESR1은 진행 후 재검 대상 (§4.6) |
| `genomic_reports[]` | `{doc_id, report_date, specimen, raw_text}` | 가상 보고서 원문 | `molecular` 우선 |

## 4. BM-2 판정 조건

§4.1·§4.2는 2026-10-12 결정, §4.7은 2026-10-15 협의, 나머지는 A 제안이다. A는 이 조건으로 정답 데이터와 가상 차트를 만든다. B가 확정한 조건과 정답이 같아야 평가가 맞으므로, 바꾸면 A에게 알려 주기 바란다.

### 4.1 ER [결정 2026-10-12]

ASCO/CAP 2020: 1% 미만 음성, 1~10% **저발현(Low Positive)**, 10% 초과 양성. 위에서부터 처음 맞는 값으로 판정한다.

| 순서 | 있는 값 | 조건 → 상태값 |
|---|---|---|
| 1 | `percent` | <1 → `negative` / 1~10 → `low` / >10 → `positive` |
| 2 | `range` | `[0,0]` → `negative` / 최대 ≤10 (예: `[1,9]`) → `low` / 최소 ≥10 (예: `[10,19]`) → `positive` (10%가 걸치는 구간은 실무상 양성) |
| 3 | `allred.ps` | 0~1 → `negative` / **2 → `low`** / **3~5 → `positive`** |
| 4 | `allred.total`만 (ps 없음) | 0~2 → `negative` / 6~8 → `positive` / **3~5 → `indeterminate`** + 비율(ps) 확인 권고 |
| 5 | `result`만 | 적힌 판정을 따름 (`low_positive` → `low`) |
| 6 | `score`(강도)만 | `indeterminate`. 강도만으로는 양성 여부를 정할 수 없음 |

**Allred 총점 5점 규칙 [결정]:** 저발현과 양성은 비율로 정해지므로 ps를 total보다 먼저 본다.

| Allred | 조합 | 판정 |
|---|---|---|
| 총점 5, **ps 2** (is 3) | 비율 1~10% | **`low`** (ER-low) |
| 총점 5, **ps 3** (is 2) | 비율 11~33% | **`positive`** |
| 총점 5, ps 4 (is 1) | 비율 34~66% | `positive` |
| 총점 5, ps 없음 | 알 수 없음 | `indeterminate` + 비율 확인 권고 |

총점 3·4도 같은 원리다. ps가 있으면 ps로 판정하고, ps가 없으면 불확정이다.

| 총점 | 가능한 조합 (ps + is) | ps가 없을 때 |
|---|---|---|
| 3 | 1+2 (<1%), 2+1 (1~10%) | 음성 또는 저발현 → 불확정 |
| 4 | 1+3 (<1%), 2+2 (1~10%), 3+1 (11~33%) | 음성, 저발현, 양성 모두 가능 → 불확정 |
| 5 | 2+3 (1~10%), 3+2, 4+1 | 저발현 또는 양성 → 불확정 |

참고: Allred 원래 기준은 총점 3 이상을 양성으로 보지만, ASCO/CAP 1% 기준과 맞지 않는다 (ps 1 = 1% 미만). ER 저발현으로 판정하면 `rag_tags`에 `ER-low`를 붙인다.

### 4.2 PR [결정 2026-10-12]

ASCO/CAP 2020은 PR에 저발현 범주를 두지 않는다: 1% 이상 양성, 1% 미만 음성. **PR에는 `low` 상태값을 쓰지 않는다.**

| 순서 | 있는 값 | 조건 → 상태값 |
|---|---|---|
| 1 | `percent` | <1 → `negative` / ≥1 → `positive` |
| 2 | `range` | `[0,0]` → `negative` / 최소 ≥1 → `positive` |
| 3 | `allred.ps` | 0~1 → `negative` / 2~5 → `positive` |
| 4 | `allred.total`만 | 0~2 → `negative` / 5~8 → `positive` / **3~4 → `indeterminate`** + 비율 확인 권고 |
| 5 | `result`만 | 적힌 판정을 따름 |
| 6 | `score`(강도)만 | `indeterminate` |

**`PR-low` 태그 [결정]:** PR이 1~10%로 확인되면 상태값은 `positive` 그대로 두고 `rag_tags`에 `PR-low`를 붙인다.

| 조건 | 예 | 결과 |
|---|---|---|
| `percent` 1~10 | `{"percent": 5}` | `positive` + `PR-low` |
| `range` 최소 ≥1, 최대 ≤10 | `{"range": [1, 9]}` (TCGA 52명) | `positive` + `PR-low` |
| `allred.ps` = 2 | `{"allred": {"total": 4, "ps": 2, "is": 2}}` | `positive` + `PR-low` |
| `result`만, 또는 `allred.total`만 | `{"result": "positive"}` | `positive` (태그 없음) |
| 10% 초과 | `{"range": [10, 19]}` | `positive` (태그 없음) |

`PR-low`는 참고 정보다. 아형(`subtype`)과 처방 분류에는 영향을 주지 않는다.

### 4.3 ER·PR 공통: 값끼리 어긋날 때

예: `{"percent": 5, "result": "positive"}`, `{"range": [0,0], "result": "positive"}`.

- 제안: 수치(`percent` → `range` → `allred.ps` → `allred.total`)로 판정하고, 적힌 판정과 다르면 `reason`에 둘 다 적고 확인이 필요하다고 표시한다.
- TCGA 정답에서는 이런 경우가 없도록 크롭 단계에서 맞췄다.

### 4.4 HER2 (score를 먼저 읽음)

| `her2_ihc.score` | `her2_ish` | 상태값 |
|---|---|---|
| `3+` | 상관없음 | `positive` |
| `2+` | `amplified` | `positive` |
| `2+` | `not_amplified` | `low` |
| `2+` | `not_done` | `indeterminate` + ISH 검사 권고 (BM-4) |
| `2+` | `not_recorded` 또는 `equivocal` | `indeterminate` |
| `1+` | 상관없음 | `low` |
| `0` + `faint: true` | 상관없음 | `ultralow` |
| `0` | 상관없음 | `zero` |
| 없음 | `result`만 `positive` | `positive` |
| 없음 | `result`만 `negative` | `indeterminate` (0과 저발현을 구분할 수 없음) + IHC 점수 확인 권고 |
| 없음 | `result`만 `unknown` | `indeterminate` |

B가 정할 경계 사례: TCGA에 `score 2+`, 원래 판정 Positive, ISH 결과 없음이 6명 있다. A는 `{"score":"2+","result":"positive"}`로 넘긴다. 위 표대로면 `indeterminate`인데, 검사실 판정(양성)을 따를지 정해야 한다.

### 4.5 재발 환자

- `value`(재생검 결과)로 판정한다.
- `history[]`의 원발 결과와 다르면 `reason`에 "원발 ○○에서 △△로 바뀜"을 적는다.
- 아형(`subtype`)도 재생검 결과로 정한다.

### 4.6 ESR1 재검

B의 규칙은 "ESR1 결과가 마지막 내분비요법 진행 **이전**이면 재검 필요"다. TCGA 정답은 날짜가 모두 `null`이지만, draft5부터 투약 순서는 `start_day`로 알 수 있다.

- 제안: ESR1 결과의 `specimen`이 `primary`(진단 시 조직)이고, `treatment_history`에 그 이후 내분비요법 진행(`best_response: PD` 또는 `stop_reason: progression`)이 있으면 `retest_needed`.
- TCGA 변이는 모두 원발 조직 결과이므로, 전이성 HR+/HER2- 환자 대부분이 `retest_needed`가 된다.

### 4.7 BRCA [협의 완료 2026-10-15]

| 정보 | 상태값 |
|---|---|
| **TCGA 정답 세트**: `molecular.mutations.BRCA1/2`가 `detected` + 병원성 변이 (ClinVar Pathogenic·Likely pathogenic, 또는 절단 변이) | gBRCA1/2 `positive` |
| TCGA 정답 세트: `detected` + 의미 불명 변이 (예: missense E9Q) | gBRCA1/2 `vus` |
| TCGA 정답 세트: `not_detected` | gBRCA1/2 `negative` |
| TCGA 정답 세트: `status = not_done` | gBRCA1/2 `not_done` |
| 가상·실제 차트: 종양 체세포 검사에서 BRCA1/2 검출 안 됨 | sBRCA1/2 `negative` |
| 가상·실제 차트: 생식세포 검사 언급 없음 | gBRCA1/2 `not_recorded` (체세포 결과로 대신하지 않음) |
| HER2 음성 전이성 + gBRCA `not_done` | BM-4 검사 권고 |
| HER2 음성 전이성 + gBRCA `not_recorded` | B가 정할 것: 검사 권고를 낼지, "시행 여부 확인"으로만 낼지 |

TCGA 변이는 종양 조직 엑솜 결과라 실제 생식세포 검사 결과와 다를 수 있다. 정답 세트를 만들기 위한 가정이며 모델 한계로 기록한다 (§9).

## 5. BM-3 근거 주석 출처: OncoKB 대신 대체 출처 [제안 2026-10-13, 4명 합의 필요]

### 5.1 요약

1. **OncoKB는 쓰지 않는 것을 제안한다.** 우리 팀 조건(기관 이메일 없음, 수동 심사 대상 제외, 부트캠프)에 맞지 않고, AI/ML 학습에 쓰는 것을 학술 목적까지 포함해 금지한다.
2. 대체 조합: **① FDA·식약처 허가사항(동반진단 변이 목록) → ② CIViC → ClinVar(생식세포) → Ensembl VEP(PTEN 기능 소실)**.
3. 네 가지 모두 가입·심사 없이 받을 수 있고, **파일로 받아 로컬에서 조회**한다. 환자 변이 정보가 외부 서버로 나가지 않으므로 "차트 정보는 외부 API로 보내지 않는다" 원칙과도 맞는다.

### 5.2 OncoKB를 빼는 이유

2026-10-13 OncoKB 라이선스 FAQ(https://faq.oncokb.org/licensing)에서 확인했다.

| 조건 | OncoKB | 우리 상황 |
|---|---|---|
| 학술 무료 이용 자격 | 기관·대학 이메일로 계정 등록 | 기관 이메일 없음 |
| 가입·API 접근 | 계정을 수동으로 심사하고, API는 사용 목적을 적어 따로 신청 | 수동 심사 대상은 후보에서 제외 (팀 원칙) |
| AI/ML 학습 | 학술·상업 목적 모두 AI/ML 모델 학습에 쓸 수 없음 | 나중에 학습·평가 라벨로 쓸 가능성이 있음 |
| 로컬 DB 사본 | 사례별로만, 추가 비용 | 외부 API를 피하려면 로컬 사본이 필요 |
| 부트캠프 | "academic setting"에 해당하는지 불분명 | 판단 근거 없음 |

**함께 지킬 것:** cBioPortal 화면에 보이는 변이 주석(Oncogenic, Level 등)은 OncoKB 데이터다. 변이 원자료는 써도 되지만, **화면의 주석을 옮겨 적거나 정답으로 쓰지 않는다.**

### 5.3 대체 출처

| 순서 | 출처 | 쓰는 곳 | 라이선스·접근 (확인 내용) | 받는 방법 |
|---|---|---|---|---|
| ① | **FDA 라벨(DailyMed)과 동반진단 요약(SSED), 식약처 의약품 허가사항** | PIK3CA, AKT1, PTEN, ESR1 중 치료 대상 변이 | 미국 정부 저작물과 국내 공공 문서. 가입 필요 없음 | 원문에서 변이 목록을 옮겨 규칙표로 만든다 (출처 문서·쪽 기록) |
| ② | **CIViC** (civicdb.org) | 허가 목록에 없는 체세포 변이의 근거 | **CC0 1.0 퍼블릭 도메인**. 2026-10-13 로그인 없이 GraphQL API 응답 확인, nightly TSV 다운로드 확인 (PIK3CA·AKT1·PTEN·ESR1 관련 108행) | `https://civicdb.org/downloads/nightly/` TSV를 날짜별로 받아 로컬 조회 |
| — | **ClinVar** (NCBI) | gBRCA1/2, PALB2, PTEN 미스센스 | NCBI 정책상 사용·배포 제한 없음. FTP 다운로드는 가입 필요 없음 | FTP의 VCF 또는 `variant_summary.txt.gz`를 받아 로컬 조회 |
| — | **Ensembl VEP** | PTEN 절단형 변이(기능 소실) 판정, 표기 정규화 | Apache 2.0, 로컬 실행 | 로컬 설치 또는 Docker |

제외한 후보:

| 후보 | 이유 |
|---|---|
| OncoKB | §5.2 |
| COSMIC | 학술 무료 이용도 가입과 기관 확인 필요 |
| JAX-CKB | 계정 등록 필요 |
| Cancer Genome Interpreter | 등록 필요. 약관 페이지가 403으로 막혀 라이선스 확인 못 함 |
| Cancer Hotspots | 코드는 AGPL-3.0, 데이터 라이선스가 명시되지 않아 확인 못 함 |
| cBioPortal 화면 주석 | 내용이 OncoKB 데이터 |

### 5.4 바이오마커별 판정 제안

PROJECT.md §5 판정 기준표의 "OncoKB 발암성 변이"를 아래로 바꾸는 제안이다. 위에서부터 처음 맞는 줄로 판정한다.

| 바이오마커 | 순서 | 조건 | 상태값 | 비고 |
|---|---|---|---|---|
| PIK3CA | 1 | 허가 동반진단 변이 목록에 있음 | 양성 | 예: C420R, E542K, E545A/D/G/K, Q546E/R, H1047L/R/Y (알펠리십 동반진단 기준. **원문에서 다시 확인**) |
| | 2 | 목록에 없고 CIViC에 발암성·예측 근거가 있음 | 양성 + `off-label-variant` 태그 | 근거 등급(A~E)을 함께 저장 |
| | 3 | 둘 다 아님 | VUS (음성 처리, 표시 유지) | |
| AKT1 | 1 | 허가 근거 변이 (예: E17K, 카피바설팁) | 양성 | 원문 확인 |
| | 2 | CIViC 근거 | 양성 + 태그 | |
| PTEN | 1 | VEP 결과 절단형 (nonsense, frameshift, 필수 스플라이스 부위) | 양성 (기능 소실) | |
| | 2 | 미스센스이고 ClinVar 병원성·병원성 가능 또는 CIViC 근거 있음 | 양성 | |
| | 3 | 그 외 | VUS | |
| ESR1 | 1 | 엘라세스트란트 동반진단의 리간드 결합 도메인 변이 (예: Y537S/N/C, D538G 등) | 양성 | 원문 확인. 이후 승인된 SERD 라벨도 확인 |
| | 2 | 기존 "재검 필요" 규칙은 그대로 | | |
| gBRCA1/2, PALB2 | 1 | ClinVar 병원성·병원성 가능이고 리뷰 등급 2성 이상 | 양성 | ACMG 4·5등급 대응 |
| | 2 | 판정 상충 또는 1성 이하 | VUS | |

변이 목록은 A가 기억하는 내용으로 쓴 **예시**다. 규칙표에는 반드시 원문(DailyMed 라벨, FDA SSED, 식약처 허가사항)에서 옮겨 적고, 출처 문서·버전·쪽을 함께 저장한다.

### 5.5 스키마 변경 제안 (4명 합의 필요)

현재 `schemas/biomarker_record.json`의 `evidence`에 `oncokb` 필드가 있다. 출처에 묶이지 않는 형식으로 바꾸는 것을 제안한다.

```json
"annotation": {
  "type": ["object", "null"],
  "properties": {
    "source": {"enum": ["label", "civic", "clinvar", "vep"]},
    "source_version": {"type": "string", "description": "예: civic nightly 2026-10-13, clinvar 2026-10-05, 라벨 개정일"},
    "call": {"type": "string", "description": "예: 허가 동반진단 변이, Pathogenic (2성), CIViC 근거 B"},
    "citation": {"type": "string", "description": "예: Piqray 라벨 §14, CIViC EID1234"}
  }
}
```

`clinvar` 필드는 `annotation`으로 합칠지, 따로 둘지 B가 정한다.

### 5.6 파일 관리와 인용

| 항목 | 규칙 |
|---|---|
| ClinVar VCF·`variant_summary` | 100MB가 넘으므로 커밋하지 않는다. 스크립트만 올린다 |
| CIViC TSV | CC0라 올려도 법적 문제는 없지만 크기를 확인한다. 파일명에 받은 날짜를 넣는다 |
| 인용 | CIViC: Griffith M et al., *Nat Genet* 2017;49:170–174. ClinVar: NCBI 고지 문구를 표시한다 |
| 라이선스 재확인 | 도입할 때 각 출처의 약관을 다시 확인하고 날짜를 PROJECT.md에 적는다 |

채택하면 함께 고칠 PROJECT.md 항목: §5 BM-3 표("DB 조회 (OncoKB, ClinVar)" → "로컬 조회 (허가사항 목록, CIViC, ClinVar, VEP)"), §5 판정 기준표 PIK3CA/AKT1/PTEN 줄, §9 유전체 도구의 OncoKB annotator 삭제, §10 데이터셋 표의 OncoKB 행. 결정 날짜와 이유(§5.2)를 함께 적는다.

## 6. 치료 상황 규칙 [협의 완료 2026-10-15]

### 6.1 현재 범주 (`setting.disease`)

| 조건 | 값 |
|---|---|
| `stage.disease_extent = metastatic` 또는 `recurrence.status = distant` | `metastatic` |
| 그 밖 (재발 없음, 국소 재발, 부위 모름, 재발 여부 모름) | `stage.disease_extent` 그대로 |

### 6.2 차수 (`setting.line`)

차수는 정답에 없다. B가 아래 재료로 판단한다.

1. `treatment_history`를 `start_day` 순으로 정렬한다 (`start_day` null은 순서를 알 수 없음).
2. `start_day ≥ recurrence.metastasis_day`인 기록이 전이 이후 요법이다. 그 전은 선행·보조요법이다.
3. 보조약(supportive care)과 골 보호제는 차수를 정하지 않는다.
4. 시작일이 가까운 기록은 한 요법으로 묶는다 (A 분석에서는 28일 이내를 같은 요법으로 봤다. 기준은 B가 정한다).
5. 진행(`best_response = PD`, `stop_reason = progression`)으로 바뀐 요법만 다음 차수로 센다. `planned_switch`(AC→T 같은 계획된 순차)와 `maintenance`는 같은 차수다.

### 6.3 심평원 급여 투여단계 (공고 p.48~63, A 확인)

급여 판정용 차수는 지침 차수와 다르게 센다.

| 규칙 | 근거 |
|---|---|
| 고식적 내분비요법과 고식적 항암화학요법의 투여단계는 **따로** 센다 | 공고 p.55 |
| CDK4/6 억제제 + AI 1차는 고식적 항암화학요법을 받지 않은 환자만 (폐경 전 ribociclib 제외) | p.55 |
| 내분비 2차 이상의 "내분비요법 후 진행": 고식적요법 중 또는 종료 후 **1달** 이내, 보조요법 중 또는 종료 후 **1년** 이내 진행도 인정 | p.57 |
| CDK4/6 억제제 + AI 1차: 비스테로이드성 AI 보조요법 종료 후 **1년 이후** 재발만 | p.55 |
| 항암 2차 이상: anthracycline과 taxane을 포함한 선행·보조요법은 **기간 제한 없이** 1차로 간주 | p.61~62 |
| T-DM1·T-DXd: 보조요법 중 또는 종료 후 **6개월** 이내 재발도 인정 | p.63 |
| sacituzumab govitecan: 선행·보조요법 중 또는 종료 후 **1년** 이내 재발이면 1차로 간주 | p.63 |
| pembrolizumab + 항암 1차 (TNBC): 보조요법 종료 후 **6개월 이후** 재발 포함 | p.58 |
| bevacizumab + paclitaxel 1차: paclitaxel 보조요법 종료 후 **1년 이후** 재발만 | p.58 |

기간 계산은 보조요법의 `end_day`와 `recurrence.metastasis_day`의 차이로 한다.

### 6.4 국소 재발 후 보조요법 (`SET-LOCAL-ADJ`)

| 조건 | 판정 |
|---|---|
| `recurrence.status = locoregional`, `surgery = yes`, `later_distant = no` | 이후 요법은 수술후보조요법 (공고 p.48 "국소재발의 경우 완치 목적의 수술을 시행 후 재발 방지를 위해 투여한 항암요법은 수술후보조요법으로 시행할 수 있음") |
| `surgery_intent` | TCGA는 모두 `unknown`. `unknown`이어도 위 규칙을 적용한다 |

### 6.5 PD-L1

A는 판정하지 않는다. B가 약제별로 판정한다.

| 약제 | 기준 | 근거 |
|---|---|---|
| pembrolizumab + 항암 (TNBC 1차) | 22C3, CPS ≥ 10 | 공고 p.58~59 (주3: IHC 22C3 pharmDx) |
| atezolizumab + nab-paclitaxel | SP142, IC ≥ 1% | ESMO MBC 2026 |

검사법(`assay`)이 기준과 다르면 해당 약제 판정에 쓰지 않는다. `biomarker_record`의 `evidence.assay`, `evidence.score`에 값을 남긴다.

### 6.6 투여 주기 해석

| `interval_basis` | 뜻 |
|---|---|
| `derived` | 투여 일수 ÷ (기록 주기 수 − 1). 예: trastuzumab 47주기, 351일 → 8일 = 매주 투여 |
| `standard` | 약제별 기본값 (`data/dictionaries/drug_classes.csv`의 `cycle_days`) |
| `recorded` | 차트에 주기 길이가 적힘 (가상·실제 차트) |
| `null` | 주기 길이를 알 수 없음 |

- 공고의 "총 18주기"(trastuzumab ± pertuzumab, p.49·53)는 3주 주기 기준이다. 횟수만으로 비교하지 말고 `value × interval_days`로 기간을 비교한다.
- `basis = estimated`는 투여 일수 ÷ 기본 주기 + 1로 계산한 근사치다.

### 6.7 anthracycline 누적 용량 (liposomal doxorubicin 급여 조건, 공고 p.60)

- 조건: doxorubicin 누적 240mg/m² 이상 또는 epirubicin 450mg/m² 이상, 또는 심장 위험 요인.
- 누적 용량 = `dose_per_admin`(mg/m²) × `cycles.value`. 단위가 mg/m²가 아니면(mg, mg/day) 체표면적이 없어 환산할 수 없으므로 "판정 불가"로 둔다.
- 병용 기록(`doxorubicin+cyclophosphamide`, `60+600`)은 약 순서대로 나눈 값이다. 나눌 수 없는 4명은 정답 세트에서 뺐다 (§7).
- 심장 위험 요인은 데이터가 없어 넘기지 않는다 (§9).

## 7. TCGA-BRCA 정답 세트의 특성 (B 테스트용)

| 항목 | 내용 |
|---|---|
| 규모 | **992명** (2026-10-15 크롭본). 병기 `[Discrepancy]`·`[Not Available]`·빈칸 12명, 범주를 정할 수 없는 Stage X 11명, 조직형 NOS·기록 없음 2명, 진단 시 전이성이 아니면서 새 원발암만 있는 19명, 재발 없음인데 재발 후 수술 YES 1명, 현재 전이성인데 전이 진단일·투약·전이 후 항암 투약이 없는 48명, anthracycline 병용 용량을 나눌 수 없는 4명을 뺌 |
| 범주 | 현재 범주: 조기 745, 국소 진행성 215, 전이성 32 |
| 날짜 | 모두 비움 (`not_recorded` 또는 `null`). 대신 진단일 기준 일수(`start_day`, `end_day`, `metastasis_day`)를 넣음 |
| ER·PR 점수 | 넣지 않음. TCGA 점수 열은 입력이 적고(약 19%) 척도가 섞여 있어 잘못 해석될 수 있음 |
| ER 저발현 | 원본 구간 `<10%` + 판정 Positive → `{"range":[1,9],"result":"low_positive"}` **15명** |
| PR 1~9% | 원본 구간 `<10%` + 판정 Positive → `{"range":[1,9],"result":"positive"}` **52명** (B가 `PR-low` 태그를 붙일 대상) |
| ER·PR `<1%` | 원본 구간 `<10%` + 판정 Negative → `{"range":[0,0],"result":"negative"}` ER 48명, PR 76명. **가정이 들어간 값**: 1% 기준은 2010년부터라, 2010년 이전 진단(ER 40명, PR 55명)은 10% 기준 음성이었을 수 있음. ER 저발현 경계 사례 테스트에는 `[1,9]` 환자만 쓰기를 권함 |
| HER2 | score 2+ 또는 Equivocal 195명에 §3.4 보정 적용 (점수 없는 Equivocal 7명은 `2+` 채움). 결과: `{"score":"2+","result":"negative"}` 133명(저발현 후보) / `{"score":"2+","result":"positive"}` 39명 / `{"score":"2+","result":"unknown"}` 20명 / `{"score":"1+","result":"negative"}` 2명 / `{"score":"3+","result":"negative"}` 1명(원자료끼리 어긋남) |
| 재발 재생검 | TCGA 정답에는 쓰지 않음 (§3.5) |
| 유전자 | 종양 엑솜. BRCA1/2는 gBRCA 측정으로 가정 (§4.7). ESR1은 모두 원발 조직 결과 |
| 진단 시 전이 부위 | M0이면 `[Not Applicable]` (532명이 해당). `[Not Available]`은 MX·M1 중 부위 기록이 없는 99명 |
| 없는 칸 | 등급, Ki-67, ECOG, cTNM, pCR/RCB, PD-L1, 수술 가능 여부, 폐경 판정 근거, 진행일. 경계 사례가 필요하면 A가 합성값으로 만들고 `synthetic` 표시 |

## 8. 예시

### 8.1 TCGA 정답 전체 예시 (범주별 1명, 스키마 검증 통과)

| 범주 | 파일 | 특징 |
|---|---|---|
| 조기 | `src/input/examples/patient_state_early_TCGA-5L-AAT0.json` | IIA기, ILC, ER+/HER2 1+(저발현 후보), PIK3CA H1047L, tamoxifen 보조요법 |
| 국소 진행성 | `src/input/examples/patient_state_locally_advanced_TCGA-A2-A0YG.json` | IIIC기, HR+/HER2 3+, AC(21일 간격) → paclitaxel(매주) + trastuzumab → anastrozole |
| 전이성 | `src/input/examples/patient_state_metastatic_TCGA-A2-A0EW.json` | IIIC기 → 1,353일째 뼈 전이 재발. 보조 AC → T → AI(exemestane 투여 중 진행). 전이 후 fulvestrant → tamoxifen → liposomal doxorubicin. doxorubicin 범위 용량(115-116 → 116) |

전이성 예시의 차수 판단: `metastasis_day` 1,353 이후 시작한 fulvestrant(1,366일) = 1L, tamoxifen(1,618일) = 2L, liposomal doxorubicin(1,696일) = 3L. 급여 기준으로는 고식적 내분비요법 1·2차, 고식적 항암화학요법 1차. 골 보호제(zoledronic acid, denosumab)는 차수에서 뺀다.

### 8.2 가상 차트 예시 (입력과 기대 출력)

규칙 설명용 가상 차트다. 재발로 전이된 환자. 진단 시 ER·PR 양성, HER2 IHC 2+ / FISH 음성. 재발 병소에서 PR이 음성으로 바뀜. AI + CDK4/6 억제제에서 진행. PIK3CA 변이 있음.

<!-- validate:patient_state -->
```json
{
  "schema_version": "0.1-draft5",
  "patient_ref": "TCGA-XX-0001",
  "created_at": "2026-10-12T19:00:00+09:00",
  "documents": [
    {"doc_id": "D1", "doc_type": "pathology", "doc_date": null},
    {"doc_id": "D2", "doc_type": "pathology", "doc_date": null},
    {"doc_id": "D3", "doc_type": "molecular", "doc_date": null},
    {"doc_id": "D4", "doc_type": "medication", "doc_date": null}
  ],
  "fields": {
    "diagnosis": {
      "histology": {"status": "present", "value": "IDC", "raw": "invasive ductal carcinoma",
                    "source": {"doc_id": "D1", "quote": "invasive ductal carcinoma"}}
    },
    "stage": {
      "metastatic_sites": {"status": "present", "value": ["bone", "liver"], "raw": "뼈, 간 전이",
                           "source": {"doc_id": "D2", "quote": "뼈, 간 전이"}}
    },
    "receptors": {
      "er_percent": {"status": "present", "value": {"range": [70, 79], "result": "positive"}, "specimen": "metastasis",
                     "raw": "재발 병소 ER 양성 (70-79%)", "source": {"doc_id": "D2", "quote": "ER 양성 (70-79%)"},
                     "history": [{"status": "present", "value": {"range": [90, 99], "result": "positive"}, "specimen": "primary",
                                  "raw": "ER 양성 (90-99%)", "superseded_reason": "recurrence"}]},
      "pr_percent": {"status": "present", "value": {"range": [0, 0], "result": "negative"}, "specimen": "metastasis",
                     "raw": "재발 병소 PR 음성 (<1%)", "source": {"doc_id": "D2", "quote": "PR 음성 (<1%)"},
                     "history": [{"status": "present", "value": {"range": [50, 59], "result": "positive"}, "specimen": "primary",
                                  "raw": "PR 양성 (50-59%)", "superseded_reason": "recurrence"}]},
      "her2_ihc": {"status": "present", "value": {"score": "2+", "result": "negative"}, "specimen": "primary",
                   "raw": "HER2 IHC 2+, FISH 음성", "source": {"doc_id": "D1", "quote": "HER2 IHC 2+"}},
      "her2_ish": {"status": "present", "value": {"result": "not_amplified", "method": "FISH"}, "specimen": "primary",
                   "raw": "FISH 음성", "source": {"doc_id": "D1", "quote": "FISH 음성"}}
    },
    "proliferation": {"ki67_percent": {"status": "not_recorded"}},
    "patient": {
      "gender": {"status": "present", "value": "FEMALE", "raw": "여", "source": {"doc_id": "D4", "quote": "여"}},
      "menopausal_status": {"status": "present", "value": "postmenopausal", "raw": "폐경 후",
                            "source": {"doc_id": "D4", "quote": "폐경 후"}}
    },
    "treatment_history": [
      {"drugs": ["letrozole", "palbociclib"], "setting": "metastatic", "start_date": null, "end_date": null,
       "duration_days": 412, "start_day": 1500, "end_day": 1912, "cycles": null,
       "stop_reason": null, "best_response": "PD",
       "source": {"doc_id": "D4", "quote": "letrozole + palbociclib, PD"}}
    ],
    "anthracycline_drug_dose": {"administered": "negative", "drugs": []},
    "neoadjuvant_response": {},
    "recurrence": {"recurrence_date": {"status": "not_recorded"},
                   "status": {"status": "present", "value": "distant"},
                   "metastatic_sites": {"status": "present", "value": ["bone", "liver"]},
                   "metastasis_day": {"status": "present", "value": 1480}},
    "molecular": {"mutations": {
      "PIK3CA": {"status": "present", "result": "detected", "specimen": "primary",
                 "variants": [{"protein_change": "H1047R", "variant_type": "Missense_Mutation", "vaf": 0.4,
                               "raw": "PIK3CA p.H1047R (missense), VAF 40.0%"}]},
      "ESR1": {"status": "present", "result": "not_detected", "variants": [], "specimen": "primary"}
    }},
    "genomic_reports": [
      {"doc_id": "D3", "report_date": null, "specimen": "primary",
       "raw_text": "종양 조직 체세포 검사(엑솜). PIK3CA p.H1047R (missense), VAF 40.0%. ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음."}
    ]
  },
  "conflicts": []
}
```

B의 기대 출력 (§4 조건을 따른 경우). `oncokb` 칸은 현재 스키마 형식이다. §5 제안이 채택되면 `annotation`으로 바뀐다.

<!-- validate:biomarker_record -->
```json
{
  "schema_version": "0.1-draft",
  "patient_ref": "TCGA-XX-0001",
  "records": [
    {"marker": "ER", "status": "positive", "reason": "재발 병소 70-79% (10% 초과). 원발 90-99%에서 유지",
     "rule_id": "BM2-ER-RANGE", "evidence": {"specimen": "metastasis"},
     "source_span": {"doc_id": "D2", "quote": "ER 양성 (70-79%)"}, "rag_tags": []},
    {"marker": "PR", "status": "negative", "reason": "재발 병소 <1%. 원발 50-59% 양성에서 음성으로 바뀜",
     "rule_id": "BM2-PR-RANGE", "evidence": {"specimen": "metastasis"},
     "source_span": {"doc_id": "D2", "quote": "PR 음성 (<1%)"}, "rag_tags": []},
    {"marker": "HER2", "status": "low", "reason": "IHC 2+, ISH 비증폭 → 저발현 (score를 먼저 읽음. result negative는 ISH 보정값)",
     "rule_id": "BM2-HER2-2PLUS-NOTAMP", "evidence": {"specimen": "primary", "ihc_score": "2+", "ish_result": "not_amplified"},
     "source_span": {"doc_id": "D1", "quote": "HER2 IHC 2+"}, "rag_tags": ["HER2-low"]},
    {"marker": "PIK3CA", "status": "positive", "reason": "p.H1047R 발암성 변이 (BM-3 근거 주석)",
     "rule_id": "BM2-PIK3CA", "evidence": {"specimen": "primary", "variant": "p.H1047R", "vaf": 0.4, "oncokb": "Oncogenic, Level 1"},
     "source_span": {"doc_id": "D3", "quote": "PIK3CA p.H1047R (missense), VAF 40.0%"}, "rag_tags": ["PIK3CA-mut"]},
    {"marker": "ESR1", "status": "retest_needed", "reason": "원발 조직 결과이고, 이후 AI + CDK4/6 억제제에서 진행 (검체·치료 순서로 판단)",
     "rule_id": "BM2-ESR1-RETEST", "evidence": {"specimen": "primary"},
     "source_span": {"doc_id": "D3", "quote": "ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음"}, "rag_tags": []},
    {"marker": "sBRCA1", "status": "negative", "reason": "종양 체세포 검사에서 검출되지 않음", "rule_id": "BM2-SBRCA",
     "evidence": {"specimen": "primary"}, "source_span": {"doc_id": "D3", "quote": "BRCA1, BRCA2"}, "rag_tags": []},
    {"marker": "gBRCA1", "status": "not_recorded", "reason": "생식세포 검사 기록 없음 (가상 차트라 체세포 결과로 대신하지 않음)",
     "rule_id": "BM2-GBRCA", "evidence": {}, "source_span": {"doc_id": "D3", "quote": "종양 조직 체세포 검사"}, "rag_tags": []}
  ],
  "subtype": "HR+/HER2-",
  "setting": {"disease": "metastatic", "line": "2L", "prior_drug_classes": ["aromatase inhibitor", "CDK4/6 inhibitor"],
              "reason": "전이 기준일(1480일) 이후 letrozole + palbociclib에서 진행 후"},
  "tests_needed": [
    {"test": "ESR1 (cfDNA)", "reason": "내분비요법 진행 후 ESR1 재검", "rule_id": "BM4-ESR1-RETEST"},
    {"test": "gBRCA1/2, PALB2", "reason": "HER2 음성 전이성인데 생식세포 검사 기록 없음", "rule_id": "BM4-GBRCA"}
  ]
}
```

`rule_id`, 문장 표현, 근거 주석 값은 형식 설명용 예시다. 실제 값은 B가 정한다.

## 9. 넘기지 않는 정보 (모델 한계)

| 정보 | 이유 | 영향 |
|---|---|---|
| 장기 위기 (visceral crisis) | 데이터와 EMR 모두에서 판단 불가 | ESMO HR+/HER2− 1L에서 내분비요법 + CDK4/6i 대신 항암화학요법을 먼저 고려하는 분기가 빠짐 |
| 심장 위험 요인 | 데이터 없음 | liposomal doxorubicin(고식적 항암화학요법 1차 이상, 공고 p.60)의 심장 위험 요인 조건을 판정 못 함. 누적 용량 조건만 판정 |
| 투약 중 여부 | 확인 불가 | `end_day: null`이 "투약 중"인지 "기록 없음"인지 구분 못 함 |
| 재발 후 수술 의도 | 기록 없음 | 모두 `unknown`. `SET-LOCAL-ADJ`는 수술 여부만으로 적용 |
| 원발암 첫 수술 종류 | 완치 목적 여부를 알 수 없음 | 넘기지 않음 |
| ERBB2 변이 | 목록에서 제외 (협의) | |
| gBRCA | TCGA는 종양 엑솜을 gBRCA로 가정 | 실제 생식세포 결과와 다를 수 있음 |
| 투여 주기 (추정값) | 투여 일수로 계산 | 독성으로 연기된 경우 반영 안 됨 |

## 10. B가 정할 것과 할 일

결정된 것:

- [x] §4.1 ER, §4.2 PR 판정 규칙과 `PR-low` 태그 (2026-10-12, PROJECT.md §5)
- [x] 차수 산출 담당: B (2026-10-15 협의). 재료는 `start_day`, `metastasis_day`
- [x] TCGA 정답의 BRCA1/2를 gBRCA 측정으로 가정 (2026-10-15 협의)

B가 정해서 A에게 알려줄 것:

- [ ] §4.4 HER2 판정 조건 확정
- [ ] 수치 기준 전체의 종양내과·병리과 검토. 바뀌면 A의 정답과 가상 차트도 바꿔야 한다
- [ ] ER·PR 수치와 적힌 판정이 어긋날 때의 처리 (§4.3)
- [ ] HER2 score 2+ + 판정 Positive + ISH 없음(TCGA 6명)을 양성으로 볼지 불확정으로 볼지 (§4.4)
- [ ] 날짜 없이 ESR1 재검을 검체·치료 순서로 판단하는 규칙 (§4.6)
- [ ] gBRCA `not_recorded`일 때 검사 권고를 낼지 (§4.7)
- [ ] ER 저발현(`low`) 환자의 아형 표기: HR+로 둘지, 별도 표시할지
- [ ] `biomarker_record`에서 PR은 `low` 상태값을 쓰지 않는다는 점 반영
- [ ] §5 BM-3 대체 출처 채택 여부 (4명 합의). `evidence.oncokb` → `annotation` 스키마 변경
- [ ] `patient_state` 0.1-draft5 검토 의견. 문제가 없으면 `0.1`로 확정한다

B가 할 일:

- [ ] §6.2 차수 계산 구현 (요법 묶음 기준일, 진행 판단)과 §6.3 심평원 투여단계 별도 계산
- [ ] §6.4 `SET-LOCAL-ADJ` 규칙 추가
- [ ] §4.7 gBRCA 판정 (ClinVar 대조 방법 포함)
- [ ] §6.5 PD-L1 약제별 판정
- [ ] §5 채택 시: 허가사항 원문에서 변이 목록 규칙표 작성(출처 기록), CIViC·ClinVar 다운로드 스크립트(`data/script/`), 로컬 조회 코드(`src/biomarker/`, 외부 API 호출 없음), 테스트(`tests/biomarker/`에 허가 목록 변이, CIViC 전용 변이, PTEN 절단형, ClinVar 상충 변이 각 1건)
