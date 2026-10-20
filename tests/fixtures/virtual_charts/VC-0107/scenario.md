# VC-0107 38세 폐경 전, 보조 내분비요법 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

38세(진단 시) 여성, 폐경 전 (월경 규칙적). 가짜 진단일 2023-05-02 (= day 0).

| day | 사건 |
|---|---|
| 0 | 외부 병원(가상의원) 진단 |
| 12 | 외부 병원 유방 부분절제 + 감시림프절. **pT1c (1.8cm) N0 (0/3) M0**, IA. ER 95%, PR 90%, HER2 IHC 1+, **등급 3 (NG3)**, Ki-67 40% |
| 40 | 본원 초진 (외부 병원 회송) = `index_day` |

## 2. 시험 목적

- **외부 병원 회송서**: 영문 약어 위주 요약 (`IDC, NG3`, `ER+ (95%)`, `s/p BCS & SLNB`) → IN-1 문서 분류, IN-2 추출
- 폐경 전 + 40세 미만·분화도 3 → 보조 AI + LHRH 급여 조건
- 폐경 판정 근거 (`menopausal_basis`)

## 3. 차트 문서 구성

1. `[진료의뢰서 / 회송서]` 가상의원 → 가상대학교병원 (영문 요약)
2. `<외래 초진 기록>` 본원 (한글 문단형, 월경력)
3. `[병리결과보고서]` 외부 병원 수술 병리 사본

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `patient` | `age` 38, `menopausal_status: premenopausal`, `menopausal_basis: age_amenorrhea` (규칙적 월경) |
| `diagnosis.grade` | 3 |
| `stage.ptnm` | T1c N0 M0, `group` IA, `disease_extent` early |
| `receptors.her2_ihc` | `{"score": "1+"}` |
| `treatment_history` | 비어 있음 |
| `deemed_lines` | 모두 `not_applicable` |
| `index_day` | 40 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: 아형 HR+/HER2-, HER2 `low`, Ki-67 `positive`, `setting.line` adjuvant
- **C (지침)**: ESMO EBC "Premenopausal patients … in case of a high risk of recurrence, ovarian suppression with either OFS—tamoxifen or OFS—AI" [I, A]. 보조 항암 여부는 C가 판단
- **D (급여)**

| 후보 | 공고 위치 | 기대 분류 | 이유 |
|---|---|---|---|
| anastrozole·letrozole·exemestane + LHRH agonist | 2. 수술후보조요법 4~6 | `covered` | 폐경 전, HR+, ① 40세 미만 ③ 분화도 2~3 |
| tamoxifen | 2.9 | `covered` | HR+ |
| goserelin ± tamoxifen | 2.7 | `covered` | HR+, 폐경 전 |

- **안전 검사**: HER2 표적치료 금지

## 6. 근거 출처

- ESMO EBC 2024-02, Recommendations > HR-positive, HER2-negative EBC (p.14)
- 공고책자 2026-10-01, 2. 수술후보조요법 4~9 (인쇄 p.52)
