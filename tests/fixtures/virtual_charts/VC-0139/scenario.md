# VC-0139 (N30) HR+/HER2- 2차, 1차 CDK4/6 후 표적 변이 없음

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N30. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 3 표적 변이 없음 갈래 (지금 0건), 9장 3다 이전 CDK4/6 사용 시 제외 (바꿔 쓰기 불가), 3다-2 exemestane + everolimus (anastrozole·letrozole 실패), 3나-6 fulvestrant |
| 이야기 핵심 값 | 63세 폐경 후. 수술 pT2N0, IIA, HR+/HER2-. 보조 anastrozole 5년 (day 1860 완료). day 2600 뼈·간 전이 (종료 2년 뒤). 1차 letrozole + palbociclib 18개월 (PD, day 3160 CT). 간 재생검 ER·PR 양성, HER2 1+, NGS PIK3CA·ESR1·AKT1·PTEN 미검출 |
| 결정 시점 | 고식 내분비 2차 |
| 짝 사례 | 폐경 전 (fulvestrant 기반 백본 급여 아님). 아직 만들지 않음 |
| B | HR+/HER2- (HER2-low), 고식 내분비 2차, 표적 변이 음성 |
| C | MBC 그림 3 `0f09b4` (exemestane-everolimus, fulvestrant-everolimus, fulvestrant-CDK4/6 바꿔 쓰기, fulvestrant) |
| D ⚑D | exemestane + everolimus 3다-2 → `covered`. fulvestrant 3나-6 → `covered`. fulvestrant + CDK4/6 3다-7~9 → `no_criteria` (이전 CDK4/6) |
| 추천 | 허용: exemestane + everolimus, fulvestrant. 금지: letrozole + palbociclib 재추천 |
