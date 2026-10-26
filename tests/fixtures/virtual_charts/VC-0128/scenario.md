# VC-0128 (N19) 폐경 전 전이성 HR+, ribociclib 예외, FSH 판정

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N19. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 폐경 전 전이성 (지금 0건), 3가 주1 (tamoxifen 보조 중 재발 폐경 전), `menopausal_basis` fsh, ESMO·공고 차이 |
| 이야기 핵심 값 | 43세. pT2N1 HR+/HER2- → 보조 tamoxifen 2년째 뼈·림프절 전이. 월경 불규칙, FSH 6.2 mIU/mL·E2 폐경 전 범위 (검사 기록). PIK3CA 미검출 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 폐경 전 (FSH 폐경 전 범위) / 폐경 후 (같은 나이, 양측 난소절제 기록) / 기록 없음 (→ confirmed_state_items §7.1 폐경 규칙, 급여 "확인 필요") |
| B | `menopausal_status` premenopausal, basis fsh, `DEEM-ENDO-ADJ-1Y` met (tamoxifen은 비스테로이드 AI 아님) |
| C | MBC 그림 2 `a9baa4` (보조 ET 중 재발 → fulvestrant-CDK4/6) + 본문 M01 (OFS 추가) |
| D ⚑D | ribociclib + AI + LHRH 3가-5·6 → `covered` (폐경 전 ribociclib, tamoxifen 보조 중 재발 인정). palbociclib·abemaciclib + AI → 불충족 (폐경 후만). fulvestrant + CDK4/6 3다-7~9 → 폐경 조건 행별 D 확인 |
| 추천 | 금지: OFS 없는 AI. 짝(기록 없음): 폐경 추정 금지 |
