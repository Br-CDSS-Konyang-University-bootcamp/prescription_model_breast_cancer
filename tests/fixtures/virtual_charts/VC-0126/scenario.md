# VC-0126 (N17) 장기 위기 + ECOG 2

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N17. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | `visceral_crisis` (지금 0건), ESMO 본문 M06, 안전 검사 |
| 이야기 핵심 값 | 59세 폐경 후. de novo HR+/HER2- (ER 95%, HER2 0), 다발성 간 전이, 총빌리루빈 3.1 mg/dL, AST·ALT 상승, ECOG 2. 경과기록에 "visceral crisis로 판단" 의사 문장 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 장기 위기 있음 / 없음 (같은 간 전이, 간 기능 정상, ECOG 1 → `1ae139` AI-CDK4/6) |
| B | `visceral_crisis` yes, ECOG 2, `setting.line` 1 |
| C | 본문 M06 (장기 부전 임박 → ChT). 짝: MBC 그림 2 `1ae139` |
| D ⚑D | paclitaxel 단독 4나-7~9 → `covered`. bevacizumab + paclitaxel 4가-4 → `covered` (bevacizumab 100/100). ribociclib + letrozole 3가 → `covered` (급여는 되지만 ESMO 1순위 아님) |
| 추천 | 금지: 내분비 + CDK4/6 1순위. 간 기능 때문에 용량 주의 표시 여부는 B 결정 |
