# VC-0112 (N03) HER2+ 보조 trastuzumab 종료 6개월 안 재발

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N03. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | `DEEM-HER2ADC-6M` met (지금 0건), ESMO는 6~12개월까지 2차로 보는데 공고는 6개월 → 두 기준 차이 |
| 이야기 핵심 값 | 46세 폐경 전. pT2N1a(2/14) HR-/HER2+ IHC 3+, 등급 3. 수술 먼저 → 보조 AC×4 → TH, trastuzumab 18주기 종료. 종료 4개월(약 120일) 뒤 폐·간 전이, 뇌 MRI 음성 |
| 결정 시점 | 고식 1차 (실제 차수 0) |
| 짝 사례 | trastuzumab 종료 → 전이 183일 / 184일 (6개월 경계, 달력 계산은 G2처럼 확인) / 270일 (ESMO 2차 갈래, 공고 1차) |
| B | `DEEM-HER2ADC-6M` met (gap 약 120), `DEEM-ANTHRA-TAXANE` met. 아형 HR-/HER2+ |
| C | 본문 M37 → 2차 선택지. MBC 그림 6 `158c93`. 짝 270일: C는 그대로 2차, 짝 184일 초과는 6개월 문구 확인 |
| D ⚑D | T-DXd 4라-22 / T-DM1 4라-21 → `covered` (간주 1차 + 2차 이상). 짝 184일: 간주 not_met → 2차 이상 불충족, 1차 docetaxel + HP 4가-5가 후보 |
| 추천 | 금지: trastuzumab 보조 직후 같은 THP를 1순위로 (짝 184·270일에서는 허용 여부 B 확인) |
