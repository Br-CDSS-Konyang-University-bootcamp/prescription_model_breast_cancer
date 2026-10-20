# VC-0105 HER2 양성, 선행 후 잔존 병변, 보조 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

49세(진단 시) 여성, 폐경 전. 가짜 진단일 2023-01-09 (= day 0).

| day | 사건 |
|---|---|
| 0 | 좌측 유방 IDC, 중심 생검. **cT2N1M0**. HER2 IHC 3+, ER 0%, PR 0%, Ki-67 50% |
| 14~119 | 선행 TCHP(docetaxel + carboplatin + trastuzumab + pertuzumab) 3주 간격 6회 |
| 150 | 유방 부분절제 + 감시림프절. **ypT1c ypN1a**, 잔존 침윤암 있음, **RCB-II** |
| 180 | **오늘 외래 (보조 결정)** = `index_day` |

## 2. 시험 목적

- 선행요법 반응 (`pcr: no`, `rcb: RCB-II`), 임상 병기(`ctnm`)와 선행 후 병리 병기(`ptnm`, ypT)를 모두 추출
- trastuzumab 주기 수 (선행 + 보조 합산 18주기 조건)
- 급여·지침 모두 보조 T-DM1

## 3. 차트 문서 구성

1. `[병리결과보고서]` 중심 생검 (영문 위주)
2. `[수술 병리 보고서]` ypTNM, RCB 표
3. `<외래 경과기록>` 보조요법 결정
4. `[투약 기록]` 약어(TCHP, T-DM1)와 상품명(허셉틴, 퍼제타) 섞음

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `stage.ctnm` | T2 N1 M0 |
| `stage.ptnm` | T1c N1a M0 (선행 후, 원문 `ypT1c ypN1a`) |
| `neoadjuvant_response` | `pcr: no`, `rcb: RCB-II` |
| `treatment_history` | 선행 docetaxel·carboplatin·trastuzumab·pertuzumab, `setting: neoadjuvant`, `cycles` 6 (21일) |
| `recurrence` | `status: none`. `recurrence_day`·`metastasis_day` 없음 |
| `deemed_lines` | 모두 `not_applicable` |
| `index_day` | 180 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: 아형 HR-/HER2+, HER2 `positive`, `setting.line` adjuvant
- **C (지침)**: ESMO EBC "Patients with residual invasive disease … should receive adjuvant treatment with T-DM1 for up to 14 cycles" [I, A]
- **D (급여)**: trastuzumab emtansine → 2. 수술후보조요법 25 → `covered` (taxane·trastuzumab 포함 선행 후 침습적 잔존 병변, HER2 양성, 14주기). 선행 TCHP 1.가.5 확인용 → `covered`
- **안전 검사**: ER·PR 음성에 내분비요법 단독 금지

## 6. 근거 출처

- ESMO EBC 2024-02, Recommendations > HER2-positive EBC (p.14)
- 공고책자 2026-10-01, 1. 선행화학요법 가.5, 2. 수술후보조요법 25 (인쇄 p.49·54)
