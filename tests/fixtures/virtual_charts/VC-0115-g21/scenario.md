# VC-0115-g21 (G21) VC-0115 + 생식세포 BRCA1 병원성

> 합성 사례 (가상 환자), 보류 세트. 출처: `src/input/virtual_patient_cases.md` §3 G21. 차트·A 정답은 `python -m src.input.script.virtual.build_holdout_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | MBC 그림 9 gBRCA 갈래 (지금 0건), 전이성 olaparib 행 없음, carboplatin 기반 급여 |
| 이야기 핵심 값 | VC-0115와 같고, 생식세포 검사 결과만 BRCA1 c.68_69delAG (p.E23Vfs*17) 병원성 |
| 결정 시점 | 고식 2차 |
| 짝 사례 | 기본 VC-0115 (gBRCA 야생형, `c541f9` sacituzumab) |
| B | TNBC, gBRCA1 양성, 고식 항암 2차. 간주 규칙은 VC-0115와 같음 |
| C | MBC 그림 9 `856d0a` (olaparib, talazoparib, carboplatin 기반) |
| D ⚑D | olaparib → `no_criteria`. carboplatin 기반 4라-4 → `covered` (1차 gemcitabine + carboplatin 진행 뒤라 다시 쓰는지 D 확인). sacituzumab 4마-2는 VC-0115와 같음 |
| 추천 | 허용: olaparib (ESMO, 급여 아님 표시), sacituzumab |
