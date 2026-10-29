# VC-0143 (N34) 단일 골전이, 소수 전이

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 N34. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 10 소수 전이 (지금 0건), 1차 CDK4/6 + AI (보조 letrozole 종료 1년 넘어 재발), zoledronic acid 골전이 조건 (최근 4주 투여) |
| 이야기 핵심 값 | 62세 폐경 후. 수술 pT2N1a (1/14), IIB, HR+/HER2-. 보조 letrozole 5년 (day 1856 완료). day 2430 PET-CT T8 단일 섭취, day 2445 T8 생검 전이성 유방암 (ER·PR 양성, HER2 1+). 다학제 "소수 전이, T8 SBRT 가능" |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 골전이 3곳 + 간 (소수 전이 아님). 아직 만들지 않음 |
| B | HR+/HER2-, metastatic, 1차. `DEEM-ENDO-ADJ-1Y` not_met (종료 19개월 뒤). 최근 4주 투여 no |
| C | MBC 그림 10 `44ccc9` (다학제, 국소 치료 고려), 그림 2 `1ae139` (AI + CDK4/6) |
| D ⚑D | CDK4/6 + AI 3가 → `covered` (비스테로이드 AI 보조 종료 1년 뒤). zoledronic acid → 조건 확인 필요 (영상·생검 입증, 최근 4주 이내 항암·호르몬제 투여 없음) |
| 추천 | 허용: AI + CDK4/6 + 국소 치료 고려 |
| 차트에 없는 칸 | 소수 전이 판단은 칸이 없다 (전이 부위 수와 다학제 문장만). §4 |
