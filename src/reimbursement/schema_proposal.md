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
