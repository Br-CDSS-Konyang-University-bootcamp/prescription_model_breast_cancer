# 치료 차수 규칙 명세: ESMO 처방 기준 차수와 심평원 급여 투여단계

> 작성: 담당 A · 기준 스키마: `schemas/patient_state.json` **0.1-draft6** · 상태: **명세 초안 (2026-10-27), 열린 결정 4개**
> 관련 문서: [handoff_to_B.md](handoff_to_B.md) §6.2·§6.3·§6.3a·§6.4 (지금 규칙), [../reimbursement/schema_proposal.md](../reimbursement/schema_proposal.md) (급여 청크의 `line_rule`·`counts_as_prior_line`), PROJECT.md §5

지금 차수 코드(`src/input/script/rules.py`의 `palliative_lines`, `deemed_lines`)를 지우고 이 문서를 기준으로 다시 작성한다.
지금 코드는 TCGA 데이터의 빈칸을 메우는 추정 규칙(28일 묶기, 끝난 이유를 모르면 다음 차수, 날짜가 겹치면 병용 추가, 항암 다음 내분비는 유지요법)을 가지고 있다.
가상 차트(`tests/fixtures/virtual_charts/`, 30명)는 요법 하나가 한 줄이고 52줄 중 51줄에 `stop_reason`이 있어 이 추정이 필요 없다.
새 코드는 patient_state에 적힌 값만으로 계산하고, 값이 없으면 추정하지 않고 `unknown`을 낸다.

| 날짜 | 내용 | 상태 |
|---|---|---|
| 2026-10-27 | 초안. 두 기준 규칙, 계산에 쓰는 칸, 빠진 칸 1개, 열린 결정 4개 | **A 제안** |

## 1. 두 기준

| 기준 | 쓰는 곳 | 세는 것 | 선행·보조요법 |
|---|---|---|---|
| ESMO 처방 기준 차수 (§3) | 지침 검색(C), 추천(B) | 전이 후 전체 차수 + 재발 시점 값 | 차수에 넣지 않는다. 재발 시점 값으로만 쓴다 |
| 심평원 급여 투여단계 (§4) | 급여 판정(D 청크와 대조) | 고식적 내분비 단계와 고식적 항암 단계를 따로 | 간주 규칙이 충족되면 1차로 친다 (실제 단계는 그대로, 규칙별 충족 여부를 따로 낸다) |

두 기준은 같은 요법 목록(§2)에서 출발한다. 같은 환자라도 두 값이 다를 수 있다 (예: 보조 anastrozole 중 전이 → ESMO 1차, 심평원 내분비 2차 이상 행 대상).

## 2. 공통 정의

### 2.1 입력 칸

| 칸 | 쓰는 곳 | 가상 차트 채움 (52줄) |
|---|---|---|
| `treatment_history[].drugs` | 요법 종류, 약 계열 | 52 |
| `treatment_history[].setting` | 선행·보조·고식 구분 | 52 |
| `treatment_history[].start_day`, `end_day` | 순서, 기간 조건 | 52, 51 |
| `treatment_history[].ongoing` | 판정 기준일에 투약 중 (`end_day` null일 때) | 1 |
| `treatment_history[].stop_reason` | 차수 넘김 판단 | 51 |
| `treatment_history[].progression_day` | 진행 시점 (공고 "종료 후 1달 이내 진행", ESMO "6개월 이내 진행") | 18 |
| `treatment_history[].best_response` | `PD`면 진행으로 본다 | 24 |
| `recurrence.metastasis_day` | 전이 기준일 (진단 시 Ⅳ기 = 0) | 18명 |
| `recurrence.recurrence_day` | 첫 재발일 (국소·원격) | 14명 |
| `recurrence.status`, `surgery`, `surgery_intent`, `later_distant` | 국소 재발 후 보조요법 (§4.5) | |
| `patient.menopausal_status` | ribociclib 폐경 전 조건 | |
| `index_day` | 판정 기준일 | 30명 |
| `data/dictionaries/drug_classes.csv`의 `drug_class`, `drug_subclass` | 요법 종류, anthracycline·taxane·AI_nonsteroidal·CDK4/6_inhibitor 등 | |

### 2.2 요법

- `treatment_history` 한 줄이 요법 하나다 (스키마 설명). 날짜로 묶지 않는다.
- 보조약(`Supportive Care`), 골 보호제(`Bone-modifying Agent`), 백신(`Vaccine`)만 있는 줄은 요법으로 세지 않는다.
- 고식적 요법 = `start_day ≥ metastasis_day`인 요법. `setting`과 어긋나면 issue로 남긴다 (가상 차트 30명은 어긋남 없음).
  전이 전에 시작해 전이 후에도 계속한 보조요법(VC-0103·0122·0128처럼 보조 내분비 중 전이)은 고식적 요법이 아니다.
- `start_day`가 없는 고식적 요법은 순서를 알 수 없으므로 그 환자의 차수는 `unknown`이다.

### 2.3 요법 끝남의 분류

| `stop_reason` (또는 다른 칸) | 분류 | 다음 요법 |
|---|---|---|
| `progression`, 또는 `progression_day` 있음, 또는 `best_response = PD` | 진행 | 다음 차수 |
| `maintenance` | 유지요법 전환 | 같은 차수 |
| `planned_switch` | 계획된 순차 요법 (AC → T 등) | 같은 차수 |
| `toxicity` | 독성 중단 | ESMO: 같은 차수. 심평원: **결정 2** |
| `completed`, `other` | 진행 없이 끝남 | 같은 차수 (다시 시작하면 재투여, 차수 그대로) |
| null | 모름 | 다음 요법의 차수 `unknown` (추정하지 않는다) |

## 3. ESMO 처방 기준 차수

근거: ESMO MBC 2026-05 (`esmo_mbc_2026-05.pdf`), ESMO EBC 2024-02. ESMO는 차수를 따로 정의하지 않으므로 권고 문장에서 읽은 규칙이다. 괄호 안은 청크 id.

### 3.1 차수 세기

| 번호 | 규칙 | 근거 |
|---|---|---|
| E-1 | 선행·보조요법은 차수에 넣지 않는다. 전이 후 첫 고식적 요법이 1차다 | 1차 치료 절이 de novo와 보조요법 후 재발을 함께 다룸 (`esmo-mbc-2026-05-luminal-1l`) |
| E-2 | 앞 요법이 진행(§2.3)으로 끝났으면 다음 요법은 다음 차수다 | 2차·3차 절이 앞 요법 진행 후 기준 (`-luminal-2l`, `-her2-2l`, `-tnbc-2l`) |
| E-3 | 유도 항암 후 유지요법은 같은 차수다 | HER2+ 1차: docetaxel + P + H 유도 후 P + H (± ET, ± tucatinib) 유지 (`-her2-1l`) |
| E-4 | 독성으로 바꾸면 같은 차수다 | 지침에 직접 문장은 없음. 진행이 없으므로 E-2에 해당하지 않음 |
| E-5 | 뇌 전이만 진행했고 국소치료 후 같은 항HER2 요법을 계속하면 같은 차수다 | `-her2-2l`, `-her2-3l`. **입력 칸 없음 (§5)** |
| E-6 | 이번에 결정할 차수 = 마지막 고식적 요법의 차수 + (그 요법이 진행으로 끝났으면 1). 고식적 요법이 없으면 1 | B `line_of`와 같음 |

출력: 요법마다 `line` (전체), 그리고 고식적 내분비·고식적 항암 횟수. ESMO도 "ET 2차 이상", "항암 1차 이상"처럼 종류별 횟수로 조건을 건다 (§3.3).
요법 종류는 §4.1과 같은 분류를 쓴다 (결정 1).

### 3.2 재발 시점 값

차수는 그대로 두고 1차 약 선택을 바꾸는 값이다. 기간은 일 단위, 끝점은 **결정 3**.

| 값 | 계산 | 쓰는 권고 |
|---|---|---|
| 보조 ET 후 기간 | 보조 내분비요법 `end_day` → 끝점. 전이 때 투여 중이면 0 | ER+: 보조 ET 중이거나 종료 후 12개월 이내 → fulvestrant + CDK4/6 (± inavolisib), 12개월 초과 또는 de novo → AI + CDK4/6 (`-luminal-1l`) |
| 보조 ET 시작 후 기간 | 보조 내분비요법 `start_day` → 끝점 | T-DXd (HER2-low): 보조 ET 24개월 이내 진행이면 ET 1차 이후 가능 (`-luminal-3l`). "24개월"을 시작부터 세는지 원문 확인 필요 |
| 보조 항HER2 후 기간 | 보조 P + H 또는 T-DM1 `end_day` → 끝점 | HER2+: 6~12개월 이내 재발이면 2차 약 고려 (`-her2-1l`) |
| DFI | 마지막 선행·보조 항암 요법(항암·HER2 표적·면역항암제 포함) `end_day` → 끝점 | TNBC: pembrolizumab + 항암·SG는 DFI ≥ 6개월, atezolizumab + nab-paclitaxel은 ≥ 12개월, Dato-DXd는 6개월 이내 재발에 우선 (`-tnbc-1l`). anthracycline·taxane 재투여는 DFI ≥ 12개월 (`-luminal-3l`) |
| 고식적 ET + CDK4/6 진행까지 기간 | 그 요법 `start_day` → `progression_day` | T-DXd (HER2-low): 6개월 이내 진행이면 ET 1차 이후 가능 (`-luminal-3l`) |
| de novo | `metastasis_day = 0` | 여러 1차 권고 |
| 선행·보조 면역항암제 사용 | 전이 전 요법에 `Immunotherapy` | TNBC 1차 (`-tnbc-1l`) |

### 3.3 종류별 횟수 조건 (예)

| 권고 | 조건 |
|---|---|
| T-DXd (HER2-low·ultralow, ER+) | 고식적 ET 2회 이상, 또는 ET 1회 + (보조 ET 24개월 이내 진행 또는 ET + CDK4/6 6개월 이내 진행) |
| SG, Dato-DXd, T-DXd (ER+ HER2-low) | 고식적 항암 1회 이상 |
| 비내분비 요법으로 넘어가기 전 | 내분비 감수성 질환은 ET 2회 이상 권고 |
| elacestrant, imlunestrant (ESR1 변이) | ET 1회 이상 |

선행·보조 항암을 "항암 1회"로 칠지는 ESMO에 문장이 없다. 이 문서는 치지 않는다 (E-1).

## 4. 심평원 급여 투여단계

근거: 「암환자에게 처방·투여하는 약제에 대한 공고」 9. 유방암 (쪽은 A 확인, handoff_to_B §6.3). 이 저장소에는 공고 원본이 없으므로(`data/reimbursement/` 없음) 코드 작성 전에 쪽마다 원문을 다시 대조한다.

### 4.1 단계 세기

| 번호 | 규칙 | 근거 |
|---|---|---|
| H-1 | 고식적 내분비요법과 고식적 항암화학요법의 투여단계를 따로 센다 | p.55 |
| H-2 | 요법 종류(내분비 / 항암)는 **결정 1** | |
| H-3 | 그 종류의 첫 고식적 요법이 1차, 그 종류 요법이 실패(§2.3, **결정 2**)한 뒤 다음 요법이 2차 | 공고 각 행의 "1차", "2차 이상" |
| H-4 | 같은 종류 안에서 유지·순차·독성 전환은 같은 단계 | §2.3 |
| H-5 | 한 차수 안에서 종류가 바뀌면 (항암 → 내분비 유지 등) 그 종류의 단계는 처음일 때만 하나 올린다 | handoff §6.2 5b |
| H-6 | 이번에 결정할 단계 = 그 종류 마지막 요법의 단계 + (진행으로 끝났으면 1). 그 종류 요법이 없으면 1. HR 음성은 내분비 `not_applicable` | B `line_kind_of`와 같음 |

출력: 요법마다 `endocrine_line`, `chemo_line`. 간주 규칙은 넣지 않는다.

### 4.2 간주 규칙 (`fields.deemed_lines`)

실제 단계는 그대로 두고 규칙마다 `met` / `not_met` / `unknown` / `not_applicable`을 낸다. 급여 판정은 행의 `counts_as_prior_line`에 맞는 규칙이 `met`이면 단계에 1을 더해 비교한다.

| rule_id | 공고 | 종류 | 조건 | 기간 끝점 |
|---|---|---|---|---|
| `DEEM-ANTHRA-TAXANE` | p.61~62 | 항암 | 선행·보조에 anthracycline과 taxane이 모두 있음, 기간 제한 없음 | 없음 |
| `DEEM-SG-1Y` | p.63 | 항암 | 선행·보조요법 중 또는 종료 후 365일 이내 재발 | 결정 3 |
| `DEEM-HER2ADC-6M` | p.62~63 | 항암 | trastuzumab 포함 보조요법 중 또는 종료 후 183일 이내 재발 | 결정 3 |
| `DEEM-ENDO-ADJ-1Y` | p.57 | 내분비 | 보조 내분비요법 중 또는 종료 후 365일 이내 진행 | 결정 3 |

- 기간 = 근거 요법 `end_day` → 끝점. 끝점에 투여 중이면 0.
- `end_day`가 없고 `ongoing = true`면 투여 중으로 본다. `end_day`가 없고 `ongoing`이 null이면 `start_day`를 하한으로 써서 그래도 기간 안이면 `met`, 아니면 `unknown`.

### 4.3 약별 기간·이력 조건

급여 행 조건이고 투여단계 자체는 바꾸지 않는다. 계산 재료만 patient_state에서 낸다.

| 행 | 조건 | 공고 | 재료 |
|---|---|---|---|
| CDK4/6 + AI 1차 | 고식적 항암 이력 없음 (폐경 전 ribociclib 제외) | p.55 | `chemo_line` |
| CDK4/6 + AI 1차 | 비스테로이드성 AI 보조요법 종료 1년 이후 재발 | p.55 | `drug_subclass = AI_nonsteroidal`, 보조 ET 후 기간 |
| ribociclib + AI 1차, 폐경 전 | AI 외 보조 내분비·보조 항암 중 또는 종료 1년 이내 재발, 또는 고식적 항암 1차 실패 | p.55 | `menopausal_status`, 보조 요법 후 기간, `chemo_line` |
| 내분비 2차 이상 | 고식적 내분비요법 중 또는 종료 후 1달 이내 진행 | p.57 | 마지막 고식적 내분비 `end_day`, `progression_day` |
| pembrolizumab + 항암 1차 (TNBC) | 보조요법 종료 6개월 이후 재발 | p.58 | DFI |
| bevacizumab + paclitaxel 1차 | paclitaxel 보조요법 종료 1년 이후 재발 | p.58 | 해당 약 `end_day` |
| lapatinib + letrozole 1차 (HER2+ HR+) | AI 보조요법 종료 1년 이후 재발 | p.58 | 보조 AI `end_day` |
| trastuzumab + anastrozole | trastuzumab·AI 보조요법 종료 1년 이후 재발 | p.60 | 해당 약 `end_day` |
| CDK4/6 병용 (연번 29) | 보조 CDK4/6 종료 12개월 초과 | | `drug_subclass = CDK4/6_inhibitor` `end_day` |

### 4.4 판정 기준일 값 (`fields.at_index`)

지금 규칙 그대로 둔다: 판정 시점 나이, 최근 4주 이내 항암·호르몬제 투여 (zoledronic acid, 공고 Ⅳ).

### 4.5 국소 재발 후 보조요법

`recurrence.status = locoregional`, `surgery = yes`, `later_distant = no`이면 이후 요법은 수술후보조요법이다 (p.48). 고식적 단계에 넣지 않는다. B가 판정한다 (handoff §6.4).

## 5. 빠진 입력 칸

| 칸 | 필요한 규칙 | 제안 | 비고 |
|---|---|---|---|
| 진행 부위 (예: `treatment_history[].progression_site`: `intracranial_only` / `extracranial` / `both` / null) | E-5 뇌 전이만 진행하면 같은 차수 | `schemas/patient_state.json`에 칸 추가 | 공용 스키마라 4명 검토. 칸이 생기기 전에는 E-5를 적용하지 않고 진행이면 다음 차수로 센다 |

## 6. 열린 결정

### 결정 1. 요법 종류(내분비 / 항암)를 어디서 정하나

애매한 조합: lapatinib + letrozole (공고 항암 표), trastuzumab + anastrozole, exemestane + everolimus, P + H + ET 유지, CDK4/6 + ET, PARP 억제제 단독, SG·Dato-DXd (사전에는 `Other Targeted Therapy`).

| 선택지 | 방법 | 장점 | 단점 |
|---|---|---|---|
| **1-A (A 추천)** | 요법 → 종류 대응표를 새로 둔다 (`data/dictionaries/regimen_category.csv`: 약 조합, 종류, 공고 쪽). 표에 없는 조합은 1-C 규칙 | 공고 표와 같은 결과, 근거 쪽을 남김 | 표를 A가 관리. D 청크와 어긋나지 않게 맞춰야 함 |
| 1-B | D 청크의 `stage`(`palliative_endocrine` / `palliative_chemo`)에서 가져온다 | 공고 원문과 바로 맞음 | A가 D 청크를 읽게 됨 (모듈 경계). 청크에 없는 요법(공고에 없는 약)은 정할 수 없음 |
| 1-C | 지금처럼 `drug_class`로 정한다 (항암·HER2 표적·면역항암제가 있으면 항암, 아니면 내분비, 그 밖 표적치료만이면 항암) | 표가 필요 없음 | 위 애매한 조합이 공고와 다를 수 있음 |

### 결정 2. 심평원 "실패"에 독성 중단을 넣나

공고 2차 이상 행의 "1차 실패" 또는 "이전 치료에 실패한"이 진행만 뜻하는지, 독성으로 중단한 경우도 포함하는지.

| 선택지 | 독성 중단 후 다음 요법 | 비고 |
|---|---|---|
| **2-A (A 추천)** | 같은 단계 (진행만 실패) | ESMO 차수(E-4)와 같음. 원문에서 "불내성"이 함께 적힌 행이 있으면 그 행만 급여 판정에서 따로 본다 |
| 2-B | 다음 단계 (독성도 실패) | ESMO 차수와 갈라짐 |
| 2-C | 원문을 행마다 확인해 급여 청크 조건으로 넘김 (투여단계는 진행만 셈) | D가 행마다 `prior_failed` 조건에 불내성 포함 여부를 적어야 함 |

### 결정 3. 기간 조건의 끝점: 첫 재발일인가 전이 기준일인가

국소 재발 후 원격 전이가 생긴 환자에서만 다르다 (가상 차트에는 아직 없음). D가 2026-10-21에 물은 문제와 같다 (schema_proposal.md "차수 간주 규칙").

| 선택지 | 끝점 | 영향 |
|---|---|---|
| **3-A (A 추천)** | 공고·ESMO 문구대로 나눈다: "재발"은 `recurrence_day`, "진행"·"전이"는 `metastasis_day`. 규칙마다 끝점을 이 문서 표에 적는다 | 원문과 같음. 규칙마다 끝점이 달라 표 관리가 필요 |
| 3-B | 모두 `metastasis_day` | 지금 코드와 같음. 국소 재발만 있는 환자는 기간을 낼 수 없음 (`not_applicable`) |
| 3-C | 모두 `recurrence_day` | 국소 재발이 원격 전이보다 먼저면 기간이 짧아져 `met`이 늘어남 |

### 결정 4. 차수를 누가 계산하고 어디에 두나

사용자는 patient_state에 적힌 값으로 계산하는 방식을 원한다. 차수 칸을 patient_state에 저장할지 정해야 한다.

| 선택지 | 계산 | 저장 | 비고 |
|---|---|---|---|
| **4-A (A 추천)** | A가 변환·추출 뒤 계산 (지금과 같은 담당, 코드만 새로) | `treatment_history[].line`·`endocrine_line`·`chemo_line`, `fields.deemed_lines`, 재발 시점 값은 새 칸 `fields.timing` | 스키마 변경은 `fields.timing` 추가뿐. 의사 확인 화면(confirmed_state)에 값이 그대로 보임 |
| 4-B | B가 `assess()`에서 patient_state 원값으로 계산 | `biomarker_record.setting`만 | patient_state에서 차수 칸 삭제 (스키마 변경). 담당 변경 (2026-10-16 결정 뒤집음) |
| 4-C | 공용 함수로 분리해 A·B가 함께 씀 | 4-A와 같음 | 모듈 간 import 금지 규칙에 걸림. 둔다면 `schemas/` 옆 공용 위치를 4명이 정해야 함 |

어느 선택지든 스키마나 담당이 바뀌므로 4명 검토가 필요하다.

## 7. 시험

- 가상 차트 30명의 `expected/patient_state.json`에 든 차수·간주 규칙 값은 케이스 생성 코드(`virtual_chart.py`, `build_virtual_cases.py`)가 `lines.annotate`로 계산해 넣고, `tests/input/test_virtual_charts.py`가 간주 규칙 일부를 확인한다. 새 코드로 바꾼 뒤에도 지금 값과 같아야 한다 (바뀌는 케이스가 있으면 이 문서의 어느 규칙 때문인지 적는다).
- 지금 가상 차트에 없는 경우. 새 케이스나 경계 쌍(`pairs.py`)으로 추가한다.

| 경우 | 확인할 규칙 |
|---|---|
| 전이 후 독성으로 약 변경 | E-4, 결정 2 |
| 뇌 전이만 진행 + 같은 항HER2 계속 | E-5 (칸 추가 후) |
| HR+ HER2- 항암 후 내분비 유지 | E-3, H-5 |
| 국소 재발 후 원격 전이 | 결정 3 |
| 같은 약 재투여 (진행 없이 끝난 뒤 / 진행 뒤) | §2.3 `completed`, E-2 |
| `stop_reason` null | §2.3 `unknown` |
| 보조 ET 종료 정확히 365일·366일 뒤 재발 | `DEEM-ENDO-ADJ-1Y` 경계 |
| ET + CDK4/6 시작 후 6개월 이내 진행 | §3.3 T-DXd |
