# A → B 전달: 국소 재발 후 치료 단계 규칙 (`SET-LOCAL-ADJ`) 설계안

> 작성: 담당 A · 2026-11-06, 갱신 2026-11-09 · 상태: **A 쪽 일부 구현 (§7), 나머지 B 검토·4명 결정**
>
> 2026-11-09 갱신: 열린 결정 1·3·4가 정해졌고 A 코드에 반영했다. 바뀐 내용과 남은 일은 **§7**에 있다. §2~§6은 11-06 당시 기록이다.
> 관련: [handoff_to_B.md](handoff_to_B.md) §6.4, [handoff_confirmed_state_to_B.md](handoff_confirmed_state_to_B.md) §6, [proposal_remove_overall_line_2026-11-06.md](proposal_remove_overall_line_2026-11-06.md)

## 1. 요약

- §6.4 국소 재발 후 보조요법 규칙은 두 줄뿐이고, **아직 아무 코드도 구현하지 않았다** (B `BM1…py` 머리말 19행 "아직 다루지 않는 것").
- 대신 "이 시점의 치료가 선행·보조·고식 중 무엇인가"를 **네 곳이 각자 다른 기준으로** 판단하고 있어 서로 어긋난다 (§2).
- 제안: 날짜 기준점으로 시간을 구간으로 나누고, **위에서부터 처음 맞는 줄 하나만** 적용하는 표 하나로 투약마다의 단계와 이번 결정의 단계를 함께 정한다 (§3). 판정 함수는 한 곳에만 두고 나머지는 결과를 읽는다.
- B에게 묻는 것은 §6에 있다.

## 2. 지금 상태

### 2.1 §6.4 규칙 (지금 전부)

| 조건 | 판정 |
|---|---|
| `recurrence.status = locoregional`, `surgery = yes`, `later_distant = no` | 이후 요법은 수술후보조요법 (공고 p.48) |
| `surgery_intent` | `unknown`이어도 위 규칙 적용 |

스키마 `recurrence.later_distant` 설명에 같은 문장이 한 번 더 있다.

### 2.2 같은 질문을 판단하는 네 곳

| 위치 | 담당 | 기준 | §6.4와 비교 |
|---|---|---|---|
| `src/input/script/pipeline.py` `_fill_treatment` (투약 `setting`) | A | 표시 없는 투약: 전이 후 → metastatic, 원발 수술 전 → neoadjuvant, 첫 재발 전 → adjuvant, 병리 없음 → neoadjuvant(확인 사유), 그 밖 → adjuvant | 재발 후 투약은 원발 수술 기준으로 adjuvant가 됨. 재발 부위 수술 여부를 보지 않음 |
| `src/input/script/confirmed.py` `setting.phase` (화면 1) | A | pTNM·ypTNM이 있으면 adjuvant, 없으면 neoadjuvant | 원발 병리만 봄. 국소 재발을 수술하지 않아도 adjuvant |
| `src/input/script/confirmed.py` `recurrence_type` (화면 1) | A | 의도가 `curative`이면 `locoregional_curative`, 그 밖 `locoregional_other` | 의도 `unknown`을 제외함 (§6.4와 다름). `surgery`를 보지 않음 |
| `BM1…py` `line_of` → `setting.line` (비전이성) | B | 마지막 선행·보조 투약의 `setting` | 재발 부위 수술 여부를 보지 않음 |
| `src/recommend/conditions_eval.py` `recurrence_operable` | B | `surgery = yes`이고 의도 `curative`이면 yes, 그 밖 알 수 없음 | 의도 `unknown`을 제외함 (D `conditions.py` FIELDS 정의와 같음) |

### 2.3 어긋나는 예 (VC-0109 변형, A가 2026-11-06 확인)

VC-0109: 보조 tamoxifen 중 흉벽 국소 재발 (day 1140), 완치 목적 절제 (day 1165), 원격 전이 없음. 원래 사례는 정답이 나오지만 **우연히** 맞는다 (B는 마지막 보조 투약을, 화면 1은 원발 pTNM을 보고 adjuvant).

| 변형 | B `setting.line` | 화면 1 `phase` | `recurrence_type` | 맞는 값 |
|---|---|---|---|---|
| 원본 (수술 yes, 의도 curative) | adjuvant | adjuvant | locoregional_curative | 수술후보조 (SET-LOCAL-ADJ) |
| 재발 부위 수술 안 함 (`surgery = no`) | adjuvant | adjuvant | locoregional_other | 공고의 "재발성" (고식 쪽, §5 결정 2) |
| 수술 yes, 의도 `unknown` | adjuvant | adjuvant | locoregional_other | §6.4대로면 수술후보조 |

## 3. 제안: 구간 표 하나

### 3.1 기준점

| 기호 | 뜻 | 칸 |
|---|---|---|
| S1 | 원발 수술일 | `stage.ptnm`·`stage.yptnm`의 관찰일 |
| R | 첫 재발일 | `recurrence.recurrence_day` |
| S2 | 재발 부위 수술일 | **칸 없음.** `recurrence.surgery`는 yes/no/unknown뿐 (§5 결정 3) |
| M | 원격 전이일 | `recurrence.metastasis_day` (진단 시 전이성이면 0) |

### 3.2 판정 표

판정 대상 날짜 d는 투약이면 시작일, 이번 결정이면 판정 기준일(index day). 위에서부터 **처음 맞는 줄 하나만** 적용한다.

| 순서 | 구간 | 결과 | 근거 |
|---|---|---|---|
| 1 | M이 있고 d ≥ M | 고식 (`metastatic`) | 전이성 |
| 2 | R이 있고 d ≥ R, 재발 부위 수술 yes, 의도 ≠ palliative, d ≥ S2 | 보조 (재발 후 수술후보조, SET-LOCAL-ADJ). 의도 `unknown`이면 확인 사유 | 공고 p.48 |
| 3 | R이 있고 d ≥ R, 재발 부위 수술 yes, d < S2 | **결정 필요** (재발 부위 선행 / 고식) | §5 결정 1 |
| 4 | R이 있고 d ≥ R, 재발 부위 수술 no·unknown, 또는 의도 palliative | **결정 필요** (공고 "재발성" = 고식 쪽으로 보임) | §5 결정 2 |
| 5 | (R 없음 또는 d < R), S1이 있고 d < S1 | 선행 (`neoadjuvant`) | |
| 6 | (R 없음 또는 d < R), S1이 있고 d ≥ S1, 또는 S1은 없지만 R이 있음 | 보조 (`adjuvant`) | 재발 전 투약 = 원발 보조 (A 2026-11-06) |
| 7 | 재발 없음, 원발 병리 없음 | 선행 (`neoadjuvant`), 확인 사유 | A 2026-11-06 |

- 투약에 차트 표시(선행·보조·고식)가 있으면 표보다 표시를 먼저 쓴다 (지금 A 규칙과 같음).
- 1번이 가장 먼저라서 **`later_distant`가 필요 없어진다.** 국소 재발 뒤 원격 전이가 생기면 M이 있으므로 1번에 걸린다. `later_distant = yes`인데 M이 없으면 입력 충돌로 확인 사유를 낸다.
- 의도 `unknown`은 2번에서 한 번만 정한다 (§6.4 그대로: 적용하되 확인 사유). A `recurrence_type`과 B·D `recurrence_operable`은 이 결과를 읽게 바꾼다.

### 3.3 하나의 결과를 읽는 곳

| 지금 각자 계산 | 바꾼 뒤 |
|---|---|
| A 투약 `setting` | 표의 결과 (d = 투약 시작일) |
| A 화면 1 `setting.phase` | 표의 결과 (d = 판정 기준일) |
| A 화면 1 `recurrence_type` | 2번 → `locoregional_curative`, 3·4번 → `locoregional_other` |
| B `line_of` (비전이성) | 화면 1 `setting.phase`와 같은 값 |
| B `recurrence_operable` | 2번이면 yes, 4번 중 `surgery = no`는 D 정의대로 알 수 없음 |

### 3.4 차수와의 관계

- 2번(재발 후 수술후보조)은 고식 차수(`endocrine_line`·`chemo_line`)에 세지 않는다.
- 간주 규칙(`deemed_lines`)의 "선행·보조 종료 후 N일 이내 전이"에서 2번 투약도 보조로 넣는다.
- 4번을 고식으로 정하면 그 투약을 고식 차수에 셀지, `setting.disease`를 무엇으로 둘지 함께 정해야 한다 (§5 결정 2).

## 4. 시험

VC-0109 짝 사례로 고정한다 (`src/input/script/virtual/cases/pairs.py`, 정답 `pairs.json`).

| 짝 | 바꾸는 값 | 기대 |
|---|---|---|
| 재발 부위 수술 안 함 | `surgery = no` | 4번 (결정 2의 값) |
| 의도 모름 | `surgery_intent = unknown` | 2번 + 확인 사유 |
| 이후 원격 전이 | `metastasis_day` 추가 | 그 뒤 투약·이번 결정은 1번 |
| 재발 부위 수술 전 투약 | 재발 후 S2 전 항암 | 3번 (결정 1의 값) |

## 5. 열린 결정

| 번호 | 질문 | 대상 |
|---|---|---|
| 1 | 국소 재발 후 재발 부위 수술 **전** 투약(3번)은 공고상 선행인가 고식인가 | D (공고 원문 확인) |
| 2 | 재발 부위를 수술하지 않은 국소 재발(4번)의 투약은 공고 "재발성"(고식)인가. 그렇다면 고식 차수에 세나, `setting.disease`는 무엇인가 | D 확인 후 B |
| 3 | S2(재발 부위 수술일)를 새 칸으로 둘지, `recurrence.surgery` 근거의 관찰일로 대신할지 | 4명 (공용 스키마) |
| 4 | 판정 함수를 어디에 둘지 (§6) | A·B |

## 6. B에게 묻는 것

1. **담당:** §6.4는 B 담당이지만 투약 `setting`과 화면 1 `phase`는 A가 이미 정한다. 표 함수를 A(`src/input/`)에 두고 B는 `patient_state`·`confirmed_state` 값을 읽기만 하는 쪽을 제안한다. B가 두고 싶다면 A는 투약 `setting` 계산에서 2~4번을 빼고 B 결과를 받는다. 어느 쪽이든 **한 곳**에서만 계산한다.
2. **의도 `unknown`:** `recurrence_operable`이 지금 `curative`만 yes로 본다. §6.4대로 `unknown`도 2번에 넣고 확인 사유를 다는 데 동의하는지 (D `conditions.py` 정의도 같이 바뀌므로 D 확인 필요).
3. **`later_distant`:** 1번 규칙으로 대신하고, 충돌 검사용으로만 남기는 데 동의하는지.
4. **`line_of` 비전이성 분기:** 화면 1 `setting.phase`와 같은 값을 쓰는 데 동의하는지. 이 PR의 `line` 삭제 제안(전이성 분기)과 함께 바꾸면 `line_of`를 한 번에 정리할 수 있다.

## 7. 2026-11-09 결정과 구현

### 7.1 정해진 것

| §5 번호 | 결정 | 근거 |
|---|---|---|
| 1 | 국소 재발 뒤 재발 부위 수술 **전** 투약(3번 줄)은 **고식**이다. 고식 차수에 센다 | 공고 유방암 선행 행의 투여대상은 모두 원발 병기다 (국소진행성 = stage III, 직경 > 2㎝, 림프절 양성, stage II∼III). 재발 병소에는 이 병기가 없으므로 선행 행으로는 급여되지 않고, 대상에 "재발성"이 있는 고식 행으로만 급여된다. 고식 행의 투약은 투여단계(1차, 2차…)를 센다 (총칙 용어 정의: 투여대상·투여단계·투여요법). ESMO EBC 2024·MBC 2026은 국소 재발 치료를 다루지 않아 충돌하지 않는다 |
| 3 | S2(재발 부위 수술일)는 **새 칸을 두지 않는다.** `recurrence.surgery` = yes 근거의 `observed_date`를 쓴다 | 사건 칸은 LLM이 날짜를 비워도 인용 구절에 날짜가 하나뿐이면 그 날짜를 넣는다 (`pipeline.py` `EVENT_FIELDS`, 커밋 bd20eef). VC-0109 정답에 2022-09-29가 들어갔다 |
| 4 | 판정 함수는 **A가 계산하고 B는 읽는다** | A가 투약 `setting`·화면 1 `phase`를 이미 계산한다 |

- `recurrence.surgery` 기록이 없을 때는 `unknown`으로 둔다. `no`로 바꾸지 않는다 (사용자 결정). 처방은 종양내과 판단이고 수술 가능 여부는 유방외과가 먼저 정한다는 전제다.
- 의도 `unknown`(§6 질문 2)은 §6.4대로 2번 줄에 넣고 확인 사유를 단다. A `recurrence_type`에 반영했다 (§7.2). B·D `recurrence_operable`은 아직 `curative`만 yes로 본다.

### 7.2 A 코드에 반영한 것

| 위치 | 바뀐 것 | 시험 |
|---|---|---|
| `pipeline.py` `_fill_treatment` | 표시 없는 투약: 국소 재발(`locoregional`) + 재발 부위 수술 yes + S2 날짜가 있을 때, R ≤ 시작일 < S2 → `metastatic`(고식). S2 뒤는 기존 규칙대로 `adjuvant` | `test_locoregional_recurrence_surgery_splits_settings` |
| `rules.py` `palliative_lines` | 전이 기준일이 없으면 `setting = metastatic`인 투약만 고식 차수(`line`·`endocrine_line`·`chemo_line`)로 센다. 그 뒤 보조 투약은 세지 않는다 | `test_palliative_without_metastasis_day_counts_only_palliative` |
| `confirmed.py` `recurrence_type` | 재발 부위 수술 yes이고 의도가 palliative가 아니면 `locoregional_curative`. 의도 기록이 없으면 확인 사유 | VC-0109 `confirmed_state.json` 재생성 |
| `screen1.py` | 재발 유형 칸을 전이성뿐 아니라 국소 재발에서도 보인다 (시스템 값 기준이라 의사가 고쳐도 잠기지 않는다) | `tests/app` |

지금 fixture에는 국소 재발 뒤 수술 전에 시작한 투약이 없어 정답 `patient_state`는 바뀌지 않았다.

### 7.3 고식 값 이름 (`metastatic` → `palliative`)

`treatment_history[].setting`과 `confirmed_state` `prior_regimens[].setting`의 `metastatic`은 실제로는 "고식"(공고 투여요법 palliative)이다. 첫 스키마(TCGA, 10-12)가 전이일 기준으로만 단계를 나눠 기준 사건 이름을 값으로 붙였다. 이번 변경은 이름 변경이 4개 모듈 코드와 fixture 63개를 건드리므로 **값은 `metastatic` 그대로 두고**, 이름 변경은 별도 PR로 낸다. 병기 범주(`setting.disease`, 청크 `setting`)의 `metastatic`은 바꾸지 않는다.

### 7.4 남은 일

| 항목 | 내용 | 대상 |
|---|---|---|
| 값 이름 변경 | 위 7.3. 공용 스키마 2곳 | 4명 |
| 재발 부위 수술 안 함·모름 (4번 줄) | 지금은 `adjuvant`로 남는다. 공고 "재발성" 고식 행 대상이지만 `unknown`을 `no`로 보지 않기로 해서 규칙으로 정하지 않았다 | A·B |
| 전이 없는 고식의 검색 경로 | `setting.disease`가 metastatic이 아니면 C는 선행·보조로만 찾는다 (`retrieve.py` `decision_lines`). 수술 불가 3기, 국소 재발 수술 전 환자는 고식 행·차수 검색 경로가 없다. `confirmed_state` `setting.phase`에도 palliative 값이 없다. B `line_endocrine`·`line_chemo`도 전이성일 때만 채운다 | B·C, 스키마 4명 |
| ESMO 근거 공백 | ESMO EBC 2024는 수술 가능한 조기·국소진행성, MBC 2026은 원격 전이만 다룬다. 수술 불가 국소진행성·국소 재발의 약물 치료 문장이 없다. 급여는 공고로 판정되지만 지침 인용을 어떻게 할지 (범위 밖 표시 / MBC 장 검색) 정해야 한다 | 4명 |
| 간주 규칙 | `deemed_lines`는 전이 기준일만 본다. 국소 재발 고식 투약의 "보조요법 종료 후 1년 이내 재발" 판정은 재발일(R)을 기준으로 해야 하는지 확인 필요 | B |
| `recurrence_operable` | 의도 `unknown`을 2번 줄에 넣는 §6.4와 맞추기 | B·D |
| 수술 예정 (`planned`) | `recurrence.surgery`에 planned를 더하면 enum 변경. 그때 `observed_date`는 예정일이 된다 | 4명 |
| `recurrence.status`의 `site_unknown`·`unknown` | TCGA 기록에서 온 값이다. 가상 차트 82개와 TCGA 정답 838명 모두 0건이다. 실제 진료에서 재발은 부위를 찾아야 진단되므로 지우고, 기록 없음·검사 중은 화면 1 필수 확인으로 처리하자고 제안한다. D `reimbursement_terms.csv`·`conditions.py`의 "재발성" 정의도 함께 바꾼다 | 4명 |
| 반대쪽 유방 새 원발암 | 재발이 아니라 새 원발암이다 (ESMO EBC "second primary"). 병기·수술 가능 여부는 새로 판단하고 투약 이력(이전 AI 투여, anthracycline 누적)은 이어진다. 스키마가 원발 종양 하나만 담으므로 v0.1은 범위 밖으로 둔다 | 4명 |
| 간 전이 | 유방암에서 온 전이면 전이성 유방암이다 (ESMO MBC: 첫 전이 때 생검으로 조직형 확인 [I, A]). 다른 원발암이면 범위 밖. 코드 변경 없음 | 기록만 |
