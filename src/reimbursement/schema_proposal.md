# schemas/chunk.json 개정안 (D 제안, 4명 검토 필요)

근거: B의 급여 청킹 설계 문서 `reimbursement_chunking_design.md`(2026-10-16)와 `reimbursement_field_values.csv`의 output 행.
지금 `chunk.json`의 `reimbursement`는 `additionalProperties: false`라서 아래 칸이 들어갈 수 없다.
반영 전까지 D는 공용 스키마에 이 칸을 더해 검사한다 (`chunks.REIMBURSEMENT_EXTENSION`).
청크 파일에는 이미 이 칸이 들어 있으니, 공용 스키마로만 검사하는 쪽(C의 색인 등)에서는 개정 전까지 이 칸을 무시해야 한다.

## `reimbursement`에 더할 칸

| 칸 | 형식 | 값 | 설계 근거 |
|---|---|---|---|
| `stage` | enum | neoadjuvant, adjuvant, palliative_endocrine, palliative_chemo, combination, supportive | §2.1 L2, csv output L2 |
| `her2_section` | enum 또는 null | positive, negative | §2.1, 선행화학요법 소단원만 |
| `line_rule` | enum 또는 null | 1차, 1차 이상, 2차, 2차 이상, 3차 이상 | §2.1, §3.1 |
| `history` | 배열 | `{notice_no, effective_from}` (시행일 순) | §2.4 |
| `regimen_parsed` | 객체 | `sequence`, `optional_drugs`, `routes`, `copay_by_drug`, `fixed_dose_combination` | §8.4 |
| `regimen_list` | 배열 | `{regimen, setting, drugs}` (G-CSF 예방 요법 목록) | §10.2 |
| `combination` | 객체 | `added_drug[]`, `added_drug_coverage`(비급여, 100/100, null), `base_regimen[]` | §1.4, §2.1 |
| `conditions_inherited_from` | 문자열 또는 null | 예: `r01` (병합 셀을 물려받은 위 연번) | §2.2 |
| `text_normalized` | 문자열 | NFKC 정규화한 본문 (판정용, ①→1, ㎝→cm) | §5 |

## `reimbursement.copay`

지금은 문자열 하나라서 약제별 본인부담을 `"pertuzumab 30/100"`처럼 적는다. 구조화된 값은 `regimen_parsed.copay_by_drug`에 있다.

## `reimbursement.conditions` 형식 (§3.5, D와 B 합의 대상)

`all_of`, `any_of`(묶음 안에서 하나 이상, §3.5에 없는 칸이라 추가 제안), `any_of_exceptions`, `line_rule`, `stage_rules`,
`counts_as_prior_line`, `notes`, `human_review`, `unmapped`.
조건 항목은 `{id, field, op, value, text[, of][, unless]}`이다. field 어휘와 환자 JSON 경로는 `conditions.FIELDS`에 있고,
op는 설계의 8개에 `contains`(이전 치료에 있어야 함)를 더했다.

읽는 법 (2026-10-19, 131개 행을 채우며 정한 것):

- `all_of`는 모두 만족해야 한다. `any_of`는 묶음 목록이고, 묶음마다 항목 하나 이상을 만족해야 한다.
- `any_of_exceptions`의 각 예외는 `all_of` 항목을 모두 만족하면, `any_of` 묶음이 실패해도 통과로 본다.
  예: '전이성 또는 절제 불가능한 국소 재발성'은 `any_of`에 전이성, 예외에 국소 재발 + 절제 불가.
- `prior_drugs contains [A, B]`는 A와 B를 모두 받은 것이다. `not_contains [A, B]`는 둘 다 받은 적이 없는 것이다.
  'A 또는 B를 받은'은 `any_of` 묶음에 항목을 나눠 넣는다. `prior_failed`도 같다.
- `unless`는 그 항목이 실패해도 unless 조건을 만족하면 통과로 본다 (예: 보조요법 종료 1년 이후 재발).
- 공고 표현을 칸·값으로 옮기는 기준은 팀 사전 `data/dictionaries/reimbursement_terms.csv`다 (2026-10-20 대조, 테스트로 확인).
  고식적요법은 `of.setting [metastatic]`, 림프절 양성·음성은 `ln_status`(N 병기), HER2 음성은 `[negative, low, ultralow, zero]`,
  국소진행성·전이성은 `stage.disease_extent`(진단 시)라서 '재발성'은 `recurrence`로 따로 적는다.
- `stage_group`의 `III`는 IIIA~IIIC를 포함한다 (사전: stage Ⅲ = `III`). 판정할 때 하위 병기는 주 병기로 비교한다.

## 검토 의견

- C (2026-10-20): 찬성. C의 색인·검색은 지침 청크만 공용 스키마로 검사하므로 `reimbursement` 아래 새 칸이 있어도 깨지지 않는다.
  `text_normalized`는 지침 청크에도 쓸 만하니(인용은 `text`, 판정·검색은 정규화본) `reimbursement` 아래가 아니라 청크 최상위 칸으로 두자는 제안.
  → D도 찬성. 정해지면 D 청크도 최상위로 옮긴다 (지금은 `reimbursement.text_normalized`).
- 부모 청크 방식: C의 #9부터 지침 청크도 "자식만 색인, 부모(`chunk_kind: section`)는 파일에 두고 `parent_id`로 찾음"이라 D와 같다.

## 함께 정할 것 (D 제안, 2026-10-20)

### `line_rule` 값

공고 표기 그대로 한국어(`1차`, `1차 이상`, `2차`, `2차 이상`, `3차 이상`)를 둔다. 원문 대조와 화면 표시에 그대로 쓰기 위해서다.
판정할 때는 `biomarker_record.setting.line`(`1L`, `2L`, `>=3L`)과 아래처럼 맞춘다. 차수는 `stage`에 따라 내분비·항암을 따로 센다.

| `line_rule` | 이번에 줄 치료의 차수 | `setting.line` 예 |
|---|---|---|
| `1차` | 1 | `1L` |
| `1차 이상` | 1 이상 | `1L`, `2L`, `>=3L` |
| `2차` | 2 | `2L` |
| `2차 이상` | 2 이상 | `2L`, `>=3L` |
| `3차 이상` | 3 이상 | `>=3L` |

영문 코드로 바꾸자는 의견이 있으면 `first`, `first_plus`, `second`, `second_plus`, `third_plus`를 제안한다.

### `copay`와 `regimen_parsed.copay_by_drug`

- `copay_by_drug`를 기준값으로 한다 (약제별 본인부담, 없으면 빈 객체).
- `copay`는 요법 전체에 하나로 정해질 때만 그 값(예: `"5/100"`)을 두고, 약제마다 다르면 `null`로 둔다.
  지금처럼 `"pertuzumab 30/100"` 같은 문장을 넣지 않는다.
- 이렇게 바꾸면 `copay`의 형식이 지금 공용 스키마(문자열)와 달라지므로 `["string", "null"]`로 넓힌다.

### 차수 간주 규칙 (`counts_as_prior_line`)과 draft6 `fields.deemed_lines[]`

| 공고 규칙 | 급여 청크 | `deemed_lines[].rule_id` |
|---|---|---|
| anthracycline·taxane 포함 선행·보조 → 1차로 간주 | 고식적 항암 2차 이상 연번 2~18, 병용요법 연번 24 (`counts_as_prior_line`) | `DEEM-ANTHRA-TAXANE` |
| 선행·보조 종료 1년 이내 재발 → 1차로 간주 | sacituzumab govitecan (`counts_as_prior_line`, `within_days` 365) | `DEEM-SG-1Y` |
| 보조요법 중·종료 6개월 이내 재발도 인정 | T-DM1, T-DXd (`prior_failed`의 `unless`, 183일) | `DEEM-HER2ADC-6M` |
| 보조 내분비요법 중·종료 1년 이내 진행도 인정 | 고식적 내분비 2차 이상 연번 4~9 (`any_of`의 `days_end_to_recurrence` 365) | `DEEM-ENDO-ADJ-1Y` |

판정 쪽은 `deemed_lines[]`의 `status`가 `met`이면 그 규칙을 충족한 것으로, `unknown`이면 확인 필요로 본다.

### 바이오마커 status가 판정값이 아닐 때

`biomarker_record.records[].status`가 `positive`·`negative`·`low`·`ultralow`가 아니면 조건 항목은 참·거짓이 아니라 "알 수 없음"으로 둔다.

| status | 조건 항목 결과 | 행 판정 |
|---|---|---|
| `not_done` | 알 수 없음 | 급여 아님이 아니라 "검사 필요" |
| `retest_needed` | 알 수 없음 | "재검 필요" |
| `not_recorded`, `unknown` | 알 수 없음 | "기록 확인 필요" |
| `vus` | `eq positive`는 거짓 (PROJECT.md §5: VUS는 음성 처리, 표시 유지) | 급여 아님 + VUS 표시 |

"알 수 없음"이 하나라도 있는 행은 다른 조건이 모두 맞아도 `covered`가 아니라 `covered_conditions_unverified`로 둔다.
