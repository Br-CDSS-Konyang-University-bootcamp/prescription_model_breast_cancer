# VC-0127 (N18) anthracycline 누적 미달 + 심장 위험 → liposomal doxorubicin

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases.md` §3 N18. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | 9장 4나-19 조건 (누적 용량 또는 심장 위험), 심장 칸 yes·종격동 방사선 yes (지금 0건) |
| 이야기 핵심 값 | 61세 폐경 후. TNBC. 보조 AC 3주기 후 심부전 의심으로 중단 (doxorubicin 누적 180 mg/m², mg 표기 + 키·몸무게), 좌측 흉벽·내유림프절 방사선. 협심증 병력, LVEF 48%. 무병 3년 뒤 폐 전이, 1차 paclitaxel PD |
| 결정 시점 | 고식 항암 2차 |
| 짝 사례 | 심장 위험 있음 / 없음 (→ 누적 미달이라 불충족) / 기록 없음 (→ `covered_conditions_unverified`) |
| B | 누적 용량 계산 값 180, 심장 병력 yes, 종격동 방사선 yes, LVEF 48 |
| C | 본문 M26 (liposomal anthracycline 재투여, DFI 12개월 이상) |
| D ⚑D | liposomal doxorubicin 4나-19 → `covered` (심장 위험요소), 50/100. 짝: 위 셋. 심장 위험요소의 공고 정의 D 확인 |
| 추천 | 금지: doxorubicin(일반) 재투여 |
