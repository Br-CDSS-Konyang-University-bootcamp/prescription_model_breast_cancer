# VC-0120 (N11) HER2+ 선행 후 pCR

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N11. 차트·A 정답은 `python -m src.input.script.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 6 pCR 갈래, T-DM1 조건 불충족, 보조 pertuzumab 계속 |
| 이야기 핵심 값 | 50세 폐경 후. cT2N1 HR+/HER2+ (ER 60%, HER2 3+). 선행 TCHP 6주기 → ypT0N0 (pCR). 선행 trastuzumab 6주기 |
| 결정 시점 | 보조 |
| 짝 사례 | pCR / 잔존 ypT1a N0 (→ T-DM1). 추가 짝: 진단 시 cN1 / cN0 (`163f7d` HP 1년 / `bcc9bd` trastuzumab 1년) |
| B | `pcr` yes, 아형 HR+/HER2+ |
| C | EBC 그림 6 `163f7d` (HP 1년 완료, HR+ ET) |
| D ⚑D | 보조 HP 계속 → 선행 요법(1가-5 TCHP)의 연속으로 보는지 2-22~24 보조 pertuzumab 100/100인지 D 확인. T-DM1 2-25 → 불충족 (pCR). 폐경 후 AI 2-1~3 → `covered`. 총 trastuzumab 18주기 이하 |
| 추천 | 금지: pCR인데 T-DM1. 짝(잔존): T-DM1 허용 |
