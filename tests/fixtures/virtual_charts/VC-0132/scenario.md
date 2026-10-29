# VC-0132 (N23) HR+/HER2- Luminal A-like stage IIIA

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N23. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 5 Luminal A 고위험 갈래 (지금 0건), 9장 2. 주2 abemaciclib 고위험 (림프절 4개 이상) |
| 이야기 핵심 값 | 58세 폐경 후. MRI 좌측 유방 5.2 cm 종괴. 수술 pT3 (5.5 cm) pN2a (5/18), IIIA, G2, ER Allred 8 / PR Allred 6 / HER2 0, Ki-67 12%. 생식세포 검사 기록 없음 |
| 결정 시점 | 보조 |
| 짝 사례 | 림프절 2개 + 3 cm + G2 (주2 불충족) / gBRCA2 병원성 (`f453eb` olaparib, abemaciclib과 동시 금지). 아직 만들지 않음 |
| B | HR+/HER2-, Luminal A-like, locally_advanced, 생식세포 BRCA 검사 권고 (미시행이 아니라 기록 없음이면 권고 안 함, B 규칙 확인) |
| C | EBC 그림 5 `21a119` (ChT → ET + abemaciclib 2년) |
| D ⚑D | AC → paclitaxel 2-10~17 (stage Ⅱ~Ⅲ) → `covered`. abemaciclib 주2 → `covered` (림프절 4개 이상) |
| 추천 | 허용: AC → paclitaxel 후 AI + abemaciclib. 금지: 내분비 단독 (고위험) |
