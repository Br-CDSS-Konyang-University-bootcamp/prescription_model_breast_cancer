# A → B 전달 문서: patient_state 0.1-draft5 변경 사항과 B의 정규화 안내

> 작성: 담당 A · 2026-10-15 · 기준 스키마: `schemas/patient_state.json` **0.1-draft5**
> 받는 사람: 담당 B ([2] 바이오마커 모듈, [4] LLM 추천 모듈)
> 관련 문서: [handoff_to_B.md](handoff_to_B.md) (draft4까지의 전달 내용, BM-2 판정 조건), [tcga_mapping.md](tcga_mapping.md) (TCGA 변환 규칙), [schema_fields.md](schema_fields.md) (필드별 상세)
> 상태: 팀 협의 완료 (2026-10-15). 이 문서의 규칙으로 TCGA 정답 세트를 만든다.

## 0. 요약

1. **차수(line)는 정답에 넣지 않는다. B가 직접 판단한다.** 재료로 투약 시작·종료일(`treatment_history[].start_day`, `end_day`)과 전이 기준일(`recurrence.metastasis_day`)을 넘긴다. 모두 진단일 = 0인 정수다 (실제 날짜가 아니므로 비식별 원칙과 충돌하지 않는다).
2. **현재 범주(`setting.disease`)**: 진단 시 IV기(`stage.disease_extent = metastatic`)이거나 원격 전이 재발(`recurrence.status = distant`)이면 전이성. 그 밖은 진단 시 범주. 국소 재발은 전이가 아니다.
3. **국소 재발 후 보조요법**: `recurrence.status = locoregional`, `surgery = yes`, `later_distant = no`이면 이후 요법은 수술후보조요법이다 (심평원 공고 p.48). 규칙 ID 제안: `SET-LOCAL-ADJ`.
4. **gBRCA**: TCGA 정답 세트에서는 BRCA1·BRCA2 결과를 gBRCA 측정으로 가정한다. A는 변이 원문을 그대로 넘기고 **B가 positive / negative / vus를 판정**한다.
5. **PD-L1은 발현 점수**다 (변이 아님). `receptors.pdl1`에 검사법·점수 종류·점수만 넘기고, **약제별 기준 판정은 B**가 한다.
6. **유전자 변이**는 `molecular.mutations`에 유전자별로 넘긴다: 변이 있음 / 변이 없음 / 미시행.
7. **anthracycline 투약 용량**(`anthracycline_drug_dose`)을 새로 넘긴다. liposomal doxorubicin 급여 조건(누적 용량) 판정용이다.
8. **주기 수에는 주기 길이(단위)가 붙는다.** "18주기"를 횟수만으로 비교하지 않는다.

## 1. draft4 → draft5 변경 목록

| 위치 | 변경 | TCGA 정답 |
|---|---|---|
| `treatment_history[].start_day`, `end_day` | 추가. 진단일 = 0인 정수 (진단 전이면 음수) | 있음 |
| `treatment_history[].cycles` | 추가. `{value, basis, interval_days, interval_basis}` | 있음 (기록값 또는 추정값) |
| `treatment_history[].progression_day` | 추가 | 모두 `null` |
| `treatment_history[].stop_reason` | `planned_switch`, `maintenance` 추가 | 모두 `null` |
| `anthracycline_drug_dose` | 새 그룹 (필수) | 있음 |
| `recurrence.status`, `metastatic_sites`, `metastasis_day`, `surgery`, `surgery_intent`, `later_distant` | 추가 | 있음 (해당 환자만) |
| `molecular.mutations.{ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2}` | 새 그룹 (필수). ERBB2는 넣지 않는다 | 있음 |
| `receptors.pdl1` | 추가 | 모두 `not_recorded` |
| `stage.operable` | 추가 (수술 가능 여부) | 모두 없음 |
| `patient.menopausal_basis` | 추가 (폐경 판정 근거) | 모두 없음 |
| `schema_version` | `"0.1-draft5"` | |

정답 세트: 크롭본 **992명** (2026-10-15). draft4 전달 때(997명)에서 anthracycline 병용 기록의 용량을 약별로 나눌 수 없는 4명을 더 뺐다 (TCGA-D8-A27N, D8-A1XL, D8-A140, D8-A1JM). 전이성 32명.

## 2. 전체 출력과 B의 정규화 (TCGA 정답 992명 기준)

추출값의 공통 틀은 draft4와 같다: `{status, value, raw, observed_date, specimen, confidence, source, history}`. `status`는 `present`(값 있음) / `not_done`(미시행) / `not_recorded`(기록 없음)이고, `value`는 `present`일 때만 있다. 해당 없는 칸은 만들지 않는다.

### 2.1 문서 단위

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `schema_version` | `"0.1-draft5"` | 고정 | 버전이 다르면 거부 |
| `patient_ref` | 문자열 | TCGA 바코드 | 그대로 |
| `documents[]` | `{doc_id, doc_type, doc_date}` | `doc_date`는 모두 `null` | |
| `conflicts[]` | `{field, candidates[], note}` | 대부분 빈 배열 | 자동 선택하지 말고 확인 요청 |

### 2.2 diagnosis / stage

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `diagnosis.diagnosis_date` | 날짜 | 모두 `not_recorded` | 순서는 `*_day`로 판단 |
| `diagnosis.histology` | `IDC` / `ILC` / `mucinous` / `metaplastic` / `invasive_NOS` / `other` | 원본 조직형 변환 | |
| `diagnosis.grade` | 1 / 2 / 3 | 모두 `not_recorded` | abemaciclib 보조요법 조건(등급 3)은 판정 불가 |
| `stage.ptnm` | `{t, n, m, edition}` | TX·NX·MX는 `not_assessed` | AJCC 판(3~7판)이 섞여 있음 |
| `stage.ctnm` | 같음 | 모두 `not_recorded` | |
| `stage.group` | `IIA`, `IIIC`, `IV`, `not_assessed` | | |
| `stage.positive_ln_count` | `{positive, examined}`. 각각 정수 또는 `[Not Available]` | | 공고 보조요법 조건 (4개 이상, 1~3개 등) |
| `stage.disease_extent` | `early` / `locally_advanced` / `metastatic` | 진단 시 범주 | 현재 범주는 §3.1 규칙으로 판정 |
| `stage.metastatic_sites` | 부위 목록 / `[Not Applicable]` / `[Not Available]` | 진단 시 전이 부위. M0(`cM0(i+)` 포함)이면 `[Not Applicable]` (2026-10-15) | `[Not Available]`은 MX·M1이면서 부위 기록이 없는 경우뿐 |
| `stage.operable` | `yes` / `no` / `unknown` | 없음 | 가상 차트용. 없으면 국소진행성의 선행·고식 구분 불가 |

### 2.3 receptors / proliferation / patient

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `receptors.er_percent`, `pr_percent` | `{percent, range, score, allred, result}` 중 있는 것 | `range` + `result` (`score` 없음) | draft4와 같음 (handoff_to_B.md §4.1·§4.2) |
| `receptors.her2_ihc`, `her2_ish` | `{score, faint, result}`, `{result, method}` | | `score`를 먼저 읽기 (handoff_to_B.md §4.4) |
| `receptors.pdl1` | `{assay, score_type, score}` | 모두 `not_recorded` | §3.5 |
| `proliferation.ki67_percent` | `{percent, range, result}` | 모두 `not_recorded` | |
| `patient.gender`, `age` | `FEMALE` / 정수 | 모두 FEMALE | |
| `patient.menopausal_status` | 폐경 4종 | 진단 시점 값 | 공고는 "약제 전환 시점"의 폐경 상태를 요구함. TCGA는 진단 시점 값으로 대신함 |
| `patient.menopausal_basis` | `age_amenorrhea` / `fsh` / `oophorectomy` / `unknown` | 없음 | 가상 차트용 |
| `patient.ecog` | 0~4 | 모두 `not_recorded` | |

### 2.4 treatment_history[] (항목 하나 = 투약 기록 하나, 2,215개)

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `drugs` | 일반명 소문자 배열 | 병용 기록은 여러 개 (예: `["doxorubicin", "cyclophosphamide"]`) | 약제 계열로 바꿔 `prior_drug_classes`에 사용 |
| `setting` | `neoadjuvant` / `adjuvant` / `metastatic` / `unknown` | adjuvant 2,107, metastatic 108 | A의 유도값 (시작일 ≥ 전이 기준일 → metastatic). neoadjuvant 13명은 수작업 확인 예정 |
| `start_date`, `end_date` | 날짜 | 모두 `null` | |
| `start_day`, `end_day` | 정수 / `null` | `start_day` null 84, `end_day` null 574 | **차수 계산의 핵심** (§3.2). `end_day` null = 종료 모름 |
| `duration_days` | 정수 / `null` | `end_day − start_day` | |
| `cycles` | `{value, basis, interval_days, interval_basis}` / `null` | 기록값 787, 추정값 716, null 712 | §3.6. 횟수만으로 공고의 "18주기"와 비교하지 않음 |
| `progression_day` | 정수 / `null` | 모두 `null` | 공고 "종료 후 1달 이내 진행" 판정 불가 |
| `stop_reason` | `progression` / `toxicity` / `completed` / `planned_switch` / `maintenance` / `other` / `null` | 모두 `null` | `planned_switch`·`maintenance`는 같은 차수 |
| `best_response` | `CR` / `PR` / `SD` / `PD` / `unknown` | | `PD`는 진행으로 차수가 넘어갔다는 근거 |

### 2.5 anthracycline_drug_dose

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `administered` | `positive` / `negative` / `No value` | positive 374, negative 344, No value 274 | `No value` = 투약 기록 없음 (투여 안 함이 아님) |
| `drugs[].drug` | `doxorubicin` / `epirubicin` / `liposomal doxorubicin` | 338 / 40 / 2 | mitoxantrone은 제외 |
| `drugs[].timeline_index`, `combined_with`, `raw` | 정수, 배열, 문자열 | | 대조용 |
| `drugs[].dose_per_admin` | `{value, unit}` / `"No value"` | No value 201, mg 95, mg/m² 68, mg/day 13, mg/m²/day 3 | 단위가 섞여 있음 (§3.7). 원문이 범위(100-102)면 최대값 |
| `drugs[].cycles` | `cycles` 형식 (`basis: recorded`만) / `"No value"` | 기록 205, No value 175 | |
| `drugs[].total_dose` | `{value, unit}` / `"No value"` | No value 217, mg 158, mg/m² 3, 기타 2 | 대부분 mg |

### 2.6 recurrence

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `recurrence_date`, `adjuvant_endocrine_end_date` | 날짜 | 모두 `not_recorded` | 대신 `*_day`와 `treatment_history` 사용 |
| `status` | `none` / `distant` / `locoregional` / `site_unknown` / `unknown` | none 776, unknown 170, distant 24, locoregional 15, site_unknown 7 | §3.1 |
| `metastatic_sites` | 부위 목록 | distant 24명만 | 국소 부위(`other: Axilla` 등)가 섞일 수 있음. 처방·급여 판정에는 쓰지 않음 |
| `metastasis_day` | 정수 (진단 시 IV기 = 0) | 전이성 32명만 | **차수 기준점** (§3.2) |
| `surgery` | `yes` / `no` / `unknown` | 재발 46명: yes 18, no 19, unknown 9 | §3.3 |
| `surgery_intent` | `curative` / `palliative` / `unknown` | 모두 `unknown` | TCGA에 기록 없음 |
| `later_distant` | `yes` / `no` / `unknown` | 20명 (모두 `no`) | §3.3 |

### 2.7 molecular / genomic_reports

| 경로 | 값 형태 | TCGA 정답 값 | B 정규화·주의 |
|---|---|---|---|
| `molecular.mutations.{유전자}` | `{status, result, variants[], specimen}` | 유전자마다 미시행 30명 | 변이 있음 = `present` + `detected`, 변이 없음 = `present` + `not_detected` (`variants` 빈 배열), 미시행 = `not_done` |
| 변이 있음 건수 | | PIK3CA 318, PTEN 53, AKT1 25, BRCA2 25, BRCA1 24, ESR1 9, PALB2 7 | `variants[]`의 `protein_change`, `variant_type`, `vaf`로 BM-3 (OncoKB·ClinVar) |
| `variants[].raw` | 문자열 | `H1047R (Missense_Mutation, VAF 0.31)` 형식 | 파싱이 안 되면 `raw`만 있음 |
| `specimen` | `primary` | 모두 원발 조직 | ESR1은 진행 후 재검 대상 (`retest_needed`) |
| `genomic_reports[]` | `{doc_id, report_date, specimen, raw_text}` | 가상 차트용 원문 | 같은 정보가 두 곳에 있으면 `molecular` 우선 |

## 3. B 규칙 (협의 완료)

### 3.1 현재 범주 (`setting.disease`)

| 조건 | 값 |
|---|---|
| `stage.disease_extent = metastatic` 또는 `recurrence.status = distant` | `metastatic` |
| 그 밖 (재발 없음, 국소 재발, 부위 모름, 재발 여부 모름) | `stage.disease_extent` 그대로 |

### 3.2 차수 (`setting.line`)

차수는 정답에 없다. B가 아래 재료로 판단한다.

1. `treatment_history`를 `start_day` 순으로 정렬한다 (`start_day` null은 순서를 알 수 없음).
2. `start_day ≥ recurrence.metastasis_day`인 기록이 전이 이후 요법이다. 그 전은 선행·보조요법이다.
3. 보조약(supportive care)과 골 보호제는 차수를 정하지 않는다.
4. 시작일이 가까운 기록은 한 요법으로 묶는다 (A 분석에서는 28일 이내를 같은 요법으로 봤다. 기준은 B가 정한다).
5. 진행(`best_response = PD`, `stop_reason = progression`)으로 바뀐 요법만 다음 차수로 센다. `planned_switch`(AC→T 같은 계획된 순차)와 `maintenance`는 같은 차수다.

심평원 급여 판정용 차수는 지침 차수와 다르게 센다 (공고 p.48~63, A 확인):

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

### 3.3 국소 재발 후 보조요법 (`SET-LOCAL-ADJ`)

| 조건 | 판정 |
|---|---|
| `recurrence.status = locoregional`, `surgery = yes`, `later_distant = no` | 이후 요법은 수술후보조요법 (공고 p.48 "국소재발의 경우 완치 목적의 수술을 시행 후 재발 방지를 위해 투여한 항암요법은 수술후보조요법으로 시행할 수 있음") |
| `surgery_intent` | TCGA는 모두 `unknown`. `unknown`이어도 위 규칙을 적용한다 |

### 3.4 gBRCA

| 입력 (`molecular.mutations.BRCA1` / `BRCA2`) | B 출력 (`gBRCA1` / `gBRCA2`) |
|---|---|
| `result = detected` + 병원성 변이 (ClinVar Pathogenic·Likely pathogenic, 또는 절단 변이) | `positive` |
| `result = detected` + 의미 불명 변이 (예: missense E9Q) | `vus` |
| `result = not_detected` | `negative` |
| `status = not_done` | `not_done` |

- TCGA 정답 세트에서만 쓰는 가정이다. 가상 차트·실제 차트에서는 차트에 적힌 검사 종류(생식세포 / 체세포)를 따른다.
- 모델 한계: TCGA 변이는 종양 조직 엑솜 결과다. 실제 생식세포 검사 결과와 다를 수 있다.

### 3.5 PD-L1

A는 판정하지 않는다. B가 약제별로 판정한다.

| 약제 | 기준 | 근거 |
|---|---|---|
| pembrolizumab + 항암 (TNBC 1차) | 22C3, CPS ≥ 10 | 공고 p.58~59 (주3: IHC 22C3 pharmDx) |
| atezolizumab + nab-paclitaxel | SP142, IC ≥ 1% | ESMO MBC 2026 |

검사법(`assay`)이 기준과 다르면 해당 약제 판정에 쓰지 않는다. `biomarker_record`의 `evidence.assay`, `evidence.score`에 값을 남긴다.

### 3.6 투여 주기 해석

| `interval_basis` | 뜻 |
|---|---|
| `derived` | 투여 일수 ÷ (기록 주기 수 − 1). 예: trastuzumab 47주기, 351일 → 8일 = 매주 투여 |
| `standard` | 약제별 기본값 (`data/dictionaries/drug_cycle_days.csv`) |
| `recorded` | 차트에 주기 길이가 적힘 (가상·실제 차트) |
| `null` | 주기 길이를 알 수 없음 |

- 공고의 "총 18주기"(trastuzumab ± pertuzumab, p.49·53)는 3주 주기 기준이다. `value × interval_days`로 기간을 비교한다.
- `basis = estimated`는 투여 일수 ÷ 기본 주기 + 1로 계산한 값이다. 정답 생성용 근사치다.

### 3.7 anthracycline 누적 용량 (liposomal doxorubicin 급여 조건, 공고 p.60)

- 조건: doxorubicin 누적 240mg/m² 이상 또는 epirubicin 450mg/m² 이상, 또는 심장 위험 요인.
- 누적 용량 = `dose_per_admin`(mg/m²) × `cycles.value`. 단위가 mg/m²가 아니면(mg, mg/day) 체표면적이 없어 환산할 수 없다. 이 경우 "판정 불가"로 둔다.
- 심장 위험 요인은 데이터가 없어 넘기지 않는다 (§5).

## 4. 예시 (TCGA 정답, 새 필드만)

TCGA-D8-A27L (AC 병용, 용량을 순서대로 나눔, PIK3CA 변이):

```json
"treatment_history": [
  {"drugs": ["doxorubicin", "cyclophosphamide"], "setting": "adjuvant",
   "start_date": null, "end_date": null, "duration_days": 138, "start_day": 100, "end_day": 238,
   "cycles": {"value": 4, "basis": "recorded", "interval_days": 46, "interval_basis": "derived"},
   "stop_reason": null, "best_response": "unknown", "source": null}
],
"anthracycline_drug_dose": {
  "administered": "positive",
  "drugs": [{"drug": "doxorubicin", "timeline_index": 0, "combined_with": ["cyclophosphamide"],
             "dose_per_admin": {"value": 60.0, "unit": "mg/m2"},
             "cycles": {"value": 4, "basis": "recorded", "interval_days": 46, "interval_basis": "derived"},
             "total_dose": {"value": 240.0, "unit": "mg"},
             "raw": "doxorubicin+cyclophosphamide [Chemotherapy] d100~d238", "source": null}]
},
"receptors": {"pdl1": {"status": "not_recorded"}},
"molecular": {"mutations": {
  "PIK3CA": {"status": "present", "result": "detected", "specimen": "primary", "source": null,
             "variants": [{"protein_change": "E545K", "variant_type": "Missense_Mutation", "vaf": 0.282,
                           "raw": "E545K (Missense_Mutation, VAF 0.282)"}]},
  "ESR1": {"status": "present", "result": "not_detected", "variants": [], "specimen": "primary", "source": null},
  "BRCA1": {"status": "present", "result": "not_detected", "variants": [], "specimen": "primary", "source": null}
}}
```

이 예시의 `interval_days: 46`은 기록 주기 수(4)와 투여 기간(138일)으로 계산한 값이다. TCGA 기록 기간이 실제 투여 간격보다 길게 적힌 경우라, `derived` 값은 참고로만 쓴다.

TCGA-A2-A25E (국소 재발 후 수술 → `SET-LOCAL-ADJ` 대상):

```json
"recurrence": {
  "recurrence_date": {"status": "not_recorded"},
  "status": {"status": "present", "value": "locoregional"},
  "surgery": {"status": "present", "value": "yes"},
  "surgery_intent": {"status": "present", "value": "unknown"},
  "later_distant": {"status": "present", "value": "no"}
}
```

TCGA-A7-A26H (원격 전이 재발, BRCA1 절단 변이 → B는 gBRCA1 `positive` 예상):

```json
"recurrence": {
  "recurrence_date": {"status": "not_recorded"},
  "status": {"status": "present", "value": "distant"},
  "metastatic_sites": {"status": "present", "value": ["liver"]},
  "metastasis_day": {"status": "present", "value": 291},
  "surgery": {"status": "present", "value": "no"},
  "surgery_intent": {"status": "present", "value": "unknown"}
},
"treatment_history": [
  {"drugs": ["anastrozole"], "setting": "adjuvant", "start_day": 44, "end_day": 296, "cycles": null, "...": "..."},
  {"drugs": ["paclitaxel"], "setting": "metastatic", "start_day": 311, "end_day": 486,
   "cycles": {"value": 8, "basis": "recorded", "interval_days": 25, "interval_basis": "derived"}, "...": "..."}
],
"molecular": {"mutations": {"BRCA1": {"status": "present", "result": "detected", "specimen": "primary", "source": null,
  "variants": [{"protein_change": "T688Vfs*12", "variant_type": "Frame_Shift_Del", "vaf": 0.367,
                "raw": "T688Vfs*12 (Frame_Shift_Del, VAF 0.367)"}]}}}
```

이 환자의 차수 판단 예: anastrozole(44~296일)은 전이 기준일(291일) 전에 시작했으므로 보조 내분비요법이고, 투여 중 재발했다. paclitaxel(311일)은 전이 후 첫 요법이므로 지침 기준 1L, 급여 기준 고식적 항암화학요법 1차다.

## 5. 넘기지 않는 정보 (모델 한계)

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

## 6. 파일 위치

| 파일 | 내용 |
|---|---|
| `schemas/patient_state.json` | 0.1-draft5 스키마 |
| `data/tcga_brca/merged/tcga_brca_merging_cropped.csv` | 정답 세트 원본 (992명) |
| `data/dictionaries/drug_cycle_days.csv` | 약제별 기본 주기 길이 |
| `src/input/tcga_mapping.md` §3.6·§3.7·§3.7a·§3.8 | TCGA → draft5 변환 규칙 |
| `src/input/examples/patient_state_{early,locally_advanced,metastatic}_*.json` | 범주별 TCGA 정답 전체 예시 1명씩 (TCGA-5L-AAT0, TCGA-A2-A0YG, TCGA-A2-A0EW). 스키마 검증 통과 |

## 7. B에게 요청

- [ ] §3.2 차수 계산 구현 (요법 묶음 기준일, 진행 판단)과 심평원 투여단계 별도 계산
- [ ] §3.3 `SET-LOCAL-ADJ` 규칙 추가
- [ ] §3.4 gBRCA 판정 (ClinVar 대조 방법 포함)
- [ ] §3.5 PD-L1 약제별 판정
- [ ] `biomarker_record`의 `schema_version`과 함께 draft5 입력으로 테스트. 문제가 없으면 `0.1`로 확정
