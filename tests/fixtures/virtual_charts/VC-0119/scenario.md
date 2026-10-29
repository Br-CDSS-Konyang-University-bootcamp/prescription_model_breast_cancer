# VC-0119 (N10) HR+/HER2- 고위험 조기, gBRCA 양성 → 보조 olaparib

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N10. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 5 olaparib, 40장-30, olaparib과 abemaciclib 동시 금지 (본문 E11) |
| 이야기 핵심 값 | 41세 폐경 전. cT3N1 HR+/HER2- (ER 80%, PR 30%, HER2 0), 등급 3. 선행 AC → paclitaxel → ypT2N1a(2개) 잔존. 생식세포 BRCA2 병원성 변이. CPS+EG 점수 계산 재료(cT·ypN·ER·등급) 모두 있음 |
| 결정 시점 | 보조 |
| 짝 사례 | gBRCA 병원성 / 미시행 (→ olaparib 대신 검사 권고, evaluation_plan §2.2) |
| B | gBRCA positive, `pcr` no, 아형 HR+/HER2-, Ki-67 기록 |
| C | EBC 그림 5 `6ffe04` (Luminal B, gBRCA 변이 → olaparib + ET). 본문 E10·E11 |
| D ⚑D | olaparib + 내분비 40장-30 → olaparib 비급여 + 내분비 급여. abemaciclib 주2 → 고위험 충족(림프절 1~3 + 등급 3) → 100/100. AI + LHRH 2-4~6 → `covered` (림프절 양성·분화도 3) |
| 추천 | 금지: olaparib + abemaciclib 동시. 짝(미시행): olaparib 추천 금지, gBRCA 검사 권고 필수 |
