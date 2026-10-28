# VC-0117 (N08) 조기 TNBC 선행 pembrolizumab 후 잔존 → capecitabine

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N08. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 7, 허가초과 인정 (pCR 미달성 pembrolizumab + capecitabine), 40장 pembrolizumab, 보조 capecitabine |
| 이야기 핵심 값 | 44세 폐경 전. cT2N1M0 TNBC, 등급 3, Ki-67 70%. 선행 paclitaxel + carboplatin → AC + pembrolizumab (KEYNOTE-522 요법) → 수술 ypT1bN1a (RCB-II). 생식세포 BRCA 음성 |
| 결정 시점 | 수술 후 보조 |
| 짝 사례 | 잔존 / pCR (ypT0N0 → `dbe131`, capecitabine 대상 아님) |
| B | `neoadjuvant_response.pcr` no, `rcb` RCB-II, gBRCA negative, `setting` adjuvant |
| C | EBC 그림 7 (170쪽) 잔존 갈래 `796507`·`9ac5a5` (보조 pembrolizumab 9주기, gBRCA wt → capecitabine). 짝: `dbe131` |
| D ⚑D | 보조 pembrolizumab 40장-20 → 추가 약제 비급여. capecitabine 9장 2-18 → `covered` (pCR 미도달 HER2-). pembrolizumab + capecitabine 병용 → 허가초과 인정 후보 (목록 확인 전). 짝(pCR): capecitabine 2-18 불충족 |
| 추천 | 금지: 짝(pCR)에서 capecitabine 추천, olaparib (gBRCA 음성) |
