# VC-0108 진단 시 뼈 전이, 골 보호제 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

70세(진단 시) 여성, 폐경 후. 가짜 진단일 2024-02-19 (= day 0).

| day | 사건 |
|---|---|
| 0 | 우측 유방 IDC, 중심 생검. ER 85%, PR 30%, HER2 IHC 0 |
| 5 | 뼈 스캔·PET: **다발성 골 전이** (척추·골반), 다른 장기 전이 없음. cT2N1M1, IV |
| 20~ | 1차 ribociclib + letrozole, **현재 복용 중** (10개월째 SD) |
| 320 | **오늘 외래** = `index_day`. denosumab 시작 결정 |

## 2. 시험 목적

- 진단 시 IV기: `metastasis_day` 0, 재발이 아니므로 `recurrence_day` 없음
- `index_day`로 "최근 4주 이내 항암제·호르몬제 투여" (zoledronic acid 조건) 판정
- **복용 중인 약의 `end_day`가 null** → "투약 중"과 "기록 없음"을 구분하지 못하는 한계 (AB_gap J-4)가 드러남
- Ⅳ 기타 약제(골 보호제) 급여 판정

## 3. 차트 문서 구성

1. `<외래 경과기록>` SOAP, 영상 결과 요약 포함
2. `[영상 판독]` 뼈 스캔 (짧게)
3. `[투약 기록]` 처방 목록 (키스칼리, 페마라)

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `stage` | `ctnm` T2 N1 M1, `group` IV, `disease_extent` metastatic, `metastatic_sites` bone |
| `recurrence` | `status: none`, `metastasis_day` 0, `recurrence_day` 없음 |
| `treatment_history` | ribociclib·letrozole `start_day` 20, `end_day` null, `setting: metastatic`, `line 1`, `endocrine_line 1` |
| `deemed_lines` | 모두 `not_met` (선행·보조요법 없음) |
| `index_day` | 320 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: 아형 HR+/HER2-, `setting.disease` metastatic
- **C (지침)**: ESMO MBC Site-specific > Bone metastases and bone-modifying agents
- **D (급여)**

| 후보 | 공고 위치 | 기대 분류 | 이유 |
|---|---|---|---|
| denosumab | Ⅳ. 기타 약제 3 | `covered` | 만 19세 이상, 영상으로 골전이 입증 |
| zoledronic acid | Ⅳ.2 나 | `covered_conditions_unverified` | 골전이 ✓, "최근 4주 이내 호르몬제 투여"는 복용 중이면 충족이지만 `end_day` null이 "투약 중"인지 확인할 수 없음 |
| ribociclib + letrozole (확인용) | 3. 고식적 내분비 가.5 | `covered` | 이전 AI 없음, 고식적 항암 없음 |

## 6. 근거 출처

- ESMO MBC 2026-05, Site-specific management > Bone metastases (p.12)
- 공고책자 2026-10-01, Ⅳ. 기타 약제 2·3 (인쇄 p.218~219), 3. 고식적 내분비요법 가.5 (p.55)
