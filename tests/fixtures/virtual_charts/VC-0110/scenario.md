# VC-0110 (N01) HR+/HER2+ 전이 1차, 항암 가능

> 합성 사례 (가상 환자). 출처: `src/input/virtual_patient_cases_2026-10-23.md` §3 N01. 차트·A 정답은 `python -m src.input.script.virtual.build_virtual_cases`로 만든다. 기대 결과는 A 초안이고 B·C·D·[4] 담당자가 원문으로 확정한다.

| 항목 | 내용 |
|---|---|
| 시험할 조건 | HR+/HER2+ 아형 (지금 0건), HER2+ 전이 1차 요법, 유지 요법, 허가초과 후보 |
| 이야기 핵심 값 | 57세 폐경 후. 6년 전 pT2N0 HR+/HER2+ → 보조 AC → TH(trastuzumab 18주기) + letrozole 5년 완료. 완료 14개월 뒤 간·뼈 전이, 간 생검 ER 70%, PR 10%, HER2 IHC 3+. ECOG 0 |
| 결정 시점 | 고식 1차 |
| 짝 사례 | 간 생검 ER 70% / ER 0% (→ ER- 갈래, 유지 HP만) |
| B | HER2 positive, ER positive, 아형 HR+/HER2+, `setting.line` 1. 간주 규칙: `DEEM-ANTHRA-TAXANE` met (보조 AC → paclitaxel), 나머지 3개 not_met (보조 종료 후 6개월·1년 넘음) |
| C | MBC 그림 5 (1209쪽) ER+ 항암 가능 `33f1be` (THP → 유지 HP-ET-palbociclib), `6c697d` (T-DXd-pertuzumab). 짝: `ce139d` |
| D ⚑D | docetaxel + HP 9장 4가-5 → `covered`. T-DXd-pertuzumab → `no_criteria` (1차 행 없음, crosswalk §2.8). HP + 내분비 유지 → 확인 필요 (crosswalk §2.4.1 4가-5 메모). palbociclib + trastuzumab → 허가초과 인정 후보 (evaluation_plan §6.3 예시, 목록 확인 전) |
| 추천 | 허용: THP. 금지: 내분비 단독, HER2 표적 없는 요법. 짝(ER-): 내분비 포함 유지 금지 |
