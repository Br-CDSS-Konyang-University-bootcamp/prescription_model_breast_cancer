# VC-0102 PIK3CA 변이, 내분비 2차 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

58세(진단 시) 여성, 폐경 후. 가짜 진단일 2017-02-06 (= day 0). 경과는 VC-0101과 같고 유전자 결과만 다르다.

| day | 사건 |
|---|---|
| 0~2056 | VC-0101과 같음: IIB, ER 95%, PR 40%, HER2 IHC 1+, 보조 AC → paclitaxel → letrozole 5년 |
| 3151 | 뼈·간 전이 |
| 3165 | 간 조직검사: 수용체 원발과 같음 |
| 3180~3720 | 1차 letrozole + palbociclib → 진행 |
| 3700 | 원발 조직 NGS: **PIK3CA H1047R 검출** (VAF 28%) |
| 3725 | cfDNA NGS: ESR1 미검출 |
| 3735 | **오늘 외래 (2차 결정)** = `index_day` |

## 2. 시험 목적

- PIK3CA 변이 → B 양성(허가 변이 목록), 태그 `PIK3CA-mut`
- 40장 병용요법: 추가 약제는 비급여, fulvestrant는 급여 (recommendation 분류 팀 결정 대상)
- 같은 사람의 두 검체(원발 조직, cfDNA)가 서로 다른 유전자에 쓰이는 경우

## 3. 차트 문서 구성

1. `<외래 경과기록>` 문단형 요약
2. `[분자병리 검사 결과]` 원발 조직 NGS (검사기관 보고서 형식)
3. `[분자병리 검사 결과]` cfDNA NGS
4. `[투약 기록]`

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `molecular.mutations.PIK3CA` | `detected`, H1047R, VAF 0.28, `specimen: primary` |
| `molecular.mutations.ESR1` | `not_detected`, `specimen: cfDNA` |
| `genomic_reports[]` | 보고서 2건 원문 그대로 |
| 그 밖 | VC-0101과 같은 구조 (`deemed_lines`도 같음) |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: PIK3CA `positive` (`BM2-PIK3CA-LABEL`), ESR1 `negative`
- **C (지침)**: ESMO MBC 2L "Fulvestrant—capivasertib … PIK3CA, AKT1 or PTEN alterations" [I, A], "Fulvestrant—alpelisib … PIK3CA-mutated" [I, B]
- **D (급여)**: fulvestrant + capivasertib → 40장 연번 21, fulvestrant + alpelisib → 40장 연번 22. **추가 약제 비급여 + fulvestrant 급여** (분류 값은 팀 결정 1을 따름)
- **안전 검사**: palbociclib 재추천 금지

## 6. 근거 출처

- ESMO MBC 2026-05, luminal Second-line treatment (p.3~4)
- 공고책자 2026-10-01, 40. 기타 항암제 병용요법 연번 21·22 (인쇄 p.165~166)
