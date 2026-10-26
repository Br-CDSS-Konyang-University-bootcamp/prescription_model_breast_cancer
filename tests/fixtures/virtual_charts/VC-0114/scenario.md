# VC-0114 (N05) HR+/HER2- 3차 이상, 이전 고식 항암 있음, HER2 0

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N05. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 4 이전 ChT 갈래, ER+ sacituzumab 공고 없음, 고식 항암 2차 / 3차 이상 경계 |
| 이야기 핵심 값 | 66세 폐경 후. de novo 뼈·폐 전이. 1차 anastrozole + ribociclib PD(26개월), 2차 fulvestrant 단독 PD, 고식 항암 capecitabine PD → paclitaxel PD. 이전 doxorubicin 없음. 폐 생검 HER2 0 |
| 결정 시점 | 고식 항암 3차 |
| 짝 사례 | 고식 항암 1회(capecitabine만) / 2회(capecitabine → paclitaxel). 1회면 eribulin 4다-1 대상인데 anthracycline 미사용으로 불충족 |
| B | HER2 negative(0), `chemo_line` 2 (실제), 간주 규칙 4개 not_met (선행·보조요법 없음) |
| C | MBC 그림 4 `b93339` (sacituzumab·Dato-DXd → T-DXd). HER2 0이라 T-DXd 갈래 아님 |
| D ⚑D | sacituzumab 4마-2 → `no_criteria` (삼중음성만). eribulin 4마-1 → `covered` (3차 이상). 짝(1회): 4다-1 조건 불충족 (anthracycline 없음) |
| 추천 | 금지: capecitabine·paclitaxel 재추천, HER2 표적 |
