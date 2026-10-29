# VC-0142 (N33) 전이성 ER-low, PD-L1 CPS 20

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N33. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | ER-low (5%)를 HR+로 보는 규칙 (B `ER_LOW_IS_HR_POSITIVE`, 9장 0. 공통)이 B 아형, C 검색 갈래, D 급여 판정에서 같게 쓰이는지. 4가-6 (TNBC) 불충족 |
| 이야기 핵심 값 | 60세 폐경 후. de novo cT2N1M1 (간). 원발·간 생검 ER 5% (약양성) / PR 0% / HER2 0. 간 생검 PD-L1 22C3 CPS 20. 생식세포 BRCA1/2 음성. 경과기록 "ER 저발현, HR+로 볼지 삼중음성에 준할지 논의" |
| 결정 시점 | 고식 1차 |
| 짝 사례 | ER 0% (진짜 TNBC, `e2f44c`, 4가-6 충족) / ER 12% (분명한 HR+). 아직 만들지 않음 |
| B | ER low → 아형 HR+/HER2-, 태그 `ER-low`, PD-L1 positive |
| C | MBC 그림 2 `1ae139` (de novo, AI + CDK4/6). ESMO MBC가 ER-low를 따로 다루는지는 C 확인 (조기는 본문 E20) |
| D ⚑D | CDK4/6 + AI 3가 → `covered`. pembrolizumab + ChT 4가-6 → `no_criteria` (TNBC 아님) |
| 추천 | 허용: AI + CDK4/6. 금지: pembrolizumab을 급여 요법으로 표시 |
