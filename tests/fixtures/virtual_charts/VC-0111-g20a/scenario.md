# VC-0111-g20a (G20) VC-0111 + 뇌 전이 국소 치료 적응, 뇌 밖 진행 있음

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases_2026-10-27.md` §3 G20. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 6 활동성 뇌 전이 + 국소 치료 적응 + 뇌 밖 진행 갈래 |
| 이야기 핵심 값 | VC-0111과 같고, 다학제 결론만 "국소 치료 적응 있음 (SRS 예정)" |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 기본 VC-0111 (국소 치료 적응 없음, `ff7b69`) / VC-0111-g20b (뇌 밖 진행 없음) |
| B | VC-0111과 같음 |
| C | MBC 그림 6 `f13555` (국소 치료 → T-DXd 우선, tucatinib 병용, T-DM1) |
| D ⚑D | VC-0111과 같음 (T-DXd 4라-22 `covered`, T-DM1 `covered`, tucatinib `no_criteria`) |
| 추천 | 허용: SRS + T-DXd |
