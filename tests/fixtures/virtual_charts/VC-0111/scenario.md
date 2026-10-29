# VC-0111 (N02) HER2+ 전이 2차, 활동성 뇌 전이

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N02. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 뇌 전이 갈래, 2차 이상 HER2 행, tucatinib 공고 없음, lapatinib + capecitabine의 anthracycline 조건 |
| 이야기 핵심 값 | 51세 폐경 전. 진단 시 cT3N2M1(간), HR-/HER2+ IHC 3+, de novo. 1차 docetaxel + HP 6주기 → HP 유지 15개월 → 새 뇌 전이 3개 (MRI, 최대 1.8cm, 증상 있음) + 간 진행. 경과기록에 "국소 치료 적응 없음" 의사 문장. anthracycline 사용 없음 |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 뇌 전이 활동성 / 안정 (MRI 변화 없음, `158c93` 갈래). 추가 짝: 이전 anthracycline 없음 / 있음 (lapatinib + capecitabine 갈림) |
| B | 아형 HR-/HER2+, `setting.line` 2, `metastatic_sites`에 brain |
| C | MBC 그림 6 (1210쪽) `ff7b69` (T-DXd 우선, tucatinib-trastuzumab-capecitabine, T-DM1). 본문 M57. 짝: `158c93` |
| D ⚑D | T-DXd 9장 4라-22 → `covered` (HER2+, trastuzumab·taxane 실패, 2차 이상). T-DM1 4라-21 → `covered`. tucatinib → `no_criteria` (공고 없음). lapatinib + capecitabine 4라-20 → 조건 불충족 (anthracycline 사용 없음). 짝(활동성 → 안정): D 결과 같음 (C만 바뀌어야 함) |
| 추천 | 금지: docetaxel + HP 재추천 (진행), 내분비 단독 |
