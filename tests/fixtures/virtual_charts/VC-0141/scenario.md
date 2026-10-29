# VC-0141 (N32) HR+/HER2- 뼈 전이만, 내분비 적합

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N32. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 4 내분비 적합 갈래 (지금 0건), 3차 이상에서 항암으로 넘어가지 않기 |
| 이야기 핵심 값 | 70세 폐경 후. de novo cT2N0M1 (뼈만). 1차 anastrozole + palbociclib 30개월 (PD), 2차 exemestane + everolimus 10개월 (PD, 뼈만). CT 내장 전이 없음. cfDNA PIK3CA·ESR1·AKT1·PTEN 미검출. 경과기록 "내분비 치료 지속 가능하다고 판단" |
| 결정 시점 | 고식 내분비 3차 |
| 짝 사례 | 간 전이 빠른 진행 → 내분비 부적합 (N04·N16 갈래). 아직 만들지 않음 |
| B | HR+/HER2- (HER2-low), 고식 내분비 3차, 고식 항암 0 |
| C | MBC 그림 4 `535699` (안 쓴 2차 선택지: fulvestrant 등) |
| D ⚑D | fulvestrant 3나-6 → `covered`. fulvestrant + CDK4/6 → `no_criteria` (이전 CDK4/6) |
| 추천 | 허용: fulvestrant. 금지: 항암 1순위, 진행한 요법 재추천 |
| 차트에 없는 칸 | "내분비 치료 지속 가능" 판단은 칸이 없다 (경과기록 문장만). §4 |
