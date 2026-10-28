# VC-0135 (N26) TNBC cT1c N0 선행 후 잔존, gBRCA1

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases_2026-10-27.md` §3 N26. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | EBC 그림 7 `<cT2 N0` 갈래 (지금 0건), 잔존 + gBRCA 병원성 → olaparib, 40장-30은 HR+ 백본만 (TNBC 보조 olaparib 행 없음), 임상 병기 Ⅰ기 |
| 이야기 핵심 값 | 38세 폐경 전. 초음파 좌측 유방 1.8 cm 종괴, 액와 이상 없음 → cT1c cN0, IA, G3, ER 0 / PR 0 / HER2 1+, Ki-67 70%. 생식세포 BRCA1 c.68_69delAG 병원성. 선행 weekly paclitaxel + carboplatin #12 → AC #4. 수술 ypT1b (6 mm) ypN0 (0/2), RCB-I |
| 결정 시점 | 보조 |
| 짝 사례 | gBRCA 야생형 (`a20657` capecitabine, 2-18 `covered`) / cT2 (2.1 cm) cN0 (≥cT2 갈래, 선행 pembrolizumab). 아직 만들지 않음 |
| B | TNBC (HER2-low), gBRCA1 양성, early, 보조. pCR no |
| C | EBC 그림 7 `474a0a` (잔존 + gBRCAm → olaparib 1년), 그림 2 `ed4466` |
| D ⚑D | olaparib → `no_criteria` (40장-30은 HR+ 백본만). capecitabine 2-18 → `covered`. 이미 받은 선행 AC→P의 1나 "stage Ⅱ~Ⅲ" 문제는 판정 대상 아님 (참고) |
| 추천 | 허용: olaparib (ESMO, 급여 아님 표시), capecitabine. 금지: 내분비요법 |
