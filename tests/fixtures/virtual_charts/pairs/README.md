# 짝 사례 (최소 대조쌍)

> 담당 A · 2026-10-23 · 만드는 곳 `src/input/chart/cases/pairs.py` · 계획 `notes/evaluation_plan_2026-10-23.md` §2.1

기본 사례에서 판정을 가르는 값 하나만 경계 양쪽으로 바꾼 사례다. **같은 묶음의 기본 사례와 짝 사례를 모두 맞혀야 통과**로 센다. 폴더마다 `chart.txt`와 A 정답 `expected/patient_state.json`이 있고, B·C·D 기대 판정 초안은 `pairs.json`의 `expect`에 있다 (각 담당자가 원문으로 확정). 손으로 고치지 말고 `python -m src.input.chart.virtual_chart`로 다시 만든다.

## G1 보조 내분비 종료 후 재발 기간 (기본 VC-0103)

기본: 보조 anastrozole 복용 중 전이 (gap -5)

| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |
|---|---|---|
| `VC-0103-g365` | anastrozole을 전이 365일 전에 부작용으로 중단 | C: ESMO MBC 그림 2 '보조 ET 중 또는 종료 12개월 이내 재발', PIK3CA wt (fig2-a9baa4) → fulvestrant–CDK4/6<br>D: 3.다 fulvestrant + CDK4/6 (2차 이상, 간주 규칙 met) 급여 / 3.가 AI + CDK4/6 (1차)은 '보조 AI 종료 1년 이후 재발' 불충족 |
| `VC-0103-g366` | anastrozole을 전이 366일 전에 부작용으로 중단 | C: ESMO MBC 그림 2 '종료 12개월 넘어 재발' (fig2-1ae139) → AI–CDK4/6<br>D: 3.가 AI + CDK4/6 (1차) 급여 (종료 1년 이후 재발. '이후'에 365일이 드는지는 D가 원문 확인) / 3.다 fulvestrant + CDK4/6 (2차 이상)은 간주 규칙 not_met이라 불충족 |

## G2 보조요법 종료 후 무병 기간 (DFI) (기본 VC-0104)

기본: paclitaxel 종료 240일 뒤 전이. 종료일 2023-01-07 + 6개월 = 181일

| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |
|---|---|---|
| `VC-0104-dfi180` | paclitaxel 종료 180일 뒤 간 전이 (6개월 하루 전) | C: ESMO MBC TNBC 1차 PD-L1+: pembrolizumab–ChT은 무병 기간 6개월 이상일 때 (본문 M44·M45). 6개월 안 재발 갈래 확인<br>D: 4.가.6 pembrolizumab + 항암 '보조요법 종료 6개월 이후 재발' 불충족 → 급여 아님 |
| `VC-0104-dfi182` | paclitaxel 종료 182일 뒤 간 전이 (6개월 하루 뒤) | D: 4.가.6 pembrolizumab '6개월 이후 재발' 충족 → 기본 사례와 같음 (covered_conditions_unverified, 급여인정기관 요건) |

## G3 PD-L1 점수·검사법 (기본 VC-0104)

기본: 22C3 CPS 12

| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |
|---|---|---|
| `VC-0104-cps9` | PD-L1 22C3 CPS 9 | B: PD-L1 negative (pembrolizumab 기준 22C3 CPS ≥ 10 미달)<br>C: ESMO MBC 그림 8 PD-L1- (fig8-b39e9e). 생식세포 BRCA 미시행 → 검사 권고<br>D: 4.가.6 pembrolizumab CPS 조건 불충족 |
| `VC-0104-cps10` | PD-L1 22C3 CPS 10 (경계) | B: PD-L1 positive (CPS ≥ 10, 경계 포함)<br>D: 4.가.6 CPS 조건 충족 (기본 사례와 같음) |
| `VC-0104-sp142` | PD-L1 검사법 SP142, IC 1% (22C3 결과 없음) | B: pembrolizumab 판정에는 쓰지 않음 (검사법이 기준과 다름). atezolizumab 기준 SP142 IC ≥ 1% positive<br>C: ESMO MBC 그림 8 PD-L1+ 중 atezolizumab–nab-paclitaxel<br>D: pembrolizumab: 22C3 결과 없음 → 조건 확인 불가. atezolizumab 급여 기준은 D가 원문 확인 |

## G4 ER Allred 총점 (기본 VC-0107)

기본: Allred 8 (5+3). 0~2 음성, 3~4 저발현, 5는 비율 점수로 가름, 6~8 양성

| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |
|---|---|---|
| `VC-0107-er2` | ER Allred 2 (1+1) | B: ER negative. PR 양성(Allred 8)이라 아형은 HR+/HER2- (ER 음성·PR 양성도 HR+, 2026-10-15) |
| `VC-0107-er3` | ER Allred 3 (2+1) | B: ER low (저발현, ER-low 태그). 아형 HR+/HER2-<br>C: ESMO의 ER-low 언급 (TNBC에 가깝게 다룸) 검색 확인 |
| `VC-0107-er5ps2` | ER Allred 5 (PS 2 + IS 3) | B: ER low (5점은 비율 점수로 가름: PS 2 = 1~10%) |
| `VC-0107-er5ps3` | ER Allred 5 (PS 3 + IS 2) | B: ER positive (5점, PS 3 = 11~33%) |
| `VC-0107-er6` | ER Allred 6 (3+3) | B: ER positive |

## G5 PR Allred 총점 (기본 VC-0109)

기본: Allred 5 (3+2). 0~2 음성, 3 이상 양성

| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |
|---|---|---|
| `VC-0109-pr2` | PR Allred 2 (1+1) | B: PR negative. ER 양성이라 아형은 HR+/HER2- 그대로 |
| `VC-0109-pr3` | PR Allred 3 (2+1) | B: PR positive (3점 이상) |

## G6 HER2 IHC·ISH (기본 VC-0101)

기본: 간 재생검 HER2 1+ (저발현)

| 짝 사례 | 바꾼 값 | 기대 판정 (초안) |
|---|---|---|
| `VC-0101-her2-0` | 간 재생검 HER2 IHC 0, 막 염색 없음 | B: HER2 negative (0). 원발 1+와 다름 → reason에 변화 기록, 전이성 HER2 재판정 확인 |
| `VC-0101-her2-0f` | 간 재생검 HER2 IHC 0 + 희미한 불완전 막 염색 (<10%) | B: HER2 ultralow (심평원 기준 최종 음성, 아형 HER2-)<br>C: 이후 차수에서 T-DXd 갈래 (ESMO MBC 그림 4 HER2 low or ultralow) |
| `VC-0101-her2-2n` | 간 재생검 HER2 IHC 2+, SISH 비증폭 | B: HER2 low (2+ / ISH 비증폭) |
| `VC-0101-her2-2a` | 간 재생검 HER2 IHC 2+, SISH 증폭 | B: HER2 positive → 아형 HR+/HER2+ (재생검 기준)<br>C: ESMO MBC HER2+ 1차 (그림 5, ER+) — 전이 후 HER2 표적 치료 없음<br>D: HER2 표적 요법 행이 후보가 됨 (고식적 항암) |
| `VC-0101-her2-3p` | 간 재생검 HER2 IHC 3+ | B: HER2 positive → 아형 HR+/HER2+<br>C: VC-0101-her2-2a와 같음<br>D: VC-0101-her2-2a와 같음 |
