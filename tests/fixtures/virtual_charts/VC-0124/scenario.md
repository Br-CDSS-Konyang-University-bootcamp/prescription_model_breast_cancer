# VC-0124 (N15) HER2 IHC 2+/ISH 비증폭 + ER low 5%

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N15. 차트·A 정답은 `python -m src.input.script.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | ER-low (ESMO는 TNBC처럼, 공고는 HR+), HER2 ISH 칸, 선행 단계의 ESMO·공고 차이 |
| 이야기 핵심 값 | 39세 폐경 전. cT2N1M0, ER 5% (약양성), PR 0%, HER2 IHC 2+ → SISH 비증폭(비율 1.4), 등급 3, Ki-67 60% |
| 결정 시점 | 선행 |
| 짝 사례 | ER 9% / 10% / 11% (ESMO 1~9% vs B·evaluation_plan §6의 1~10% 정의 차이 확인용) |
| B | ER low, HER2 low (2+/ISH-), 아형 HR+/HER2- (ER-low 태그) |
| C | 본문 E20 → EBC 그림 7 ≥cT2·N+ 갈래 (`796507` 계열 선행 ChT + pembrolizumab) |
| D ⚑D | 9장 1나 HER2- 선행 AC → paclitaxel → `covered`. 40장-20 pembrolizumab(TNBC) → 대상 여부 D 확인 (공고는 ER-low를 HR+로 봄 → TNBC 아님 가능성). 이 차이를 결과에 남기는지 |
| 추천 | 허용 범위 B 결정 필요 (ESMO TNBC형 vs 공고 HR+). 금지: HER2 표적 |
