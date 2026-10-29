# VC-0140 (N31) HR+/HER2- 2차, 생식세포 BRCA2 병원성

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N31. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 3 gBRCA 갈래 (지금 0건), 전이성 olaparib 행 없음, talazoparib 유방암 행 없음, 생식세포 칸 → gBRCA (B) |
| 이야기 핵심 값 | 52세 폐경 후. de novo cT2N1M1 (뼈만). 1차 letrozole + ribociclib 19개월 (PD, day 588 골스캔). 원발 NGS PIK3CA·ESR1·AKT1·PTEN 미검출. 가족력으로 생식세포 검사: BRCA2 c.9097dupA (p.T3033Nfs*11) 병원성 |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 생식세포 PALB2 병원성 (`d5aff4`, [II, B]) / 체세포 BRCA2만 검출 (gBRCA 아님). 아직 만들지 않음 |
| B | HR+/HER2-, gBRCA2 양성, 고식 내분비 2차 |
| C | MBC 그림 3 `8bf8f8` (olaparib, talazoparib) |
| D ⚑D | olaparib → `no_criteria`, talazoparib → `no_criteria`. 내분비 대안은 N30과 같음 (fulvestrant + CDK4/6은 이전 CDK4/6으로 불충족) |
| 추천 | 허용: olaparib (ESMO, 급여 아님 표시), exemestane + everolimus |
