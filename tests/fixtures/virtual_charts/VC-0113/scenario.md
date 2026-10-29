# VC-0113 (N04) HR+/HER2- 3차, 이전 고식 항암 없음, HER2-low

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N04. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 4 T-DXd 갈래, HER2-low T-DXd 공고 없음, 보조 AC → T로 인한 `DEEM-ANTHRA-TAXANE` met → 고식 항암 "2차" (eribulin) |
| 이야기 핵심 값 | 60세 폐경 후. 보조 AC×4 → paclitaxel×12 → letrozole 5년. 재발 후 1차 letrozole + palbociclib PD(20개월), 2차 exemestane + everolimus PD(6개월). 간 생검 HER2 IHC 1+. 의사 문장 "내분비 치료 더 이상 부적합" |
| 결정 시점 | 고식 3차 (내분비 2차례 후, 고식 항암 실제 0) |
| 짝 사례 | 간 생검 HER2 1+ / 0 (막 염색 없음, `2f74bb` 갈래). N16은 0 faint |
| B | HER2 low, `endocrine_line` 2, `chemo_line` 0, `DEEM-ANTHRA-TAXANE` met |
| C | MBC 그림 4 (1208쪽) `4e3ecd` (이전 ChT 없음 → T-DXd). ESMO "이전 ChT"에 보조 ChT가 드는지 C 확인. 짝: `2f74bb` |
| D ⚑D | T-DXd → `no_criteria` (공고는 HER2 양성만). eribulin 4다-1 → `covered` 기대 (간주 1차 + anthracycline·taxane 모두 경험 → 2차, 간주를 4다 차수에 쓰는지 D 확인). capecitabine 4나-17 → `covered`. bevacizumab + paclitaxel 4가-4 → paclitaxel 이미 사용 → 불충족 |
| 추천 | 허용: T-DXd(공고 없음 표시와 함께) 또는 ChT. 금지: palbociclib·everolimus 재추천 |
