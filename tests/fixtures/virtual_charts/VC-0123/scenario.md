# VC-0123 (N14) HR+/HER2- 2차, AKT1 변이

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N14. 차트·A 정답은 `python -m src.input.script.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 3 AKT1·PTEN, 40장-21의 폐경 후 백본 |
| 이야기 핵심 값 | 64세 폐경 후. de novo 뼈 전이. 1차 letrozole + abemaciclib PD(22개월). 뼈 생검 실패 → 원발 조직 NGS AKT1 E17K 검출, PIK3CA·ESR1 미검출 |
| 결정 시점 | 고식 내분비 2차 |
| 짝 사례 | 폐경 후 / 폐경 전 (같은 이야기, 46세 월경 있음 → fulvestrant 백본도 급여 아님) |
| B | AKT1 positive, PIK3CA·ESR1 negative, `endocrine_line` 1 |
| C | MBC 그림 3 `416e66` (fulvestrant-capivasertib) |
| D ⚑D | capivasertib + fulvestrant 40장-21 → capivasertib 비급여 + fulvestrant 급여. fulvestrant + CDK4/6 3다-7~9 → 불충족 (이전 CDK4/6). everolimus + exemestane 3다-2 → `covered`. 짝(폐경 전): fulvestrant 3나-6·40장-21 백본 불충족, everolimus 폐경 후 조건 불충족 |
| 추천 | 금지: abemaciclib 재추천 |
