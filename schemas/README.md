# schemas/ — 모듈 간 데이터 형식 (공용, 4명 합의)

모듈끼리 주고받는 JSON 형식을 [JSON Schema 2020-12](https://json-schema.org/)로 정의한다. 지금 파일은 **0단계 검토용 초안**이다 (`patient_state`는 `0.1-draft5`, 나머지는 `0.1-draft`). 4명 검토가 끝나면 `"0.1"`로 올린다.

바꿀 때는 4명이 모두 검토한다. 필드를 추가·삭제하면 이 README의 표와 예시도 함께 고친다.

## 1. 파일과 흐름

```
[1] 입력 (A) ──patient_state──▶ [2] 바이오마커 (B) ──biomarker_record──┬──▶ [3] 검색 필터 (C)
      │                                                               │
      └──────────────patient_state────────────────────────────────────┴──▶ [4] 추천 (B) ──recommendation──▶ 화면
[3] 지침 RAG (C) ─┐
[5] 급여 (D) ─────┴──chunk──▶ 공용 검색 색인 (C) ──검색 결과(chunk 목록)──▶ [4] 추천 (B)
```

| 파일 | 내용 | 만드는 쪽 | 쓰는 쪽 | 초안 검토 |
|---|---|---|---|---|
| [patient_state.json](patient_state.json) (0.1-draft6) | 차트에서 추출한 환자 상태 | [1] 입력 (A) | [2], [4] | B, C, D |
| [biomarker_record.json](biomarker_record.json) | 바이오마커 상태값, 아형, 치료 상황, 검사 공백 | [2] 바이오마커 (B) | [3] 필터, [4] | A, C, D |
| [chunk.json](chunk.json) | 검색 색인 청크 (지침·급여 공용) | [3] (C), [5] (D) | [3] 색인, [4] | D 필수, A, B |
| [recommendation.json](recommendation.json) | 처방 후보, 급여 분류, 검사 권고 | [4] 추천 (B) | 출력 화면 | A, C, D |

## 2. 공통 규칙

- 날짜는 `YYYY-MM-DD`로 쓰고, 차트에 월·연도까지만 있으면 `YYYY-MM`·`YYYY`도 허용한다 (`patient_state`). 모르면 `null`. 시각은 ISO 8601(`2026-10-12T09:00:00+09:00`)로 쓴다.
- 코드값은 영문으로 저장하고, 화면에 보일 때만 아래 한국어 표시로 바꾼다.
- `patient_ref`는 가명 ID다. 실제 이름, 등록번호, 주민번호를 어떤 스키마에도 넣지 않는다.
- 약제명은 일반명 소문자로 쓴다 (예: `palbociclib`). `dictionaries/drug_names.csv`로 맞춘다.
- 모든 스키마는 `additionalProperties: false`다. 정의되지 않은 필드를 넣으면 검증에서 실패한다. 필드가 필요하면 스키마를 먼저 고친다.

코드값과 한국어 표시:

| 구분 | 코드 | 표시 |
|---|---|---|
| 추출 상태 (IN-6) | `present` / `not_done` / `not_recorded` | 값 있음 / 미시행 / 기록 없음 |
| 수용체 판정 (A가 옮긴 값) | `positive` / `low_positive` (ER만) / `negative` / `indeterminate` / `unknown` (HER2만) | 양성 / 저발현 / 음성 / 판정 불가 / 알 수 없음 |
| 특수 표기 | `not_assessed` / `[Not Available]` / `[Not Applicable]` | 평가 안됨 / 기록 없음 / 해당 없음 |
| 바이오마커 상태 | `positive` / `negative` / `intermediate` / `unknown` / `not_done` / `retest_needed` / `not_recorded` | 양성 / 음성 / 중간 (Ki-67) / 판정 불가 / 미시행 / 재검 필요 / 기록 없음 (`indeterminate`는 쓰지 않음, 2026-10-15) |
| 바이오마커 세부 | `low` / `ultralow` / `vus` | 저발현 / 초저발현 / VUS (`zero`는 2026-10-15 삭제, HER2 IHC 0은 `negative`) |
| 급여 분류 | `covered` | 급여 (조건 충족) |
| | `covered_conditions_unverified` | 급여 (조건 확인 필요) |
| | `offlabel_approved` | 허가초과 인정 |
| | `no_criteria` | 급여 기준 없음 (비급여 가능성, 확인 필요) |

## 3. patient_state.json — [1] 입력 → [2], [4]

버전 `0.1-draft6` (2026-10-16, 판정 기준일·첫 재발일·투약별 차수·차수 간주 규칙 추가. draft5는 2026-10-15, 진단일 기준 일수·투여 주기·재발·전이·PD-L1·유전자 변이·anthracycline 용량 추가. B 전달 문서: [src/input/handoff_to_B.md](../src/input/handoff_to_B.md)). 필드별 표준값, 정규화 예시, TCGA 정답 규칙은 [src/input/schema_fields.md](../src/input/schema_fields.md)에 있다.

추출값 하나는 모두 같은 틀(`$defs/extracted`)이고, `value`의 형태만 필드마다 다르다.

| 항목 | 설명 |
|---|---|
| `status` | `present` / `not_done` / `not_recorded`. 필수 |
| `value` | 표준값. `present`이면 필수 |
| `raw` | 정규화 전 원문 표기 |
| `observed_date` | 검사일·기록일. `YYYY-MM-DD`, `YYYY-MM`, `YYYY` 또는 `null` |
| `specimen` | `primary` / `metastasis` / `cfDNA` / `unknown` |
| `confidence` | LLM 추출 확신도 0–1 |
| `source` | `{doc_id, quote, char_start, char_end}` 또는 `null` (TCGA 정답 1단계는 `null`, 가상 차트 생성 후 채움) |
| `history[]` | 새 결과에 밀려난 이전 값. `superseded_reason`: `recurrence`(재발 재생검으로 대체) / `newer_result` |

`fields` 그룹과 주요 `value` 형태:

| 그룹 | 필드 | `value` 형태 |
|---|---|---|
| diagnosis | `diagnosis_date`, `histology`, `grade` | 날짜 / `IDC`·`ILC`·`mucinous`·`metaplastic`·`invasive_NOS`·`other` / `1`·`2`·`3` |
| stage | `ctnm`, `ptnm` | `{t, n, m, edition}`. X값은 `not_assessed` |
| | `group` | `IIA`, `IIIC`, `IV` … 또는 `not_assessed` |
| | `disease_extent` | `early`(I~II기) / `locally_advanced`(III기, 심평원 급여 조건) / `metastatic`(IV기). 진단 시 기준 |
| | `positive_ln_count` | `{positive, examined}`. 각각 정수 또는 `"[Not Available]"` |
| | `metastatic_sites` | 부위 목록 또는 `"[Not Applicable]"` / `"[Not Available]"` |
| | `operable` | `yes` / `no` / `unknown` (수술 가능 여부) |
| receptors | `er_percent`, `pr_percent` | `{percent, range, allred, result}` 중 있는 것 모두. `allred`는 `{total, ps, is}` (강도 점수는 `allred.is`. 별도 `score` 키 없음, 2026-10-15). `result`: `positive`·`negative`·`indeterminate`, ER만 `low_positive` 추가 |
| | `her2_ihc` | `{score, faint, result}` 중 있는 것 모두. `result`는 ISH로 보정한 값 (`unknown` 포함) |
| | `her2_ish` | `{result, method}` |
| | `pdl1` | `{assay, score_type, score}`. 발현 점수. 판정은 B가 약제별로 (22C3 CPS ≥ 10 등) |
| proliferation | `ki67_percent` | `{percent, range, result}` |
| patient | `gender`, `age`, `menopausal_status`, `menopausal_basis`, `ecog` | `FEMALE`·`MALE` / 정수 / 폐경 4종 / `age_amenorrhea`·`fsh`·`oophorectomy`·`unknown` / `0`~`4` |
| treatment_history[] | 투약 기록 하나 | `drugs`, `setting`, `start_date`, `end_date`, `start_day`, `end_day`, `duration_days`, `cycles` (`{value, basis, interval_days, interval_basis}`), `progression_day`, `stop_reason`, `best_response`, `source` |
| anthracycline_drug_dose | `administered`, `drugs[]` | `positive`·`negative`·`No value` / 약별 `dose_per_admin`, `cycles`, `total_dose` (`{value, unit}` 또는 `"No value"`) |
| neoadjuvant_response | `pcr`, `rcb` | `yes`·`no` / `RCB-0`~`RCB-III` |
| recurrence | `recurrence_date`, `adjuvant_endocrine_end_date` | 날짜 |
| | `status` | `none`·`distant`·`locoregional`·`site_unknown`·`unknown` |
| | `metastatic_sites`, `metastasis_day` | 재발 전이 부위 목록 / 전이 기준일 (진단일 = 0, 진단 시 IV기 = 0) |
| | `surgery`, `surgery_intent`, `later_distant` | 재발 후 수술 `yes`·`no`·`unknown` / `curative`·`palliative`·`unknown` / 국소 재발 후 원격 전이 `yes`·`no`·`unknown` |
| molecular | `mutations.{ESR1, PIK3CA, AKT1, PTEN, BRCA1, BRCA2, PALB2}` | `{status, result, variants[], specimen}`. 변이 있음 = `detected`, 변이 없음 = `not_detected`, 미시행 = `status: not_done` |
| genomic_reports[] | 보고서 하나 | `doc_id`, `report_date`, `specimen`, `raw_text` (해석하지 않음) |

TCGA 정답은 실제 날짜가 없으므로, 날짜 칸은 추출값이면 `status: not_recorded`, 치료 이력·보고서의 날짜는 `null`이다. 대신 진단일 기준 일수(`*_day`)를 넣는다. 차수는 A가 변환할 때 `start_day`와 `metastasis_day`로 계산해 `treatment_history[].line`·`endocrine_line`·`chemo_line`에 넣고, 심평원 간주 규칙 충족 여부는 `fields.deemed_lines`에 넣는다 (2026-10-16 draft6. 2026-10-15에는 B가 판단하기로 했었다).

예시 (가상 차트에서 추출한 경우):

```json
{
  "schema_version": "0.1-draft6",
  "patient_ref": "VC-0001",
  "created_at": "2026-10-12T09:00:00+09:00",
  "documents": [
    {"doc_id": "D1", "doc_type": "pathology", "doc_date": "2024-03-05"},
    {"doc_id": "D2", "doc_type": "molecular", "doc_date": "2026-07"}
  ],
  "fields": {
    "diagnosis": {
      "histology": {"status": "present", "value": "IDC", "raw": "invasive ductal carcinoma", "confidence": 0.98,
                    "source": {"doc_id": "D1", "quote": "invasive ductal carcinoma, grade 2"}}
    },
    "stage": {
      "ptnm": {"status": "present", "value": {"t": "T2", "n": "N1a", "m": "M0", "edition": "8th"}, "raw": "pT2 pN1a M0",
               "source": {"doc_id": "D1", "quote": "pT2 pN1a M0"}},
      "positive_ln_count": {"status": "present", "value": {"positive": 2, "examined": 15}, "raw": "LN 2/15 (+)",
                            "source": {"doc_id": "D1", "quote": "LN 2/15 (+)"}},
      "disease_extent": {"status": "present", "value": "early", "raw": "pT2 pN1a M0",
                         "source": {"doc_id": "D1", "quote": "pT2 pN1a M0"}}
    },
    "receptors": {
      "er_percent": {"status": "present", "value": {"percent": 95, "result": "positive"}, "raw": "ER(+) 95%", "specimen": "primary",
                     "source": {"doc_id": "D1", "quote": "ER(+) 95%"}},
      "her2_ihc": {"status": "present", "value": {"score": "2+", "result": "negative"}, "raw": "HER2 (4B5) 2+, SISH 음성", "specimen": "primary",
                   "source": {"doc_id": "D1", "quote": "HER2 (4B5) 2+"}},
      "her2_ish": {"status": "present", "value": {"result": "not_amplified", "method": "SISH"}, "raw": "SISH 음성",
                   "source": {"doc_id": "D1", "quote": "SISH 음성"}}
    },
    "proliferation": {},
    "patient": {
      "gender": {"status": "present", "value": "FEMALE", "raw": "F/62", "source": {"doc_id": "D1", "quote": "F/62"}},
      "menopausal_status": {"status": "present", "value": "postmenopausal", "raw": "폐경 후", "confidence": 0.9,
                            "source": {"doc_id": "D1", "quote": "폐경 후"}}
    },
    "treatment_history": [
      {"drugs": ["letrozole", "palbociclib"], "setting": "metastatic", "start_date": "2025-01-10", "end_date": "2026-06-20",
       "duration_days": 526, "start_day": 300, "end_day": 826, "cycles": null,
       "stop_reason": "progression", "best_response": "PR",
       "source": {"doc_id": "D1", "quote": "AI + palbociclib, PD"}}
    ],
    "anthracycline_drug_dose": {"administered": "negative", "drugs": []},
    "neoadjuvant_response": {},
    "recurrence": {
      "recurrence_date": {"status": "not_recorded"},
      "status": {"status": "present", "value": "distant"},
      "metastasis_day": {"status": "present", "value": 290}
    },
    "molecular": {"mutations": {}},
    "genomic_reports": [
      {"doc_id": "D2", "report_date": "2026-07", "specimen": "cfDNA", "raw_text": "ESR1 p.Y537S detected, VAF 4.2%"}
    ]
  },
  "conflicts": []
}
```

## 4. biomarker_record.json — [2] → [3] 필터, [4]

파일 이름은 `biomarker_record`지만, 모듈 출력 전체(레코드 목록 + 아형 + 치료 상황 + 검사 공백)를 정의한다.

| 필드 | 설명 |
|---|---|
| `records[]` | 마커별 판정 결과. `marker`, `status`, `reason`, `rule_id`, `evidence`, `source_span`, `rag_tags` |
| `subtype` | `HR+/HER2-` / `HR+/HER2+` / `HR-/HER2+` / `TNBC` / `unknown` (ER·PR·HER2 판정이 없어 정할 수 없음. `indeterminate`는 쓰지 않음, 2026-10-15). RAG 하드 필터 |
| `setting` | `disease`(early / locally_advanced / metastatic / unknown. 진단 시 전이성 또는 원격 전이 재발 → metastatic, 그 밖은 진단 시 범주. unknown은 진단 시 병기를 모를 때만), `line`(neoadjuvant / adjuvant / 1L / 2L / >=3L / unknown), 이전 약제 계열. RAG 하드 필터 |
| `tests_needed[]` | BM-4 검사 공백. `test`, `reason`, `rule_id` |

마커별 허용 상태값 (BM-2 판정 기준표, PROJECT.md §5):

| 마커 | 허용 status |
|---|---|
| HER2 | positive, low, ultralow, negative, unknown, not_done, not_recorded (IHC 0 → negative, `zero`·`indeterminate`는 쓰지 않음. ultralow는 심평원 기준 최종 음성, 2026-10-15) |
| ER | positive, low, negative, unknown, not_done, not_recorded (unknown = 값은 있지만 percent·range·Allred·적힌 판정 중 판정에 쓸 값이 없음. indeterminate는 쓰지 않음, 2026-10-15) |
| PR | positive, negative, unknown, not_done, not_recorded (indeterminate는 쓰지 않음, 2026-10-15) |
| Ki-67 | positive (기준 이상, 고증식), negative, intermediate (구간이 기준에 걸치거나 적힌 판정이 intermediate), unknown (쓸 값 없음), not_done, not_recorded (`evidence.percent` 사용. 기준값 20%, 2026-10-15 확정) |
| gBRCA1, gBRCA2, PALB2 | positive, negative, vus, not_done, not_recorded. TCGA 정답 세트에서는 `molecular.mutations.BRCA1/2`를 gBRCA 측정으로 가정해 판정 (2026-10-15 협의) |
| sBRCA1, sBRCA2, PIK3CA, AKT1, PTEN | positive, negative, not_done, not_recorded |
| ESR1 | positive, negative, retest_needed, not_done, not_recorded |
| PD-L1 | positive, negative, not_done, not_recorded (`evidence.assay`, `evidence.score` 함께 저장) |

이 표는 아직 스키마로 강제하지 않는다. 0단계 검토 후 B가 마커별 `if/then` 검사로 추가한다.

```json
{
  "schema_version": "0.1-draft",
  "patient_ref": "VC-0001",
  "records": [
    {"marker": "HER2", "status": "unknown", "reason": "IHC 2+ 인데 ISH 미시행, 적힌 판정 unknown. 판정 불가, ISH 검사 권고", "rule_id": "BM2-HER2-2PLUS-NOISH",
     "evidence": {"test_date": "2024-03-05", "assay": "4B5"},
     "source_span": {"doc_id": "D1", "quote": "HER2 (4B5) 2+"}, "rag_tags": []},
    {"marker": "ESR1", "status": "positive", "reason": "cfDNA에서 활성화 변이 검출, 마지막 진행(2026-06) 이후 검사", "rule_id": "BM2-ESR1-01",
     "evidence": {"test_date": "2026-07-01", "specimen": "cfDNA", "variant": "p.Y537S", "vaf": 0.042},
     "source_span": {"doc_id": "D2", "quote": "ESR1 p.Y537S detected, VAF 4.2%"}, "rag_tags": ["ESR1-mut"]}
  ],
  "subtype": "HR+/HER2-",
  "setting": {"disease": "metastatic", "line": "2L", "prior_drug_classes": ["aromatase inhibitor", "CDK4/6 inhibitor"],
              "reason": "전이성 1차 AI + palbociclib 진행 후"},
  "tests_needed": [
    {"test": "HER2 ISH", "reason": "IHC 2+인데 ISH가 없어 HER2 상태 불확정", "rule_id": "BM4-HER2-ISH"},
    {"test": "PIK3CA·AKT1·PTEN", "reason": "HR+/HER2- 전이성에서 미시행", "rule_id": "BM4-PI3K"}
  ]
}
```

## 5. chunk.json — [3], [5] → 공용 색인 → [4]

지침 청크와 급여 청크가 같은 형식을 쓰고 `doc_type`으로 나뉜다.

| 필드 | 설명 |
|---|---|
| `chunk_id`, `doc_type`, `source`, `version`, `section`, `page_start`, `page_end`, `url`, `text` | 출처와 본문 |
| `chunk_kind` | recommendation / section / algorithm / table_row / reimbursement_condition / offlabel_regimen |
| `parent_id` | 부모 소단원 청크. LLM에는 부모 전체를 함께 넘긴다 |
| `setting`, `subtype`, `line` | 하드 필터. `setting`은 early(I~II기) / locally_advanced(III기) / metastatic. `subtype`·`line`은 해당 없으면 `any` |
| `biomarker_tags`, `drugs` | 가중치, 키워드 검색 |
| `evidence` | LoE, GoR, ESMO-MCBS, ESCAT |
| `superseded_by` | 후속 개정 청크 ID. 대체된 청크는 지우지 않는다 |
| `copyright_notice` | ESMO 청크에 저작권 문구 |
| `reimbursement` | **급여 청크에만 필수.** `source_type`(baseline / overlay / preview), `notice_no`, `effective_from`, `regimen`, `conditions`, `copay` |

검색은 `reimbursement.effective_from`이 오늘 이전인 baseline·overlay 청크만 판정에 쓴다. preview는 안내용이다. `conditions`의 세부 키는 D가 정하고 B가 검토한다.

```json
{
  "schema_version": "0.1-draft",
  "chunk_id": "hira-booklet-20261001-p52-c02",
  "doc_type": "reimbursement",
  "source": "HIRA-booklet",
  "version": "2026-10-01",
  "section": "9. 유방암 > 2. 수술후보조요법",
  "page_start": 52,
  "page_end": 52,
  "url": "https://www.hira.or.kr/",
  "chunk_kind": "reimbursement_condition",
  "parent_id": null,
  "text": "(예시 문장) 호르몬 수용체 양성, HER2 음성, 림프절 양성으로 재발 위험이 높은 조기 유방암의 수술후보조요법 ...",
  "setting": ["early"],
  "subtype": ["HR+/HER2-"],
  "line": ["adjuvant"],
  "biomarker_tags": [],
  "drugs": ["abemaciclib"],
  "evidence": null,
  "superseded_by": null,
  "copyright_notice": null,
  "reimbursement": {
    "source_type": "baseline",
    "notice_no": "제2026-210호",
    "effective_from": "2026-10-01",
    "regimen": ["abemaciclib", "endocrine therapy"],
    "conditions": {"hr": "positive", "her2": "negative", "positive_ln_count_min": 4},
    "copay": null
  }
}
```

쪽 번호, 공고번호, 본문은 형식 설명용 예시다. 실제 값은 D가 공고에서 확인해 채운다.

## 6. recommendation.json — [4] → 화면

| 필드 | 설명 |
|---|---|
| `options[]` | `therapy`, `drugs`, `rationale`, `evidence`, `guideline_source`(ESMO / ASCO, 합치지 않음), `citations`(지침 청크 ID, 1개 이상), `reimbursement`, `reimbursement_reason`, `reimbursement_citations`, `copay`, `pending_notices` |
| `tests_needed[]` | 검사 권고. `blocks_therapy`에 이 검사가 없어 추천 대신 권고로 바꾼 치료를 적는다 |
| `out_of_scope`, `out_of_scope_reason` | 범위 외이거나 검색 결과가 없으면 추천을 만들지 않는다 |
| `conflicts[]` | 예: ESMO와 ASCO 권고 차수가 다름 |
| `index_status` | 화면 하단 요약 (공고책자 날짜, 덧씌운 공고, 예정·진행중 개수). D가 값을 제공 |

스키마가 강제하는 규칙: `citations`는 1개 이상이고, 급여 분류가 `no_criteria`가 아니면 `reimbursement_citations`도 1개 이상이어야 한다.

```json
{
  "schema_version": "0.1-draft",
  "patient_ref": "VC-0001",
  "generated_at": "2026-10-12T09:00:05+09:00",
  "model": "local-llm-tbd",
  "options": [
    {"therapy": "elacestrant 단독", "drugs": ["elacestrant"],
     "rationale": "(예시) ESR1 변이 HR+/HER2- 전이성, CDK4/6 억제제 진행 후 2차 치료로 권고",
     "evidence": "LoE I, GoR A", "guideline_source": "ESMO",
     "citations": ["esmo-mbc-2026-05-hrpos-2l-r03"],
     "reimbursement": "no_criteria", "reimbursement_reason": "급여 기준과 허가초과 인정 목록에 해당 항목 없음",
     "reimbursement_citations": [], "copay": null, "pending_notices": []}
  ],
  "tests_needed": [
    {"test": "HER2 ISH", "reason": "IHC 2+, ISH 미시행", "blocks_therapy": "HER2 표적치료"}
  ],
  "out_of_scope": false,
  "out_of_scope_reason": null,
  "conflicts": [],
  "index_status": {"booklet_date": "2026-10-01", "overlay_notices": [], "scheduled_count": 0, "in_progress_count": 0}
}
```

예시의 권고 문장과 급여 분류는 형식 설명용이다. 실제 판단 근거가 아니다.

## 7. 검증 방법

```python
import json
from jsonschema import Draft202012Validator

schema = json.load(open("schemas/patient_state.json", encoding="utf-8"))
Draft202012Validator(schema).validate(data)  # 실패하면 ValidationError
```

`jsonschema` 패키지가 필요하다: `conda install -n team_project jsonschema`

## 8. 0단계에서 정할 것

- [x] `biomarker_record.setting`(치료 단계·차수)을 누가 산출하나 → B (2026-10-15 협의). A는 `treatment_history[].start_day`와 `recurrence.metastasis_day`를 넘긴다
- [ ] 마커별 허용 상태값을 스키마로 강제할지 (B)
- [ ] `chunk.reimbursement.conditions` 세부 키 목록 (D 초안, B 검토)
- [ ] 검색 API 반환 형식: chunk 목록 + 점수 + 부모 청크. 별도 스키마(`search_result.json`)로 만들지 (C)
- [ ] 화면용 한국어 표시 매핑을 코드 어디에 둘지 (`schemas/labels.py` 등)
