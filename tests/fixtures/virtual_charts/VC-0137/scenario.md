# VC-0137 (N28) 78세 HR+/HER2+ de novo, 항암 어려움

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases_2026-10-27.md` §3 N28. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 5 ER+ 항암 불가 갈래 (지금 0건), 9장 4나-18 trastuzumab + anastrozole, 4가-3 lapatinib + letrozole (폐경 후, 이전 trastuzumab·AI 없음) |
| 이야기 핵심 값 | 78세 폐경 후. 만성 신장병 3b (eGFR 38), LVEF 57%. ECOG 3. de novo cT2N1M1 (뼈·폐). 중심 생검 ER 80% / PR 20% / HER2 3+. 경과기록 "고령·수행 상태 저하로 세포독성 항암 치료는 어렵다고 판단". 투약 이력 없음 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 보조 trastuzumab 받은 재발 (두 행 모두 불충족) / ER- 항암 불가 (`a0919f`). 아직 만들지 않음 |
| B | HR+/HER2+, metastatic, 1차 |
| C | MBC 그림 5 `eaa54b` (ET-trastuzumab, ET-HP, ET-lapatinib 등) |
| D ⚑D | trastuzumab + anastrozole 4나-18 → `covered`. lapatinib + letrozole 4가-3 → `covered` |
| 추천 | 허용: 내분비 + 항HER2. 금지: THP 등 세포독성 항암 1순위 (의사가 항암 어렵다고 판단) |
| 차트에 없는 칸 | "항암 어려움" 판단은 `patient_state`에 칸이 없다 (경과기록 문장만). §4 |
