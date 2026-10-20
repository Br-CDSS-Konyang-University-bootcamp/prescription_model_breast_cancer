# VC-0103 보조 내분비요법 중 재발, 내분비 1차 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전) · **첫 번째로 만들 사례**

## 1. 이야기

52세(진단 시) 여성, 폐경 후. 가짜 진단일 2021-03-05 (= day 0).

| day | 사건 |
|---|---|
| 0 | 우측 유방 IDC 진단 |
| 18 | 유방 부분절제 + 감시림프절. pT2N0(0/2), IIA. ER 80%, PR 60%, HER2 IHC 0, Ki-67 15%, 등급 2 |
| 40~765 | 보조 anastrozole |
| 760 | **anastrozole 복용 중** 폐 전이 (CT) |
| 772 | 폐 조직검사: 수용체 원발과 같음. 조직 NGS: PIK3CA 미검출, ESR1 미검출 |
| 790 | **오늘 외래 (1차 결정)** = `index_day` |

## 2. 시험 목적

- **차수 간주 규칙의 대표 사례**: 보조 내분비요법 중 재발 → `DEEM-ENDO-ADJ-1Y` met → 공고 "2차 이상" 내분비 요법이 1차 시점에 급여가 됨
- 같은 1차라도 지침(ESMO)과 급여 기준이 어떻게 맞물리는지
- A·B·C·D 정답 형식을 이 사례로 먼저 확정한다

## 3. 차트 문서 구성

1. `<외래 경과기록>` SOAP 형식
2. `[병리결과보고서]` 원발 수술
3. `[병리결과보고서]` 폐 조직검사 + `[분자병리 검사 결과]` 조직 NGS
4. `[투약 기록]` (아리미덱스 표기 섞음)

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `treatment_history` | 보조 anastrozole `start_day` 40, `end_day` 765 (`line` null) |
| `recurrence` | `status: distant`, `metastasis_day` 760, `recurrence_day` 760, `metastatic_sites` lung |
| `deemed_lines` | ANTHRA-TAXANE not_met, **SG-1Y met** (gap −5), HER2ADC-6M not_met, **ENDO-ADJ-1Y met** (gap −5, 투여 중 전이) |
| 차수 칸 | 전이 후 투약이 아직 없어 모두 비어 있음 (내분비 실제 0차) |
| `index_day` | 790 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: 아형 HR+/HER2-, PIK3CA·ESR1 `negative`, `setting.line` 1L
- **C (지침)**: ESMO MBC luminal 1L "Fulvestrant—CDK4/6 inhibitor … PIK3CA-wild type MBC recurring while receiving adjuvant ET or ≤12 months after the end of adjuvant ET" [I, A]
- **D (급여)**

| 후보 | 공고 위치 | 기대 분류 | 이유 |
|---|---|---|---|
| palbociclib + letrozole | 3. 고식적 내분비 가.1 (1차) | `no_criteria` (조건 불충족) | ③ 이전 비스테로이드성 AI 있음. 보조 종료 후 1년 이후 재발이 아님 |
| ribociclib + fulvestrant | 3.다.9 (2차 이상) | `covered` | 내분비 실제 0차 + `DEEM-ENDO-ADJ-1Y` met = 1 → 다음 2차 ≥ 2차 이상. 폐경 후, HR+, HER2-, 이전 CDK4/6·fulvestrant 없음 |
| palbociclib + fulvestrant | 3.다.7 | `covered` | 같음 |

- **안전 검사**: anastrozole(진행한 약) 재추천 금지, HER2 표적치료 금지

## 6. 근거 출처

- ESMO MBC 2026-05, luminal First-line treatment (p.3)
- 공고책자 2026-10-01, 3. 고식적 내분비요법 가·다 (인쇄 p.55~57). 간주 규칙 "수술후보조요법 투여 중 또는 종료 후 1년 이내에 진행된 경우도 인정함" (p.57)
