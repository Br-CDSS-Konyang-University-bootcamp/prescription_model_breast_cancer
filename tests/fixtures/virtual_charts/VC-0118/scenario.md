# VC-0118 (N09) 조기 TNBC cT1b N0 수술 먼저

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N09. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 7 작은 종양 갈래, TC 급여 "1cm 이상 또는 N+" |
| 이야기 핵심 값 | 63세 폐경 후. 검진 발견 8mm TNBC → 부분절제 + 감시림프절 → pT1b(8mm) N0(0/2), 등급 2 |
| 결정 시점 | 보조 |
| 짝 사례 | ESMO 경계 pT1a 5mm / pT1b 6mm (`5ab655` 보조 없음 고려 / `8ccb0b` ChT). 공고 경계 9mm / 10mm (TC "1cm 이상") |
| B | 아형 TNBC, `ptnm` T1b N0, `disease_extent` early |
| C | EBC 그림 7 `8ccb0b`. 짝 5mm: `5ab655` |
| D ⚑D | TC 9장 2-16 계열 → 조건 불충족 (1cm 미만, N0). AC 계열 행의 크기 조건 D 확인. 짝 10mm: TC `covered` |
| 추천 | 짝 5mm: 전신 요법 필수 표현 금지 (ESMO "고려") |
