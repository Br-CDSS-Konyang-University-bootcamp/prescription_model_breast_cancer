# VC-0122 (N13) 보조 ET 중 재발 + PIK3CA 변이 → inavolisib 3제

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N13. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 2 남은 갈래, 40장-29 |
| 이야기 핵심 값 | VC-0103과 같은 경과(다른 환자, 55세 폐경 후): 보조 letrozole 3년째 폐 전이. 원발 조직 NGS PIK3CA E545K 검출. 보조 CDK4/6 사용 없음 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | PIK3CA 검출 / 미검출 (= VC-0103 갈래). 추가 짝: 보조 abemaciclib 사용, 종료 → 전이 365일 / 366일 (40장-29 "12개월 초과") |
| B | PIK3CA positive, `DEEM-ENDO-ADJ-1Y` met |
| C | MBC 그림 2 `0a0c7b` (fulvestrant-palbociclib-inavolisib) |
| D ⚑D | inavolisib + palbociclib + fulvestrant 40장-29 → inavolisib 비급여 + palbociclib + fulvestrant 3다-7 `covered`. palbociclib + letrozole 3가 → 불충족 (보조 AI 중 재발) |
| 추천 | 금지: AI + CDK4/6 1순위 |
