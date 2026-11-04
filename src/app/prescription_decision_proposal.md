# `prescription_decision` 스키마 제안 (2026-11-03)

작성: 담당 A. 받는 사람: B, C, D (4명 검토 뒤 `schemas/`로 옮김).

화면 2에서 의사가 고른 처방을 남기는 파일이다. 지금까지는 스키마 없이 ui_design §7.2 예시 형식으로 저장했다.
초안 스키마는 [prescription_decision.json](prescription_decision.json)이고, 화면 2(`src/app/script/screen2.py` `save_decision`)는
저장 전에 이 초안으로 검사한다. `schemas/`는 4명 검토 대상이라 검토 전까지 `src/app/`에 둔다.

저장 위치: `data/app/decisions/<patient_ref>/v<n>.json` (덮어쓰지 않음, git에 올리지 않음).

## 1. 흐름에서의 자리

```
화면 1 → confirmed_state (v<n>) → C 검색 → B recommend() → recommendation → 화면 2 → prescription_decision
                                                                                     └→ 결과 보고서 (ui_design §6), 채택률 평가
```

## 2. 칸

| 칸 | 값 | 비고 |
|---|---|---|
| `schema_version` | `0.1-draft` | |
| `patient_ref` | 가명 ID | |
| `confirmed_state_ref` | `{version, confirmed_at}` | 근거가 된 확정 파일 |
| `recommendation_ref` | `{generated_at, model}` 또는 `null` | 추천이 실패하면 null (기타·보류만 가능) |
| `decided_at`, `decided_by` | 시각, 가명 사용자 ID | |
| `action` | `accept_option` / `custom` / `defer` | 추천안 채택 / 기타 처방 / 보류 |
| `selected_option_index` | `options[]` 순서 (0부터) | accept_option만 |
| `selected_rank` | **새 칸.** 화면에 보인 순서 (1부터) | accept_option만 |
| `shown_option_count` | 처음 보인 안 개수 (5 이하) | |
| `therapy`, `drugs` | 최종 처방 이름, 일반명 목록 | defer면 null·빈 목록 |
| `setting` | `neoadjuvant` / `adjuvant` / `palliative` | accept_option은 확정값에서 채움 |
| `line` | `1L` / `2L` / `>=3L` | custom + palliative만. accept_option은 확정 파일의 차수를 따름 |
| `reimbursement` | **새 칸.** 고른 안의 급여 분류 | accept_option만. custom·defer는 `null` = 판정 안 함 (기타 처방 급여는 v0.1에서 판정하지 않음) |
| `reimbursement_reason` | **새 칸.** 고른 안의 급여 판정 이유 | accept_option만, 아니면 null |
| `citations` | **새 칸.** 고른 안이 인용한 지침 청크 ID | accept_option만, 아니면 빈 목록 |
| `reimbursement_citations` | **새 칸.** 고른 안의 급여 행 ID (책자 날짜 포함) | accept_option만, 아니면 빈 목록 |
| `custom_unlisted_drugs` | 약 사전에 없어 글로 쓴 약 | custom만 |
| `defer_reason` | **코드로 바꿈.** `pending_test` / `mdt` / `patient_discussion` / `other` | defer만 |
| `memo` | 의사 메모 | 실명·등록번호 금지 |

`action`마다 채워야 하는 칸과 비워야 하는 칸은 스키마의 `allOf` 조건으로 검사한다
(예: defer인데 `therapy`가 있으면 실패, custom인데 약이 하나도 없으면 실패).

## 3. ui_design §7.2 예시에서 바꾼 것

1. **`selected_rank` 추가**: `selected_option_index`는 B `options[]`의 원래 순서인데, 화면 2는 근거 수준 → 급여 순으로 다시 정렬해 보여 준다.
   §7.2가 말한 "1안 채택률"은 화면의 첫 안을 골랐는지이므로 보인 순서가 따로 필요하다.
2. **`reimbursement` 추가**: 결과 보고서와 평가에서 "급여 안 되는 안을 골랐는지"를 추천 파일을 다시 열지 않고 볼 수 있게 한다.
3. **`defer_reason`을 코드로**: 지금 화면은 한국어 문장("검사 후 결정")을 그대로 저장한다. `schemas/README.md` §2 "코드값은 영문, 화면에서만 한국어"에 맞춘다.
4. **고른 안의 근거 인용 추가** (검토 의견, 2026-11-04): `citations`(지침 청크 ID), `reimbursement_citations`(급여 행 ID),
   `reimbursement_reason`. `recommendation_ref`(생성 시각·모델)만으로는 추천 캐시(`data/app/recommendations/`)가 지워지거나
   다시 만들어지면 고른 처방의 출처를 찾을 수 없다. 프로젝트 원칙(출력마다 문서·쪽·날짜)에 맞추고, 결과 보고서가 이 파일만으로 출처를 쓰게 한다.

## 4. 정할 것

| 번호 | 정할 것 | A 제안 | 함께 정할 사람 |
|---|---|---|---|
| 1 | 이 초안을 `schemas/prescription_decision.json`으로 | 검토 뒤 옮기고 `schemas/README.md` 표에 더함 | 4명 |
| 2 | accept_option의 `line` | 비워 두고 확정 파일 차수를 따른다. 내분비·항암 차수 중 어느 쪽인지는 약 계열로 정해지므로 저장하지 않음 | B |
| 3 | 기타 처방의 급여 판정 | v0.1은 하지 않음 (`reimbursement` null = 판정 안 함, ui_design §8.2-3). **D 동의 (2026-11-04)** | D, B |
| 4 | 보류 이유 코드 | 위 4개. 더 필요하면 추가 | 4명 |
| 5 | `src/app/` 폴더 위치·담당 | (팀 안건, 화면 전체와 함께) | 4명 |

## 5. 검토 의견과 반영 (2026-11-04)

| 의견 | 반영 |
|---|---|
| 추천안을 채택하면 그 안의 지침 인용(청크 ID)도 남겨야, 추천 파일이 지워져도 출처를 찾을 수 있다 (필수 아님) | `citations` 추가 (§3-4) |
| D: 기타 처방 급여 판정 안 함에 동의, 제안 문서에 "null = 판정 안 함"을 적어 달라 | §2 표·§4-3에 적음 |
| D: 채택 때 `reimbursement_citations`(급여 행 ID)와 `reimbursement_reason`도 남겨 달라. 행 ID에 책자 날짜가 있어 기준이 남는다 | 두 칸 추가 (§3-4) |
