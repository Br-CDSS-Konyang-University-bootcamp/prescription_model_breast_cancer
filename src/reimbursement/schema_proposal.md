# schemas/chunk.json 개정안 (D 제안, 4명 검토 필요)

근거: B의 급여 청킹 설계 문서 `reimbursement_chunking_design.md`(2026-10-16)와 `reimbursement_field_values.csv`의 output 행.
2026-10-21 현재: 아래 "`reimbursement`에 더할 칸"은 main의 `chunk.json`에 합쳐졌다. 남은 것은 청크 최상위 `text_normalized`
(회의 1)와 `copay` 설명(회의 3)이고, PR `schema/chunk-text-normalized`로 올린다.
합쳐지기 전까지 D는 공용 스키마에 없는 칸만 더해 검사한다 (`chunks.REIMBURSEMENT_EXTENSION`, `TOP_LEVEL_EXTENSION`).

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

## 청크 최상위에 더할 칸

| 칸 | 형식 | 값 | 근거 |
|---|---|---|---|
| `text_normalized` | 문자열 (필수 아님) | NFKC 정규화한 본문 (판정용, ①→1, ㎝→cm). 인용과 의미 검색은 `text` | 설계 §5. 최상위에 둔다 (회의 1 결정, 2026-10-21) |

회의 1 결정 (2026-10-21): 최상위로 옮기되 필수 칸으로 두지 않는다. ESMO 지침은 영어라 이미 정리된 글이어서 이 칸이 필요 없고,
필수로 하면 지침 청크를 모두 고쳐야 한다. 검색은 지금처럼 원문 `text`로 한다 (C의 색인은 `text`로 의미 검색, 급여 검색은 문장이
아니라 약 이름·날짜로 거름). 그래서 칸을 옮겨도 C 검색 코드는 바뀌지 않는다. `schemas/chunk.json`은 공용 파일이라 4명 검토가 필요하다.

## `reimbursement.copay`

요법 전체에 하나로 정해질 때만 값을 두고, 일부 약제에만 붙은 값은 `null`이다. 약제별 값은 `regimen_parsed.copay_by_drug`에 있다
(아래 "copay와 regimen_parsed.copay_by_drug", 2026-10-20 D 반영).

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
- `cycles_total`의 `of.drugs [A, B]`는 A나 B가 하나라도 들어간 `treatment_history[]` 항목(요법 하나)의 `cycles.value`를
  항목마다 한 번씩 더한 값이다. 예: 'trastuzumab ± pertuzumab 투여 주기 18주기 이하' -> `of.drugs [trastuzumab, pertuzumab]`,
  'trastuzumab + pertuzumab 6주기' 항목은 6으로 센다 (12가 아님).
- 공고 표현을 칸·값으로 옮기는 기준은 팀 사전 `data/dictionaries/reimbursement_terms.csv`다 (2026-10-20 대조, 테스트로 확인).
  고식적요법은 `of.setting [metastatic]`, 림프절 양성·음성은 `ln_status`(N 병기), HER2 음성은 `[negative, low, ultralow]`
  (값은 B의 `biomarker_record` 값 기준. 사전에는 `zero`가 있지만 B는 IHC 0을 `negative`로 내보내고 `zero`를 쓰지 않으므로 뺐다, 2026-10-20),
  국소진행성·전이성은 사전 값(early / locally_advanced / metastatic)을 쓰되 칸은 `biomarker_record.setting.disease`다.
  사전은 `stage.disease_extent`(진단 시)로 적었지만, 스키마 설명("재발 후 상태는 `biomarker_record.setting.disease`")과
  `handoff_to_B.md` §6.1에 따라 원격 재발까지 담은 지금 범위를 쓴다. 그렇지 않으면 원문에 '전이성'만 있는 23행에서
  진단 후 원격 재발한 환자가 빠진다. 국소 재발은 `setting.disease`에 들어가지 않으므로 '재발성'은 `recurrence`로 따로 적는다.
  (사전의 칸을 `setting.disease`로 맞출지 팀에 확인 필요)
- `stage_group`의 `III`는 IIIA~IIIC를 포함한다 (사전: stage Ⅲ = `III`). 판정할 때 하위 병기는 주 병기로 비교한다.

## 검토 의견

- C (2026-10-20): 찬성. C의 색인·검색은 지침 청크만 공용 스키마로 검사하므로 `reimbursement` 아래 새 칸이 있어도 깨지지 않는다.
  `text_normalized`는 지침 청크에도 쓸 만하니(인용은 `text`, 판정·검색은 정규화본) `reimbursement` 아래가 아니라 청크 최상위 칸으로 두자는 제안.
  → 2026-10-20 결정: 최상위 칸으로 옮김. D 청크는 `text_normalized`를 최상위에 두고 `reimbursement` 안에는 두지 않는다.
- 부모 청크 방식: C의 #9부터 지침 청크도 "자식만 색인, 부모(`chunk_kind: section`)는 파일에 두고 `parent_id`로 찾음"이라 D와 같다.

## 함께 정할 것 (D 제안 2026-10-20, 회의 2·3 결정 2026-10-21)

### `line_rule` 값

회의 2 결정 (2026-10-21): 아래 D 제안대로 한국어 그대로 + 대응표. 다른 팀원 문서에 다른 의견이 없고 B가 동의했다.

공고 표기 그대로 한국어(`1차`, `1차 이상`, `2차`, `2차 이상`, `3차 이상`)를 둔다. 원문 대조와 화면 표시에 그대로 쓰기 위해서다.
판정할 때는 고식적 내분비요법과 고식적 항암화학요법의 차수를 따로 센다 (공고 55쪽, A handoff §6.3a). 그래서 전체 차수 `biomarker_record.setting.line`이 아니라 `stage`에 맞는 차수와 맞춘다.
`palliative_endocrine` 행은 `setting.line_endocrine`(confirmed_state `setting.line_endocrine`), `palliative_chemo` 행은 `setting.line_chemo`(confirmed_state `setting.line_chemo`)를 쓴다.
이 두 값에는 간주 규칙이 들어 있지 않으므로, 행의 `counts_as_prior_line`에 맞는 규칙(`fields.deemed_lines`)이 `met`이면 차수에 1을 더해 비교한다 (아래 "차수 간주 규칙").

| `line_rule` | 이번에 줄 치료의 차수 | `setting.line_endocrine`·`line_chemo` 예 |
|---|---|---|
| `1차` | 1 | `1L` |
| `1차 이상` | 1 이상 | `1L`, `2L`, `>=3L` |
| `2차` | 2 | `2L` |
| `2차 이상` | 2 이상 | `2L`, `>=3L` |
| `3차 이상` | 3 이상 | `>=3L` |

(영문 코드 `first`, `first_plus`, `second`, `second_plus`, `third_plus` 안은 쓰지 않기로 했다.)

### `copay`와 `regimen_parsed.copay_by_drug`

회의 3 결정 (2026-10-21): 아래 D 제안대로. B 동의, 다른 팀원 문서에 다른 의견 없음.

- `copay_by_drug`를 기준값으로 한다 (약제별 본인부담, 없으면 빈 객체).
- `copay`는 요법 전체에 하나로 정해질 때만 그 값(예: `"5/100"`)을 두고, 약제마다 다르면 `null`로 둔다.
  지금처럼 `"pertuzumab 30/100"` 같은 문장을 넣지 않는다.
- 공용 스키마의 `copay`는 이미 `["string", "null"]`이라 형식은 그대로다. 설명만 고친다.
- B 동의 (2026-10-20). D 청크에 반영함: `copay`가 있는 행은 단일 약제 요법 2행(`50/100`)뿐이고,
  pertuzumab·bevacizumab에만 붙은 7행(선행 HER2 양성 연번 4~6 `30/100`, 수술후보조 연번 22~24·고식적 항암 1차 연번 4 `100/100`)은 `null`.
- 함께 고칠 공용 파일 설명 (4명 검토):
  - `schemas/chunk.json` `reimbursement.copay`: 스키마 PR(`schema/chunk-text-normalized`)에 넣음. 새 급여 칸은 이미 main에 합쳐짐 (2026-10-21 확인).
  - `schemas/recommendation.json` `options[].copay`: 지금 "허가초과 인정일 때 본인부담률"뿐이라 B가 약별 본인부담률을
    적을 수 없다. 설명만 고치는 PR로 올림 (형식은 그대로): 허가초과 인정이면 그 본인부담률, 급여 요법은 `reimbursement.copay`,
    약제마다 다르면 `copay_by_drug`를 약제별로 이어 씀 (예: pertuzumab 30/100). 합쳐지면 B가 추천 결과를 그렇게 쓴다.

### 차수 간주 규칙 (`counts_as_prior_line`)과 draft6 `fields.deemed_lines[]`

| 공고 규칙 | 급여 청크 | `deemed_lines[].rule_id` |
|---|---|---|
| anthracycline·taxane 포함 선행·보조 → 1차로 간주 | 고식적 항암 2차 이상 연번 2~18, 병용요법 연번 24 (`counts_as_prior_line`) | `DEEM-ANTHRA-TAXANE` |
| 선행·보조 종료 1년 이내 재발 → 1차로 간주 | sacituzumab govitecan (`counts_as_prior_line`, `within_days` 365) | `DEEM-SG-1Y` |
| 보조요법 중·종료 6개월 이내 재발도 인정 | T-DM1, T-DXd (`prior_failed`의 `unless`, 183일). 투여단계(2차 이상)도 이 규칙으로 1차를 받은 것으로 보므로 `counts_as_prior_line`에 `rule_id: DEEM-HER2ADC-6M`으로도 적는다 (2026-10-22, B 요청) | `DEEM-HER2ADC-6M` |
| 보조 내분비요법 중·종료 1년 이내 진행도 인정 | 고식적 내분비 2차 이상 연번 4~9, 병용 연번 29 (`any_of`의 `days_end_to_metastasis` lte 365: A와 같이 종료일부터 **전이 기준일**까지, B 확인 2026-10-20). 투여단계(2차 이상)도 이 규칙으로 1차를 받은 것으로 보므로 `counts_as_prior_line`에 `rule_id: DEEM-ENDO-ADJ-1Y`로도 적는다 (2026-10-22, VC-0103). 적용 행은 공고 원문에 이 문구가 있는 행뿐이고 (같은 소단원의 연번 1~3에는 없음), A handoff §6.3a 표의 '쓰는 요법'(AI·exemestane + LHRH, CDK4/6 + fulvestrant)과 같다 | `DEEM-ENDO-ADJ-1Y` |

`counts_as_prior_line` 항목에 `rule_id`가 있으면 판정 쪽은 그 규칙의 `deemed_lines[].status`를 그대로 본다. 없으면 지금처럼
약(anthracycline·taxane → `DEEM-ANTHRA-TAXANE`)과 `within_days` 365(→ `DEEM-SG-1Y`)로 맞춘다.
예: VC-0103(보조 anastrozole 중 폐 전이)은 DEEM-ENDO-ADJ-1Y가 met이라 전이 후 첫 내분비 치료가 공고상 '2차 이상' 행(CDK4/6 + fulvestrant)의 대상이다.
| 보조로 비스테로이드성 AI를 썼으면 종료 1년 **이후** 재발 / 폐경 전 보조 내분비·항암 종료 1년 **이내** 재발 | 고식적 내분비 1차(3가) 연번 1~6 (`unless`의 `days_end_to_metastasis` gt 365, 예외의 lte 365) | `DEEM-ENDO-ADJ-1Y`와 같은 기준 (1년 이후 = not_met). A 답변 2026-10-21 |
| (간주 규칙 아님) 보조 CDK4/6 억제제 종료 후 12개월 **초과** | 병용 연번 29 (`days_end_to_metastasis` gt 365, of CDK4/6) | DEEM 값을 쓰지 않음: 기준 약(CDK4/6)과 경계(초과)가 다르고 끝점(전이 기준일)만 같음 (A 답변 2026-10-21) |

A가 전이 기준일로 세라고 한 것은 3가뿐이라, 그 밖에 '재발'로 적힌 기간 조건은 첫 재발일(`days_end_to_recurrence`) 그대로 둔다:
고식적 내분비 2차 이상 연번 4~6, 고식적 항암 1차 연번 3·4, 1차 이상 연번 18, 2차 이상 연번 21·22, 병용 연번 21.
같은 원칙을 적용할지는 A에게 확인 중이다 (2026-10-21). 전이 기준일로 세면 국소 재발만 있는 환자는 알 수 없음이 된다.

판정 쪽은 `deemed_lines[]`의 `status`가 `met`이면 그 규칙을 충족한 것으로, `unknown`이면 확인 필요로 본다.

### 바이오마커 status가 판정값이 아닐 때

`biomarker_record.records[].status`가 `positive`·`negative`·`low`·`ultralow`가 아니면 조건 항목은 참·거짓이 아니라 "알 수 없음"으로 둔다.

| status | 조건 항목 결과 | 행 판정 |
|---|---|---|
| `not_done` | 알 수 없음 | 급여 아님이 아니라 "검사 필요" |
| `retest_needed` | 알 수 없음 | "재검 필요" |
| `not_recorded`, `unknown` | 알 수 없음 | "기록 확인 필요" |
| 그 마커의 줄이 아예 없음 | 알 수 없음 | "기록 확인 필요". BRCA1/2는 모든 차트에서 gBRCA로 보고 sBRCA 레코드는 만들지 않는다 (A 결정 2026-10-21, handoff §4.7). 그래서 `sbrca` 조건은 늘 알 수 없음 (쓰는 행 없음) |
| `vus` | `eq positive`는 거짓 (PROJECT.md §5: VUS는 음성 처리, 표시 유지) | 급여 아님 + VUS 표시 |

"알 수 없음"이 하나라도 있는 행은 다른 조건이 모두 맞아도 `covered`가 아니라 `covered_conditions_unverified`로 둔다.

### 환자 칸 값이 판정값이 아닐 때 (A의 `data_needs_by_module_2026-10-20.md` §6, 2026-10-20)

`patient_state` 칸도 위와 같다. 아래 값이면 조건 항목은 "알 수 없음"이고 행은 `covered_conditions_unverified`다.

| 칸 | 값 | 사유 표시 |
|---|---|---|
| 추출 칸 전체 | `status`가 `not_recorded` / `not_done` | "기록 없음" / "미시행" |
| `patient.menopausal_status` | `indeterminate` (그리고 위 두 status) | "폐경 상태 기록 없음/미시행/판단 불가" (A의 폐경 규칙 2026-10-20). 화면 1에서 의사가 입력하면 그 값으로 다시 판정 |
| `stage.group` | `not_assessed` (Stage X) | "병기 판정 불가" |
| `at_index.age` | null (`index_day` 없음) | `age_at_index` 조건만 해당 |
| `at_index.recent_therapy_28d.status` | `unknown` | "최근 투약 확인 필요" |
| `treatment_history[].end_day` 등 계산에 쓰는 일수 | null | 기간 조건 (`days_end_to_*`, `treatment_years`) |

- 칸을 두지 않는 조건 (A 답변 2026-10-21):
  - 재발 병소 절제 가능 여부(`recurrence_operable`): 데이터에 없고 의학적 판단이라, 재발 후 실제 수술 여부로 대신한다.
    `recurrence.surgery = yes`이고 `surgery_intent = curative`면 절제했으므로 '절제 불가능한 국소 재발성'은 거짓.
    그 밖(`no`, `unknown`, `palliative`)은 알 수 없음, 사유 "재발 병소 절제 가능 여부 확인 필요". 수술하지 않은 것을 절제 불가로 읽지 않는다.
  - 심장 병력·종격동 방사선(`cardiac_history`, `mediastinal_radiation`): 이번 모델 제외 (PROJECT.md §12). 늘 알 수 없음.
    liposomal doxorubicin(고식적 항암 1차 이상 연번 19)은 누적용량 기준을 만족하면 이 조건 없이 충족, 투여했는데 못 미치면
    `covered_conditions_unverified`와 사유 "심장 위험요소 확인 필요". D 조건은 '누적용량 또는 심장 위험요소' 묶음이라 이 규칙대로 나온다.
- 병용요법(40장) 표의 허가사항 열도 급여 조건이다 (2026-10-21 D 결정, A에게 근거 전달).
  40장 머리 원칙(165쪽, 제2025-133호): 기존 항암요법에 타 항암제를 병용할 때 "가) 병용요법은 식품의약품안전처의 허가사항 범위 이내,
  나) 투여대상은 기존 항암요법의 급여범위 이내"를 **모두** 만족해야 기존 요법의 본인부담률을 적용한다.
  그래서 허가사항 열(예: 연번 21·22의 PIK3CA 변이, 23·24의 PD-L1 CPS≥10, 30의 gBRCA)과 급여기준 열을 함께 판정한다.
  허가 여부를 D가 따로 판단하는 것이 아니라 공고 표에 적힌 내용을 공고 조건대로 적용하므로 PROJECT.md §2와 부딪히지 않는다.
  공고는 "허가사항은 공고 시점의 허가이므로 투여 전 변경 여부를 확인"하라고 적고 있어, 이 문구는 상위 청크(`…-combo`)에 있다.
  (A 답변 2026-10-21은 연번 21의 허가사항 조건을 빼자고 했으나 위 원칙에 따라 남긴다.)
- 최근 4주 투약: A가 계산한 `at_index.recent_therapy_28d`를 그대로 쓴다 (zoledronic acid 골전이, `recent_therapy_28d eq yes`, A §6-1).
- 나이: `age`는 진단 시 나이(`patient.age`)로 선행·수술후보조 대상 조건에, `age_at_index`는 판정 기준일 나이(`at_index.age`)로
  투여 시점 조건(G-CSF·denosumab '만 19세 이상', dexrazoxane '70세 이상')에 쓴다 (A §6-2).
- 실패(`prior_failed`): 그 약이 든 요법의 `stop_reason = progression` 또는 `best_response = PD`면 실패로 본다 (A §4).
  둘 다 없으면 "알 수 없음" (실패 아님으로 보지 않는다).
- `not_contains`(받은 적 없음): 투약 기록(`treatment_history`)이 하나도 없는 환자는 "안 받음"과 "기록 없음"을 가를 수 없으므로
  참이 아니라 "알 수 없음"으로 둔다 (A §6-5, TCGA 205명).
- `cycles_total`: 더한 값 중 `cycles.basis = estimated`가 있으면 결과에 "추정 주기 포함"을 표시한다 (A §4).
