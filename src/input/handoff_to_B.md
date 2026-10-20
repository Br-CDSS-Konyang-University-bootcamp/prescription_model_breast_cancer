# A → B 전달 문서: patient_state 사용 안내, BM-2 판정 조건, BM-3 출처, 치료 상황 규칙

> 작성: 담당 A · 기준 스키마: `schemas/patient_state.json` **0.1-draft6**
> 받는 사람: 담당 B ([2] 바이오마커 모듈, [4] LLM 추천 모듈)
> 관련 문서: [schema_fields.md](schema_fields.md) (필드별 상세), [tcga_mapping.md](tcga_mapping.md) (TCGA 정답 규칙), [schemas/README.md](../../schemas/README.md), PROJECT.md §5·§10
> 이 문서는 아래 세 문서를 합친 것이다 (2026-10-15). 이전 문서는 git 이력에 있다.

| 날짜 | 내용 | 상태 |
|---|---|---|
| 2026-10-12 | patient_state 사용 안내와 BM-2 판정 조건 (기존 `handoff_to_B.md`, draft4) | ER·PR 결정, 나머지 A 제안 |
| 2026-10-13 | BM-3 근거 주석에서 OncoKB를 빼고 대체 출처를 쓰는 제안 (기존 `handoff_to_B_bm3.md`) | **결정** (2026-10-15, 스키마 변경만 4명 합의 필요) |
| 2026-10-15 | draft5: 차수 재료, 재발·전이, PD-L1, 유전자 변이, anthracycline 용량, gBRCA 규칙 (기존 `handoff_to_B_draft5.md`) | **협의 완료** |
| 2026-10-16 | B 진행 현황과 남은 작업 순서 정리 (§10). 차수·투여단계·누적 용량 계산은 A로, 국소 재발 후 보조요법은 B로 담당 변경 (§6) | **정리** |
| 2026-10-16 | §10 갱신: 유전자 7개 BM-2·BM-4 완료(PR #2) 반영, A의 차수 계산 함수(`src/input/common/lines.py`)와 약제 사전 추가 | **정리** |
| 2026-10-16 | draft6: 판정 기준일 `index_day`, 첫 재발일 `recurrence.recurrence_day`, 투약별 차수 `line`·`endocrine_line`·`chemo_line`, 차수 간주 규칙 `deemed_lines` (§6.2·§6.3a). 차수 칸 위치 결정 (§10.4). 2026-10-19: 미시행의 `raw` 고정 표기 "결과 대기"·"예정", 유전자 칸에 `raw` 추가 (§0 5번) | **제안** (4명 검토) |

## 목차

0. 요약
1. 전달 방식
2. A와 B의 경계
3. B가 받는 값 (JSON 구조, 공통 틀, 수용체, 재발, 유전자, 전체 필드표)
4. BM-2 판정 조건
5. BM-3 근거 주석 출처 (결정)
6. 치료 상황 규칙 (현재 범주, 차수, 급여 투여단계, 국소 재발, PD-L1, 주기, anthracycline)
7. TCGA-BRCA 정답 세트의 특성
8. 예시
9. 넘기지 않는 정보 (모델 한계)
10. B 진행 현황과 남은 작업 순서

## 0. 요약

1. A는 환자마다 `patient_state` JSON 하나를 넘긴다. 형식은 `schemas/patient_state.json`(0.1-draft6)이고, 스키마 검증을 통과한 것만 보낸다.
2. A는 **적힌 값을 표준 표기로 정리**만 한다. 양성·음성·저발현 판정은 B가 한다. 예외는 둘이다. HER2 IHC의 `result`는 A가 ISH 결과로 보정해서 넘긴다 (§3.4). 그래서 **HER2는 `result`보다 `score`를 먼저 읽어야** 저발현을 놓치지 않는다. 또 TCGA 정답의 ER `low_positive`·PR `[1, 9]` 구간은 원본에 적힌 판정이 아니라, A가 크롭 단계에서 원본 구간 `<10%`와 판정 Positive를 나눠 만든 값이다 (§7).
3. 저발현 판정값(`low_positive`)은 **ER에만** 있다 (ASCO/CAP 2020). PR은 양성/음성 두 범주만 쓴다 (§4.2).
4. 재발 환자는 **재생검(재발 병소) 결과가 `value`**이고, 원발 결과는 `history[]`에 있다 (§3.5). 가상 차트·실제 차트에만 해당하고, **TCGA 정답은 원발 결과만** 쓴다.
5. `not_done`(미시행)과 `not_recorded`(기록 없음)는 다르다. 미시행만 검사 권고 대상이다. 미시행 중 검사를 의뢰·예약한 경우는 `raw`에 고정 표기 `"결과 대기"`(결과를 기다림) 또는 `"예정"`(아직 시행 전)이 들어간다 (draft6, schema_fields.md §2). 이때는 검사 권고 대신 "결과 확인 필요"로 내는 것을 제안한다 (B 결정).
6. **차수(line)와 심평원 투여단계는 A가 `patient_state`로 옮길 때 계산한다** (2026-10-16 담당 변경. 2026-10-15에는 B가 판단하기로 했었다). 결과는 `treatment_history[]`의 `line`·`endocrine_line`·`chemo_line`과 `fields.deemed_lines`에 넣는다 (draft6, §6.2·§6.3a). 재료는 투약 시작·종료일(`treatment_history[].start_day`, `end_day`)과 전이 기준일(`recurrence.metastasis_day`)이다. 모두 진단일 = 0인 정수다 (§6.2).
7. **현재 범주**: 진단 시 IV기이거나 원격 전이 재발이면 전이성. 국소 재발은 전이가 아니다 (§6.1). **국소 재발 후 수술**(이후 원격 전이 없음)이면 이후 요법은 수술후보조요법이다 (§6.4, 차트를 보고 판단해야 해서 B 담당).
8. **gBRCA**: TCGA 정답 세트에서는 BRCA1·BRCA2 결과를 gBRCA 측정으로 가정한다. B가 positive / negative / vus를 판정한다 (§4.7).
9. **PD-L1은 발현 점수**다 (변이 아님). 검사법·점수만 넘기고 약제별 판정은 B가 한다 (§6.5).
10. **유전자 변이**는 `molecular.mutations`에 유전자별로 넘긴다: 변이 있음 / 변이 없음 / 미시행 (§3.6).
11. **anthracycline 투약 용량**과 **주기 길이가 붙은 투여 주기**를 넘긴다 (§6.6·§6.7). 누적 용량은 A가 변환할 때 `anthracycline_drug_dose`에 계산해 넣는다 (2026-10-16 담당 변경).
12. BM-3(변이 근거 주석)은 OncoKB 대신 허가사항·CIViC·ClinVar·VEP를 쓴다 (§5, 2026-10-15 결정).
13. §4.1 ER, §4.2 PR 판정 규칙은 2026-10-12 결정이다 (2026-10-15에 ER은 Allred 총점 우선, PR은 Allred 총점 우선 + 9% 기준으로 변경, PR-low 태그 삭제). HER2·Ki-67·아형 규칙도 2026-10-15에 확정했다 (PROJECT.md §5). 유전자 판정 규칙(§4.6·§4.7·§5.4)은 B가 2026-10-16에 1차 규칙으로 다시 넣었다 (`src/biomarker/README.md`). 진행 현황과 남은 순서는 §10.

## 1. 전달 방식

| 항목 | 내용 |
|---|---|
| 형식 | `schemas/patient_state.json` (JSON Schema 2020-12). 환자 1명 = JSON 1개 |
| 개발 중 | 파일로 전달: `tests/fixtures/patient_state/<patient_ref>.json` (예정. 공용 폴더라 4명 합의 후 생성). 지금은 범주별 예시 3명이 `src/input/examples/`에 있다 (§8.1) |
| TCGA 변환 | `src/input/script/tcga_to_patient_state.py`의 `convert(load_rows())`가 크롭본 874명을 `{patient_id: patient_state}`로 바로 돌려준다. 기본은 파일을 만들지 않는다 (`--out`을 줄 때만 저장). `data/truth/`는 2026-10-16에 지웠다 |
| 연결 후 | 함수 반환값: A의 `run(chart_text) → patient_state` 결과를 B의 `assess(patient_state) → biomarker_record`가 받는다. B 코드는 `src/biomarker/BM1_ER,PR,HER2,Ki_67,subtype.py`이고, 파일 이름에 쉼표가 있어 `importlib`로 경로를 지정해 불러온다 (`tests/biomarker/test_bm.py` 참고) |
| 검증 | A가 보내기 전에 검증한다. B도 받을 때 검증하면 버전 불일치를 바로 알 수 있다 (`schema_version` = `"0.1-draft6"`) |
| TCGA 정답 세트 | 874명 (§7). 변환 결과를 B에 넣으면 874명 전원 `patient_state`·`biomarker_record` 스키마를 통과한다 (2026-10-16 확인) |

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
├── schema_version            "0.1-draft6"
├── patient_ref               가명 ID (TCGA는 바코드)
├── created_at                생성 시각
├── index_day                 판정 기준일 (진단일 = 0) [draft6]
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
│   │   ├── er_percent        {percent, range, allred, result}
│   │   ├── pr_percent        {percent, range, allred, result}
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
│   │   ├── line, endocrine_line, chemo_line   전이 후 차수 (전이 전 null) [draft6]
│   │   └── source
│   ├── deemed_lines[]        차수 간주 규칙 4개 {rule_id, category, status, basis, regimen_refs, gap_days, notice_page} [draft6]
│   ├── at_index              기준일 시점 값 {age, recent_therapy_28d {status yes/no/unknown, basis, regimen_refs, gap_days}} [2026-10-20, 검토 전]
│   ├── anthracycline_drug_dose
│   │   ├── administered      positive / negative / No value
│   │   └── drugs[]
│   │       ├── drug, timeline_index, combined_with[]
│   │       ├── dose_per_admin   {value, unit} 또는 "No value"
│   │       ├── cycles           cycles 형식 또는 "No value"
│   │       ├── total_dose       {value, unit} 또는 "No value"
│   │       └── raw, source
│   ├── neoadjuvant_response
│   │   ├── pcr               yes / no
│   │   └── rcb               RCB-0 ~ RCB-III
│   ├── recurrence
│   │   ├── recurrence_date, adjuvant_endocrine_end_date
│   │   ├── status            none / distant / locoregional / site_unknown / unknown
│   │   ├── metastatic_sites  재발 전이 부위
│   │   ├── metastasis_day    전이 기준일 (진단일 = 0)
│   │   ├── recurrence_day    첫 재발일 (국소·원격, 진단일 = 0) [draft6]
│   │   ├── surgery           재발 후 수술 yes / no / unknown
│   │   ├── surgery_intent    curative / palliative / unknown
│   │   └── later_distant     국소 재발 후 원격 전이 yes / no / unknown
│   ├── molecular
│   │   └── mutations
│   │       └── ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2
│   │           ├── status    present / not_done / not_recorded
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
| `allred` | Allred 점수 `{total, ps, is}` 중 적힌 것 | `Allred 6/8 (PS 4, IS 2)` → `{"allred": {"total": 6, "ps": 4, "is": 2}}` |
| `result` | 차트에 적힌 판정 | ER: `positive` / `low_positive` / `negative` / `indeterminate`, PR: `positive` / `negative` / `indeterminate` |

- `low_positive`는 **ER에만** 있다.
- Allred: total = ps + is (0, 2~8). ps = 비율 점수 (0 없음, 1 <1%, 2 1~10%, 3 11~33%, 4 34~66%, 5 ≥67%), is = 강도 점수 (0~3).
- 척도가 적혀 있지 않은 점수(예: `ER score 6`)는 `raw`에만 남기고 `value`에 넣지 않는다.
- ER·PR에는 `score` 키가 없다 (2026-10-15 결정). Allred 총점은 `allred.total`, 강도는 `allred.is`로만 받는다.
- **TCGA 정답에는 `allred`가 없다** (§7).

### 3.4 HER2 (`receptors.her2_ihc`, `receptors.her2_ish`)

| 칸 | `value` | 비고 |
|---|---|---|
| `her2_ihc` | `{score, faint, result}` 중 있는 것 모두 | `score`: `0`, `1+`, `2+`, `3+` / `faint`: IHC 0이면서 10% 이하 세포에 희미한 불완전 막 염색이 있으면 `true` (초저발현 판정용, 그 외에는 칸을 만들지 않음) / `result`: `positive`, `negative`, `equivocal`, `indeterminate`, `unknown` |
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

### 3.7 필드별 전체 출력과 B의 정규화 (TCGA 정답 874명 기준)

**문서 단위**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `schema_version` | `"0.1-draft6"` | 고정 | 버전이 다르면 거부 |
| `patient_ref` | 문자열 | TCGA 바코드 | 그대로 |
| `documents[]` | `{doc_id, doc_type, doc_date}` | `doc_date`는 모두 `null` | |
| `conflicts[]` | `{field, candidates[], note}` | 대부분 빈 배열 | 자동 선택하지 말고 확인 요청 |

**diagnosis / stage**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `diagnosis.diagnosis_date` | 날짜 | 모두 `not_recorded` | 순서는 `*_day`로 판단 |
| `diagnosis.histology` | `IDC` / `ILC` / `mucinous` / `metaplastic` / `invasive_NOS` / `other` | 원본 조직형 변환 | |
| `diagnosis.grade` | 1 / 2 / 3 | 모두 `not_recorded` | abemaciclib 보조요법 조건(등급 3) 판정 불가 |
| `stage.ptnm` | `{t, n, m, edition}` | TX·NX·MX는 `not_assessed`. `edition` null 122 | AJCC 판(3~7판)이 섞여 있음 |
| `stage.ctnm` | 같음 | 모두 `not_recorded` | |
| `stage.group` | `IIA`, `IIIC`, `IV`, `not_assessed` | | |
| `stage.positive_ln_count` | `{positive, examined}`. 각각 정수 또는 `[Not Available]` | | 공고 보조요법 조건 (4개 이상, 1~3개 등) |
| `stage.disease_extent` | `early` / `locally_advanced` / `metastatic` | 진단 시 범주 | 현재 범주는 §6.1 |
| `stage.metastatic_sites` | 부위 목록 / `[Not Applicable]` / `[Not Available]` | `[Not Applicable]` 781, `[Not Available]` 83, 부위 목록 10. M0(`cM0(i+)` 포함)이면 `[Not Applicable]` (2026-10-15) | `[Not Available]`은 MX·M1이면서 부위 기록이 없는 경우뿐 |
| `stage.operable` | `yes` / `no` / `unknown` | 없음 | 국소진행성의 선행·고식 구분 불가 |

**receptors / proliferation / patient**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `receptors.er_percent`, `pr_percent` | §3.3 | `range` + `result`. 원본 구간이 없으면 `result`만 (ER 452명). 미시행 ER 0, PR 0 (ER·PR·HER2 모두 미시행 43명과 ER 또는 PR 미시행 2명은 정답 세트에서 뺌) | §4.1·§4.2. `result`만 있으면 비율을 모름 |
| `receptors.her2_ihc`, `her2_ish` | §3.4 | `score` 없이 `result`만 있는 환자 261 (negative 218, positive 40, indeterminate 3). 원본끼리 어긋남: `1+`·positive 10, `3+`·negative 3 | `score`를 먼저 읽기 (§4.4). `result`만 negative면 `indeterminate` |
| `receptors.pdl1` | `{assay, score_type, score}` | 모두 `not_recorded` | §6.5 |
| `proliferation.ki67_percent` | `{percent, range, result}` | 모두 `not_recorded` | |
| `patient.gender`, `age` | `FEMALE` / 정수 | 모두 FEMALE | |
| `patient.menopausal_status` | 폐경 4종 | 진단 시점 값. 기록 없음 55, 미시행 5 | 공고는 "약제 전환 시점"의 폐경 상태를 요구함 |
| `patient.menopausal_basis` | `age_amenorrhea` / `fsh` / `oophorectomy` / `unknown` | 없음 | |
| `patient.ecog` | 0~4 | 모두 `not_recorded` | |

**treatment_history[]** (투약 기록 2,033개, 투약 기록이 있는 환자 655명. 한 환자가 여러 개를 가질 수 있다)

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `drugs` | 일반명 소문자 배열 | 병용 기록은 여러 개 (`["doxorubicin", "cyclophosphamide"]`) | 약제 계열로 바꿔 `prior_drug_classes`에 사용 |
| `setting` | `neoadjuvant` / `adjuvant` / `metastatic` / `unknown` | adjuvant 1,928, neoadjuvant 8, metastatic 97 | A의 유도값 (시작일 ≥ 전이 기준일 → metastatic, 선행요법 이력 Yes인 환자의 첫 투약 → neoadjuvant). 수술일이 없어 neoadjuvant 8명은 수작업 확인 대상 |
| `start_date`, `end_date` | 날짜 | 모두 `null` | |
| `start_day`, `end_day` | 정수 / `null` (진단 전이면 음수) | 크롭본 `drug_start_days`, `drug_end_days`. `start_day` null 84, `end_day` null 495, 음수 6 | **차수 계산의 핵심** (§6.2). `end_day` null = 종료 모름 |
| `duration_days` | 정수 / `null` | `end_day − start_day` | |
| `cycles` | `{value, basis, interval_days, interval_basis}` / `null` | 기록값 720, 추정값 661, null 652 | §6.6 |
| `progression_day` | 정수 / `null` | 모두 `null` | 공고 "종료 후 1달 이내 진행" 판정 불가 |
| `stop_reason` | `progression` / `toxicity` / `completed` / `planned_switch` / `maintenance` / `other` / `null` | 모두 `null` | `planned_switch`·`maintenance`는 같은 차수 |
| `best_response` | `CR` / `PR` / `SD` / `PD` / `unknown` | | `PD`는 진행으로 차수가 넘어갔다는 근거 |

골 보호제(zoledronic acid, denosumab 등)와 보조약도 기록에 들어 있다. 차수를 셀 때는 뺀다.

**anthracycline_drug_dose**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `administered` | `positive` / `negative` / `No value` | positive 348, negative 313, No value 213 | `No value` = 투약 기록 없음 (투여 안 함이 아님) |
| `drugs[].drug` | `doxorubicin` / `epirubicin` / `liposomal doxorubicin` | 313 / 37 / 2 | mitoxantrone은 제외 |
| `drugs[].timeline_index`, `combined_with`, `raw` | 정수, 배열, 문자열 | | 대조용 |
| `drugs[].dose_per_admin` | `{value, unit}` / `"No value"` | No value 190, mg/m² 160 (2026-10-20, 860명) | 원문이 범위(100-102)면 최대값. 2026-10-20부터 크롭 단계에서 mg/m²로 맞춤 (mg는 체표면적 1.84 m² 추정으로 나눔, tcga_mapping.md §3.7a) |
| `drugs[].cycles` | `cycles` 형식 (`basis: recorded`만) / `"No value"` | 기록 189, No value 163 | |
| `drugs[].total_dose` | `{value, unit}` / `"No value"` | No value 197, mg/m² 153 (2026-10-20, 860명) | 152건 중 92건은 mg ÷ 1.84 추정 (§6.7) |

**recurrence**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `recurrence_date`, `adjuvant_endocrine_end_date` | 날짜 | 모두 `not_recorded` | 대신 `*_day`와 `treatment_history` 사용 |
| `status` | `none` / `distant` / `locoregional` / `site_unknown` / `unknown` | none 688, unknown 152, distant 22, locoregional 12. `site_unknown`(재발했지만 부위 모름)은 정답 세트에서 뺐다 (2026-10-15) | §6.1 |
| `metastatic_sites` | 부위 목록 | distant 22명만 | 국소 부위(`other: Axilla` 등)가 섞일 수 있음. 처방·급여 판정에는 쓰지 않음 |
| `metastasis_day` | 정수 (진단 시 IV기 = 0) | 크롭본 `metastasis_dx_days`. 전이성 28명만. 사건별 진단일은 크롭본 `nte_event_types`·`nte_dx_days` | **차수 기준점** (§6.2) |
| `surgery` | `yes` / `no` / `unknown` | 재발 34명: yes 15, no 17, unknown 2 | §6.4 |
| `surgery_intent` | `curative` / `palliative` / `unknown` | 모두 `unknown` | |
| `later_distant` | `yes` / `no` / `unknown` | 17명 (모두 `no`) | §6.4 |

**molecular / genomic_reports**

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `molecular.mutations.{유전자}` | §3.6 | 유전자마다 미시행 28명 | |
| 변이 있음 건수 | | PIK3CA 280, PTEN 49, AKT1 23, BRCA2 24, BRCA1 24, ESR1 9, PALB2 6 | `variants[]`로 BM-3 (§5) |
| `molecular.mutations.{유전자}.specimen` | `primary` | 모두 원발 조직 (미시행 28명은 칸 없음) | ESR1은 진행 후 재검 대상 (§4.6) |
| `genomic_reports[]` | `{doc_id, report_date, specimen, raw_text}` | 가상 보고서 원문 846명 (미시행 28명은 빈 배열) | `molecular` 우선 |

## 4. BM-2 판정 조건

§4.1·§4.2는 2026-10-12 결정, §4.7은 2026-10-15 협의, 나머지는 A 제안이다. A는 이 조건으로 정답 데이터와 가상 차트를 만든다. B가 확정한 조건과 정답이 같아야 평가가 맞으므로, 바꾸면 A에게 알려 주기 바란다.

### 4.1 ER [결정 2026-10-12]

ASCO/CAP 2020: 1% 미만 음성, 1~10% **저발현(Low Positive)**, 10% 초과 양성.

**Allred 총점을 먼저 본다 [변경 2026-10-15].** 저발현(`low`)은 **Allred 3~4점**, **Allred 5점 중 비율이 1~10%**, 또는 **Allred 없이 비율(percent·range)이 1~10%**일 때만 판정한다. 모든 환자를 percent → range → allred 순서로 보는 것이 아니다. TCGA 정답에는 Allred가 없어 `range`와 `result`로 판정한다.

| 순서 | 있는 값 | 조건 → 상태값 |
|---|---|---|
| 1 | `allred.total` | 0~2 → `negative` / **3~4 → `low`** / **5 → 비율로 `low`·`positive`를 가름** (순서 2). 비율 정보가 없으면 `unknown` + 비율 확인 권고 / 6~8 → `positive` |
| 2 | 비율: `percent`, `range`, `allred.ps` (Allred가 없거나 5점일 때) | <1% (`range` `[0,0]`, ps 0~1) → `negative` / **1~10% (`range` 최대 ≤10, ps 2) → `low`** / >10% (`range` 최소 ≥10, ps 3~5) → `positive` (10%가 걸치는 구간은 실무상 양성). **0부터 시작하는 구간은 최대값을 percent로 보고 판정** (2026-10-15): `[0,1]` → 음성, `[0,9]`·`[0,10]` → 저발현, `[0,15]` → 양성 |
| 3 | `result`만 | 적힌 판정을 따름 (`low_positive` → `low`) |
| 4 | 위 값이 하나도 없음 (`result`가 indeterminate인 경우 포함) | `unknown` [결정 2026-10-15] |

0단계: 칸의 `status`만 본다 (`not_done` → 미시행, 칸 없음·`not_recorded` → 기록 없음). Allred 총점은 ps(비율 점수) + is(강도 점수)이고 percent·range·ps는 비율만 잰 값이라, 총점이 있으면 총점을 따른다 (총점과 비율이 달라도 총점). ER·PR에는 `score` 키가 없다 (강도는 `allred.is`). 재발 환자는 `value`(가장 최근 재생검 결과)로 판정하고 원발 결과(`history[]`)는 설명에만 쓴다. **ER에는 `indeterminate`를 쓰지 않는다** (2026-10-15 결정).

**Allred 총점 5점 규칙:** 같은 5점이라도 비율에 따라 판정이 갈린다.

| Allred | 조합 | 판정 |
|---|---|---|
| 총점 5, **ps 2** (is 3) | 비율 1~10% | **`low`** (ER-low) |
| 총점 5, **ps 3** (is 2) | 비율 11~33% | **`positive`** |
| 총점 5, ps 4 (is 1) | 비율 34~66% | `positive` |
| 총점 5, ps 없음 | 알 수 없음 | `indeterminate` + 비율 확인 권고 |

**Allred 총점 3~4점 규칙 [결정 2026-10-15]:** 비율과 상관없이 `low`(ER-low)로 판정한다.

| 총점 | 가능한 조합 (ps + is) | 판정 |
|---|---|---|
| 3 | 1+2 (<1%), 2+1 (1~10%) | `low` |
| 4 | 1+3 (<1%), 2+2 (1~10%), 3+1 (11~33%) | `low` |
| 5 | 2+3 (1~10%), 3+2, 4+1 | 비율로 가름. 비율이 없으면 `indeterminate` |

3~4점에는 비율상 <1%(ps 1)나 11~33%(ps 3)인 조합도 있지만, 팀 결정으로 저발현 하나로 단순화했다.

참고: Allred 원래 기준은 총점 3 이상을 양성으로 보지만, ASCO/CAP 1% 기준과 맞지 않는다 (ps 1 = 1% 미만). ER 저발현으로 판정하면 `rag_tags`에 `ER-low`를 붙인다.

### 4.2 PR [결정 2026-10-12, 순서와 기준 변경 2026-10-15]

PR에는 저발현 범주가 없다. **PR에는 `low` 상태값을 쓰지 않는다.** 2026-10-15 팀 결정으로 Allred 총점을 먼저 보고, 비율 기준을 9%로 둔다 (ASCO/CAP 2020의 1% 기준과 다름). TCGA 정답의 PR `[1,9]` 49명은 최대값 9라 `positive`다.

| 순서 | 있는 값 | 조건 → 상태값 |
|---|---|---|
| 1 | `allred.total` (있을 때만) | 0~2 → `negative` / 3 이상 → `positive` |
| 2 | `range` `[x, y]` | `[0,0]` → `negative` / 최대값 y ≥ 9 → `positive` / 그 밖(y < 9) → `negative` |
| 3 | `percent` | ≥ 9 → `positive` / < 9 → `negative` |
| 4 | `allred.ps` | 0~1 → `negative` / 2~5 → `positive` |
| 5 | `result`만 | `positive`·`negative`는 그대로 / `low_positive` → `positive` |
| 6 | 쓸 값이 없음 (`result`가 `indeterminate`인 경우 포함) | `unknown` |

처음 맞는 값으로 판정한다. **PR에는 `indeterminate`를 쓰지 않는다.**

**`PR-low` 태그: 쓰지 않는다 [결정 2026-10-15].** ASCO·ESMO 지침에 PR-low 범주가 없다.

### 4.3 ER·PR 공통: 값끼리 어긋날 때

예: `{"percent": 5, "result": "positive"}`, `{"range": [0,0], "result": "positive"}`.

- 제안: 수치로 판정하고(ER은 §4.1 순서: Allred 총점 → 비율, PR은 §4.2 순서: `allred.total` → `range` → `percent` → `allred.ps`), 적힌 판정과 다르면 `reason`에 둘 다 적고 확인이 필요하다고 표시한다.
- TCGA 정답에서는 이런 경우가 없도록 크롭 단계에서 맞췄다.

### 4.4 HER2 (score를 먼저 읽음) [결정 2026-10-15]

| 단계 | `her2_ihc.score` | `her2_ish` (FISH·SISH) | 판정 |
|---|---|---|---|
| 1 | 3+ | 상관없음 | `positive` (무조건) |
| 2 | 2+ | 증폭 | `positive` |
| 2 | 2+ | 비증폭 | `low` |
| 2 | 2+ | 미시행·기록 없음 + 적힌 판정 positive | `positive` + ISH 검사 권고 |
| 2 | 2+ | 미시행·기록 없음 + 적힌 판정 negative | `negative` |
| 2 | 2+ | equivocal, 또는 ISH 없이 적힌 판정이 그 외 | `unknown` (판정 불가). TCGA 정답에서는 삭제 |
| 3 | 1+ | 상관없음 | `low` |
| 4 | 0 + 10% 미만 세포의 미약한 막 염색 (`faint: true`) | 증폭 외 | `ultralow` (심평원 기준 최종 음성, 아형은 HER2-) |
| 4 | 0 (`faint` 없음·false) | 증폭 외 | `negative` |
| 4 | 0 | 증폭 | `unknown` + 원자료 확인 (데이터 오류로 봄, TCGA 0명) |
| 5 | 없음 | 증폭 | `positive` |
| 5 | 없음 | `result`만 positive | `positive` |
| 5 | 없음 | `result`만 negative | `negative` (0과 저발현은 구분 못 함) |
| 5 | 없음 | 비증폭 | `negative` (0과 저발현은 구분 못 함) |
| 5 | 없음 | `result`만 equivocal·indeterminate·unknown | `unknown`. TCGA 정답에서는 삭제 |
| 5 | IHC 미시행 | ISH 없음 | `not_done`. TCGA 정답에서는 삭제 |
| 5 | 없음 | 없음 | `not_recorded`. TCGA 정답에서는 삭제 |

`zero`와 `indeterminate`는 쓰지 않는다. `HER2-low`·`HER2-ultralow` 태그도 쓰지 않고 상태값 `low`·`ultralow`로만 표시한다. 재생검(전이 병소) 결과가 있으면 그 점수로 같은 규칙을 적용하고, 없으면 기존 점수를 쓴다. `evidence`에 IHC 점수·ISH 결과를 따로 남기지 않는다.

TCGA 정답 세트에서 IHC 2+ + 적힌 판정 Positive + ISH 결과 없음 5명은 한때 뺐다가(985명 → 980명), ISH가 없으면 적힌 판정을 따르기로 해 다시 넣었다 (869명 → 874명). 같은 날 HER2 판정 불가 62명(IHC 2+인데 ISH가 equivocal·미시행·기록 없음 21명, IHC 점수 없이 판정이 Indeterminate·미시행·기록 없음이고 ISH도 없는 41명)도 뺐다 (931명 → 869명). 그래서 TCGA 정답의 HER2는 모두 positive·low·ultralow·negative 중 하나로 판정된다. `score 0` + ISH 증폭은 크롭 스크립트에도 삭제 규칙으로 넣었다 (해당 0명).

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

## 5. BM-3 근거 주석 출처: OncoKB 대신 대체 출처 [결정 2026-10-15. §5.5 스키마 변경은 4명 합의 필요]

### 5.1 요약

1. **OncoKB는 쓰지 않는다 (2026-10-15 결정).** 우리 팀 조건(기관 이메일 없음, 수동 심사 대상 제외, 부트캠프)에 맞지 않고, AI/ML 학습에 쓰는 것을 학술 목적까지 포함해 금지한다.
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

### 5.4 바이오마커별 판정

PROJECT.md §5 판정 기준표에 반영했다 (2026-10-15). 위에서부터 처음 맞는 줄로 판정한다.

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

## 6. 치료 상황 규칙 [협의 완료 2026-10-15, 담당 변경 2026-10-16]

담당 (2026-10-16): §6.2 차수, §6.3 심평원 투여단계, §6.7 누적 용량은 **A가 변환 단계에서 계산**한다. §6.4 국소 재발 후 보조요법은 차트를 보고 판단해야 해서 **B**가 맡는다. §6.5 PD-L1은 B가 유전자 판정과 함께 한다. 약제명 사전(차트마다 다른 표기를 같은 약으로 묶기)은 A가 만든다.

### 6.1 현재 범주 (`setting.disease`)

| 조건 | 값 |
|---|---|
| `stage.disease_extent = metastatic` 또는 `recurrence.status = distant` | `metastatic` |
| 그 밖 (재발 없음, 국소 재발, 부위 모름, 재발 여부 모름) | `stage.disease_extent` 그대로 |

### 6.2 차수 (`treatment_history[].line`, `endocrine_line`, `chemo_line`) [draft6]

A가 변환할 때 계산해 투약마다 넣는다 (`src/input/common/lines.py`의 `palliative_lines`, 2026-10-16). 전이 전 투약·보조약·골 보호제·시작일 없는 투약은 `null`. B는 이 값으로 `setting.line`을 채운다. 규칙:

1. `treatment_history`를 `start_day` 순으로 정렬한다 (`start_day` null은 순서를 알 수 없음).
2. `start_day ≥ recurrence.metastasis_day`인 기록이 전이 이후 요법이다. 그 전은 선행·보조요법이다.
3. 보조약(supportive care)과 골 보호제는 차수를 정하지 않는다.
4. 묶음 첫 투약에서 시작일이 28일 이내인 기록은 한 요법으로 묶는다.
4a. 요법 종류: 항암·HER2 표적·면역항암제가 하나라도 있으면 항암, 없고 내분비요법이 있으면 내분비, 그 밖의 표적치료만 있으면 항암. 내분비 차수와 항암 차수를 따로 센다 (§6.3).
5. 진행(`best_response = PD`, `stop_reason = progression`)으로 바뀐 요법만 다음 차수로 센다. `planned_switch`(AC→T 같은 계획된 순차)·`maintenance`·`toxicity`는 같은 차수다. 끝난 이유를 모르면 다음 차수로 센다 (TCGA는 대부분 이 경우).
5a. [2026-10-20] 끝난 이유를 몰라도 셋은 같은 차수다. (1) 순차 요법: anthracycline 요법이 끝나고 28일 이내에 taxane(± HER2 표적) 요법 시작 (AC → paclitaxel). (2) 병용 추가: 앞 요법이 끝나기 전에 시작 (capecitabine 투여 중 bevacizumab 추가). (3) 유지요법: 항암 요법 다음에 내분비 요법이 시작됨 (진행 기록 없음). 근거는 `notes`에 남긴다.
5b. [2026-10-20] 같은 차수 안에서 요법 종류가 바뀌면(항암 → 내분비 유지요법 등) 그 종류의 차수는 이 차수에서 처음일 때만 하나 올린다 (예: AC → letrozole 유지 = 1차, 항암 1차·내분비 1차).

### 6.3a 차수 간주 규칙 (`fields.deemed_lines`) [draft6]

공고는 선행·보조요법을 고식적 요법 1회로 간주하는 경우가 있다. 약마다 기간이 달라 차수를 하나로 낼 수 없으므로, **실제 차수는 그대로 두고 규칙 4개의 충족 여부를 따로 낸다.** 급여 판정은 행마다 맞는 규칙을 골라 "실제 차수 + (그 규칙이 `met`이면 1)"로 투여단계와 비교한다.

| 규칙 | 공고 | 올리는 차수 | 조건 | 쓰는 요법 |
|---|---|---|---|---|
| `DEEM-ANTHRA-TAXANE` | p.61~62 | 항암 | 선행·보조에 anthracycline과 taxane이 모두 있음 (기간 제한 없음) | gemcitabine·vinorelbine 등 2차 이상, 40장 pembrolizumab + gemcitabine + carboplatin |
| `DEEM-SG-1Y` | p.63 | 항암 | 선행·보조 종료 후 365일 이내 전이 | sacituzumab govitecan |
| `DEEM-HER2ADC-6M` | p.62~63 | 항암 | trastuzumab 포함 보조요법 종료 후 183일 이내 전이 | T-DM1, T-DXd |
| `DEEM-ENDO-ADJ-1Y` | p.57 | 내분비 | 보조 내분비요법 종료 후 365일 이내 전이 | AI·exemestane + LHRH, CDK4/6 + fulvestrant (2차 이상) |

- `status`: `met` / `not_met` / `unknown`(종료일이 없어 기간을 알 수 없음) / `not_applicable`(전이성 아님). 기간은 종료일부터 전이 기준일까지 세고, 종료일이 없으면 시작일을 하한으로 쓴다.
- 기준 시점은 첫 재발일이 아니라 전이 기준일이다.

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
| lapatinib + letrozole 1차 (HER2+, HR+): AI 보조요법 종료 후 **1년 이후** 재발만 | p.58 |
| trastuzumab + anastrozole (HER2+, HR+): trastuzumab·AI 보조요법 종료 후 **1년 이후** 재발만 | p.60 |
| ribociclib + AI 1차, 폐경 전: AI 외 내분비요법·항암화학요법 보조요법 중 또는 종료 후 **1년 이내** 재발, 또는 고식적 항암화학요법 1차 실패도 급여 | p.55 |

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
- 누적 용량 = `total_dose`(mg/m²). 2026-10-20부터 A가 크롭 단계에서 모두 mg/m²로 맞춘다. mg로 적힌 기록은 체표면적 1.84 m²(추정)로 나눈 값이라, 240 mg/m² 근처(±15%) 56건은 판정이 바뀔 수 있다 (tcga_mapping.md §3.7a).
- 병용 기록(`doxorubicin+cyclophosphamide`, `60+600`)은 약 순서대로 나눈 값이다. 나눌 수 없는 4명은 정답 세트에서 뺐다 (§7).
- 심장 위험 요인은 데이터가 없어 넘기지 않는다 (§9).

## 7. TCGA-BRCA 정답 세트의 특성 (B 테스트용)

| 항목 | 내용 |
|---|---|
| 규모 | **874명** (2026-10-15 크롭본). 병기 `[Discrepancy]`·`[Not Available]`·빈칸 12명, 범주를 정할 수 없는 Stage X 11명, 조직형 NOS·기록 없음 2명, 진단 시 전이성이 아니면서 새 원발암만 있는 19명, 재발 없음인데 재발 후 수술 YES 1명, 현재 전이성인데 전이 진단일·투약·전이 후 항암 투약이 없는 48명, anthracycline 병용 용량을 나눌 수 없는 4명, 재발했지만 부위를 모르는 7명, PR 판정 Indeterminate만 있는 4명, ER·PR·HER2 모두 미시행 43명, ER 또는 PR이 미시행인 2명(TCGA-C8-A9FZ, E9-A1N8, HR 평가 불가), HER2 판정 불가 62명(IHC 2+인데 ISH가 equivocal·미시행·기록 없음 21명, IHC 점수 없이 판정이 Indeterminate·미시행·기록 없음이고 ISH도 없는 41명)을 뺌 |
| 범주 | 현재 범주: 조기 742, 국소 진행성 212, 전이성 31 |
| 날짜 | 모두 비움 (`not_recorded` 또는 `null`). 대신 진단일 기준 일수(`start_day`, `end_day`, `metastasis_day`)를 넣음 |
| ER·PR 점수 | 넣지 않음. TCGA 점수 열은 입력이 적고(약 19%) 척도가 섞여 있어 잘못 해석될 수 있음 |
| ER 저발현 | 원본 구간 `<10%` + 판정 Positive → `{"range":[1,9],"result":"low_positive"}` **14명**. 원본에는 `Low Positive`라는 판정이 없고, A가 크롭 단계에서 만든 값이다 |
| PR 1~9% | 원본 구간 `<10%` + 판정 Positive → `{"range":[1,9],"result":"positive"}` **49명**. PR 9% 기준(2026-10-15, §4.2)으로 B는 `positive`로 판정한다 |
| ER·PR `<1%` | 원본 구간 `<10%` + 판정 Negative → `{"range":[0,0],"result":"negative"}` ER 48명, PR 75명. **가정이 들어간 값**: 1% 기준은 2010년부터라, 2010년 이전 진단(ER 40명, PR 55명)은 10% 기준 음성이었을 수 있음. ER 저발현 경계 사례 테스트에는 `[1,9]` 환자만 쓰기를 권함 |
| HER2 | score 2+ 또는 Equivocal 194명에 §3.4 보정 적용 (점수 없는 Equivocal 7명은 `2+` 채움). 결과: `{"score":"2+","result":"negative"}` 132명(저발현 후보) / `{"score":"2+","result":"positive"}` 39명 / `{"score":"2+","result":"unknown"}` 20명 / `{"score":"1+","result":"negative"}` 2명 / `{"score":"3+","result":"negative"}` 1명(원자료끼리 어긋남) |
| 재발 재생검 | TCGA 정답에는 쓰지 않음 (§3.5) |
| 유전자 | 종양 엑솜. BRCA1/2는 gBRCA 측정으로 가정 (§4.7). ESR1은 모두 원발 조직 결과 |
| 진단 시 전이 부위 | M0이면 `[Not Applicable]` (468명이 해당). `[Not Available]`은 MX·M1 중 부위 기록이 없는 83명 |
| 없는 칸 | 등급, Ki-67, ECOG, cTNM, pCR/RCB, PD-L1, 수술 가능 여부, 폐경 판정 근거, 진행일. 경계 사례가 필요하면 A가 합성값으로 만들고 `synthetic` 표시 |

## 8. 예시

### 8.1 TCGA 정답 전체 예시 (범주별 1명, 스키마 검증 통과)

| 범주 | 파일 | 특징 |
|---|---|---|
| 조기 | `src/input/examples/patient_state_early_TCGA-5L-AAT0.json` | IIA기, ILC, ER+/HER2 1+(저발현 후보), PIK3CA H1047L, tamoxifen 보조요법 |
| 국소 진행성 | `src/input/examples/patient_state_locally_advanced_TCGA-A2-A0YG.json` | IIIC기, HR+/HER2 3+, AC(21일 간격) → paclitaxel(매주) + trastuzumab, docetaxel 1회(173일) → anastrozole(날짜 없음) |
| 전이성 | `src/input/examples/patient_state_metastatic_TCGA-A2-A0EW.json` | IIIC기 → 1,353일째 뼈 전이 재발. 보조 AC → T → AI(exemestane 투여 중 진행). 전이 후 fulvestrant → tamoxifen → liposomal doxorubicin. doxorubicin 범위 용량(115-116 → 116) |

전이성 예시의 차수 판단: `metastasis_day` 1,353 이후 시작한 fulvestrant(1,366일) = 1L, tamoxifen(1,618일) = 2L, liposomal doxorubicin(1,696일) = 3L. 급여 기준으로는 고식적 내분비요법 1·2차, 고식적 항암화학요법 1차. 골 보호제(zoledronic acid, denosumab)는 차수에서 뺀다.

### 8.2 가상 차트 예시 (입력과 기대 출력)

규칙 설명용 가상 차트다. 재발로 전이된 환자. 진단 시 ER·PR 양성, HER2 IHC 2+ / FISH 음성. 재발 병소에서 PR이 음성으로 바뀜. AI + CDK4/6 억제제에서 진행. PIK3CA 변이 있음.

<!-- validate:patient_state -->
```json
{
  "schema_version": "0.1-draft6",
  "patient_ref": "VC-0001",
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
      "disease_extent": {"status": "present", "value": "early", "raw": "pT2 pN1a M0",
                         "source": {"doc_id": "D1", "quote": "pT2 pN1a M0"}},
      "metastatic_sites": {"status": "present", "value": "[Not Applicable]", "raw": "M0",
                           "source": {"doc_id": "D1", "quote": "pT2 pN1a M0"}}
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
                   "metastatic_sites": {"status": "present", "value": ["bone", "liver"], "raw": "뼈, 간 전이",
                                        "source": {"doc_id": "D2", "quote": "뼈, 간 전이"}},
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
  "patient_ref": "VC-0001",
  "records": [
    {"marker": "ER", "status": "positive", "reason": "재발 병소 70-79% (10% 초과). 원발 90-99%에서 유지",
     "rule_id": "BM2-ER-RANGE", "evidence": {"specimen": "metastasis"},
     "source_span": {"doc_id": "D2", "quote": "ER 양성 (70-79%)"}, "rag_tags": []},
    {"marker": "PR", "status": "negative", "reason": "재발 병소 <1%. 원발 50-59% 양성에서 음성으로 바뀜",
     "rule_id": "BM2-PR-RANGE", "evidence": {"specimen": "metastasis"},
     "source_span": {"doc_id": "D2", "quote": "PR 음성 (<1%)"}, "rag_tags": []},
    {"marker": "HER2", "status": "low", "reason": "IHC 2+, ISH 비증폭 → 저발현 (score를 먼저 읽음. result negative는 ISH 보정값)",
     "rule_id": "BM2-HER2-2PLUS-NOTAMP", "evidence": {"specimen": "primary"},
     "source_span": {"doc_id": "D1", "quote": "HER2 IHC 2+"}, "rag_tags": []},
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

## 10. B 진행 현황과 남은 작업 순서

2026-10-16 기준. B 작업물은 main에 병합했다 (`b7362c2`, 유전자 판정은 PR #2).

### 10.1 완료

| 항목 | 내용 | 위치 |
|---|---|---|
| BM-2 ER·PR·HER2·Ki-67 판정 | PROJECT.md §5 세부 규칙 (2026-10-15 확정) | `src/biomarker/BM1_ER,PR,HER2,Ki_67,subtype.py` |
| 아형 | HR+/HER2-, HR+/HER2+, HR-/HER2+, TNBC, 정할 수 없으면 `unknown`. ER low와 ER 음성·PR 양성은 HR+ | 같음 (`subtype_of`) |
| 분자 아형 | Luminal A / Luminal B(HER2 negative) / Luminal B(HER2 positive) / HER2_enriched / Basal_like / unknown. 규칙 함수만 있고 출력에는 넣지 않음 | 같음 (`molecular_subtype_of`) |
| BM-4 수용체 검사 공백 | ER·PR·HER2 미시행, HER2 ISH 권고(2+), 전이성 HER2 재판정, 전이성 TNBC PD-L1 미시행 | 같음 (`tests_needed_of`) |
| 유전자 7개 BM-2 (1차 규칙, PR #2) | ESR1, PIK3CA, AKT1, PTEN, BRCA1/2, PALB2. 허가 동반진단 변이 목록 또는 절단 변이로 양성, 나머지 검출 변이는 VUS, ESR1 재검 필요 | 같음 (`judge_gene`), `src/biomarker/actionable_variants.csv` |
| 유전자 BM-4 (PR #2) | 전이성 + 미시행일 때 gBRCA·PALB2, PIK3CA·AKT1·PTEN, ESR1 검사, ESR1 재검 | 같음 (`tests_needed_of`) |
| TCGA 정답 세트 | 판정할 수 없는 환자를 크롭 단계에서 빼서 874명. ER·PR·HER2·아형이 전원 판정됨 | `data/script/tcga_brca_crop.py` |
| patient_state 변환 | 크롭본 → patient_state (파일 저장 없이) | `src/input/script/tcga_to_patient_state.py` |
| 테스트 | 판정 규칙 케이스 + TCGA 874명 변환 → BM 출력 스키마 확인 | `tests/biomarker/test_bm.py` |

결정 사항 (2026-10-15):

- [x] §4.1 ER: Allred 총점 → 비율(percent → range → ps) → 적힌 판정. 0부터 시작하는 구간은 최대값을 percent로 본다. 쓸 값이 없으면 `unknown`
- [x] §4.2 PR: Allred 총점(0~2 음성, 3 이상 양성) → range(최대값 ≥ 9 양성) → percent(≥ 9 양성) → ps → 적힌 판정. `PR-low` 태그는 쓰지 않는다
- [x] §4.3 수치와 적힌 판정이 어긋나면 수치를 따르고 `reason`에 확인 필요를 적는다
- [x] §4.4 HER2: 3+ 양성 / 2+는 ISH로 가르고, ISH가 없으면 적힌 판정(positive·negative)을 따름 / 1+ 저발현 / 0은 음성, 미약한 막 염색이면 초저발현(심평원 기준 최종 음성). `zero`·`indeterminate`·HER2-low 태그는 쓰지 않는다
- [x] Ki-67: 20% 이상 positive, 미만 negative, 20%에 걸치는 구간·적힌 판정 intermediate는 `intermediate`, 쓸 값 없으면 `unknown`
- [x] 결과값에 `indeterminate`를 쓰지 않는다. 판정 불가는 `unknown` (바이오마커, 아형, `setting`)
- [x] 기록 없음(`not_recorded`)은 검사 권고 없이 기록 없음으로만 표기. 검사 권고는 미시행(`not_done`)일 때만
- [x] 재생검 결과가 있으면 그 결과로 판정한다
- [x] §5 BM-3 출처: OncoKB 대신 허가사항·CIViC·ClinVar·VEP
- [x] TCGA 정답의 BRCA1/2를 gBRCA 측정으로 가정 (유전자 판정을 다시 쓸 때 적용)

### 10.2 담당 변경 (2026-10-16)

| 작업 | 담당 | 비고 |
|---|---|---|
| §6.2 차수 계산 | **A** (변환 단계) | 2026-10-15에는 B였다. 계산 함수 `src/input/common/lines.py`의 `palliative_lines` (전체·고식적 내분비·고식적 항암 차수를 따로 셈, 2026-10-16). 결과는 draft6의 `treatment_history[].line` 등과 `deemed_lines` (§6.2·§6.3a) |
| §6.3 심평원 투여단계 | **A** (변환 단계) | |
| §6.7 anthracycline 누적 용량 | **A** (변환 단계) | `anthracycline_drug_dose`에 넣는다. 지금 `total_dose`는 TCGA에 적힌 값을 그대로 옮긴 것 |
| 약제명 사전 | **A** | 차트마다 다른 표기를 같은 약으로 묶기. `drug_classes.csv`에 `drug_subclass` 열 추가됨. 2026-10-16: CDK4/6 억제제·면역관문억제제·지침 약제 18개, 상품명·공고 요법 약어(EC, FEC, CMF, TAC, TCHP, DA, ED, GT) 추가 |
| §6.4 국소 재발 후 보조요법 | **B** | 차트를 보고 판단 |
| §6.5 PD-L1 약제별 판정 | **B** | 유전자 판정과 함께 |

### 10.3 남은 B 작업 순서

유전자 BM-2(옛 1번)와 유전자 BM-4(옛 3번)는 PR #2로 끝나 §10.1로 옮겼다.

1. **PD-L1 약제별 판정** (§6.5): 22C3 CPS ≥ 10, SP142 IC ≥ 1%. TCGA는 모두 기록 없음이라 규칙과 테스트 케이스만 만든다
2. **BM-3 근거 주석 (로컬 조회)** (§5): AKT1·ESR1 변이 목록 원문 확인(`actionable_variants.csv`의 `verified = no`), CIViC·ClinVar 다운로드 스크립트(`data/script/`), 로컬 조회 코드(외부 API 호출 없음). 유전자 판정에서 VUS로 남는 변이(BRCA1 C61G 같은 병원성 미스센스)를 다시 가른다
3. **국소 재발 후 수술 → 보조요법 (`SET-LOCAL-ADJ`)** (§6.4): 결과를 넣을 칸을 먼저 정한다 (아래 10.4)
4. **BM-1 보고서 파싱 (로컬 LLM)**: `llm/` 공통 인터페이스와 가상 차트가 생긴 뒤
5. **[4] LLM 추천 모듈**: 프롬프트, `recommendation.json` 검증, 환각 방지 후처리, 급여 분류. C의 검색 API(`src/rag/`)는 main에 있다. D의 급여 청크가 준비되면 본격 진행

### 10.4 정할 것

- [x] A가 계산한 차수·투여단계를 어느 칸에 넣을지 (2026-10-16 A 제안, draft6): `patient_state.treatment_history[]`의 `line`·`endocrine_line`·`chemo_line`과 `fields.deemed_lines`. B는 이 값으로 `setting.line`을 채운다. `SET-LOCAL-ADJ`(3번) 결과 칸은 따로 정한다
- [ ] `evidence.oncokb` → `annotation` 스키마 변경 (4명 합의)
- [ ] 분자 아형을 `biomarker_record` 출력에 넣을지 (넣으려면 스키마 칸 추가)
- [ ] 수치 기준 전체의 종양내과·병리과 검토. 바뀌면 A의 정답과 가상 차트도 바꿔야 한다
- [ ] `patient_state` 0.1-draft6 검토 의견. 문제가 없으면 `0.1`로 확정한다
