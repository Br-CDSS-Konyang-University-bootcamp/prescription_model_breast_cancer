# VC-0130 (N21) HER2+ cT1 cN0 수술 먼저, pT1a N0

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N21. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 조기 HER2+ cT1 cN0 수술 먼저 갈래 (지금 0건), 9장 2-20 trastuzumab "림프절 양성 또는 종양 1cm 초과" 불충족, weekly paclitaxel + trastuzumab 보조 행 없음 |
| 이야기 핵심 값 | 52세 폐경 후. 초음파 우측 유방 0.9 cm 종괴, 액와 이상 없음. 수술 pT1a (8 mm) pN0 (0/2), IA, G2, ER 0 / PR 0 / HER2 3+, Ki-67 30% |
| 결정 시점 | 보조 |
| 짝 사례 | pT1c 11 mm N0 (2-20 충족, ESMO 같은 갈래) / pT2 N0 (`f25e5f` ChT-trastuzumab 1년) / pN1 (`549ca3` ChT-HP, 2-22 pertuzumab). 아직 만들지 않음 |
| B | HR-/HER2+, early, 보조 |
| C | EBC 그림 6 `207157` (pT1 pN0 → paclitaxel 12주 + trastuzumab 18주기), 그림 2 `c9e462` |
| D ⚑D | trastuzumab 2-20 → `no_criteria` (1cm 이하, N0). paclitaxel + trastuzumab 보조 행 없음. 짝 11 mm: trastuzumab `covered`, 요법 행은 D 확인 |
| 추천 | 허용: paclitaxel + trastuzumab (ESMO), 급여 아님 표시. 금지: 내분비요법 (HR-) |
