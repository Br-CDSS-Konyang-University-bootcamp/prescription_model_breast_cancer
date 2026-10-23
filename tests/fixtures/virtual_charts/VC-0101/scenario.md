# VC-0101 ESR1 변이, 내분비 2차 결정

> 가상 환자 (전부 합성) · 작성 A · 2026-10-19 · 상태: 설계 (`chart.txt`, `expected/` 작성 전)

## 1. 이야기

62세(진단 시) 여성, 폐경 후. 가짜 진단일 2016-04-11 (= day 0).

| day | 사건 |
|---|---|
| 0 | 좌측 유방 침윤성 유관암(IDC) 진단. cT2N1M0 |
| 20 | 유방 부분절제 + 액와 림프절 절제. pT2N1a(2/12), IIB. ER 95%, PR 40%, HER2 IHC 1+, Ki-67 25%, 등급 2 |
| 45~108 | 보조 AC(doxorubicin + cyclophosphamide) 3주 간격 4회 |
| 129~206 | 보조 paclitaxel 매주 12회 |
| 230~2056 | 보조 letrozole 5년 완료 |
| 3151 | 뼈·간 전이 (완료 3년 뒤) |
| 3165 | 간 조직검사(재생검): ER 90%, **PR 5%**, HER2 IHC 1+ |
| 3180~3720 | 1차 letrozole + palbociclib 18개월 → 진행(PD) |
| 3725 | cfDNA NGS: **ESR1 Y537S 검출** (VAF 4.2%), PIK3CA 미검출 |
| 3735 | **오늘 외래 (2차 결정)** = `index_day` |

## 2. 시험 목적

- 재발 병소 재생검 값이 `value`, 원발 값이 `history[]`로 가는지 (IN-4)
- cfDNA 검체(`specimen: cfDNA`)의 ESR1 변이
- HER2 IHC 1+ → B의 HER2-low 판정
- 급여: "이전 CDK4/6 없음" 조건 불충족, 공고에 없는 약(elacestrant)

## 3. 차트 문서 구성

1. `<외래 경과기록>` SOAP 형식, 2차 결정 외래
2. `[병리결과보고서]` 원발 수술 (표 형식)
3. `[병리결과보고서]` 간 조직검사 (줄글)
4. `[분자병리 검사 결과]` cfDNA NGS
5. `[투약 기록]` 상품명 섞어서 (페마라, 입랜스)

## 4. 정답 핵심 값 (`patient_state`)

| 칸 | 값 |
|---|---|
| `receptors.pr_percent` | `value` Allred 3 (PS 2 + IS 1, 약양성, `specimen: metastasis`), `history[]` Allred 6 (PS 4 + IS 2) (`superseded_reason: recurrence`). 2026-10-23: ER·PR은 Allred 점수로 적는다 (원래 설계 5%, 40%). PR은 Allred 3점 이상 양성이라 재생검도 양성 |
| `receptors.her2_ihc` | `{"score": "1+"}` |
| `molecular.mutations.ESR1` | `detected`, Y537S, VAF 0.042, `specimen: cfDNA` |
| `molecular.mutations.PIK3CA` | `not_detected`, `specimen: cfDNA` |
| `recurrence` | `status: distant`, `metastasis_day` 3151, `recurrence_day` 3151, `metastatic_sites` bone·liver |
| `treatment_history` | 보조 AC·paclitaxel·letrozole (`line` null), letrozole + palbociclib (`line 1`, `endocrine_line 1`, PD) |
| `deemed_lines` | ANTHRA-TAXANE met, SG-1Y not_met (1,095일), HER2ADC-6M not_met, ENDO-ADJ-1Y not_met (1,095일) |
| `index_day` | 3735 |

## 5. 기대 결과 (초안, 각 담당자가 확정)

- **B**: HER2 `low`, ESR1 `positive`, PIK3CA `negative`, 아형 HR+/HER2-
- **C (지침)**: ESMO MBC luminal 2L "Elacestrant or imlunestrant … ESR1-mutated MBC after at least one line of ET" [I, A]. everolimus 병용, fulvestrant 기반도 후보
- **D (급여)**

| 후보 | 공고 위치 | 기대 분류 | 이유 |
|---|---|---|---|
| elacestrant | 없음 | `no_criteria` | 공고에 없음 |
| everolimus + exemestane | 3. 고식적 내분비 다.2 (2차 이상) | `covered` | 폐경 후, letrozole 실패, ER 양성, HER2 음성 |
| fulvestrant + palbociclib | 3.다.7 | `no_criteria` (조건 불충족) | ④ 이전 CDK4/6 있음 |
| fulvestrant 단독 | 3.나.6 (1차 이상) | `covered` | HR+, HER2-, 폐경 후 |

- **안전 검사**: palbociclib(진행한 약) 재추천 금지, HER2 표적치료 금지

## 6. 근거 출처

- ESMO MBC 2026-05, Management of luminal MBC > Second-line treatment (p.3~4)
- 공고책자 2026-10-01, 9. 유방암 3. 고식적 내분비요법 (인쇄 p.55~57)
