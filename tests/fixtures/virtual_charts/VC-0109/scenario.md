# VC-0109 국소 재발 후 완치 목적 절제, 재발 후 보조요법 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

58세(진단 시) 여성, 폐경 후. 가짜 진단일 2019-07-22 (= day 0).

| day | 사건 |
|---|---|
| 0 | 좌측 유방 IDC 진단 |
| 14 | 유방 부분절제 + 감시림프절. pT2N0(0/3), IIA. ER 70%, PR 20%, HER2 IHC 0, 등급 2 |
| 45~1150 | 보조 tamoxifen |
| 1140 | **흉벽 국소 재발** (조직검사, 수용체 같음) |
| 1150 | tamoxifen 중단 |
| 1160 | PET-CT: 원격 전이 없음 |
| 1165 | 흉벽 광범위 절제 (완치 목적, 절제연 음성) |
| 1190 | **오늘 외래 (재발 후 보조요법 결정)** = `index_day` |

## 2. 시험 목적

- 국소 재발: `recurrence_day` 있음, `metastasis_day` 없음 → 차수 칸 모두 null, 간주 규칙 `not_applicable`
- 재발 후 수술 정보 (`surgery: yes`, `surgery_intent: curative`, `later_distant: no`)
- B의 `SET-LOCAL-ADJ` (국소 재발 후 완치 목적 수술 → 이후 요법은 수술후보조요법) → `setting.line` adjuvant
- 급여: 투여 원칙의 국소 재발 조항으로 "2. 수술후보조요법" 단계를 고르는지

## 3. 차트 문서 구성

1. `<외래 경과기록>` 문단형, 재발 경과 요약
2. `[수술 기록 요약]` 흉벽 광범위 절제, 수술 목적
3. `[병리결과보고서]` 흉벽 재발 병소
4. `[투약 기록]` (놀바덱스 표기)

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `recurrence` | `status: locoregional`, `recurrence_day` 1140, `metastasis_day` 없음, `surgery: yes`, `surgery_intent: curative`, `later_distant: no` |
| `treatment_history` | 보조 tamoxifen `start_day` 45, `end_day` 1150, `best_response` 또는 `stop_reason: progression` (차수 칸 null) |
| `deemed_lines` | 모두 `not_applicable` |
| `index_day` | 1190 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: `SET-LOCAL-ADJ` 적용 → `setting.line` adjuvant, `setting.disease` early
- **C (지침)**: 국소 재발 절제 후 내분비요법 전환 (± 항암, 방사선). C가 ESMO EBC·MBC에서 해당 권고를 찾음
- **D (급여)**: 투여 원칙 "국소재발의 경우 완치 목적의 수술을 시행 후 재발 방지를 위해 투여한 항암요법은 수술후보조요법" → 2. 수술후보조요법. anastrozole 2.1 나 (tamoxifen 2~3년 후 전환, 총 5년), exemestane 2.3 → `covered` (폐경은 전환 시점에 확인)
- **안전 검사**: tamoxifen(진행 중 재발한 약) 재추천 금지, HER2 표적치료 금지

## 6. 근거 출처

- 공고책자 2026-10-01, 9. 유방암 [투여 원칙] (인쇄 p.48), 2. 수술후보조요법 1·3 (p.51)
- `src/input/handoff_to_B.md` §6.4 (`SET-LOCAL-ADJ`)
