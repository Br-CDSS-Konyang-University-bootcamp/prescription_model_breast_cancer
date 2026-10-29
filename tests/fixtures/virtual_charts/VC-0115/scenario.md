# VC-0115 (N06) TNBC 2차, gBRCA 야생형 → sacituzumab

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N06. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 9, sacituzumab 3차 이상 + `DEEM-SG-1Y` 경계 |
| 이야기 핵심 값 | 42세 폐경 전. pT2N1 TNBC (ER 0%, PR 0%, HER2 0) → 보조 AC → paclitaxel. 보조 종료 300일 뒤 폐 전이. PD-L1 22C3 CPS 2. 생식세포 BRCA1·2 검사 음성(문서 있음). 1차 고식 gemcitabine + carboplatin PD(7개월) |
| 결정 시점 | 고식 2차 (실제 1) |
| 짝 사례 | 보조 종료 → 전이 365일 / 366일 (`DEEM-SG-1Y` met / not_met) |
| B | 아형 TNBC, gBRCA negative (germline), `DEEM-SG-1Y` met, `chemo_line` 1 |
| C | MBC 그림 9 (1214쪽) `dde930` (sacituzumab 우선, ChT). 본문 M51 |
| D ⚑D | sacituzumab 4마-2 → `covered` (간주 1차 + 실제 1 = 3차, 이전 taxane 있음). 짝 366일: 실제 2차 → 3차 이상 불충족. eribulin 4다-1 → `covered` (2차) |
| 추천 | 금지: gemcitabine + carboplatin 재추천, PARP 억제제 (gBRCA 음성) |
