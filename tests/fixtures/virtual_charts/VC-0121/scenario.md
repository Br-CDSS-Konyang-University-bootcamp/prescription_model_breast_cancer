# VC-0121 (N12) HR+/HER2- 선행화학요법 결정

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N12. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 공고 1. 선행 HER2 음성 (지금 0건), EBC 그림 2 HR+/HER2- 선행 |
| 이야기 핵심 값 | 47세 폐경 전. cT3N1M0 IIIA, ER 90%, PR 5%, HER2 1+, 등급 3, Ki-67 45% (중심부 생검). 다학제 회의에서 선행 항암 결정 |
| 결정 시점 | 선행 (치료 전, `treatment_history` 비어 있음) |
| 짝 사례 | cT3N1 (stage Ⅲ) / cT1cN0 (IA, 선행 급여 stage Ⅱ~Ⅲ 밖) |
| B | 아형 HR+/HER2- (HER2-low), `setting` neoadjuvant, `ctnm`만 있고 `ptnm` 없음 |
| C | EBC 그림 2 `5abbd1` |
| D ⚑D | AC → paclitaxel 9장 1나 → `covered` (stage Ⅱ~Ⅲ). carboplatin 추가 → 행 없음. 짝 IA: 선행 행 조건 불충족 |
| 추천 | 금지: pembrolizumab 선행 (TNBC 아님) |
