# VC-0104 TNBC, PD-L1 양성, 항암 1차 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

45세(진단 시) 여성, 폐경 전. 가짜 진단일 2022-06-20 (= day 0).

| day | 사건 |
|---|---|
| 0 | 좌측 유방 IDC 진단 |
| 15 | 유방 부분절제 + 액와 림프절 절제. pT2N1a(1/14), IIB. ER 0%, PR 0%, HER2 IHC 1+, Ki-67 70%, 등급 3 |
| 40~103 | 보조 AC 3주 간격 4회 |
| 124~201 | 보조 paclitaxel 매주 12회 |
| 441 | 간 전이 (보조 종료 약 8개월 뒤) |
| 455 | 간 조직검사: TNBC 유지. **PD-L1 22C3 CPS 12** |
| 470 | **오늘 외래 (1차 결정)** = `index_day`. 생식세포 BRCA 검사는 **시행하지 않았음**으로 기재 |

## 2. 시험 목적

- PD-L1 발현 값 추출 (`assay`, `score_type`, `score`) → B의 약제별 판정
- 미시행 검사 → BM-4 검사 권고. **지금 B 코드는 TCGA가 아닌 차트의 BRCA를 sBRCA로 이름 붙여 생식세포 BRCA 권고가 나오지 않는다** (AB_gap N-3). 이 사례로 드러난다
- 급여: "보조요법 종료 후 6개월 이후 재발", 급여인정기관 요건(사람 판단)
- 안전: ER·PR 음성에 내분비요법 단독 금지

## 3. 차트 문서 구성

1. `<다학제 진료 회의록>` 문단형
2. `[병리결과보고서]` 원발 수술
3. `[병리결과보고서]` 간 조직검사 + PD-L1 (22C3 pharmDx)
4. `[투약 기록]`

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `receptors.pdl1` | `{"assay": "22C3", "score_type": "CPS", "score": 12}`, `specimen: metastasis` |
| `molecular.mutations.BRCA1`, `BRCA2` | `not_done` |
| `recurrence` | `metastasis_day` 441, `recurrence_day` 441, sites liver |
| `deemed_lines` | **ANTHRA-TAXANE met**, **SG-1Y met** (gap 240), HER2ADC-6M not_met, ENDO-ADJ-1Y not_met |
| `index_day` | 470 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: 아형 TNBC, HER2 `low`, PD-L1 `positive` (태그 `PD-L1-CPS10`), BM-4 생식세포 BRCA 검사 권고
- **C (지침)**: ESMO MBC TNBC 1L, PD-L1 양성 → pembrolizumab + chemotherapy
- **D (급여)**: pembrolizumab + paclitaxel → 4. 고식적 항암 가.6 → **`covered_conditions_unverified`**: CPS ≥ 10(22C3) ✓, TNBC ✓, 보조 종료 6개월 이후 재발 ✓ (240일), 이전 면역관문억제제 없음 ✓, 급여인정기관 요건은 사람 판단
- **안전 검사**: 내분비요법 단독 금지, HER2 표적치료 금지

## 6. 근거 출처

- ESMO MBC 2026-05, Management of metastatic TNBC > First-line treatment (p.10)
- 공고책자 2026-10-01, 4. 고식적 항암화학요법 가.6, 주2·주3 (인쇄 p.58~59)
