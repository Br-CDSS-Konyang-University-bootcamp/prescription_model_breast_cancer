# VC-0136 (N27) 조기 pembrolizumab 후 간 전이 TNBC

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases_2026-10-27.md` §3 N27. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 9장 4가-6 "이전 면역관문억제제 사용 시 제외" (KEYNOTE-522 환자), ESMO M45는 금지하지 않음, DFI 6개월 이상 |
| 이야기 핵심 값 | 49세 폐경 전. cT2 cN1, IIB, TNBC. 선행 pembrolizumab + paclitaxel + carboplatin → pembrolizumab + AC, 수술 ypT0 ypN0 (pCR). 보조 pembrolizumab 9회 (day 383 완료). day 931 간 다발성 전이 (종료 18개월 뒤). 간 생검 ER 0 / PR 0 / HER2 0, PD-L1 22C3 CPS 15. 생식세포 BRCA1/2 음성 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 조기 pembrolizumab 없음 (같은 경과, 4가-6 충족). 아직 만들지 않음 |
| B | TNBC, PD-L1 positive (CPS 15), metastatic, 1차. 간주 규칙 `DEEM-ANTHRA-TAXANE` met (선행 AC + paclitaxel) |
| C | MBC 그림 8 `e2f44c` (pembrolizumab-ChT, 이전 ICI 자료 적음 메모) |
| D ⚑D | pembrolizumab + ChT 4가-6 → `no_criteria` (이전 ICI). ChT 단독 4나 → `covered`. `DEEM-ANTHRA-TAXANE` met이 4가 "1차" 판정에 쓰이는지 D 확인 |
| 추천 | 허용: ChT (taxane 등), pembrolizumab-ChT (ESMO, 급여 아님 표시). 금지: 내분비요법 |
