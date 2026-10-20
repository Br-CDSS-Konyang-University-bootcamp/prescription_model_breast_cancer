# VC-0106 HR+ 고위험 조기, 크기 조건, 시점이 다른 Ki-67

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

55세(진단 시) 여성, 폐경 후. 가짜 진단일 2022-09-14 (= day 0).

| day | 사건 |
|---|---|
| 0 | 외부 병원(가상의원) 중심 생검: IDC, ER 양성, **Ki-67 15%** |
| 25 | 본원 유방 전절제 + 액와 림프절 절제. **pT3 (5.5cm) N1a (2/15) M0**, IIIA. ER 90%, PR 70%, HER2 IHC 0, 등급 2, **Ki-67 25%** (수술 조직) |
| 45 | **다학제 회의 (보조 결정)** = `index_day`. 보조 항암 후 내분비요법 + CDK4/6 억제제 추가를 논의 |

## 2. 시험 목적

- 시점이 다른 두 Ki-67 값 → 최신 값(수술 조직)이 `value`, 외부 생검 값이 `history[]` (`superseded_reason: newer_result`)
- 종양 크기 5.5cm → T3로 abemaciclib 고위험 조건 판정 (`tumor_size_mm` 칸은 없음, A-3 보류)
- 병기 IIIA → `disease_extent: locally_advanced`
- 보조 CDK4/6: 기존 내분비요법 급여 + 추가 약제 비급여

## 3. 차트 문서 구성

1. `[외부 병원 병리 보고서]` 생검 (가상의원)
2. `[병리결과보고서]` 전절제 (표 형식)
3. `<다학제 진료 회의록>`

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `stage.ptnm` | T3 N1a M0, `group` IIIA, `disease_extent` locally_advanced |
| `stage.positive_ln_count` | `{positive: 2, examined: 15}` |
| `diagnosis.grade` | 2 |
| `proliferation.ki67_percent` | `value` 25% (수술 조직), `history[]` 15% (외부 생검, `newer_result`) |
| `treatment_history` | 비어 있음 (아직 치료 전) |
| `deemed_lines` | 모두 `not_applicable` |
| `index_day` | 45 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: 아형 HR+/HER2-, Ki-67 `positive` (25% ≥ 20%), `setting.line` adjuvant
- **C (지침)**: ESMO EBC "Abemaciclib for 2 years in addition to ET … stage III or high-risk stage II EBC" [I, A]. 항암 후 ET
- **D (급여)**: 보조요법 주2 abemaciclib 병용 → 림프절 1~3개 + 종양 ≥ 5cm(T3) 충족 → **AI 5/100, abemaciclib 100/100(전액본인)**. ribociclib + AI → 40장 연번 25·26 (ribociclib 비급여). 둘 다 "기존 요법 급여 + 추가 약제 비급여"
- **안전 검사**: HER2 표적치료 금지

## 6. 근거 출처

- ESMO EBC 2024-02, Recommendations > HR-positive, HER2-negative EBC (p.14)
- 공고책자 2026-10-01, 2. 수술후보조요법 주2 (인쇄 p.54), 40. 병용요법 연번 25~28 (인쇄 p.167~168)
