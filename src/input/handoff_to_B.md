# A → B 전달 문서: patient_state 사용 안내와 BM-2 판정 조건 제안

> 작성: 담당 A · 2026-10-12 · 기준 스키마: `schemas/patient_state.json` **0.1-draft4** (2026-10-13 `stage.disease_extent` 추가)
> 받는 사람: 담당 B ([2] 바이오마커 모듈, [4] LLM 추천 모듈)
> 관련 문서: [schema_fields.md](schema_fields.md) (필드별 상세), [tcga_mapping.md](tcga_mapping.md) (TCGA 정답 규칙), [schemas/README.md](../../schemas/README.md)

## 0. 요약

1. A는 환자마다 `patient_state` JSON 하나를 넘긴다. 형식은 `schemas/patient_state.json`이고, 넘기기 전에 스키마 검증을 통과한 것만 보낸다.
2. A는 **적힌 값을 표준 표기로 정리**만 한다. 양성·음성·저발현 판정은 B가 한다. 예외는 하나: HER2 IHC의 `result`는 A가 ISH 결과로 보정해서 넘긴다 (§3.3).
3. 그래서 **HER2는 `result`보다 `score`를 먼저 읽어야** 저발현을 놓치지 않는다.
4. 저발현 판정값(`low_positive`)은 **ER에만** 있다. ASCO/CAP 2020의 Low Positive가 ER에만 정의되어 있기 때문이다. PR은 양성/음성 두 범주만 쓴다 (§4.2).
5. 재발 환자는 **재생검(재발 병소) 결과가 `value`**이고, 원발 결과는 `history[]`에 있다 (§3.4). 가상 차트·실제 차트에만 해당하고, **TCGA 정답은 원발 결과만** 쓴다.
6. `not_done`(미시행)과 `not_recorded`(기록 없음)는 다르다. 미시행만 검사 권고 대상이다 (§3.1).
7. §4.1 ER, §4.2 PR 판정 규칙(Allred 비율 점수 우선, `PR-low` 태그)은 **2026-10-12에 결정**했다. 같은 내용이 팀 설계 문서 PROJECT.md §5에 있다. 나머지 §4 조건은 A의 제안이고, 수치 기준의 최종 확인은 종양내과·병리과 검토로 한다. §7에 B가 정해서 알려줄 것을 모았다.

## 1. 전달 방식

| 항목 | 내용 |
|---|---|
| 형식 | `schemas/patient_state.json` (JSON Schema 2020-12). 환자 1명 = JSON 1개 |
| 개발 중 | 파일로 전달: `tests/fixtures/patient_state/<patient_ref>.json` (예정. 공용 폴더라 4명 합의 후 생성) |
| 연결 후 | 함수 반환값: A의 `run(chart_text) → patient_state` 결과를 B의 `assess(patient_state) → biomarker_record`가 받는다 |
| 검증 | A가 보내기 전에 검증한다. B도 받을 때 검증하면 버전 불일치를 바로 알 수 있다 (`schema_version` = `"0.1-draft4"`) |
| 첫 전달 예정 | TCGA-BRCA 정답 세트 997명 (§5) 중 경계 사례 5건부터 |

검증 코드:

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
| **판정 기준**이 바뀌면 고쳐야 하는 규칙인가? (ASCO/CAP 기준, 1% 경계) | B |

| 원문 | A가 넘기는 값 | B가 판정할 것 |
|---|---|---|
| ER 90% | `{"percent": 90}` | ER 양성 |
| ER Allred 6/8 | `{"allred": {"total": 6}}` | ER 양성 |
| HER2 2+, SISH 음성 | `her2_ihc {"score":"2+","result":"negative"}`, `her2_ish {"result":"not_amplified"}` | HER2 저발현 |
| PIK3CA p.H1047R, VAF 31% | 보고서 원문 그대로 (`genomic_reports[].raw_text`) | 파싱(BM-1) → 양성(BM-2) → OncoKB(BM-3) |

## 3. B가 받는 값

### 3.1 모든 칸의 공통 틀

| 키 | 의미 | B가 쓰는 방법 |
|---|---|---|
| `status` | `present` 값 있음 / `not_done` 미시행 / `not_recorded` 기록 없음 | `not_done` → 검사 공백 규칙(BM-4)의 검사 권고 대상. `not_recorded` → "기록 없음"으로만 남김 |
| `value` | 표준값 (형태는 칸마다 다름) | 판정 입력 |
| `raw` | 원문 표기 | 판정이 이상할 때 확인용 |
| `specimen` | `primary` 원발 / `metastasis` 전이·재발 병소 / `cfDNA` / `unknown` | 재생검 여부, ESR1 재검 판단 |
| `observed_date` | 검사일. `YYYY-MM-DD`, `YYYY-MM`, `YYYY` 또는 `null` | 재검 필요 판단. **TCGA 정답은 항상 `null`** (§5) |
| `source` | 원문 근거 `{doc_id, quote, char_start, char_end}` | B 출력의 `source_span`에 그대로 사용 |
| `history[]` | 새 결과에 밀려난 이전 값. `superseded_reason`: `recurrence`(재발 재생검으로 대체) / `newer_result` | 판정에는 쓰지 않고 "바뀜" 설명에 사용 |

### 3.2 ER·PR (`receptors.er_percent`, `receptors.pr_percent`)

`value`는 아래 키 중 **차트에 적힌 것을 모두** 담은 객체다. A는 하나를 고르지 않는다.

| 키 | 의미 | 예 |
|---|---|---|
| `percent` | 양성 세포 비율 (%) | `ER 95%` → `{"percent": 95}` |
| `range` | 비율 구간 `[최소, 최대]` | `90-99%` → `[90, 99]` / `1-9%` → `[1, 9]` / `<1%` → `[0, 0]` |
| `score` | **염색 강도** 점수 `0`, `1+`~`4+` | `ER intensity 3+`, `strong` → `{"score": "3+"}` |
| `allred` | Allred 점수 `{total, ps, is}` 중 적힌 것 | `Allred 6/8 (PS 4, IS 2)` → `{"allred": {"total": 6, "ps": 4, "is": 2}}` |
| `result` | 차트에 적힌 판정 | ER: `positive` / `low_positive` / `negative` / `indeterminate`, PR: `positive` / `negative` / `indeterminate` |

- `low_positive`는 **ER에만** 있다. PR `value`에는 나오지 않는다.
- Allred: total = ps + is (0, 2~8). ps = 비율 점수 (0 없음, 1 <1%, 2 1~10%, 3 11~33%, 4 34~66%, 5 ≥67%), is = 강도 점수 (0~3).
- 척도가 적혀 있지 않은 점수(예: `ER score 6`)는 A가 `raw`에만 남기고 `value`에 넣지 않는다. 이 경우 `value`에 다른 정보가 없으면 B는 판정 정보가 부족한 것으로 본다.
- **TCGA 정답에는 `score`와 `allred`가 없다** (§5).

### 3.3 HER2 (`receptors.her2_ihc`, `receptors.her2_ish`)

| 칸 | `value` | 비고 |
|---|---|---|
| `her2_ihc` | `{score, faint, result}` 중 있는 것 모두 | `score`: `0`, `1+`, `2+`, `3+` / `faint`: IHC 0 중 미약한 막 염색 / `result`: `positive`, `negative`, `equivocal`, `indeterminate`, `unknown` |
| `her2_ish` | `{result, method}` | `result`: `amplified`, `not_amplified`, `equivocal` / `method`: `FISH`, `SISH`, `DISH`, `unknown`. 복제수·비율은 넣지 않는다 |

**A의 `result` 보정 규칙 (A 결정, TCGA 정답에 적용):**

1. `score`와 `result`가 둘 다 있으면 둘 다 넣는다.
2. 판정이 Equivocal인데 점수가 없으면 `score: "2+"`를 채운다 (Equivocal의 정의가 IHC 2+).
3. `score`가 `2+`이거나 판정이 Equivocal이면 ISH 결과로 `result`를 바꾼다: ISH 음성 → `negative`, ISH 양성 → `positive`, ISH 결과가 없는데 판정이 Equivocal → `unknown`.

그래서 B가 받는 `{"score":"2+","result":"negative"}`는 "IHC 2+, ISH 비증폭"이라는 뜻이다. **`result`만 보고 HER2 음성으로 판정하면 저발현 환자를 놓친다.** 트라스투주맙 데룩스테칸 같은 저발현 대상 치료가 후보에서 빠진다.

### 3.4 재발 환자

- 재발 병소 재생검 결과를 `value`로 쓰고 `specimen: "metastasis"`. PROJECT.md IN-4 규칙(최신 값, 전이 병소 재생검 우선)과 같다.
- 원발 결과는 `history[]`에 `"superseded_reason": "recurrence"`, `"specimen": "primary"`로 들어 있다.
- 재생검에서 검사하지 않은 마커는 원발 결과가 그대로 `value`다. 예: ER만 재검했으면 PR·HER2는 원발 값.
- **TCGA 정답 예외:** TCGA 정답은 진단 시(원발 종양) 병기·수용체만 쓴다. 재발 병소 수용체(`gdc_nte_*`)는 정답에 쓰지 않는다 (크롭본 4명 중 재발 기록과 맞는 환자가 1명뿐, 검사 부위·날짜도 없음). 재발 병소 결과 우선 규칙(IN-4)은 가상 차트와 실제 차트 등 다른 입력에만 적용한다 (사용자 결정, 2026-10-14).

```json
"er_percent": {
  "status": "present", "value": {"range": [70, 79], "result": "positive"}, "specimen": "metastasis",
  "history": [{"status": "present", "value": {"range": [90, 99], "result": "positive"},
               "specimen": "primary", "superseded_reason": "recurrence"}]
}
```

### 3.5 유전자 보고서 (`genomic_reports[]`)

- `{doc_id, report_date, specimen, raw_text}`. A는 `raw_text`를 해석하지 않는다. 변이 파싱은 B의 BM-1이다.
- **TCGA 보고서는 종양 조직 체세포 검사(엑솜)다.** 보고서 문장에 "종양 조직 체세포 검사"라고 적는다. 그 안의 BRCA1/2·PALB2 결과를 생식세포(gBRCA) 결과로 쓰면 안 된다. 체세포 결과는 sBRCA로만 저장한다.
- TCGA 보고서의 `specimen`은 항상 `primary`, `report_date`는 `null`이다.

### 3.6 그 밖에 B가 쓸 수 있는 칸

| 칸 | `value` | B에서의 용도 |
|---|---|---|
| `stage.ptnm`, `stage.ctnm` | `{t, n, m, edition}`. X값은 `not_assessed` | 치료 단계 판단 |
| `stage.group` | `IIA`, `IIIC`, `IV` … 또는 `not_assessed` | 치료 단계 판단 |
| `stage.positive_ln_count` | `{positive, examined}`. 각각 정수 또는 `"[Not Available]"` | 심평원 abemaciclib 기준 (4개) |
| `stage.metastatic_sites` | 부위 목록 또는 `"[Not Applicable]"` / `"[Not Available]"` | 전이성 여부 |
| `patient.gender`, `menopausal_status` | `FEMALE`·`MALE` / 폐경 4종 | 범위 외 판정, 내분비요법 |
| `treatment_history[]` | `drugs`, `setting`, `start_date`, `end_date`, `duration_days`, `stop_reason`, `best_response` | 치료 차수, 이전 약제 계열, ESR1 재검 판단. TCGA는 날짜가 `null`이고 순서는 배열 순서 |

특수 표기: `not_assessed` 평가 안됨, `[Not Available]` 그 항목만 기록 없음, `[Not Applicable]` 해당 없음.

## 4. BM-2 판정 조건

§4.1·§4.2는 2026-10-12 결정, §4.3 이후는 A 제안이다. A는 이 조건으로 정답 데이터와 가상 차트를 만든다. B가 확정한 조건과 정답이 같아야 평가가 맞으므로, 바꾸면 A에게 알려 주기 바란다.

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

참고: Allred 원래 기준은 총점 3 이상을 양성으로 보지만, ASCO/CAP 1% 기준과 맞지 않는다 (ps 1 = 1% 미만).

ER 저발현으로 판정하면 `rag_tags`에 `ER-low`를 붙인다.

### 4.2 PR [결정 2026-10-12]

ASCO/CAP 2020은 PR에 저발현 범주를 두지 않는다: 1% 이상 양성, 1% 미만 음성. **PR에는 `low` 상태값을 쓰지 않는다.**

| 순서 | 있는 값 | 조건 → 상태값 |
|---|---|---|
| 1 | `percent` | <1 → `negative` / ≥1 → `positive` |
| 2 | `range` | `[0,0]` → `negative` / 최소 ≥1 → `positive` |
| 3 | `allred.ps` | 0~1 → `negative` / 2~5 → `positive` |
| 4 | `allred.total`만 | 0~2 → `negative` / 5~8 → `positive` (총점 5 이상은 ps 2 이상만 가능) / **3~4 → `indeterminate`** + 비율 확인 권고 |
| 5 | `result`만 | 적힌 판정을 따름 |
| 6 | `score`(강도)만 | `indeterminate` |

**`PR-low` 태그 [결정]:** PR이 1~10%로 확인되면 상태값은 `positive` 그대로 두고 `rag_tags`에 `PR-low`를 붙인다.

| 조건 | 예 | 결과 |
|---|---|---|
| `percent` 1~10 | `{"percent": 5}` | `positive` + `PR-low` |
| `range` 최소 ≥1, 최대 ≤10 | `{"range": [1, 9]}` (TCGA 53명) | `positive` + `PR-low` |
| `allred.ps` = 2 | `{"allred": {"total": 4, "ps": 2, "is": 2}}` | `positive` + `PR-low` |
| `result`만, 또는 `allred.total`만 | `{"result": "positive"}` | `positive` (태그 없음. 비율을 알 수 없음) |
| 10% 초과 | `{"range": [10, 19]}` | `positive` (태그 없음) |

`PR-low`는 참고 정보다. 아형(`subtype`)과 처방 분류에는 영향을 주지 않는다. ER 양성이면서 PR이 낮은 경우를 설명할 때 쓴다.

### 4.3 ER·PR 공통: 값끼리 어긋날 때

예: `{"percent": 5, "result": "positive"}`, `{"range": [0,0], "result": "positive"}`.

- 제안: 수치(`percent` → `range` → `allred.ps` → `allred.total`)로 판정하고, 적힌 판정과 다르면 `reason`에 둘 다 적고 확인이 필요하다고 표시한다.
- TCGA 정답에서는 이런 경우가 없도록 크롭 단계에서 맞췄다 (§5).

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

B가 정할 경계 사례: TCGA에 `score 2+`, 원래 판정 Positive, ISH 결과 없음이 6명 있다. A는 Equivocal이 아니므로 `{"score":"2+","result":"positive"}`로 넘긴다. 위 표대로면 `indeterminate`인데, 검사실 판정(양성)을 따를지 정해야 한다.

### 4.5 재발 환자

- `value`(재생검 결과)로 판정한다.
- `history[]`의 원발 결과와 다르면 `reason`에 "원발 ○○에서 △△로 바뀜"을 적는다.
- 아형(`subtype`)도 재생검 결과로 정한다.

### 4.6 ESR1 재검과 날짜가 없는 경우

B의 규칙은 "ESR1 결과가 마지막 내분비요법 진행 **이전**이면 재검 필요"다. TCGA 정답은 날짜가 모두 `null`이다.

- 제안: 날짜가 없으면 검체와 치료 순서로 판단한다. ESR1 결과의 `specimen`이 `primary`(진단 시 조직)이고, `treatment_history`에 그 이후 내분비요법 진행(`best_response: PD` 또는 `stop_reason: progression`)이 있으면 `retest_needed`.
- TCGA 변이는 모두 원발 조직 결과이므로, 전이성 HR+/HER2- 환자 대부분이 `retest_needed`가 된다.

### 4.7 BRCA

| 정보 | 상태값 |
|---|---|
| 종양 체세포 검사에서 BRCA1/2 검출 안 됨 | sBRCA1/2 `negative` |
| 생식세포 검사 언급 없음 | gBRCA1/2 `not_recorded` (체세포 결과로 대신하지 않음) |
| HER2 음성 전이성 + gBRCA `not_done` | BM-4 검사 권고 |
| HER2 음성 전이성 + gBRCA `not_recorded` | B가 정할 것: 검사 권고를 낼지, "시행 여부 확인"으로만 낼지 |

## 5. TCGA-BRCA 정답 세트의 특성 (B 테스트용)

| 항목 | 내용 |
|---|---|
| 규모 | **997명** (2026-10-14 크롭본). 병기 `[Discrepancy]` 6명, `[Not Available]` 5명, 전부 빈칸 1명, 범주를 정할 수 없는 Stage X 11명, 조직형 NOS·기록 없음 2명, 진단 시 전이성이 아니면서 새 원발암만 있는 18명, 현재 전이성인데 전이 후 항암 투약 기록이 없는 46명을 뺌. 아래 건수는 997명 기준 (2026-10-14 재집계) |
| 날짜 | 모두 비움 (`not_recorded` 또는 `null`). 순서는 치료 이력 배열 순서와 `duration_days`(투여 기간)로만 알 수 있음 |
| ER·PR 점수 | 넣지 않음. TCGA 점수 열은 입력이 적고(약 19%) 척도가 섞여 있어 잘못 해석될 수 있음 |
| ER 저발현 | 원본 구간 `<10%` + 판정 Positive → `{"range":[1,9],"result":"low_positive"}` **16명** |
| PR 1~9% | 원본 구간 `<10%` + 판정 Positive → `{"range":[1,9],"result":"positive"}` **53명** (저발현 범주 없음, B가 `PR-low` 태그를 붙일 대상) |
| ER·PR `<1%` | 원본 구간 `<10%` + 판정 Negative → `{"range":[0,0],"result":"negative"}` ER 48명, PR 76명. **가정이 들어간 값**: 1% 기준은 2010년부터라, 2010년 이전 진단(ER 40명, PR 55명)은 10% 기준 음성이었을 수 있음. ER 저발현 경계 사례 테스트에는 `[1,9]` 환자만 쓰기를 권함 |
| HER2 | score 2+ 또는 Equivocal 196명에 §3.3 보정 적용. 결과: `{"score":"2+","result":"negative"}` 134명(저발현 후보) / `{"score":"2+","result":"positive"}` 39명 / `{"score":"2+","result":"unknown"}` 20명 / `{"score":"1+","result":"negative"}` 2명 / `{"score":"3+","result":"negative"}` 1명(원자료끼리 어긋남) |
| 재발 재생검 | **TCGA 정답에는 쓰지 않음** (2026-10-14). 크롭본 4명 중 재발 기록과 맞는 환자 1명뿐이라 원발 결과만 `value`로 쓴다. 재생검 우선 규칙은 가상 차트로 테스트 |
| 유전자 | 체세포 엑솜. gBRCA 정보 없음. ESR1은 모두 원발 조직 결과 |
| 없는 칸 | 등급, Ki-67, ECOG, cTNM, pCR/RCB, PD-L1. 경계 사례가 필요하면 A가 합성값으로 만들고 `synthetic` 표시 |

HER2 건수도 정답 세트(997명) 기준이다.

## 6. 전체 예시 (입력과 기대 출력)

(규칙 설명용 가상 차트 예시. TCGA 정답에는 재발 병소 결과를 쓰지 않는다.) 재발로 전이된 환자. 진단 시 ER·PR 양성, HER2 IHC 2+ / FISH 음성. 재발 병소에서 PR이 음성으로 바뀜. AI + CDK4/6 억제제에서 진행. PIK3CA 변이 있음.

<!-- validate:patient_state -->
```json
{
  "schema_version": "0.1-draft4",
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
       "duration_days": 412, "stop_reason": null, "best_response": "PD",
       "source": {"doc_id": "D4", "quote": "letrozole + palbociclib, PD"}}
    ],
    "neoadjuvant_response": {},
    "recurrence": {"recurrence_date": {"status": "not_recorded"}},
    "genomic_reports": [
      {"doc_id": "D3", "report_date": null, "specimen": "primary",
       "raw_text": "종양 조직 체세포 검사(엑솜). PIK3CA p.H1047R (missense), VAF 40.0%. ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음."}
    ]
  },
  "conflicts": []
}
```

B의 기대 출력 (§4 조건을 따른 경우):

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
    {"marker": "PIK3CA", "status": "positive", "reason": "p.H1047R 발암성 변이 (BM-1 파싱 → BM-3 OncoKB)",
     "rule_id": "BM2-PIK3CA", "evidence": {"specimen": "primary", "variant": "p.H1047R", "vaf": 0.4, "oncokb": "Oncogenic, Level 1"},
     "source_span": {"doc_id": "D3", "quote": "PIK3CA p.H1047R (missense), VAF 40.0%"}, "rag_tags": ["PIK3CA-mut"]},
    {"marker": "ESR1", "status": "retest_needed", "reason": "원발 조직 결과이고, 이후 AI + CDK4/6 억제제에서 진행 (날짜 없음, 검체·치료 순서로 판단)",
     "rule_id": "BM2-ESR1-RETEST", "evidence": {"specimen": "primary"},
     "source_span": {"doc_id": "D3", "quote": "ESR1, AKT1, PTEN, BRCA1, BRCA2, PALB2: 검출되지 않음"}, "rag_tags": []},
    {"marker": "sBRCA1", "status": "negative", "reason": "종양 체세포 검사에서 검출되지 않음", "rule_id": "BM2-SBRCA",
     "evidence": {"specimen": "primary"}, "source_span": {"doc_id": "D3", "quote": "BRCA1, BRCA2"}, "rag_tags": []},
    {"marker": "gBRCA1", "status": "not_recorded", "reason": "생식세포 검사 기록 없음 (체세포 결과로 대신하지 않음)",
     "rule_id": "BM2-GBRCA", "evidence": {}, "source_span": {"doc_id": "D3", "quote": "종양 조직 체세포 검사"}, "rag_tags": []}
  ],
  "subtype": "HR+/HER2-",
  "setting": {"disease": "metastatic", "line": "2L", "prior_drug_classes": ["aromatase inhibitor", "CDK4/6 inhibitor"],
              "reason": "전이성에서 letrozole + palbociclib 진행 후"},
  "tests_needed": [
    {"test": "ESR1 (cfDNA)", "reason": "내분비요법 진행 후 ESR1 재검", "rule_id": "BM4-ESR1-RETEST"},
    {"test": "gBRCA1/2, PALB2", "reason": "HER2 음성 전이성인데 생식세포 검사 기록 없음", "rule_id": "BM4-GBRCA"}
  ]
}
```

`rule_id`, 문장 표현, OncoKB 레벨은 형식 설명용 예시다. 실제 값은 B가 정한다.

## 7. B가 정해서 A에게 알려줄 것

- [x] §4.1 ER, §4.2 PR 판정 규칙과 `PR-low` 태그 (2026-10-12 결정, PROJECT.md §5)
- [ ] §4.4 HER2 판정 조건 확정
- [ ] 수치 기준 전체의 종양내과·병리과 검토. 바뀌면 A의 정답과 가상 차트도 바꿔야 한다
- [ ] ER·PR 수치와 적힌 판정이 어긋날 때의 처리 (§4.3)
- [ ] HER2 score 2+ + 판정 Positive + ISH 없음(TCGA 6명)을 양성으로 볼지 불확정으로 볼지 (§4.4)
- [ ] 날짜가 없을 때 ESR1 재검을 검체·치료 순서로 판단하는 규칙 (§4.6)
- [ ] gBRCA `not_recorded`일 때 검사 권고를 낼지 (§4.7)
- [ ] ER 저발현(`low`) 환자의 아형 표기: HR+로 둘지, 별도 표시할지 (`rag_tags`에 `ER-low` 등)
- [ ] `biomarker_record`에서 PR은 `low` 상태값을 쓰지 않는다는 점 반영 (B의 스키마·규칙)
- [ ] `patient_state` 0.1-draft4 검토 의견. 문제가 없으면 `0.1`로 확정한다
