# VC-0138 (N29) HER2+ 전이 3차, T-DXd 후

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N29. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 7 (지금 0건), 9장 4라-21 T-DM1, 4라-20 lapatinib + capecitabine (anthracycline·taxane·trastuzumab 모두 사용), tucatinib 행 없음, T-DXd 재추천 금지 |
| 이야기 핵심 값 | 55세 폐경 후. 수술 pT2N1a (1/12), IIB, HR-/HER2+. 보조 AC #4 → paclitaxel + trastuzumab → trastuzumab (총 18회, day 485 완료). day 1400 간·폐 전이. 1차 DPH #6 → HP 유지 (PD, day 1895 CT). 2차 T-DXd #23 (PD, day 2398 CT). Brain MRI 전이 없음 |
| 결정 시점 | 고식 3차 |
| 짝 사례 | 활동성 뇌 전이 + 국소 치료 적응 (`4d7ea5`) / 보조 anthracycline 없음 (4라-20 불충족). 아직 만들지 않음 |
| B | HR-/HER2+, metastatic, 고식 항암 3차. `DEEM-ANTHRA-TAXANE` met, `DEEM-HER2ADC-6M` not_met (종료 뒤 2년) |
| C | MBC 그림 7 `c5908c` (T-DXd 후 → T-DM1, tucatinib-trastuzumab-capecitabine, lapatinib 병용) |
| D ⚑D | T-DM1 4라-21 → `covered`. lapatinib + capecitabine 4라-20 → `covered`. tucatinib → `no_criteria` |
| 추천 | 허용: T-DM1, lapatinib + capecitabine. 금지: T-DXd·HP 재추천 (진행) |
