# VC-0131 (N22) 폐경 전 Luminal A 1기

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N22. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 4 폐경 전 Luminal A 1기 → tamoxifen (지금 0건), 9장 2-4~6 AI + LHRH 조건 (40세 미만·림프절 양성·분화도 2~3) 불충족 |
| 이야기 핵심 값 | 45세 폐경 전 (LMP 3주 전). 수술 pT1c (1.4 cm) pN0 (0/3), IA, G1, ER Allred 8 / PR Allred 7 / HER2 1+, Ki-67 8% |
| 결정 시점 | 보조 |
| 짝 사례 | 39세 G2 (AI + LHRH 급여 조건 충족인데 ESMO 1순위는 tamoxifen → "급여되지만 지침 1순위 아님"). 아직 만들지 않음 |
| B | HR+/HER2-, 폐경 전, Ki-67 negative (20% 미만) |
| C | EBC 그림 4 `08ac92` tamoxifen |
| D ⚑D | tamoxifen 2-7 → `covered`. AI + LHRH 2-4~6 → `no_criteria` (조건 불충족) |
| 추천 | 허용: tamoxifen. 금지: 항암 (저위험) |
